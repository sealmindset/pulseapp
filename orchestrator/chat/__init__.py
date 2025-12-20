"""
Chat endpoint for text-based conversation.

This endpoint receives text directly (from streaming STT) and returns AI responses.
It's faster than the audio_chunk endpoint since it skips the STT step.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import azure.functions as func


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
        
        return _ok({
            "aiResponse": ai_response,
            "avatarEmotion": emotion,
            "sessionId": session_id,
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
