"""Application configuration."""

import os
from pathlib import Path

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/computer_use.db")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# API
API_KEY_FILE = Path("~/.anthropic/api_key").expanduser()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# VNC / noVNC
VNC_HOST = os.getenv("VNC_HOST", "localhost")
VNC_PORT = int(os.getenv("VNC_PORT", "5900"))
NOVNC_PORT = int(os.getenv("NOVNC_PORT", "6080"))
NOVNC_PATH = os.getenv("NOVNC_PATH", "/opt/noVNC")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Agent defaults
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MAX_TOKENS = 16384
DEFAULT_TOOL_VERSION = "computer_use_20251124"

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
