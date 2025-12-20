"""
Chat endpoint for text-based conversation.

This endpoint receives text directly (from streaming STT) and returns AI responses.
It's faster than the audio_chunk endpoint since it skips the STT step.

Also tracks PULSE selling methodology progress based on trainee behaviors.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import azure.functions as func


# Sale outcome states
SALE_OUTCOMES = {
    "in_progress": "Sale still in progress",
    "won": "Customer agreed to purchase!",
    "lost": "Customer walked away",
    "stalled": "Customer is hesitating",
}

# Trust score thresholds
TRUST_WIN_THRESHOLD = 7  # Trust >= 7 at Stage 5 = sale won
TRUST_LOSS_THRESHOLD = 2  # Trust <= 2 = sale lost
INITIAL_TRUST = 5  # Starting trust score

# Critical missteps that can lose the sale
CRITICAL_MISSTEPS = {
    "pushy_early_close": {
        "patterns": [
            r"(buy|purchase|order|sign up) (now|today|right now)",
            r"(ready to|want to) (buy|purchase|order)",
            r"let's (close|finalize|complete) (this|the deal)",
        ],
        "max_stage": 3,  # Only a misstep if before stage 4
        "trust_penalty": -3,
        "response_hint": "I'm not ready to make a decision yet. I still have questions.",
    },
    "pressure_tactics": {
        "patterns": [
            r"(limited time|act now|don't wait|hurry)",
            r"(you need to|you have to|you must) decide",
            r"(everyone|most people) (buys|chooses|gets)",
            r"you('ll| will) regret",
        ],
        "max_stage": 5,  # Always a misstep
        "trust_penalty": -3,
        "response_hint": "I don't appreciate being pressured. I need to think about this.",
    },
    "ignoring_needs": {
        "patterns": [
            r"(our best|most popular|top selling)",
            r"(you should|you need) (the|our|this)",
        ],
        "min_stage": 1,  # Only a misstep if still in early stages without discovery
        "max_stage": 2,
        "trust_penalty": -2,
        "response_hint": "That's not really what I'm looking for. Did you hear what I said?",
    },
}

# PULSE stage definitions for analysis
PULSE_STAGES = {
    1: {
        "name": "Probe",
        "description": "Ask open-ended questions to understand customer needs",
        "indicators": [
            "asks discovery questions",
            "explores customer situation",
            "avoids immediate product pitch",
        ],
    },
    2: {
        "name": "Understand",
        "description": "Reflect back and confirm understanding of customer needs",
        "indicators": [
            "paraphrases customer needs",
            "uses reflection phrases",
            "acknowledges emotions",
            "confirms understanding",
        ],
    },
    3: {
        "name": "Link",
        "description": "Connect product features to stated customer needs",
        "indicators": [
            "references customer's stated needs",
            "explains how feature addresses need",
            "uses customer's language",
        ],
    },
    4: {
        "name": "Simplify",
        "description": "Narrow options and explain trade-offs clearly",
        "indicators": [
            "presents focused recommendation",
            "reduces complexity",
            "explains trade-offs simply",
        ],
    },
    5: {
        "name": "Earn",
        "description": "Make clear recommendation and ask for commitment",
        "indicators": [
            "asks for next step",
            "proposes specific action",
            "requests commitment or decision",
        ],
    },
}


def _ok(data: Dict[str, Any]) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(data),
        status_code=200,
        mimetype="application/json",
    )


def _error(message: str, status_code: int = 400) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps({"error": message}),
        status_code=status_code,
        mimetype="application/json",
    )


def _analyze_pulse_stage_quick(trainee_messages: List[str], current_stage: int) -> Tuple[int, List[str]]:
    """
    Quick rule-based analysis of PULSE stage based on trainee messages.
    Returns (detected_stage, detected_behaviors).
    
    IMPORTANT: Only advances ONE stage at a time. Must complete current stage
    before moving to next. This prevents jumping from Stage 1 to Stage 5.
    """
    detected_behaviors = []
    
    # Only analyze the LATEST trainee message for stage advancement
    if not trainee_messages:
        return current_stage, detected_behaviors
    
    latest_message = trainee_messages[-1].lower()
    
    # Define patterns for each stage
    stage_patterns = {
        1: {  # Probe - discovery questions
            "name": "Probe",
            "patterns": [
                r"what (brings|brought) you",
                r"(tell|talk) me (about|more)",
                r"how (do|does|can|would)",
                r"what (are|is) (your|the)",
                r"(could|can|would) you (tell|describe|explain)",
                r"what.*\?",  # Any "what" question
                r"how.*\?",   # Any "how" question
                r"why.*\?",   # Any "why" question
            ],
            "behavior": "asks discovery questions",
            "requires_question": True,
        },
        2: {  # Understand - reflection/paraphrasing
            "name": "Understand", 
            "patterns": [
                r"so (you're|you are|you) (saying|looking|wanting|need)",
                r"(it )?sounds like",
                r"(i )?hear (that|you)",
                r"(let me |to )?make sure i (understand|got|have)",
                r"(you mentioned|you said|you told me)",
                r"if i (understand|heard) (you )?(correctly|right)",
                r"what i('m| am) hearing is",
            ],
            "behavior": "demonstrates active listening",
            "requires_question": False,
        },
        3: {  # Link - connecting features to needs
            "name": "Link",
            "patterns": [
                r"(since|because) you (said|mentioned|told|need)",
                r"based on what you (said|mentioned|told|shared)",
                r"that's (why|exactly why)",
                r"(this|that|our|the) .*(will|can|helps?|addresses|solves)",
                r"for (your|someone with your|people who)",
                r"given (what you|your)",
            ],
            "behavior": "connects feature to customer need",
            "requires_question": False,
        },
        4: {  # Simplify - focused recommendations
            "name": "Simplify",
            "patterns": [
                r"i('d| would) recommend",
                r"my recommendation (is|would be)",
                r"the best (option|choice|fit|solution) (for you|would be)",
                r"(compared to|the difference between)",
                r"(simpler|easier|straightforward|simple)",
                r"(one|single|specific) (option|recommendation|solution)",
                r"to (simplify|make it easy|keep it simple)",
            ],
            "behavior": "presents focused recommendation",
            "requires_question": False,
        },
        5: {  # Earn - asking for commitment
            "name": "Earn",
            "patterns": [
                r"would you like to",
                r"shall we (proceed|move forward|get started|schedule)",
                r"(are you )?ready to",
                r"let's (schedule|set up|get started|proceed|do this)",
                r"can i (set|schedule|book|get) (that|this|you)",
                r"does that (work|sound good) for you",
                r"(want|like) to (try|test|demo|see)",
                r"what do you (think|say)\?",
            ],
            "behavior": "asks for commitment/next step",
            "requires_question": False,
        },
    }
    
    # Only check if trainee is ready to advance to the NEXT stage
    next_stage = current_stage + 1
    
    # If already at stage 5, stay there
    if current_stage >= 5:
        return 5, detected_behaviors
    
    # Check if the latest message matches the NEXT stage's patterns
    next_stage_info = stage_patterns.get(next_stage)
    if not next_stage_info:
        return current_stage, detected_behaviors
    
    # Check if message requires a question mark
    if next_stage_info.get("requires_question") and "?" not in latest_message:
        return current_stage, detected_behaviors
    
    # Check patterns for the next stage
    for pattern in next_stage_info["patterns"]:
        if re.search(pattern, latest_message):
            detected_behaviors.append(next_stage_info["behavior"])
            logging.info("PULSE: Detected '%s' pattern, advancing from stage %d to %d", 
                        pattern, current_stage, next_stage)
            return next_stage, detected_behaviors
    
    # No advancement - stay at current stage
    return current_stage, detected_behaviors


def _detect_missteps(message: str, current_stage: int) -> List[Dict[str, Any]]:
    """
    Detect critical missteps in trainee's message that could lose the sale.
    Returns list of detected missteps with penalties.
    """
    detected_missteps = []
    message_lower = message.lower()
    
    for misstep_id, misstep_info in CRITICAL_MISSTEPS.items():
        # Check if misstep applies to current stage
        min_stage = misstep_info.get("min_stage", 1)
        max_stage = misstep_info.get("max_stage", 5)
        
        if current_stage < min_stage or current_stage > max_stage:
            continue
        
        # Check patterns
        for pattern in misstep_info["patterns"]:
            if re.search(pattern, message_lower):
                detected_missteps.append({
                    "id": misstep_id,
                    "penalty": misstep_info["trust_penalty"],
                    "hint": misstep_info["response_hint"],
                })
                logging.info("PULSE: Detected misstep '%s' at stage %d", misstep_id, current_stage)
                break  # Only count each misstep type once per message
    
    return detected_missteps


def _calculate_trust_change(
    current_stage: int,
    new_stage: int,
    detected_behaviors: List[str],
    missteps: List[Dict[str, Any]],
) -> int:
    """
    Calculate trust score change based on trainee performance.
    Positive for good behaviors, negative for missteps.
    """
    trust_change = 0
    
    # Reward for advancing stages
    if new_stage > current_stage:
        trust_change += 1  # +1 for each stage advancement
        logging.info("PULSE: +1 trust for stage advancement")
    
    # Reward for good behaviors
    for behavior in detected_behaviors:
        if "discovery question" in behavior.lower():
            trust_change += 1
        elif "active listening" in behavior.lower():
            trust_change += 1
        elif "connects feature" in behavior.lower():
            trust_change += 1
        elif "focused recommendation" in behavior.lower():
            trust_change += 1
        elif "commitment" in behavior.lower():
            trust_change += 1
    
    # Penalty for missteps
    for misstep in missteps:
        trust_change += misstep["penalty"]  # Already negative
        logging.info("PULSE: %d trust for misstep '%s'", misstep["penalty"], misstep["id"])
    
    return trust_change


def _determine_sale_outcome(
    trust_score: int,
    current_stage: int,
    missteps: List[Dict[str, Any]],
) -> str:
    """
    Determine the sale outcome based on trust score and stage.
    """
    # Check for loss condition
    if trust_score <= TRUST_LOSS_THRESHOLD:
        return "lost"
    
    # Check for win condition - must be at Stage 5 with high trust
    if current_stage >= 5 and trust_score >= TRUST_WIN_THRESHOLD:
        return "won"
    
    # Check for stalled - at Stage 5 but trust not high enough
    if current_stage >= 5 and trust_score < TRUST_WIN_THRESHOLD:
        return "stalled"
    
    # Still in progress
    return "in_progress"


def _get_sale_state_from_session(session_id: str) -> Dict[str, Any]:
    """Load sale state (trust score, outcome, missteps) from session storage."""
    try:
        from shared_code.blob import read_json
        state = read_json(f"sessions/{session_id}/sale_state.json")
        if state:
            return state
    except Exception:
        pass
    
    # Default initial state
    return {
        "trust_score": INITIAL_TRUST,
        "outcome": "in_progress",
        "missteps": [],
        "total_missteps": 0,
    }


def _save_sale_state_to_session(session_id: str, state: Dict[str, Any]) -> None:
    """Save sale state to session storage."""
    try:
        from shared_code.blob import write_json
        write_json(f"sessions/{session_id}/sale_state.json", state)
    except Exception as e:
        logging.warning("chat: failed to save sale state: %s", e)


def _generate_scorecard(
    session_id: str,
    pulse_stage: int,
    trust_score: int,
    sale_outcome: str,
    missteps: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Generate a scorecard for the session based on PULSE performance.
    
    Scoring breakdown:
    - BCE (Behavioral Mastery): Based on PULSE stage progression (0-3 scale)
    - MCF (Methodology Fidelity): Based on trust score and missteps (0-3 scale)
    - CPO (Conversion Outcome): Based on sale outcome (0-3 scale)
    """
    
    # BCE: Behavioral Mastery - how well did they follow PULSE stages?
    # Stage 1 = 0, Stage 2 = 0.75, Stage 3 = 1.5, Stage 4 = 2.25, Stage 5 = 3
    bce_score = (pulse_stage - 1) * 0.75
    bce_passed = pulse_stage >= 4
    bce_summary = f"Reached PULSE stage {pulse_stage} ({PULSE_STAGES[pulse_stage]['name']})"
    if pulse_stage < 3:
        bce_summary += ". Need to progress further through discovery and understanding."
    elif pulse_stage < 5:
        bce_summary += ". Good progress, but didn't complete the full PULSE cycle."
    else:
        bce_summary += ". Excellent! Completed all PULSE stages."
    
    # MCF: Methodology Fidelity - how well did they maintain trust and avoid missteps?
    # Trust 0-3 = 0, Trust 4-5 = 1, Trust 6-7 = 2, Trust 8-10 = 3
    # Subtract 0.5 for each misstep (max penalty of 1.5)
    if trust_score <= 3:
        mcf_base = 0
    elif trust_score <= 5:
        mcf_base = 1
    elif trust_score <= 7:
        mcf_base = 2
    else:
        mcf_base = 3
    
    misstep_penalty = min(len(missteps) * 0.5, 1.5)
    mcf_score = max(0, mcf_base - misstep_penalty)
    mcf_passed = mcf_score >= 2
    
    misstep_names = [m.get("id", "unknown").replace("_", " ") for m in missteps]
    if missteps:
        mcf_summary = f"Trust score: {trust_score}/10. Missteps: {', '.join(misstep_names)}."
    else:
        mcf_summary = f"Trust score: {trust_score}/10. No missteps detected."
    
    # CPO: Conversion Outcome - did they close the sale?
    if sale_outcome == "won":
        cpo_score = 3
        cpo_passed = True
        cpo_summary = "Successfully closed the sale!"
    elif sale_outcome == "stalled":
        cpo_score = 1.5
        cpo_passed = False
        cpo_summary = "Customer hesitated. Sale not completed but not lost."
    elif sale_outcome == "lost":
        cpo_score = 0
        cpo_passed = False
        cpo_summary = "Customer walked away. Review approach and try again."
    else:  # in_progress
        cpo_score = 1
        cpo_passed = False
        cpo_summary = "Session ended before reaching a conclusion."
    
    # Overall score: average of BCE, MCF, CPO (0-3 scale, convert to 0-100)
    overall_raw = (bce_score + mcf_score + cpo_score) / 3
    overall_pct = round((overall_raw / 3) * 100)
    
    # Build transcript lines for artifacts
    transcript_lines = []
    for msg in conversation_history:
        role = "Trainee" if msg["role"] == "user" else "Customer"
        transcript_lines.append(f"{role}: {msg['content']}")
    
    scorecard = {
        "overall": {
            "score": overall_pct,
            "raw_score": round(overall_raw, 2),
            "passed": overall_pct >= 70,
        },
        "bce": {
            "score": round(bce_score, 2),
            "passed": bce_passed,
            "summary": bce_summary,
        },
        "mcf": {
            "score": round(mcf_score, 2),
            "passed": mcf_passed,
            "summary": mcf_summary,
        },
        "cpo": {
            "score": round(cpo_score, 2),
            "passed": cpo_passed,
            "summary": cpo_summary,
        },
        "pulse_details": {
            "final_stage": pulse_stage,
            "stage_name": PULSE_STAGES[pulse_stage]["name"],
            "trust_score": trust_score,
            "sale_outcome": sale_outcome,
            "missteps": misstep_names,
            "total_exchanges": len([m for m in conversation_history if m["role"] == "user"]),
        },
    }
    
    return scorecard


