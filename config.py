"""Configuration manager for GhostWriter AI."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

# Load existing environment variables
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

DEFAULT_MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-pro-latest",
]

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
DEFAULT_LANGUAGE = os.getenv("NOVEL_DEFAULT_LANGUAGE", "Indonesian")


def get_api_key() -> str:
    """Retrieve Gemini API key from environment."""
    return os.getenv("GEMINI_API_KEY", "").strip()


def save_api_key(api_key: str, model: str = DEFAULT_MODEL) -> None:
    """Save API key and model to .env file."""
    api_key = api_key.strip()
    env_content = f"GEMINI_API_KEY={api_key}\nGEMINI_MODEL={model}\nNOVEL_DEFAULT_LANGUAGE={DEFAULT_LANGUAGE}\n"
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(env_content)
    # Update current process environment
    os.environ["GEMINI_API_KEY"] = api_key
    os.environ["GEMINI_MODEL"] = model
