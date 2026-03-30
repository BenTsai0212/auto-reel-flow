import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

LLM_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
NATURALNESS_THRESHOLD = 70
