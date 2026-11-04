"""LLM client interface supporting Google Gemini."""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Union

import config


def safe_log(message: str) -> None:
    """Safely log messages to avoid UnicodeEncodeError on Windows terminals."""
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
    if not api_key:
        return []
    import urllib.request
    import urllib.error
    url = "https://api.x.ai/v1/models"
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
        },
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            chat_models = []
            for item in data.get("data", []):
                mid = item.get("id", "")
                if mid and not any(term in mid.lower() for term in ["image", "embed", "tts"]):
                    chat_models.append(mid)
            if chat_models:
                return chat_models
    except Exception:
        pass
    return []


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
                self.available_models = config.GROK_MODELS
        else:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                try:
                    import google.generativeai as gai
                    gai.configure(api_key=self.api_key)
                    self._client = "legacy"
                except Exception:
                    self._client = "rest"

    def is_configured(self) -> bool:
        """Check if an API key is provided and client initialized."""
        return bool(self.api_key and self._client)

    def _execute_request(
        self,
        model_name: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        is_json: bool = False,
    ) -> str:
        """Execute a single generation request with a specific model."""
        if self.provider == "grok" or self._client == "grok_rest":
            import urllib.request
            import urllib.error
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
                },
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    choices = resp_data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "") or ""
                    return ""
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"xAI Grok API Error ({e.code}): {err_body}")

        elif self._client == "rest":
            import urllib.request
            import urllib.error
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            gen_config: Dict[str, Any] = {
                "temperature": temperature,
                "maxOutputTokens": 8192,
            }
            if is_json:
                gen_config["responseMimeType"] = "application/json"

            payload: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": gen_config,
            }
            if system_instruction:
                payload["system_instruction"] = {
                    "parts": [{"text": system_instruction}]
                }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        candidate = candidates[0]
                        finish_reason = candidate.get("finishReason")
                        if finish_reason == "SAFETY":
                            raise RuntimeError("Respons terblokir oleh Google Safety Filter.")
                        parts = candidate.get("content", {}).get("parts", [])
                        # Concatenate all text parts (filter out thoughts if any)
                        full_text = "".join(
                            p.get("text", "") for p in parts
                            if "text" in p and not p.get("thought", False)
                        )
                        if not full_text:
                            full_text = "".join(p.get("text", "") for p in parts if "text" in p)
                        return full_text
                    return ""
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Gemini API Error ({e.code}): {err_body}")

        elif self._client == "legacy":
            import google.generativeai as gai
            model_instance = gai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction,
            )
            gen_cfg: Dict[str, Any] = {"temperature": temperature}
            if is_json:
                gen_cfg["response_mime_type"] = "application/json"
            response = model_instance.generate_content(
                prompt,
                generation_config=gen_cfg,
            )
            return response.text or ""
        else:
            from google.genai import types
            cfg_kwargs: Dict[str, Any] = {"temperature": temperature}
            if is_json:
                cfg_kwargs["response_mime_type"] = "application/json"
            if system_instruction:
                cfg_kwargs["system_instruction"] = system_instruction
            cfg = types.GenerateContentConfig(**cfg_kwargs)

            response = self._client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=cfg,
            )
            return response.text or ""

    def _is_overload_error(self, error: Exception) -> bool:
        """Check if error is due to server overload (503, high demand, unavailable, 429 rate limit)."""
        err_str = str(error).lower()
        return any(term in err_str for term in [
            "503", "429", "too many requests", "rate limit",
            "unavailable", "high demand", "temporarily", "overloaded",
            "resource_exhausted", "quota"
        ])

    def _is_model_unavailable_error(self, error: Exception) -> bool:
        """Check if error indicates the model is not found, deprecated, or invalid."""
        err_str = str(error).lower()
        return any(term in err_str for term in [
            "404", "not_found", "no longer available", "not found",
            "is not supported", "invalid model", "does not exist"
        ])

    def _is_auth_error(self, error: Exception) -> bool:
        """Check if error is due to invalid API key or permission denied."""
        err_str = str(error).lower()
        return any(term in err_str for term in [
            "401", "unauthenticated", "invalid api key", "api_key_invalid", "403", "permission_denied",
            "incorrect api key", "unauthorized", "invalid_api_key"
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
                    return self._execute_request(
                        model_name=current_model,
                        prompt=prompt,
                        system_instruction=system_instruction,
                        temperature=temperature,
                        is_json=is_json,
                    )
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
                            safe_log(f"[GhostWriter] Model {current_model} sedang sibuk / rate-limited. Mencoba kembali dalam {wait_seconds}s...")
                            time.sleep(wait_seconds)
                        else:
                            safe_log(f"[GhostWriter] Model {current_model} masih sibuk. Mengalihkan ke model alternatif berikutnya...")
                            break
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(1.5 ** attempt)
                        else:
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

        # 0. Clean common JSON issues: remove JS/C++ comments
        cleaned = re.sub(r"//.*?\n", "\n", cleaned)
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
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            candidates.append((start_obj, end_obj + 1))
        if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            candidates.append((start_arr, end_arr + 1))

        candidates.sort(key=lambda x: x[0])

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
            # If unterminated string quote, close it
            num_quotes = len(re.findall(r'(?<!\\)"', partial))
            if num_quotes % 2 != 0:
                partial += '"'
            partial = re.sub(r",\s*$", "", partial.strip())
            open_braces = partial.count("{") - partial.count("}")
            open_brackets = partial.count("[") - partial.count("]")
            repaired = partial + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
            repaired_cleaned = re.sub(r",\s*([\]}])", r"\1", repaired)
            try:
                return json.loads(repaired_cleaned, strict=False)
            except Exception:
                pass

        raise ValueError(f"Tidak dapat mem-parsing respons menjadi JSON yang valid:\n{text[:300]}...")
