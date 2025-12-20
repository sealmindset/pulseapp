"""
Avatar service using Azure Speech Services Text-to-Speech Avatar.

Provides real-time lip-synced avatar video streaming for the PULSE training platform.
The avatar represents the AI customer persona during training sessions.

Azure Speech Avatar advantages over Sora-2:
- No time limit (Sora-2 limited to 12 seconds)
- Real-time WebRTC streaming for interactive conversations
- Pre-built avatar characters with customizable voices
- Lower latency for conversational AI
"""

import base64
import io
import json
import logging
import os
import tempfile
from typing import Any, Dict, Optional

import requests

from .blob import get_container_client, now_iso


def _get_speech_config() -> Dict[str, str]:
    """Get Azure Speech Services configuration."""
    return {
        "key": os.getenv("AZURE_SPEECH_KEY", ""),
        "region": os.getenv("AZURE_SPEECH_REGION", "eastus2"),
        "endpoint": os.getenv("AZURE_SPEECH_ENDPOINT", ""),
    }


def _validate_speech_config(config: Dict[str, str]) -> None:
    """Validate Azure Speech Services configuration."""
    if not config["key"]:
        raise RuntimeError("Missing AZURE_SPEECH_KEY for avatar generation")
    if not config["region"]:
        raise RuntimeError("Missing AZURE_SPEECH_REGION for avatar generation")


# Azure Speech Avatar character mappings per persona type
# See: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/text-to-speech-avatar/standard-avatars
# NOTE: For real-time API, lisa-graceful-sitting, lisa-graceful-standing, 
# lisa-technical-sitting, and lisa-technical-standing are NOT supported.
# Use lisa with casual-sitting for real-time streaming.
PERSONA_AVATAR_CONFIGS = {
    "Director": {
        "character": "lisa",  # Professional female avatar
        "style": "casual-sitting",  # casual-sitting works with real-time API
        "voice": "en-US-JennyNeural",  # Confident, professional voice
        "voice_style": "customerservice",  # Professional tone
        "description": "Professional business executive, confident and direct",
    },
    "Relater": {
        "character": "lisa",  # Use lisa (standard avatar) - harry not available
        "style": "casual-sitting",  # casual-sitting works with real-time API
        "voice": "en-US-SaraNeural",  # Warm, friendly female voice to match Lisa avatar
        "voice_style": "friendly",  # Warm tone
        "description": "Warm friendly person, patient and empathetic",
    },
    "Socializer": {
        "character": "lisa",  # Expressive female avatar
        "style": "casual-sitting",  # casual-sitting works with real-time API
        "voice": "en-US-AriaNeural",  # Energetic voice
        "voice_style": "cheerful",  # Enthusiastic tone
        "description": "Energetic expressive person, enthusiastic and engaging",
    },
    "Thinker": {
        "character": "lisa",  # Use lisa (standard avatar) - harry not available
        "style": "casual-sitting",  # casual-sitting works with real-time API
        "voice": "en-US-MichelleNeural",  # Calm, measured female voice to match Lisa avatar
        "voice_style": "calm",  # Thoughtful tone
        "description": "Thoughtful analytical person, careful and methodical",
    },
}

# Emotion to SSML expression style mapping for Azure Speech
EMOTION_EXPRESSIONS = {
    "neutral": "neutral",
    "interested": "friendly",
    "skeptical": "unfriendly",
    "pleased": "cheerful",
    "concerned": "empathetic",
    "excited": "excited",
    "hesitant": "shy",
}


def is_avatar_service_available() -> bool:
    """Check if the Azure Speech Avatar service is configured and available."""
    config = _get_speech_config()
    return bool(config["key"] and config["region"])


def get_avatar_config(persona_type: str) -> Dict[str, Any]:
    """
    Get Azure Speech Avatar configuration for a persona.
    
    Returns configuration needed for real-time WebRTC avatar streaming.
    The actual avatar rendering happens client-side using the Speech SDK.
    
    Args:
        persona_type: Customer persona (Director, Relater, Socializer, Thinker)
    
    Returns:
        Dict with avatar character, style, voice, and connection info
    """
    config = _get_speech_config()
    avatar_config = PERSONA_AVATAR_CONFIGS.get(persona_type, PERSONA_AVATAR_CONFIGS["Relater"])
    
    return {
        "available": is_avatar_service_available(),
        "character": avatar_config["character"],
        "style": avatar_config["style"],
        "voice": avatar_config["voice"],
        "voice_style": avatar_config["voice_style"],
        "description": avatar_config["description"],
        "region": config["region"],
        "persona": persona_type,
    }


