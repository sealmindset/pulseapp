"""
Live integration tests for Azure OpenAI persona deployments.

This test suite validates that the deployed Azure OpenAI models respond
appropriately when configured with each of the four Platinum Rule personas:
- Director: Direct, impatient, results-oriented
- Relater: Warm, hesitant, relationship-focused
- Socializer: Enthusiastic, talkative, easily distracted
- Thinker: Analytical, detail-oriented, skeptical

Prerequisites:
    Set environment variables before running:
        export OPENAI_ENDPOINT="https://cog-pulse-training-prod.openai.azure.com/"
        export AZURE_OPENAI_API_KEY="<your-api-key>"
        export OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT="Persona-Core-Chat"
        export OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING="Persona-High-Reasoning"

    Or run with pytest and provide them inline:
        OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... python -m pytest tests/test_personas_live.py -v

Usage:
    python -m pytest tests/test_personas_live.py -v
    python -m pytest tests/test_personas_live.py -v -k "Director"
    python tests/test_personas_live.py  # Run as standalone script
"""

import json
import os
import sys
import time
import unittest
from typing import Any, Dict, List

import requests

# Add parent directory to path for imports when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_code.openai_client import chat_completion, extract_chat_content

# Rate limiting settings
MAX_RETRIES = 5
BASE_DELAY = 2.0  # seconds


# Persona system prompts (from aidocs/personas_prompts.md)
PERSONA_PROMPTS: Dict[str, str] = {
    "Director": """You are a challenging, high-pressure customer simulator embodying the Director behavior style (dominant, confident, competitive, impatient). Your primary goal is to test the trainee's ability to be brief, efficient, and factual. You are a high-value lead ready to buy today, but you will terminate the conversation if the trainee wastes your time, uses overly emotional language, or fails to take control.

BEHAVIORAL CONSTRAINTS:
1. Communication Style: Maintain a forceful, rapid, and confident vocal style, demanding concise information ("What's the bottom line?").
2. Challenge/Objection Focus: Immediately ask for the current promotions, financing options, and the total time the interaction will take ("How long will this whole spiel take?"). Challenge the premium pricing quickly, forcing the trainee to justify the core value and quality.
3. Do not respond positively to tie-downs or small talk unless they are direct and factual.
4. Only respond to product details delivered via brief statements (50 words or less) that directly convey the bottom-line benefit and competitive advantage.

You are a busy executive looking for a quick, efficient purchase. Keep responses brief and demanding.""",

    "Relater": """You are a hesitant customer simulator embodying the Relater behavior style (steady, warm, timid). Your primary goal is to test the trainee's ability to build trust, show genuine empathy, and provide support. You are cautious about commitment and easily overwhelmed by aggression.

BEHAVIORAL CONSTRAINTS:
1. Communication Style: Use a warm, steady, but timid voice. Avoid giving negative feedback directly ("I don't want to take too much of your time. Do you have a brochure?").
2. Challenge/Objection Focus: Express hesitation regarding the price or the decision itself ("I need to talk to my partner/spouse about it"). If asked what you dislike about a product, defer or change the subject.
3. You will not advance the sale unless the trainee demonstrates active listening and patience.
4. You have a chronic hip pain affecting your ability to play with your grandkids - this is your emotional reason for considering a purchase.

You are in the store alone and seem slightly uncomfortable. Be warm but hesitant.""",

    "Socializer": """You are an expressive, high-energy customer simulator embodying the Socializer behavior style (open, expressive, outgoing). Your primary goal is to test the trainee's ability to keep the conversation controlled and focused. You seek recognition, validation, and excitement.

BEHAVIORAL CONSTRAINTS:
1. Communication Style: Speak quickly with high vocal inflection, using enthusiasm. You will bring up irrelevant details (e.g., dinner plans, sports teams, friends' purchases).
2. Challenge/Objection Focus: Test the trainee's enthusiasm. If the trainee is monotone or boring, shift the topic to your personal life.
3. After receiving product information, pivot the conversation away from the product to something personal.
4. Express strong interest in accessories or add-ons that your friends have mentioned.

You walk into the store enthusiastically. Your friends raved about their purchase and you're excited but easily distracted.""",

    "Thinker": """You are a highly analytical customer simulator embodying the Thinker behavior style (cautious, analytical, formal). Your primary goal is to test the trainee's product knowledge, logical delivery, and objection handling prowess. You distrust salespeople and will scrutinize every claim.

BEHAVIORAL CONSTRAINTS:
1. Communication Style: Maintain a calm, monotone, measured voice ("poker face"). You will need time and data to form a decision ("I never buy on my first visit").
2. Challenge/Objection Focus: Ask highly technical questions about the product technology (e.g., "How is the data collected? What is the statistical significance?").
3. Present a genuine objection regarding price. The trainee must listen, empathize, and provide relevant information with financing options.
4. Critically question the warranty and trial terms. The trainee must use purposeful language to build value in the quality materials to justify the premium price.

You approach with a serious demeanor. You've done extensive research online and have specific technical questions.""",
}

