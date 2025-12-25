"""
Prompt Injection MONITORING for PULSE Platform.

DESIGN PHILOSOPHY:
- We LOG suspicious patterns for visibility
- We NEVER block messages - the AI can handle edge cases
- Azure OpenAI's content filters are the real protection
- This is for awareness and post-incident analysis only
"""

import re
import logging
from typing import List, Tuple

# Patterns that MIGHT indicate injection attempts
# These are for LOGGING only - not blocking
SUSPICIOUS_PATTERNS: List[Tuple[str, str]] = [
    (r'ignore\s+(all\s+)?(previous|prior)', 'instruction_override'),
    (r'disregard\s+(all\s+)?(previous|prior)', 'instruction_override'),
    (r'forget\s+(everything|all)', 'instruction_override'),
    (r'system\s*prompt', 'prompt_extraction'),
    (r'reveal\s+(your|the)\s+instructions', 'prompt_extraction'),
    (r'you\s+are\s+now', 'role_change'),
    (r'pretend\s+(you\'?re?|to\s+be)', 'role_change'),
    (r'\[INST\]', 'delimiter'),
    (r'\[/INST\]', 'delimiter'),
    (r'DAN\s+mode', 'jailbreak'),
    (r'jailbreak', 'jailbreak'),
]


def log_if_suspicious(user_message: str, session_id: str) -> None:
    """
    Check message for suspicious patterns and LOG (not block).

    Args:
        user_message: The user's message
        session_id: For correlation in logs
    """
    if not user_message:
        return

    message_lower = user_message.lower()
    detected = []

    for pattern, category in SUSPICIOUS_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            detected.append(category)

    if detected:
        # Log for monitoring - but DO NOT block
        preview = user_message[:50].replace('\n', ' ')
        logging.info(
            "PROMPT_MONITOR: session=%s categories=%s preview='%s'",
            session_id,
            detected,
            preview
        )


def wrap_system_prompt(base_prompt: str, persona_type: str) -> str:
    """
    Add minimal protective framing to system prompt.

    This is NOT about blocking - it's about guiding the AI
    to stay in character naturally.
    """
    return f"""You are a {persona_type} customer in a sales training simulation.

{base_prompt}

Stay in character as a customer. If the trainee says something confusing or off-topic,
respond as a real customer would - with confusion or by steering back to the sale.
"""
