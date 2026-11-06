"""Configuration manager for GhostWriter AI."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path: Path = None) -> None:
        """Fallback .env loader when python-dotenv is not installed."""
        path = Path(dotenv_path) if dotenv_path else Path(".env")
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

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

# Supported Providers: "grok" (Prioritized) or "gemini"
DEFAULT_PROVIDER = os.getenv("AI_PROVIDER", "grok").lower()

GROK_MODELS = [
    "grok-4.7",
    "grok-4",
    "grok-3",
    "grok-2",
    "grok-2-1212",
    "grok-2-mini",
    "grok-2-latest",
    "grok-beta",
]
DEFAULT_GROK_MODEL = os.getenv("GROK_MODEL", "grok-4.7")

GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-pro-latest",
]
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

# Fallback alias for backward compatibility
DEFAULT_MODELS = GROK_MODELS if DEFAULT_PROVIDER == "grok" else GEMINI_MODELS
DEFAULT_MODEL = DEFAULT_GROK_MODEL if DEFAULT_PROVIDER == "grok" else DEFAULT_GEMINI_MODEL

DEFAULT_LANGUAGE = os.getenv("NOVEL_DEFAULT_LANGUAGE", "Indonesian")


def get_provider() -> str:
    """Retrieve current AI provider (grok or gemini)."""
    p = os.getenv("AI_PROVIDER", "grok").strip().lower()
    return "gemini" if p == "gemini" else "grok"


def get_api_key(provider: str = None) -> str:
    """Retrieve API key for given or active provider."""
    prov = (provider or get_provider()).lower()
    if prov == "grok":
        return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY", "")).strip()
    return os.getenv("GEMINI_API_KEY", "").strip()


def get_models_for_provider(provider: str = None) -> list:
    """List available model identifiers for the provider."""
    prov = (provider or get_provider()).lower()
    return GROK_MODELS if prov == "grok" else GEMINI_MODELS


def get_active_model(provider: str = None) -> str:
    """Retrieve active model name for the provider."""
    prov = (provider or get_provider()).lower()
    if prov == "grok":
        return os.getenv("GROK_MODEL", DEFAULT_GROK_MODEL).strip()
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()


def save_settings(
    provider: str,
    api_key: str,
    model: str,
    language: str = DEFAULT_LANGUAGE,
) -> None:
    """Save provider, API key, and model to .env file."""
    provider = provider.strip().lower()
    api_key = api_key.strip()
    model = model.strip()

    # Read existing keys to preserve the other provider's credentials
    grok_key = api_key if provider == "grok" else get_api_key("grok")
    grok_model = model if provider == "grok" else get_active_model("grok")
    gemini_key = api_key if provider == "gemini" else get_api_key("gemini")
    gemini_model = model if provider == "gemini" else get_active_model("gemini")

    env_lines = [
        f"AI_PROVIDER={provider}",
        f"GROK_API_KEY={grok_key}",
        f"GROK_MODEL={grok_model}",
        f"GEMINI_API_KEY={gemini_key}",
        f"GEMINI_MODEL={gemini_model}",
        f"NOVEL_DEFAULT_LANGUAGE={language}",
    ]
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")

    # Update in-memory environment
    os.environ["AI_PROVIDER"] = provider
    os.environ["GROK_API_KEY"] = grok_key
    os.environ["GROK_MODEL"] = grok_model
    os.environ["GEMINI_API_KEY"] = gemini_key
    os.environ["GEMINI_MODEL"] = gemini_model
    os.environ["NOVEL_DEFAULT_LANGUAGE"] = language


def save_api_key(api_key: str, model: str = None) -> None:
    """Legacy helper function: save to active provider."""
    prov = get_provider()
    m = model or get_active_model(prov)
    save_settings(provider=prov, api_key=api_key, model=m)