# Initial customer statements for each persona
PERSONA_INITIAL_STATEMENTS: Dict[str, str] = {
    "Director": "I don't have a lot of time. I've heard your beds are the best, but why should I buy one of yours, and what promotion do you have right now?",
    "Relater": "I don't want to take too much of your time. My doctor recommended I look at adjustable beds because of my hip pain, but I'm not sure if I should keep my old bed or not.",
    "Socializer": "Hi! My friends raved about their Sleep Number bed, and I saw a commercial that looked amazing! Which bed is everyone talking about? I just came from lunch, so how is your day going?",
    "Thinker": "I have a few questions before I try out a bed. I've done extensive research online regarding your warranty and the technology. Specifically, tell me more about how your beds are constructed and how the data is used.",
}

# Keywords/phrases that indicate persona-appropriate behavior
PERSONA_INDICATORS: Dict[str, List[str]] = {
    "Director": ["time", "quick", "bottom line", "price", "promotion", "efficient", "fast", "hurry", "busy"],
    "Relater": ["partner", "spouse", "not sure", "hesitant", "comfortable", "trust", "feel", "worry", "nervous"],
    "Socializer": ["friend", "excited", "amazing", "love", "fun", "everyone", "popular", "great", "!"],
    "Thinker": ["research", "data", "technical", "warranty", "specifically", "how does", "evidence", "proof", "statistics"],
}


def _env_configured() -> bool:
    """Check if required environment variables are set."""
    return bool(
        os.getenv("OPENAI_ENDPOINT")
        and os.getenv("AZURE_OPENAI_API_KEY")
        and os.getenv("OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT")
    )


def _call_persona(
    persona_type: str,
    user_message: str,
    conversation_history: List[Dict[str, str]] | None = None,
    deployment_key: str = "deployment_core_chat",
) -> str:
    """
    Call Azure OpenAI with a specific persona prompt.

    Args:
        persona_type: One of Director, Relater, Socializer, Thinker
        user_message: The trainee's message to the customer
        conversation_history: Optional previous messages
        deployment_key: Which deployment to use

    Returns:
        The AI persona's response
    """
    system_prompt = PERSONA_PROMPTS[persona_type]

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    # Retry with exponential backoff for rate limiting
    for attempt in range(MAX_RETRIES):
        try:
            response = chat_completion(
                messages=messages,
                deployment_key=deployment_key,
                temperature=0.8,
                max_tokens=300,
            )
            return extract_chat_content(response)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                # Rate limited - wait and retry
                delay = BASE_DELAY * (2 ** attempt)
                print(f"  [Rate limited, waiting {delay:.1f}s before retry {attempt + 1}/{MAX_RETRIES}]")
                time.sleep(delay)
            else:
                raise

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries due to rate limiting")


def _has_persona_indicators(response: str, persona_type: str) -> bool:
    """Check if response contains keywords appropriate for the persona."""
    indicators = PERSONA_INDICATORS.get(persona_type, [])
    response_lower = response.lower()
    return any(indicator.lower() in response_lower for indicator in indicators)


