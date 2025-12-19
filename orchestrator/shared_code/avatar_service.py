"""
Avatar video generation service using Sora-2.

Generates lip-synced avatar videos for the PULSE training platform.
The avatar represents the AI customer persona during training sessions.
"""

import base64
import json
import logging
import os
from typing import Any, Dict, Optional

import requests

from .blob import get_container_client, now_iso


def _get_config() -> Dict[str, str]:
    """Get Azure OpenAI configuration for Sora-2."""
    return {
        "endpoint": os.getenv("OPENAI_ENDPOINT", "").rstrip("/"),
        "api_version": os.getenv("OPENAI_API_VERSION", "2024-12-01-preview"),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
        "deployment": os.getenv("OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET", ""),
    }


def _validate_config(config: Dict[str, str]) -> None:
    """Validate Sora-2 configuration."""
    if not config["endpoint"]:
        raise RuntimeError("Missing OPENAI_ENDPOINT for avatar generation")
    if not config["api_key"]:
        raise RuntimeError("Missing AZURE_OPENAI_API_KEY for avatar generation")
    if not config["deployment"]:
        raise RuntimeError("Missing OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET for avatar generation")


# Avatar appearance configurations per persona type
PERSONA_AVATAR_CONFIGS = {
    "Director": {
        "appearance": "professional business executive, confident posture, direct eye contact",
        "style": "formal business attire, neutral background office setting",
        "demeanor": "assertive, time-conscious, results-focused",
    },
    "Relater": {
        "appearance": "warm friendly person, relaxed posture, genuine smile",
        "style": "smart casual attire, comfortable home or cafe setting",
        "demeanor": "patient, empathetic, relationship-oriented",
    },
    "Socializer": {
        "appearance": "energetic expressive person, animated gestures, bright smile",
        "style": "trendy casual attire, vibrant colorful setting",
        "demeanor": "enthusiastic, talkative, socially engaging",
    },
    "Thinker": {
        "appearance": "thoughtful analytical person, attentive expression, measured movements",
        "style": "neat professional casual, organized workspace setting",
        "demeanor": "careful, detail-oriented, methodical",
    },
}

# Emotion to visual expression mapping
EMOTION_EXPRESSIONS = {
    "neutral": "calm neutral expression, attentive listening posture",
    "interested": "slightly raised eyebrows, leaning forward, engaged expression",
    "skeptical": "slight frown, crossed arms, questioning look",
    "pleased": "warm smile, relaxed posture, nodding",
    "concerned": "furrowed brow, thoughtful expression, slight head tilt",
    "excited": "bright smile, animated gestures, enthusiastic expression",
    "hesitant": "uncertain expression, slight pause, considering look",
}


def is_avatar_service_available() -> bool:
    """Check if the avatar service (Sora-2) is configured and available."""
    config = _get_config()
    return bool(config["endpoint"] and config["api_key"] and config["deployment"])


