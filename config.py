import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_FALLBACK_MODEL = "openai/gpt-oss-20b"

CREDENTIALS_FILE = BASE_DIR / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = BASE_DIR / os.getenv("GMAIL_TOKEN_FILE", "token.json")

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

AUTO_REPLY_AUTO_SEND = os.getenv("AUTO_REPLY_AUTO_SEND", "false").lower() in ("true", "1", "yes")
DEFAULT_REPLY_TONE = os.getenv("DEFAULT_REPLY_TONE", "professional")

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