def generate_avatar_video(
    persona_type: str,
    speech_text: str,
    emotion: str = "neutral",
    duration_seconds: float = 5.0,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate avatar synthesis configuration for Azure Speech Avatar.
    
    Note: Azure Speech Avatar uses real-time WebRTC streaming, not pre-generated videos.
    This function returns the configuration and SSML needed for client-side rendering.
    
    Args:
        persona_type: Customer persona (Director, Relater, Socializer, Thinker)
        speech_text: Text the avatar will speak (for TTS + lip-sync)
        emotion: Emotional state (neutral, interested, skeptical, pleased, etc.)
        duration_seconds: Not used for real-time avatar (kept for API compatibility)
        session_id: Optional session ID for logging
    
    Returns:
        Dict with:
        - ssml: SSML markup for speech synthesis with avatar
        - avatar_config: Avatar character and style configuration
        - emotion: Emotion style applied
        - persona: Persona type used
    """
    config = _get_speech_config()
    
    # Check if service is available
    if not is_avatar_service_available():
        logging.warning("avatar_service: Azure Speech not configured, returning placeholder")
        return _generate_placeholder_response(persona_type, emotion)
    
    _validate_speech_config(config)
    
    # Get persona-specific avatar configuration
    avatar_config = PERSONA_AVATAR_CONFIGS.get(persona_type, PERSONA_AVATAR_CONFIGS["Relater"])
    expression_style = EMOTION_EXPRESSIONS.get(emotion, EMOTION_EXPRESSIONS["neutral"])
    
    # Build SSML for avatar speech synthesis
    ssml = _build_avatar_ssml(avatar_config, expression_style, speech_text)
    
    logging.info(
        "avatar_service: generating avatar config for persona=%s, emotion=%s, text_length=%d",
        persona_type, emotion, len(speech_text)
    )
    
    return {
        "ssml": ssml,
        "avatar_config": {
            "character": avatar_config["character"],
            "style": avatar_config["style"],
            "voice": avatar_config["voice"],
        },
        "emotion": emotion,
        "persona": persona_type,
        "region": config["region"],
        "generated_at": now_iso(),
        "streaming": True,  # Indicates real-time WebRTC streaming
    }


def _build_avatar_ssml(
    avatar_config: Dict[str, str],
    expression_style: str,
    speech_text: str,
) -> str:
    """
    Build SSML markup for Azure Speech Avatar synthesis.
    
    The SSML includes voice selection, expression style, and the text to speak.
    This is used by the client-side Speech SDK for real-time avatar rendering.
    """
    voice = avatar_config.get("voice", "en-US-JennyNeural")
    voice_style = avatar_config.get("voice_style", "neutral")
    
    # Escape XML special characters in speech text
    escaped_text = (
        speech_text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    
    # Build SSML with voice style for emotional expression
    ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" 
       xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
    <voice name="{voice}">
        <mstts:express-as style="{voice_style}">
            {escaped_text}
        </mstts:express-as>
    </voice>
</speak>"""
    
    return ssml


def get_ice_server_info(region: str, speech_key: str) -> Optional[Dict[str, Any]]:
    """
    Get ICE server information for WebRTC connection.
    
    This is needed for establishing the real-time avatar video stream.
    """
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1"
    
    headers = {
        "Ocp-Apim-Subscription-Key": speech_key,
    }
    
    try:
        logging.info("avatar_service: requesting ICE servers from %s", url)
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        ice_data = resp.json()
        logging.info("avatar_service: ICE server response: %s", str(ice_data)[:500])
        return ice_data
    except requests.exceptions.HTTPError as exc:
        logging.error("avatar_service: HTTP error getting ICE servers: %s, response: %s", exc, exc.response.text if exc.response else "N/A")
        return None
    except Exception as exc:
        logging.error("avatar_service: failed to get ICE server info: %s", exc)
        return None


def get_avatar_token() -> Optional[Dict[str, Any]]:
    """
    Get authentication token for Azure Speech Avatar.
    
    Returns token and region info needed for client-side SDK initialization.
    """
    config = _get_speech_config()
    
    if not is_avatar_service_available():
        return None
    
    region = config["region"]
    key = config["key"]
    
    # Get authorization token
    token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    try:
        logging.info("avatar_service: requesting token from %s", token_url)
        resp = requests.post(token_url, headers=headers, timeout=10)
        resp.raise_for_status()
        token = resp.text
        logging.info("avatar_service: token obtained successfully, length=%d", len(token))
        
        # Get ICE server info for WebRTC
        ice_info = get_ice_server_info(region, key)
        
        return {
            "token": token,
            "region": region,
            "ice_servers": ice_info,
            "expires_in": 600,  # Token valid for 10 minutes
        }
    except requests.exceptions.HTTPError as exc:
        logging.error("avatar_service: HTTP error getting token: %s, response: %s", exc, exc.response.text if exc.response else "N/A")
        return None
    except Exception as exc:
        logging.error("avatar_service: failed to get token: %s", exc)
        return None


def transcribe_audio_speech_services(
    audio_data: bytes,
    audio_format: str = "webm",
    language: str = "en-US",
) -> Optional[str]:
    """
    Transcribe audio using Azure Speech Services STT.
    
    This has much higher rate limits than OpenAI Whisper.
    
    Args:
        audio_data: Raw audio bytes
        audio_format: Audio format (webm, wav, mp3, etc.)
        language: Language code (e.g., en-US)
    
    Returns:
        Transcribed text or None on failure
    """
    config = _get_speech_config()
    
    if not config["key"] or not config["region"]:
        logging.warning("avatar_service: Speech Services not configured for STT")
        return None
    
    region = config["region"]
    key = config["key"]
    
    # Azure Speech Services REST API for STT
    # Supports: wav, ogg, webm, mp3, flac
    stt_url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    
    # Map audio format to content type
    content_types = {
        "webm": "audio/webm",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
    }
    content_type = content_types.get(audio_format, "audio/webm")
    
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": f"{content_type}; codecs=opus",
        "Accept": "application/json",
    }
    
    params = {
        "language": language,
        "format": "detailed",
    }
    
    try:
        logging.info("avatar_service: transcribing audio via Speech Services, size=%d bytes, format=%s", len(audio_data), audio_format)
        resp = requests.post(stt_url, headers=headers, params=params, data=audio_data, timeout=30)
        resp.raise_for_status()
        
        result = resp.json()
        logging.info("avatar_service: STT response: %s", str(result)[:500])
        
        # Extract the recognized text
        if result.get("RecognitionStatus") == "Success":
            # Get the best recognition result
            if result.get("NBest") and len(result["NBest"]) > 0:
                transcript = result["NBest"][0].get("Display", "")
                logging.info("avatar_service: STT success, transcript: %s", transcript[:100] if transcript else "(empty)")
                return transcript
            elif result.get("DisplayText"):
                return result["DisplayText"]
        elif result.get("RecognitionStatus") == "NoMatch":
            logging.warning("avatar_service: STT NoMatch - audio format may not be supported or no speech detected")
            return ""
        elif result.get("RecognitionStatus") == "InitialSilenceTimeout":
            logging.warning("avatar_service: STT InitialSilenceTimeout - no speech detected in audio")
            return ""
        
        logging.warning("avatar_service: STT returned no text, status: %s, full response: %s", result.get("RecognitionStatus"), str(result)[:200])
        return ""
        
    except requests.exceptions.HTTPError as exc:
        logging.error("avatar_service: STT HTTP error: %s, response: %s", exc, exc.response.text if exc.response else "N/A")
        return None
    except Exception as exc:
        logging.error("avatar_service: STT failed: %s", exc)
        return None