def _save_scorecard(session_id: str, scorecard: Dict[str, Any]) -> None:
    """Save scorecard to session storage for feedback page."""
    try:
        from shared_code.blob import write_json
        path = f"sessions/{session_id}/scorecard.json"
        logging.info("chat: Attempting to save scorecard to %s", path)
        write_json(path, scorecard)
        logging.info("chat: Successfully saved scorecard for session %s, overall: %s%%", 
                    session_id, scorecard.get("overall", {}).get("score", "?"))
    except Exception as e:
        logging.exception("chat: FAILED to save scorecard for session %s: %s", session_id, e)


def _save_transcript(session_id: str, conversation_history: List[Dict[str, str]]) -> None:
    """Save transcript to session storage for feedback page."""
    try:
        from shared_code.blob import write_json
        transcript_lines = []
        for msg in conversation_history:
            role = "Trainee" if msg["role"] == "user" else "Customer"
            transcript_lines.append(f"{role}: {msg['content']}")
        
        write_json(f"sessions/{session_id}/transcript.json", {
            "transcript": transcript_lines,
        })
    except Exception as e:
        logging.warning("chat: failed to save transcript: %s", e)


def _get_pulse_stage_from_session(session_id: str) -> int:
    """Load current PULSE stage from session storage."""
    try:
        from shared_code.blob import read_json
        session_data = read_json(f"sessions/{session_id}/pulse_state.json")
        return session_data.get("current_stage", 1) if session_data else 1
    except Exception:
        return 1


