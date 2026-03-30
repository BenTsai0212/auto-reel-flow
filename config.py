import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel（預設）
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

LLM_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
NATURALNESS_THRESHOLD = 70

# MVP-2: Audio Pipeline
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # "base" 或 "small"
