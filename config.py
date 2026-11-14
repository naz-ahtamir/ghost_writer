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

# Supported Providers: "grok", "openrouter", or "gemini"
SUPPORTED_PROVIDERS = ("grok", "openrouter", "gemini")
DEFAULT_PROVIDER = os.getenv("AI_PROVIDER", "grok").lower()

GROK_MODELS = [
    "grok-3",
    "grok-3-mini",
    "grok-2-latest",
    "grok-2-1212",
    "grok-2",
    "grok-beta",
]
DEFAULT_GROK_MODEL = os.getenv("GROK_MODEL", "grok-3")
DEFAULT_GROK_REASONING_EFFORT = os.getenv("GROK_REASONING_EFFORT", "low").strip().lower()
GROK_TOKEN_CONTEXT_LIMIT = int(os.getenv("GROK_TOKEN_CONTEXT_LIMIT", "200000"))
GROK_TOKEN_WARN_THRESHOLD = int(os.getenv("GROK_TOKEN_WARN_THRESHOLD", "160000"))

OPENROUTER_MODELS = [
    "nousresearch/hermes-4-405b",
    "deepseek/deepseek-chat-v3-0324",
    "mistralai/mistral-large-2512",
    "sao10k/l3.1-euryale-70b",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition",
]
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-4-405b")

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-pro",
    "gemini-pro-latest",
]
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Fallback alias for backward compatibility
_PROVIDER_MODEL_MAP = {
    "grok": (GROK_MODELS, DEFAULT_GROK_MODEL),
    "openrouter": (OPENROUTER_MODELS, DEFAULT_OPENROUTER_MODEL),
    "gemini": (GEMINI_MODELS, DEFAULT_GEMINI_MODEL),
}
DEFAULT_MODELS, DEFAULT_MODEL = _PROVIDER_MODEL_MAP.get(DEFAULT_PROVIDER, (GROK_MODELS, DEFAULT_GROK_MODEL))

DEFAULT_LANGUAGE = os.getenv("NOVEL_DEFAULT_LANGUAGE", "Indonesian")

# Illustration / Image Generation Settings
ILLUSTRATIONS_PER_CHAPTER = int(os.getenv("ILLUSTRATIONS_PER_CHAPTER", "3"))
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "1280"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "720"))

IMAGE_PROVIDERS = ["pollinations", "grok", "gemini", "local_sd"]
DEFAULT_IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "pollinations").strip().lower()

POLLINATIONS_IMAGE_MODELS = [
    "flux-realism",
    "flux",
    "flux-pro",
    "flux-cablyai",
    "turbo",
]
GROK_IMAGE_MODELS = [
    "grok-2-image",
    "grok-2-image-1212",
]
GEMINI_IMAGE_MODELS = [
    "imagen-3.0-generate-002",
    "gemini-2.0-flash-exp-image-generation",
]
LOCAL_SD_IMAGE_MODELS = [
    "sdxl-realism-uncensored",
]

DEFAULT_IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux-realism").strip()
DEFAULT_SD_API_URL = os.getenv("SD_API_URL", "http://127.0.0.1:7860").strip()


def get_image_provider() -> str:
    """Retrieve active image generation provider."""
    p = os.getenv("IMAGE_PROVIDER", DEFAULT_IMAGE_PROVIDER).strip().lower()
    return p if p in IMAGE_PROVIDERS else "pollinations"


def get_image_models_for_provider(provider: str = None) -> list:
    """Return available image models for given image provider."""
    prov = (provider or get_image_provider()).lower()
    if prov == "grok":
        return GROK_IMAGE_MODELS
    if prov == "gemini":
        return GEMINI_IMAGE_MODELS
    if prov == "local_sd":
        return LOCAL_SD_IMAGE_MODELS
    return POLLINATIONS_IMAGE_MODELS


def get_image_model(provider: str = None) -> str:
    """Retrieve active image model name."""
    prov = (provider or get_image_provider()).lower()
    models = get_image_models_for_provider(prov)
    current = os.getenv("IMAGE_MODEL", "").strip()
    if current and current in models:
        return current
    return models[0]


def get_sd_api_url() -> str:
    """Retrieve local Stable Diffusion / Forge WebUI URL."""
    return os.getenv("SD_API_URL", DEFAULT_SD_API_URL).strip()


def get_provider() -> str:
    """Retrieve current AI provider (grok, openrouter, or gemini)."""
    p = os.getenv("AI_PROVIDER", "grok").strip().lower()
    return p if p in SUPPORTED_PROVIDERS else "grok"


def get_api_key(provider: str = None) -> str:
    """Retrieve API key for given or active provider."""
    prov = (provider or get_provider()).lower()
    if prov == "grok":
        return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY", "")).strip()
    if prov == "openrouter":
        return os.getenv("OPENROUTER_API_KEY", "").strip()
    return os.getenv("GEMINI_API_KEY", "").strip()