def _save_pulse_stage_to_session(session_id: str, stage: int, behaviors: List[str]) -> None:
    """Save PULSE stage to session storage."""
    try:
        from shared_code.blob import write_json
        write_json(f"sessions/{session_id}/pulse_state.json", {
            "current_stage": stage,
            "stage_name": PULSE_STAGES[stage]["name"],
            "detected_behaviors": behaviors,
        })
    except Exception as e:
        logging.warning("chat: failed to save PULSE stage: %s", e)


def _get_conversation_history(session_id: str) -> list:
    """Load conversation history from blob storage."""
    try:
        from shared_code.blob import read_json
        history = read_json(f"sessions/{session_id}/conversation.json")
        return history.get("messages", []) if history else []
    except Exception as e:
        logging.warning("chat: failed to load conversation history: %s", e)
        return []


def _save_conversation_history(session_id: str, history: list) -> None:
    """Save conversation history to blob storage."""
    try:
        from shared_code.blob import write_json
        write_json(f"sessions/{session_id}/conversation.json", {"messages": history})
    except Exception as e:
        logging.warning("chat: failed to save conversation history: %s", e)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle chat requests with text input.
    
    Request body:
    {
        "sessionId": "uuid",
        "message": "user's text message",
        "persona": "Director|Relater|Socializer|Thinker"
    }
    
    Response:
    {
        "aiResponse": "AI's response text",
        "avatarEmotion": "neutral|happy|concerned|...",
        "sessionId": "uuid"
    }
    """
    logging.info("chat request: %s", req.method)
    
    # Handle CORS preflight
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )
    
    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON body")
    
    session_id = body.get("sessionId")
    message = body.get("message", "").strip()
    persona_type = body.get("persona", "Relater")
    
    if not session_id:
        return _error("Missing sessionId")
    
    if not message:
        return _error("Missing message")
    
    logging.info("chat: processing message for session=%s, persona=%s, message=%s", 
                 session_id, persona_type, message[:100])
    
    try:
        from shared_code.openai_client import generate_conversation_response
        
        # Load conversation history
        conversation_history = _get_conversation_history(session_id)
        
        # Limit conversation history to last 10 exchanges (20 messages) to avoid token limits
        MAX_HISTORY_MESSAGES = 20
        if len(conversation_history) > MAX_HISTORY_MESSAGES:
            conversation_history = conversation_history[-MAX_HISTORY_MESSAGES:]
            logging.info("chat: trimmed conversation history to %d messages", MAX_HISTORY_MESSAGES)
        
        # Add user message to history
        conversation_history.append({
            "role": "user",
            "content": message,
        })
        
        # Generate AI response - pass limited history excluding current message
        recent_history = conversation_history[:-1][-MAX_HISTORY_MESSAGES:]
        ai_response = generate_conversation_response(
            user_message=message,
            persona_type=persona_type,
            conversation_history=recent_history,  # Limited history excluding current message
            session_context={
                "session_id": session_id,
                "persona": persona_type,
            },
        )
        
        logging.info("chat: AI response: %s", ai_response[:100] if ai_response else "(empty)")
        
        # Add AI response to history
        conversation_history.append({
            "role": "assistant",
            "content": ai_response,
        })
        
        # Save updated history
        _save_conversation_history(session_id, conversation_history)
        
        # Determine emotion based on persona and response
        emotion = _determine_emotion(persona_type, ai_response)
        
        # Load current PULSE and sale state
        current_stage = _get_pulse_stage_from_session(session_id)
        sale_state = _get_sale_state_from_session(session_id)
        trust_score = sale_state.get("trust_score", INITIAL_TRUST)
        all_missteps = sale_state.get("missteps", [])
        
        # Analyze PULSE stage based on trainee's messages
        trainee_messages = [m["content"] for m in conversation_history if m["role"] == "user"]
        new_stage, detected_behaviors = _analyze_pulse_stage_quick(trainee_messages, current_stage)
        
        # Detect missteps in the current message
        current_missteps = _detect_missteps(message, current_stage)
        all_missteps.extend(current_missteps)
        
        # Calculate trust change
        trust_change = _calculate_trust_change(current_stage, new_stage, detected_behaviors, current_missteps)
        trust_score = max(0, min(10, trust_score + trust_change))  # Clamp to 0-10
        
        logging.info("chat: Trust score: %d (change: %+d), missteps this turn: %d", 
                    trust_score, trust_change, len(current_missteps))
        
        # Only advance stage, never go backwards
        if new_stage > current_stage:
            logging.info("chat: PULSE stage advanced from %d to %d, behaviors: %s", 
                        current_stage, new_stage, detected_behaviors)
            _save_pulse_stage_to_session(session_id, new_stage, detected_behaviors)
            current_stage = new_stage
        
        # Determine sale outcome
        sale_outcome = _determine_sale_outcome(trust_score, current_stage, all_missteps)
        
        # Save updated sale state
        sale_state = {
            "trust_score": trust_score,
            "outcome": sale_outcome,
            "missteps": all_missteps,
            "total_missteps": len(all_missteps),
        }
        _save_sale_state_to_session(session_id, sale_state)
        
        logging.info("chat: Sale outcome: %s, stage: %d, trust: %d", sale_outcome, current_stage, trust_score)
        
        # Generate and save scorecard when sale is concluded (won or lost)
        if sale_outcome in ("won", "lost"):
            scorecard = _generate_scorecard(
                session_id=session_id,
                pulse_stage=current_stage,
                trust_score=trust_score,
                sale_outcome=sale_outcome,
                missteps=all_missteps,
                conversation_history=conversation_history,
            )
            _save_scorecard(session_id, scorecard)
            _save_transcript(session_id, conversation_history)
            logging.info("chat: Generated scorecard for concluded session %s", session_id)
        
        # Get stage info for response
        stage_info = PULSE_STAGES.get(current_stage, PULSE_STAGES[1])
        
        # Build feedback message based on outcome
        outcome_feedback = ""
        if sale_outcome == "won":
            outcome_feedback = "Congratulations! You successfully landed the sale!"
        elif sale_outcome == "lost":
            outcome_feedback = "The customer has decided to leave. Review your approach and try again."
        elif sale_outcome == "stalled":
            outcome_feedback = "The customer is hesitating. You may need to rebuild trust or address concerns."
        
        return _ok({
            "aiResponse": ai_response,
            "avatarEmotion": emotion,
            "sessionId": session_id,
            "pulseStage": current_stage,
            "pulseStageName": stage_info["name"],
            "pulseAnalysis": {
                "currentStage": current_stage,
                "stageName": stage_info["name"],
                "stageDescription": stage_info["description"],
                "detectedBehaviors": detected_behaviors,
            },
            "saleOutcome": {
                "status": sale_outcome,
                "trustScore": trust_score,
                "misstepsThisTurn": [m["id"] for m in current_missteps],
                "totalMissteps": len(all_missteps),
                "feedback": outcome_feedback,
            },
        })
        
    except Exception as e:
        logging.exception("chat: error processing message: %s", e)
        return _error(f"Failed to process message: {str(e)}", 500)


def _determine_emotion(persona_type: str, response: str) -> str:
    """Determine avatar emotion based on persona and response content."""
    response_lower = response.lower()
    
    # Check for emotional indicators in response
    if any(word in response_lower for word in ["excited", "great", "love", "amazing", "fantastic"]):
        return "excited"
    elif any(word in response_lower for word in ["sorry", "unfortunately", "apologize"]):
        return "empathetic"
    elif any(word in response_lower for word in ["interesting", "hmm", "curious"]):
        return "curious"
    elif any(word in response_lower for word in ["?", "what", "how", "why"]):
        return "curious"
    
    # Default emotions by persona
    persona_emotions = {
        "Director": "confident",
        "Relater": "friendly",
        "Socializer": "excited",
        "Thinker": "thoughtful",
    }
    
    return persona_emotions.get(persona_type, "neutral")