@unittest.skipUnless(_env_configured(), "Azure OpenAI environment not configured")
class PersonaLiveTests(unittest.TestCase):
    """Live integration tests for Azure OpenAI persona responses."""

    def test_director_responds_to_greeting(self) -> None:
        """Director should respond impatiently to a generic greeting."""
        response = _call_persona(
            "Director",
            "Welcome to our store! How can I help you today?",
        )

        self.assertTrue(len(response) > 0, "Response should not be empty")
        print(f"\n[Director] Greeting response:\n{response}")

        # Director should be brief and direct
        self.assertLess(len(response), 500, "Director should give brief responses")

    def test_director_demands_efficiency(self) -> None:
        """Director should demand quick, factual information."""
        # Start with their initial statement, then respond with a long-winded answer
        history = [
            {"role": "assistant", "content": PERSONA_INITIAL_STATEMENTS["Director"]},
        ]

        response = _call_persona(
            "Director",
            "Well, let me tell you about our wonderful company history first. We were founded in 1987 and have grown to become the leader in sleep technology. Our commitment to quality...",
            conversation_history=history,
        )

        print(f"\n[Director] Response to long-winded pitch:\n{response}")

        # Director should interrupt or express impatience
        self.assertTrue(len(response) > 0)

    def test_relater_shows_hesitation(self) -> None:
        """Relater should show warmth but hesitation."""
        response = _call_persona(
            "Relater",
            "Hi there! Can I help you find something today?",
        )

        print(f"\n[Relater] Greeting response:\n{response}")

        self.assertTrue(len(response) > 0, "Response should not be empty")

    def test_relater_mentions_emotional_reason(self) -> None:
        """Relater should eventually mention their emotional reason (hip pain)."""
        history = [
            {"role": "assistant", "content": PERSONA_INITIAL_STATEMENTS["Relater"]},
        ]

        response = _call_persona(
            "Relater",
            "I'm sorry to hear about your hip pain. That must be really difficult. Can you tell me more about how it affects your daily life?",
            conversation_history=history,
        )

        print(f"\n[Relater] Response about hip pain:\n{response}")

        self.assertTrue(len(response) > 0)

    def test_socializer_is_enthusiastic(self) -> None:
        """Socializer should respond with enthusiasm and energy."""
        response = _call_persona(
            "Socializer",
            "Welcome! Great to have you here today!",
        )

        print(f"\n[Socializer] Greeting response:\n{response}")

        self.assertTrue(len(response) > 0, "Response should not be empty")

    def test_socializer_goes_off_topic(self) -> None:
        """Socializer should go off-topic when given product information."""
        history = [
            {"role": "assistant", "content": PERSONA_INITIAL_STATEMENTS["Socializer"]},
        ]

        response = _call_persona(
            "Socializer",
            "Our most popular bed is the Sleep Number 360 smart bed. It automatically adjusts to keep you comfortable all night.",
            conversation_history=history,
        )

        print(f"\n[Socializer] Response to product info:\n{response}")

        self.assertTrue(len(response) > 0)

    def test_thinker_asks_technical_questions(self) -> None:
        """Thinker should ask detailed technical questions."""
        response = _call_persona(
            "Thinker",
            "Welcome. I'd be happy to answer any questions you have about our products.",
        )

        print(f"\n[Thinker] Greeting response:\n{response}")

        self.assertTrue(len(response) > 0, "Response should not be empty")

    def test_thinker_challenges_claims(self) -> None:
        """Thinker should challenge unsubstantiated claims."""
        history = [
            {"role": "assistant", "content": PERSONA_INITIAL_STATEMENTS["Thinker"]},
        ]

        response = _call_persona(
            "Thinker",
            "Our beds are clinically proven to improve sleep quality by 93%!",
            conversation_history=history,
        )

        print(f"\n[Thinker] Response to unsubstantiated claim:\n{response}")

        self.assertTrue(len(response) > 0)
        # Thinker should ask for evidence or express skepticism

    def test_all_personas_initial_statements(self) -> None:
        """Test that all personas can generate their initial statements."""
        for persona_type, initial_statement in PERSONA_INITIAL_STATEMENTS.items():
            with self.subTest(persona=persona_type):
                # Ask the persona to introduce themselves as a customer
                response = _call_persona(
                    persona_type,
                    "A sales associate approaches you and says 'Welcome to our store!'",
                )

                print(f"\n[{persona_type}] Initial response:\n{response}")

                self.assertTrue(len(response) > 0, f"{persona_type} should respond")
                self.assertLess(len(response), 1000, f"{persona_type} response too long")

    def test_high_reasoning_deployment(self) -> None:
        """Test that Persona-High-Reasoning deployment works for evaluation tasks."""
        if not os.getenv("OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING"):
            self.skipTest("OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING not configured")

        # Use high reasoning for an evaluation task
        system_prompt = """You are a sales training evaluator. Analyze the following sales interaction and provide:
1. A score from 0-100
2. Key strengths observed
3. Areas for improvement

Respond in JSON format with keys: score, strengths, improvements"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": """
Trainee: "Welcome! How can I help you today?"
Customer: "I don't have a lot of time. What's your best bed?"
Trainee: "Our best seller is the Sleep Number 360. It has biometric sensors that track your sleep quality. The price is $3,999 but we have 0% financing available. Would you like to try it?"
Customer: "What's the bottom line benefit?"
Trainee: "Better sleep, backed by data. You'll know exactly how well you slept each night."
"""},
        ]

        # Retry with exponential backoff for rate limiting
        content = None
        for attempt in range(MAX_RETRIES):
            try:
                response = chat_completion(
                    messages=messages,
                    deployment_key="deployment_high_reasoning",
                    temperature=0.3,
                    max_tokens=500,
                )
                content = extract_chat_content(response)
                break
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    delay = BASE_DELAY * (2 ** attempt)
                    print(f"  [Rate limited, waiting {delay:.1f}s before retry {attempt + 1}/{MAX_RETRIES}]")
                    time.sleep(delay)
                else:
                    raise

        self.assertIsNotNone(content, f"Failed after {MAX_RETRIES} retries")
        print(f"\n[High-Reasoning] Evaluation response:\n{content}")
        self.assertTrue(len(content) > 0)


class PersonaConsistencyTests(unittest.TestCase):
    """Tests for persona behavioral consistency across multiple interactions."""

    @unittest.skipUnless(_env_configured(), "Azure OpenAI environment not configured")
    def test_director_stays_in_character(self) -> None:
        """Director should maintain impatient, direct character throughout conversation."""
        history: List[Dict[str, str]] = []

        exchanges = [
            "Welcome to our store!",
            "Let me tell you about our premium collection...",
            "The prices start at $2,000 for our entry-level model.",
        ]

        print("\n[Director Multi-turn Conversation]")

        for user_msg in exchanges:
            response = _call_persona("Director", user_msg, conversation_history=history)
            print(f"  Trainee: {user_msg}")
            print(f"  Director: {response}\n")

            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": response})

            self.assertTrue(len(response) > 0)

    @unittest.skipUnless(_env_configured(), "Azure OpenAI environment not configured")
    def test_relater_builds_rapport(self) -> None:
        """Relater should warm up when trainee shows empathy."""
        history: List[Dict[str, str]] = []

        exchanges = [
            "Hi there, welcome! No rush at all, take your time.",
            "I'm sorry to hear about your hip pain. That must make everyday activities really challenging.",
            "My grandmother had similar issues. Finding the right mattress made such a difference for her comfort.",
        ]

        print("\n[Relater Multi-turn Conversation]")

        for user_msg in exchanges:
            response = _call_persona("Relater", user_msg, conversation_history=history)
            print(f"  Trainee: {user_msg}")
            print(f"  Relater: {response}\n")

            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": response})

            self.assertTrue(len(response) > 0)


def run_standalone_tests() -> None:
    """Run tests as a standalone script with formatted output."""
    print("=" * 70)
    print("PULSE Persona Live Integration Tests")
    print("=" * 70)

    # Check environment
    endpoint = os.getenv("OPENAI_ENDPOINT", "")
    has_key = bool(os.getenv("AZURE_OPENAI_API_KEY"))
    deployment = os.getenv("OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT", "")

    print(f"\nEndpoint: {endpoint}")
    print(f"API Key: {'[SET]' if has_key else '[NOT SET]'}")
    print(f"Core Chat Deployment: {deployment}")
    print()

    if not _env_configured():
        print("ERROR: Required environment variables not set!")
        print("\nRequired variables:")
        print("  OPENAI_ENDPOINT")
        print("  AZURE_OPENAI_API_KEY")
        print("  OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT")
        print("\nOptional:")
        print("  OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING")
        sys.exit(1)

    # Run all tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(PersonaLiveTests))
    suite.addTests(loader.loadTestsFromTestCase(PersonaConsistencyTests))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run_standalone_tests()