def generate_avatar_video(
    persona_type: str,
    speech_text: str,
    emotion: str = "neutral",
    duration_seconds: float = 5.0,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an avatar video clip using Sora-2.
    
    Args:
        persona_type: Customer persona (Director, Relater, Socializer, Thinker)
        speech_text: Text the avatar will appear to speak (for lip-sync)
        emotion: Emotional state (neutral, interested, skeptical, pleased, etc.)
        duration_seconds: Approximate video duration
        session_id: Optional session ID for caching/storage
    
    Returns:
        Dict with:
        - video_url: URL to the generated video (if stored)
        - video_base64: Base64 encoded video data
        - duration: Actual video duration
        - persona: Persona type used
        - emotion: Emotion expressed
    """
    config = _get_config()
    
    # Check if service is available
    if not is_avatar_service_available():
        logging.warning("avatar_service: Sora-2 not configured, returning placeholder")
        return _generate_placeholder_response(persona_type, emotion)
    
    _validate_config(config)
    
    # Get persona-specific avatar configuration
    avatar_config = PERSONA_AVATAR_CONFIGS.get(persona_type, PERSONA_AVATAR_CONFIGS["Relater"])
    expression = EMOTION_EXPRESSIONS.get(emotion, EMOTION_EXPRESSIONS["neutral"])
    
    # Build the video generation prompt
    prompt = _build_video_prompt(avatar_config, expression, speech_text, duration_seconds)
    
    logging.info(
        "avatar_service: generating video for persona=%s, emotion=%s, text_length=%d",
        persona_type, emotion, len(speech_text)
    )
    
    try:
        # Call Sora-2 API
        video_data = _call_sora_api(config, prompt, duration_seconds)
        
        # Store video if session_id provided
        video_url = None
        if session_id and video_data:
            video_url = _store_video(session_id, video_data, persona_type, emotion)
        
        return {
            "video_url": video_url,
            "video_base64": base64.b64encode(video_data).decode("utf-8") if video_data else None,
            "duration": duration_seconds,
            "persona": persona_type,
            "emotion": emotion,
            "generated_at": now_iso(),
        }
        
    except Exception as exc:
        logging.exception("avatar_service: failed to generate video: %s", exc)
        return _generate_placeholder_response(persona_type, emotion)


def _build_video_prompt(
    avatar_config: Dict[str, str],
    expression: str,
    speech_text: str,
    duration: float,
) -> str:
    """Build the prompt for Sora-2 video generation."""
    return f"""Generate a realistic talking head video of a person with the following characteristics:

APPEARANCE: {avatar_config['appearance']}
SETTING: {avatar_config['style']}
DEMEANOR: {avatar_config['demeanor']}
EXPRESSION: {expression}

The person should appear to be speaking the following text naturally with appropriate lip movements and facial expressions:
"{speech_text}"

Video requirements:
- Duration: approximately {duration} seconds
- Frame rate: 24fps
- Resolution: 720p
- Camera: static medium close-up shot, head and shoulders visible
- Lighting: professional, well-lit
- The person should maintain eye contact as if speaking to someone across a desk
"""


def _call_sora_api(
    config: Dict[str, str],
    prompt: str,
    duration: float,
) -> Optional[bytes]:
    """
    Call the Sora-2 API to generate video.
    
    Note: This is a placeholder implementation. The actual Sora-2 API
    may have different endpoints and parameters when released.
    """
    deployment = config["deployment"]
    
    # Sora-2 video generation endpoint (placeholder - actual API may differ)
    url = f"{config['endpoint']}/openai/deployments/{deployment}/videos/generations?api-version={config['api_version']}"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": config["api_key"],
    }
    
    payload = {
        "prompt": prompt,
        "duration": min(duration, 20.0),  # Cap at 20 seconds
        "resolution": "720p",
        "fps": 24,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        
        # Handle response - may be direct video bytes or a job ID for async generation
        content_type = resp.headers.get("content-type", "")
        
        if "video" in content_type:
            return resp.content
        elif "application/json" in content_type:
            # Async job - poll for completion
            job_data = resp.json()
            return _poll_video_job(config, job_data)
        else:
            logging.warning("avatar_service: unexpected response type: %s", content_type)
            return None
            
    except requests.exceptions.HTTPError as exc:
        if exc.response.status_code == 404:
            logging.warning("avatar_service: Sora-2 endpoint not available (404)")
        else:
            logging.error("avatar_service: API error: %s", exc)
        return None
    except Exception as exc:
        logging.error("avatar_service: request failed: %s", exc)
        return None


def _poll_video_job(
    config: Dict[str, str],
    job_data: Dict[str, Any],
    max_attempts: int = 30,
    poll_interval: float = 2.0,
) -> Optional[bytes]:
    """Poll for async video generation job completion."""
    import time
    
    job_id = job_data.get("id") or job_data.get("job_id")
    if not job_id:
        logging.warning("avatar_service: no job ID in response")
        return None
    
    deployment = config["deployment"]
    url = f"{config['endpoint']}/openai/deployments/{deployment}/videos/generations/{job_id}?api-version={config['api_version']}"
    
    headers = {
        "api-key": config["api_key"],
    }
    
    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            
            status_data = resp.json()
            status = status_data.get("status", "").lower()
            
            if status == "succeeded":
                # Get the video URL and download
                video_url = status_data.get("result", {}).get("url")
                if video_url:
                    video_resp = requests.get(video_url, timeout=60)
                    video_resp.raise_for_status()
                    return video_resp.content
                return None
                
            elif status in ("failed", "cancelled"):
                logging.error("avatar_service: job %s failed: %s", job_id, status_data.get("error"))
                return None
            
            # Still processing
            time.sleep(poll_interval)
            
        except Exception as exc:
            logging.error("avatar_service: poll error: %s", exc)
            time.sleep(poll_interval)
    
    logging.warning("avatar_service: job %s timed out", job_id)
    return None


def _store_video(
    session_id: str,
    video_data: bytes,
    persona_type: str,
    emotion: str,
) -> Optional[str]:
    """Store generated video in blob storage and return URL."""
    try:
        from azure.storage.blob import ContentSettings
        
        cc = get_container_client()
        timestamp = now_iso().replace(":", "-").replace(".", "-")
        blob_path = f"sessions/{session_id}/avatars/{persona_type}_{emotion}_{timestamp}.mp4"
        
        bc = cc.get_blob_client(blob_path)
        bc.upload_blob(
            video_data,
            overwrite=True,
            content_settings=ContentSettings(content_type="video/mp4"),
        )
        
        # Return the blob URL
        return bc.url
        
    except Exception as exc:
        logging.exception("avatar_service: failed to store video: %s", exc)
        return None


def _generate_placeholder_response(
    persona_type: str,
    emotion: str,
) -> Dict[str, Any]:
    """Generate a placeholder response when Sora-2 is not available."""
    return {
        "video_url": None,
        "video_base64": None,
        "duration": 0,
        "persona": persona_type,
        "emotion": emotion,
        "generated_at": now_iso(),
        "placeholder": True,
        "message": "Avatar video generation (Sora-2) is not currently available. "
                   "Request access to enable dynamic avatar videos.",
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