def _generate_placeholder_response(
    persona_type: str,
    emotion: str,
) -> Dict[str, Any]:
    """Generate a placeholder response when Azure Speech Avatar is not available."""
    return {
        "ssml": None,
        "avatar_config": None,
        "persona": persona_type,
        "emotion": emotion,
        "generated_at": now_iso(),
        "placeholder": True,
        "streaming": False,
        "message": "Azure Speech Avatar is not currently configured. "
                   "Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION to enable avatar.",
    }


def generate_intro_avatar(
    persona_type: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an introductory avatar video for session start.
    
    This creates a short video of the avatar in a neutral/welcoming state
    before the conversation begins.
    """
    intro_text = _get_intro_text(persona_type)
    
    return generate_avatar_video(
        persona_type=persona_type,
        speech_text=intro_text,
        emotion="neutral",
        duration_seconds=3.0,
        session_id=session_id,
    )


def _get_intro_text(persona_type: str) -> str:
    """Get persona-appropriate intro text."""
    intros = {
        "Director": "Hello. I'm here to look at your products. Let's get started.",
        "Relater": "Hi there! I've been thinking about making a purchase and wanted to chat.",
        "Socializer": "Hey! I'm so excited to be here! I've heard great things about you!",
        "Thinker": "Good afternoon. I've done some research and have a few questions.",
    }
    return intros.get(persona_type, intros["Relater"])
