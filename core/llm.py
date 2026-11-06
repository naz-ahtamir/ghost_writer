"""LLM client interface supporting xAI Grok and Google Gemini."""

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Union

import config


def _create_ssl_context() -> ssl.SSLContext:
    """Create an SSL context resilient to OpenSSL 3.x unexpected EOF errors on mobile/Termux."""
    ctx = ssl.create_default_context()
    if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
    return ctx


def safe_log(message: str) -> None:
    """Safely log messages to avoid UnicodeEncodeError on Windows/mobile terminals."""
    try:
        from cli.ui import console
        console.print(f"[dim yellow]{message}[/dim yellow]")
    except Exception:
        try:
            print(message.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass


def fetch_available_grok_models(api_key: str) -> List[str]:
    """Dynamically query xAI API for available chat models on this account."""
    if not api_key or api_key.startswith("xai-test") or api_key.startswith("fake"):
        return []
    url = "https://api.x.ai/v1/models"
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
            "Connection": "close",
        },
        method="GET",
    )
    try:
        ctx = _create_ssl_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            chat_models = []
            for item in data.get("data", []):
                mid = item.get("id", "")
                if mid and not any(term in mid.lower() for term in ["image", "embed", "tts", "vision"]):
                    chat_models.append(mid)
            if chat_models:
                # Prioritize preferred models if available
                ordered = [m for m in config.GROK_MODELS if m in chat_models]
                for m in chat_models:
                    if m not in ordered:
                        ordered.append(m)
                return ordered
    except Exception:
        pass
    return []


def fetch_available_gemini_models(api_key: str) -> List[str]:
    """Dynamically query Google Gemini API for available text generation models."""
    if not api_key or not api_key.strip().startswith("AIza"):
        return []
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "Connection": "close",
        },
        method="GET",
    )
    try:
        ctx = _create_ssl_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            live_models = []
            excluded_terms = (
                "embedding", "imagen", "veo", "tts", "aqa", "bisheng",
                "learnlm", "robotics", "computer-use", "audio", "vision",
                "thinking", "image",
            )
            for item in data.get("models", []):
                methods = item.get("supportedGenerationMethods", [])
                if "generateContent" not in methods:
                    continue
                mid = item.get("name", "").replace("models/", "")
                if mid.startswith("gemini-") and not any(t in mid.lower() for t in excluded_terms):
                    live_models.append(mid)
            if live_models:
                ordered = [m for m in config.GEMINI_MODELS if m in live_models]
                for m in live_models:
                    if m not in ordered:
                        ordered.append(m)
                return ordered
    except Exception:
        pass
    return []


GEMINI_CORE_SAFETY_CATEGORIES = [
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
]

GEMINI_SAFETY_CATEGORIES = GEMINI_CORE_SAFETY_CATEGORIES

REFUSAL_PREFIXES = (
    "maaf, saya tidak dapat",
    "maaf, saya tidak bisa",
    "maaf, sebagai ai",
    "sebagai ai,",
    "sebagai model bahasa",
    "saya tidak dapat memenuhi",
    "saya tidak bisa memenuhi",
    "saya tidak dapat menulis",
    "saya tidak bisa menulis",
    "i cannot fulfill",
    "i can't fulfill",
    "i'm sorry, but i cannot",
    "i'm sorry, i cannot",
    "i'm sorry, i can't",
    "i am sorry, i cannot",
    "as an ai",
    "as a language model",
)