def get_models_for_provider(provider: str = None) -> list:
    """List available model identifiers for the provider."""
    prov = (provider or get_provider()).lower()
    return _PROVIDER_MODEL_MAP.get(prov, (GEMINI_MODELS, DEFAULT_GEMINI_MODEL))[0]


def get_active_model(provider: str = None) -> str:
    """Retrieve active model name for the provider."""
    prov = (provider or get_provider()).lower()
    if prov == "grok":
        return os.getenv("GROK_MODEL", DEFAULT_GROK_MODEL).strip()
    if prov == "openrouter":
        return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip()
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()


def get_grok_reasoning_effort() -> str:
    """Retrieve active xAI Grok reasoning effort level ('low', 'medium', 'high', 'xhigh')."""
    effort = os.getenv("GROK_REASONING_EFFORT", DEFAULT_GROK_REASONING_EFFORT).strip().lower()
    return effort if effort in ("low", "medium", "high", "xhigh") else "low"


def save_settings(
    provider: str,
    api_key: str,
    model: str,
    language: str = DEFAULT_LANGUAGE,
    grok_reasoning_effort: str = None,
) -> None:
    """Save provider, API key, model, and reasoning effort to .env file."""
    provider = provider.strip().lower()
    api_key = api_key.strip()
    model = model.strip()

    # Read existing keys to preserve the other provider's credentials
    grok_key = api_key if provider == "grok" else get_api_key("grok")
    grok_model = model if provider == "grok" else get_active_model("grok")
    effort = (grok_reasoning_effort or get_grok_reasoning_effort()).strip().lower()
    openrouter_key = api_key if provider == "openrouter" else get_api_key("openrouter")
    openrouter_model = model if provider == "openrouter" else get_active_model("openrouter")
    gemini_key = api_key if provider == "gemini" else get_api_key("gemini")
    gemini_model = model if provider == "gemini" else get_active_model("gemini")
    img_prov = get_image_provider()
    img_model = get_image_model(img_prov)
    sd_url = get_sd_api_url()

    env_lines = [
        f"AI_PROVIDER={provider}",
        f"GROK_API_KEY={grok_key}",
        f"GROK_MODEL={grok_model}",
        f"GROK_REASONING_EFFORT={effort}",
        f"OPENROUTER_API_KEY={openrouter_key}",
        f"OPENROUTER_MODEL={openrouter_model}",
        f"GEMINI_API_KEY={gemini_key}",
        f"GEMINI_MODEL={gemini_model}",
        f"NOVEL_DEFAULT_LANGUAGE={language}",
        f"IMAGE_PROVIDER={img_prov}",
        f"IMAGE_MODEL={img_model}",
        f"SD_API_URL={sd_url}",
    ]
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")

    # Update in-memory environment
    os.environ["AI_PROVIDER"] = provider
    os.environ["GROK_API_KEY"] = grok_key
    os.environ["GROK_MODEL"] = grok_model
    os.environ["GROK_REASONING_EFFORT"] = effort
    os.environ["OPENROUTER_API_KEY"] = openrouter_key
    os.environ["OPENROUTER_MODEL"] = openrouter_model
    os.environ["GEMINI_API_KEY"] = gemini_key
    os.environ["GEMINI_MODEL"] = gemini_model
    os.environ["NOVEL_DEFAULT_LANGUAGE"] = language


def save_grok_reasoning_effort(effort: str) -> None:
    """Update and persist xAI Grok reasoning effort."""
    valid_effort = effort.strip().lower()
    if valid_effort not in ("low", "medium", "high", "xhigh"):
        valid_effort = "low"
    active_prov = get_provider()
    save_settings(
        provider=active_prov,
        api_key=get_api_key(active_prov),
        model=get_active_model(active_prov),
        grok_reasoning_effort=valid_effort,
    )


def save_image_settings(
    image_provider: str,
    image_model: str = None,
    sd_api_url: str = None,
) -> None:
    """Save illustration engine settings to .env and environment."""
    prov = image_provider.strip().lower()
    if prov not in IMAGE_PROVIDERS:
        prov = "pollinations"
    model = (image_model or get_image_model(prov)).strip()
    url = (sd_api_url or get_sd_api_url()).strip()

    os.environ["IMAGE_PROVIDER"] = prov
    os.environ["IMAGE_MODEL"] = model
    os.environ["SD_API_URL"] = url

    # Persist to .env alongside LLM settings
    active_llm_prov = get_provider()
    save_settings(
        provider=active_llm_prov,
        api_key=get_api_key(active_llm_prov),
        model=get_active_model(active_llm_prov),
    )


def save_api_key(api_key: str, model: str = None) -> None:
    """Legacy helper function: save to active provider."""
    prov = get_provider()
    m = model or get_active_model(prov)
    save_settings(provider=prov, api_key=api_key, model=m)
