"""
Azure OpenAI client utilities for PULSE orchestrator.

Provides unified access to:
- gpt-5-chat (Persona-Core-Chat) - conversational AI
- o4-mini (Persona-High-Reasoning) - complex reasoning for BCE/MCF/CPO
- gpt-4o-realtime-preview (PULSE-Audio-Realtime) - speech I/O
- sora-2 (Persona-Visual-Asset) - avatar video generation
"""

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests


def _get_config() -> Dict[str, str]:
    """Get Azure OpenAI configuration from environment."""
    return {
        "endpoint": os.getenv("OPENAI_ENDPOINT", "").rstrip("/"),
        "api_version": os.getenv("OPENAI_API_VERSION", "2024-12-01-preview"),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
        "deployment_core_chat": os.getenv("OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT", ""),
        "deployment_high_reasoning": os.getenv("OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING", ""),
        "deployment_audio_realtime": os.getenv("OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME", ""),
        "deployment_visual_asset": os.getenv("OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET", ""),
    }


def _validate_config(config: Dict[str, str], required_deployment: str) -> None:
    """Validate that required configuration is present."""
    if not config["endpoint"]:
        raise RuntimeError("Missing OPENAI_ENDPOINT environment variable")
    if not config["api_key"]:
        raise RuntimeError("Missing AZURE_OPENAI_API_KEY environment variable")
    if not config.get(required_deployment):
        raise RuntimeError(f"Missing {required_deployment} deployment configuration")


def chat_completion(
    messages: List[Dict[str, str]],
    deployment_key: str = "deployment_core_chat",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Call Azure OpenAI chat completion API.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        deployment_key: Which deployment to use (deployment_core_chat, deployment_high_reasoning)
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens in response
        response_format: Optional response format (e.g., {"type": "json_object"})
    
    Returns:
        Full API response as dict
    """
    config = _get_config()
    _validate_config(config, deployment_key)
    
    deployment = config[deployment_key]
    url = f"{config['endpoint']}/openai/deployments/{deployment}/chat/completions?api-version={config['api_version']}"
    
    payload: Dict[str, Any] = {
        "messages": messages,
        "temperature": temperature,
    }
    
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if response_format:
        payload["response_format"] = response_format
    
    headers = {
        "Content-Type": "application/json",
        "api-key": config["api_key"],
    }
    
    logging.info("openai_client: calling chat completion on deployment=%s", deployment)
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    
    return resp.json()


def extract_chat_content(response: Dict[str, Any]) -> str:
    """Extract the content string from a chat completion response."""
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("No choices returned from Azure OpenAI")
    
    message = choices[0].get("message") or {}
    content = message.get("content")
    
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Empty content from Azure OpenAI")
    
    return content.strip()


def transcribe_audio(
    audio_data: bytes,
    audio_format: str = "webm",
    language: str = "en",
) -> str:
    """
    Transcribe audio using Azure OpenAI Whisper or realtime API.
    
    Args:
        audio_data: Raw audio bytes
        audio_format: Audio format (webm, wav, mp3, etc.)
        language: Language code
    
    Returns:
        Transcribed text
    """
    config = _get_config()
    _validate_config(config, "deployment_audio_realtime")
    
    deployment = config["deployment_audio_realtime"]
    
    # Use the transcription endpoint
    url = f"{config['endpoint']}/openai/deployments/{deployment}/audio/transcriptions?api-version={config['api_version']}"
    
    headers = {
        "api-key": config["api_key"],
    }
    
    files = {
        "file": (f"audio.{audio_format}", audio_data, f"audio/{audio_format}"),
    }
    
    data = {
        "language": language,
        "response_format": "text",
    }
    
    logging.info("openai_client: transcribing audio, size=%d bytes, format=%s", len(audio_data), audio_format)
    
    resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
    resp.raise_for_status()
    
    return resp.text.strip()


def generate_speech(
    text: str,
    voice: str = "alloy",
    speed: float = 1.0,
) -> bytes:
    """
    Generate speech audio from text using Azure OpenAI TTS.
    
    Args:
        text: Text to synthesize
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        speed: Speech speed (0.25 to 4.0)
    
    Returns:
        Audio bytes (MP3 format)
    """
    config = _get_config()
    _validate_config(config, "deployment_audio_realtime")
    
    deployment = config["deployment_audio_realtime"]
    
    url = f"{config['endpoint']}/openai/deployments/{deployment}/audio/speech?api-version={config['api_version']}"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": config["api_key"],
    }
    
    payload = {
        "model": deployment,
        "input": text,
        "voice": voice,
        "speed": speed,
        "response_format": "mp3",
    }
    
    logging.info("openai_client: generating speech, text_length=%d, voice=%s", len(text), voice)
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    
    return resp.content


def generate_conversation_response(
    user_message: str,
    persona_type: str,
    conversation_history: List[Dict[str, str]],
    session_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate a conversational response as the AI trainer persona.
    
    Args:
        user_message: The user's (trainee's) message
        persona_type: Customer persona type (Director, Relater, Socializer, Thinker)
        conversation_history: Previous messages in the conversation
        session_context: Optional session context (scenario, PULSE step, etc.)
    
    Returns:
        AI response text
    """
    system_prompt = f"""You are an AI customer in a sales training simulation for the PULSE Selling methodology.

You are playing the role of a **{persona_type}** customer persona based on the Platinum Rule behavioral styles:
- **Director**: Direct, results-oriented, impatient, values efficiency and bottom-line results
- **Relater**: Warm, patient, relationship-focused, values trust and personal connection
- **Socializer**: Enthusiastic, talkative, optimistic, values recognition and social interaction
- **Thinker**: Analytical, detail-oriented, cautious, values accuracy and logical reasoning

Stay in character as a {persona_type}. Respond naturally to the sales associate's approach.
- If they're doing well with PULSE methodology, be receptive but still present realistic challenges
- If they're struggling, present appropriate objections or concerns for your persona type
- Keep responses concise (1-3 sentences typically) to simulate natural conversation flow

Current context: {json.dumps(session_context or {}, ensure_ascii=False)}
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    
    response = chat_completion(
        messages=messages,
        deployment_key="deployment_core_chat",
        temperature=0.8,
        max_tokens=200,
    )
    
    return extract_chat_content(response)