class LLMClient:
    """Unified client supporting xAI Grok (Prioritized) and Google Gemini."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        self.provider = (provider or config.get_provider()).lower()
        self.api_key = api_key or config.get_api_key(self.provider)
        self.model = model or config.get_active_model(self.provider)
        self._client = None
        self.available_models: List[str] = []
        self._init_client()

    def set_provider(self, provider: str, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        """Switch AI provider (grok or gemini) and reinitialize."""
        self.provider = provider.lower()
        self.api_key = api_key or config.get_api_key(self.provider)
        self.model = model or config.get_active_model(self.provider)
        self._init_client()

    def set_api_key(self, api_key: str, model: Optional[str] = None) -> None:
        """Update API key and reinitialize."""
        self.api_key = api_key.strip()
        if model:
            self.model = model
        self._init_client()

    def _init_client(self) -> None:
        """Initialize provider client and auto-detect models."""
        # Sanitize legacy invalid model names that might be stored in .env
        invalid_legacy = {
            "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.7-flash", "grok-4.7", "grok-4"
        }
        if self.model in invalid_legacy:
            self.model = (
                config.DEFAULT_GROK_MODEL if self.provider == "grok" else config.DEFAULT_GEMINI_MODEL
            )

        if not self.api_key:
            self._client = None
            return

        if self.provider == "grok":
            self._client = "grok_rest"
            live = fetch_available_grok_models(self.api_key)
            if live:
                self.available_models = live
                if self.model not in live:
                    self.model = live[0]
            else:
                self.available_models = list(config.GROK_MODELS)
                if self.model not in self.available_models:
                    self.model = self.available_models[0]
        else:
            self._client = "rest"
            live = fetch_available_gemini_models(self.api_key)
            if live:
                self.available_models = live
                if self.model not in live:
                    self.model = live[0]
            else:
                self.available_models = list(config.GEMINI_MODELS)
                if self.model not in self.available_models:
                    self.model = self.available_models[0]

    def is_configured(self) -> bool:
        """Check if an API key is provided and client initialized."""
        return bool(self.api_key and self._client)

    @staticmethod
    def _is_refusal_response(text: str) -> bool:
        """Detect if the model returned a refusal instead of fulfilling the prompt."""
        if not text or not text.strip():
            return True
        lowered = text.strip().lower()
        lowered_clean = re.sub(r"^[\*\#\-\s]+", "", lowered)
        if any(lowered_clean.startswith(prefix) for prefix in REFUSAL_PREFIXES):
            return True
        if len(lowered_clean) < 280 and any(
            phrase in lowered_clean
            for phrase in (
                "tidak dapat memenuhi permintaan",
                "tidak bisa menulis adegan",
                "melanggar kebijakan",
                "pedoman keamanan",
                "konten dewasa atau eksplisit",
                "cannot fulfill this request",
                "against my safety guidelines",
            )
        ):
            return True
        return False

    def _execute_request(
        self,
        model_name: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        is_json: bool = False,
    ) -> str:
        """Execute a single generation request with a specific model."""
        ctx = _create_ssl_context()

        if self.provider == "grok" or self._client == "grok_rest":
            url = "https://api.x.ai/v1/chat/completions"
            messages: List[Dict[str, str]] = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }
            if is_json:
                payload["response_format"] = {"type": "json_object"}

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "Connection": "close",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    choices = resp_data.get("choices", [])
                    if choices and "message" in choices[0]:
                        content = choices[0]["message"].get("content", "") or ""
                        if self._is_refusal_response(content):
                            raise RuntimeError(f"Model menolak respons: {content[:120]}")
                        return content
                    raise RuntimeError("Respons dari Grok kosong.")
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"xAI Grok API Error ({e.code}): {err_body}")

        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            gen_config: Dict[str, Any] = {
                "temperature": temperature,
                "maxOutputTokens": 8192,
            }
            if is_json:
                gen_config["responseMimeType"] = "application/json"

            contents_list: List[Dict[str, Any]] = [
                {"role": "user", "parts": [{"text": prompt}]}
            ]

            # Try OFF first (Gemini 2.0/2.5), then BLOCK_NONE, then default (no safetySettings) if 400
            safety_configs_to_try: List[Optional[List[Dict[str, str]]]] = [
                [{"category": cat, "threshold": "OFF"} for cat in GEMINI_CORE_SAFETY_CATEGORIES],
                [{"category": cat, "threshold": "BLOCK_NONE"} for cat in GEMINI_CORE_SAFETY_CATEGORIES],
                None,
            ]

            last_http_err = None
            for safety_cfg in safety_configs_to_try:
                payload = {
                    "contents": contents_list,
                    "generationConfig": gen_config,
                }
                if safety_cfg is not None:
                    payload["safetySettings"] = safety_cfg
                if system_instruction:
                    payload["system_instruction"] = {
                        "parts": [{"text": system_instruction}]
                    }

                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Connection": "close",
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                        resp_data = json.loads(resp.read().decode("utf-8"))
                        candidates = resp_data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            candidate = candidates[0]
                            parts = candidate.get("content", {}).get("parts", [])
                            full_text = "".join(
                                p.get("text", "") for p in parts
                                if "text" in p and not p.get("thought", False)
                            )
                            if not full_text:
                                full_text = "".join(p.get("text", "") for p in parts if "text" in p)
                            if full_text and not self._is_refusal_response(full_text):
                                return full_text
                        block_reason = (
                            resp_data.get("promptFeedback", {}).get("blockReason")
                            or (candidates[0].get("finishReason") if candidates else "EMPTY")
                        )
                        raise RuntimeError(f"Respons Gemini tidak menghasilkan teks ({block_reason}).")
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", errors="replace")
                    last_http_err = f"Gemini API Error ({e.code}): {err_body}"
                    if e.code == 400 and safety_cfg is not None:
                        continue
                    raise RuntimeError(last_http_err)
            raise RuntimeError(last_http_err or "Gagal memanggil Gemini REST API.")

    def _is_overload_error(self, error: Exception) -> bool:
        """Check if error is due to server overload (503, high demand, unavailable, 429 rate limit)."""
        err_str = str(error).lower()
        return any(term in err_str for term in [
            "503", "429", "too many requests", "rate limit",
            "unavailable", "high demand", "temporarily", "overloaded",
            "resource_exhausted", "quota", "eof occurred", "unexpected eof",
            "connection reset", "timed out", "timeout",
        ])

    def _is_model_unavailable_error(self, error: Exception) -> bool:
        """Check if error indicates the model is not found, deprecated, or invalid."""
        err_str = str(error).lower()
        return any(term in err_str for term in [
            "404", "not_found", "no longer available", "not found",
            "is not supported", "invalid model", "does not exist",
        ])

    def _is_auth_error(self, error: Exception) -> bool:
        """Check if error is due to invalid API key or permission denied."""
        err_str = str(error).lower()
        return any(term in err_str for term in [
            "401", "unauthenticated", "invalid api key", "api_key_invalid", "403", "permission_denied",
            "incorrect api key", "unauthorized", "invalid_api_key",
        ])

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
        is_json: bool = False,
    ) -> str:
        """Generate text using active provider with automatic retry and model fallback."""
        prov_label = "xAI Grok" if self.provider == "grok" else "Google Gemini"
        if not self.is_configured():
            raise ValueError(
                f"{prov_label} API Key belum diset! Silakan masukkan API Key Anda di menu Pengaturan atau file .env."
            )

        # Build list of fallback models for active provider
        models_to_try = [self.model]
        provider_models = getattr(self, "available_models", None) or config.get_models_for_provider(self.provider)
        for candidate in provider_models:
            if candidate not in models_to_try:
                models_to_try.append(candidate)

        last_error = None

        for model_idx, current_model in enumerate(models_to_try):
            if model_idx > 0:
                safe_log(f"[GhostWriter] Beralih ke model cadangan {prov_label}: {current_model}...")

            for attempt in range(max_retries):
                try:
                    # On final retry if previous attempt had a block, use minimal system instruction
                    active_sys = system_instruction if attempt < max_retries - 1 else None
                    active_prompt = (
                        prompt
                        if active_sys is not None or not system_instruction
                        else f"{system_instruction}\n\n{prompt}"
                    )
                    result = self._execute_request(
                        model_name=current_model,
                        prompt=active_prompt,
                        system_instruction=active_sys,
                        temperature=temperature,
                        is_json=is_json,
                    )
                    # Remember working model so subsequent calls don't repeat failed models
                    self.model = current_model
                    return result
                except Exception as e:
                    last_error = e

                    if self._is_auth_error(e):
                        if self.provider == "grok":
                            raise ValueError(
                                f"xAI Grok API Key tidak valid atau akun belum memiliki saldo kredit aktif.\n"
                                f"Pesan dari xAI: {e}\n"
                                f"💡 Tips: API key Grok harus dibuat di https://console.x.ai dan membutuhkan saldo kredit (bukan langganan X Premium biasa).\n"
                                f"Jika ingin menggunakan AI gratis, silakan beralih kembali ke Google Gemini di Menu 8."
                            )
                        else:
                            raise ValueError(f"Google Gemini API Key tidak valid atau tidak memiliki akses: {e}")

                    if self._is_model_unavailable_error(e):
                        safe_log(f"[GhostWriter] Model '{current_model}' tidak tersedia (404/Deprecated). Mencoba model lain...")
                        break

                    if self._is_overload_error(e):
                        if attempt < 2:
                            wait_seconds = 3 * (attempt + 1)
                            safe_log(f"[GhostWriter] Model {current_model} sedang sibuk / terkendala jaringan. Mencoba kembali dalam {wait_seconds}s...")
                            time.sleep(wait_seconds)
                        else:
                            safe_log(f"[GhostWriter] Model {current_model} masih sibuk. Mengalihkan ke model alternatif berikutnya...")
                            break
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(1.5 ** attempt)
                        else:
                            safe_log(f"[GhostWriter] Kendala pada model {current_model}: {e}")
                            break

        raise RuntimeError(
            f"Gagal memanggil {prov_label} setelah mencoba model {models_to_try}. "
            f"Penyebab terakhir: {last_error}"
        )

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.5,
    ) -> Union[Dict[str, Any], List[Any]]:
        """Generate content and parse response as JSON."""
        full_prompt = (
            f"{prompt}\n\n"
            "PENTING: Berikan HANYA format JSON murni yang valid tanpa teks pembuka atau penutup. "
            "Jangan gunakan kutipan atau komentar di luar struktur JSON."
        )
        response_text = self.generate(
            prompt=full_prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            is_json=True,
        )
        return self.extract_json(response_text)

    @staticmethod
    def extract_json(text: str) -> Union[Dict[str, Any], List[Any]]:
        """Extract and parse JSON from text that might contain markdown fences or surrounding comments."""
        if not text or not text.strip():
            raise ValueError("Respons dari LLM kosong.")

        cleaned = text.strip()

        # 0. Clean common JSON issues: remove standalone JS/C++ line comments and block comments
        cleaned = re.sub(r"(?m)^\s*//.*$", "", cleaned)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

        # 1. First attempt: Look for ```json ... ``` code fences anywhere in text
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            candidate = fence_match.group(1).strip()
            candidate_cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                return json.loads(candidate_cleaned, strict=False)
            except Exception:
                pass

        # 2. Direct parse attempt after stripping outer fences if any
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        stripped = re.sub(r"\n?```$", "", stripped).strip()
        stripped_cleaned = re.sub(r",\s*([\]}])", r"\1", stripped)
        try:
            return json.loads(stripped_cleaned, strict=False)
        except Exception:
            pass

        # 3. Search for outermost {...} or [...]
        start_obj = cleaned.find("{")
        end_obj = cleaned.rfind("}")
        start_arr = cleaned.find("[")
        end_arr = cleaned.rfind("]")

        candidates = []
        if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
            if end_arr != -1 and end_arr > start_arr:
                candidates.append((start_arr, end_arr + 1))
        elif start_obj != -1:
            if end_obj != -1 and end_obj > start_obj:
                candidates.append((start_obj, end_obj + 1))

        for start, end in candidates:
            snippet = cleaned[start:end]
            snippet_cleaned = re.sub(r",\s*([\]}])", r"\1", snippet)
            try:
                return json.loads(snippet_cleaned, strict=False)
            except Exception:
                pass

        # 4. Repair incomplete / cut-off JSON (e.g. unclosed brackets/braces/quotes)
        first_open = -1
        if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
            first_open = start_obj
        elif start_arr != -1:
            first_open = start_arr

        if first_open != -1:
            partial = cleaned[first_open:]
            in_string = False
            escape = False
            stack: List[str] = []
            for ch in partial:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if ch in ("{", "["):
                        stack.append(ch)
                    elif ch == "}" and stack and stack[-1] == "{":
                        stack.pop()
                    elif ch == "]" and stack and stack[-1] == "[":
                        stack.pop()

            if in_string:
                partial += '"'
            partial = re.sub(r",\s*$", "", partial.strip())
            closers = "".join("}" if opener == "{" else "]" for opener in reversed(stack))
            repaired = partial + closers
            repaired_cleaned = re.sub(r",\s*([\]}])", r"\1", repaired)
            try:
                return json.loads(repaired_cleaned, strict=False)
            except Exception:
                pass

        raise ValueError(f"Tidak dapat mem-parsing respons menjadi JSON yang valid:\n{text[:300]}...")
