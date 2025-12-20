"""
Audio chunk handler for PULSE training sessions.

Processes audio chunks from the trainee, performs:
1. Speech-to-text (STT) using gpt-4o-realtime-preview
2. AI response generation using gpt-5-chat
3. Text-to-speech (TTS) for the response
4. Avatar video generation using Sora-2 (when available)
"""

import base64
import json
import logging
import os
from typing import Any, Dict, Optional

import azure.functions as func

from shared_code.blob import read_json, write_json, now_iso
from shared_code.http import json_ok, no_content, text_error


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _ok(body: Any, status: int = 200) -> func.HttpResponse:
    return json_ok(body, status=status, headers=CORS_HEADERS)


def _no_content() -> func.HttpResponse:
    return no_content(headers=CORS_HEADERS)


def _error(message: str, status: int) -> func.HttpResponse:
    return text_error(message, status=status, headers=CORS_HEADERS)


def _orchestrator_enabled() -> bool:
    value = os.getenv("TRAINING_ORCHESTRATOR_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def _audio_processing_enabled() -> bool:
    """Check if audio processing (STT/TTS) is enabled."""
    value = os.getenv("AUDIO_PROCESSING_ENABLED", "true").strip().lower()
    return value in ("true", "1", "yes")


def _get_session_data(session_id: str) -> Optional[Dict[str, Any]]:
    """Load session data from blob storage."""
    return read_json(f"sessions/{session_id}/session.json")


def _get_conversation_history(session_id: str) -> list:
    """Load conversation history for the session."""
    history = read_json(f"sessions/{session_id}/conversation.json")
    return history.get("messages", []) if history else []


def _save_conversation_history(session_id: str, messages: list) -> None:
    """Save conversation history to blob storage."""
    write_json(f"sessions/{session_id}/conversation.json", {
        "session_id": session_id,
        "messages": messages,
        "updated_at": now_iso(),
    })


def _determine_emotion(response_text: str, persona_type: str) -> str:
    """Determine avatar emotion based on response content."""
    text_lower = response_text.lower()
    
    if any(word in text_lower for word in ["great", "excellent", "perfect", "love"]):
        return "pleased"
    elif any(word in text_lower for word in ["hmm", "not sure", "concern", "worry"]):
        return "concerned"
    elif any(word in text_lower for word in ["really", "wow", "amazing", "exciting"]):
        return "excited"
    elif any(word in text_lower for word in ["but", "however", "price", "expensive"]):
        return "skeptical"
    elif any(word in text_lower for word in ["tell me more", "interested", "sounds good"]):
        return "interested"
    else:
        return "neutral"


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("audio_chunk request: %s", req.method)

    if req.method == "OPTIONS":
        return _no_content()

    if req.method != "POST":
        return _error("Method not allowed", 405)

    if not _orchestrator_enabled():
        return _error(
            "Training orchestrator is disabled in this environment. "
            "Set TRAINING_ORCHESTRATOR_ENABLED to true to enable.",
            503,
        )

    # Extract session ID from form data or query params
    session_id = req.form.get("sessionId") if req.form else None
    if not session_id:
        session_id = req.params.get("sessionId") if req.params else None
    if not session_id:
        return _error("Missing sessionId", 400)

    # Get audio chunk from form data
    audio_file = req.files.get("chunk") if req.files else None
    if not audio_file:
        return _error("Missing audio chunk", 400)

    audio_data = audio_file.read()
    if not audio_data:
        return _error("Empty audio chunk", 400)

    logging.info("audio_chunk: processing chunk for session=%s, size=%d bytes", session_id, len(audio_data))

    # Check if audio processing is enabled
    if not _audio_processing_enabled():
        return _ok({
            "partialTranscript": None,
            "message": "Audio received but processing is disabled. Enable AUDIO_PROCESSING_ENABLED.",
            "sessionId": session_id,
        })

    # Load session data to get persona type
    session_data = _get_session_data(session_id)
    if not session_data:
        return _error(f"Session {session_id} not found", 404)

    persona_type = session_data.get("persona") or "Relater"
    
    try:
        # Import here to avoid circular imports and allow graceful degradation
        from shared_code.openai_client import (
            transcribe_audio,
            generate_speech,
            generate_conversation_response,
        )
        from shared_code.avatar_service import (
            generate_avatar_video,
            is_avatar_service_available,
            transcribe_audio_speech_services,
        )
        
        # Step 1: Transcribe audio (STT) - Use Whisper (webm format supported)
        # Note: Azure Speech Services REST API doesn't support webm/opus well
        transcript = None
        try:
            transcript = transcribe_audio(audio_data, audio_format="webm")
            logging.info("audio_chunk: Whisper transcribed: %s", transcript[:100] if transcript else "(empty)")
        except Exception as stt_exc:
            logging.exception("audio_chunk: Whisper STT failed: %s", stt_exc)
            transcript = None
        
        if not transcript or not transcript.strip():
            return _ok({
                "partialTranscript": None,
                "message": "No speech detected in audio chunk",
                "sessionId": session_id,
            })
        
        # Step 2: Load conversation history and generate AI response
        conversation_history = _get_conversation_history(session_id)
        
        # Add user message to history
        conversation_history.append({
            "role": "user",
            "content": transcript,
        })
        
        # Generate AI response
        try:
            ai_response = generate_conversation_response(
                user_message=transcript,
                persona_type=persona_type,
                conversation_history=conversation_history[:-1],  # Exclude current message
                session_context={
                    "session_id": session_id,
                    "persona": persona_type,
                },
            )
            logging.info("audio_chunk: AI response: %s", ai_response[:100] if ai_response else "(empty)")
        except Exception as llm_exc:
            logging.exception("audio_chunk: LLM response failed: %s", llm_exc)
            ai_response = "I'm sorry, I didn't catch that. Could you repeat?"
        
        # Add AI response to history
        conversation_history.append({
            "role": "assistant",
            "content": ai_response,
        })
        
        # Save updated conversation history
        _save_conversation_history(session_id, conversation_history)
        
        # Step 3: Generate speech (TTS)
        audio_base64 = None
        try:
            speech_audio = generate_speech(ai_response, voice="alloy")
            audio_base64 = base64.b64encode(speech_audio).decode("utf-8")
            logging.info("audio_chunk: generated speech, size=%d bytes", len(speech_audio))
        except Exception as tts_exc:
            logging.exception("audio_chunk: TTS failed: %s", tts_exc)
        
        # Step 4: Generate avatar video (if Sora-2 is available)
        avatar_video = None
        if is_avatar_service_available():
            try:
                emotion = _determine_emotion(ai_response, persona_type)
                avatar_result = generate_avatar_video(
                    persona_type=persona_type,
                    speech_text=ai_response,
                    emotion=emotion,
                    duration_seconds=min(len(ai_response) / 15, 10.0),  # Rough estimate
                    session_id=session_id,
                )
                if avatar_result and not avatar_result.get("placeholder"):
                    avatar_video = {
                        "url": avatar_result.get("video_url"),
                        "base64": avatar_result.get("video_base64"),
                        "emotion": avatar_result.get("emotion"),
                    }
            except Exception as avatar_exc:
                logging.exception("audio_chunk: avatar generation failed: %s", avatar_exc)
        
        # Build response
        response_data: Dict[str, Any] = {
            "sessionId": session_id,
            "partialTranscript": transcript,
            "aiResponse": ai_response,
            "audioBase64": audio_base64,
            "avatarState": "speaking" if audio_base64 else "idle",
        }
        
        if avatar_video:
            response_data["avatarVideo"] = avatar_video
        
        return _ok(response_data)
        
    except ImportError as imp_exc:
        logging.exception("audio_chunk: missing dependencies: %s", imp_exc)
        return _ok({
            "partialTranscript": None,
            "message": "Audio processing dependencies not available",
            "sessionId": session_id,
        })
    except Exception as exc:
        logging.exception("audio_chunk: unexpected error: %s", exc)
        return _error(f"Audio processing failed: {exc}", 500)
