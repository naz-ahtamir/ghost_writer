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


class LLMClient:
    """Unified client for interacting with Google Gemini models."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or config.get_api_key()
        self.model = model or config.DEFAULT_MODEL
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Google GenAI client."""
        if not self.api_key:
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        except Exception:
            # Fallback to google-generativeai if genai fails
            try:
                import google.generativeai as gai
                gai.configure(api_key=self.api_key)
                self._client = "legacy"
            except Exception:
                # Direct REST API fallback via Python standard library (zero pip dependencies required)
                self._client = "rest"

    def is_configured(self) -> bool:
        """Check if an API key is provided and client initialized."""
        return bool(self.api_key and self._client)

    def set_api_key(self, api_key: str, model: Optional[str] = None) -> None:
        """Update API key and reinitialize."""
        self.api_key = api_key.strip()
        if model:
            self.model = model
        self._init_client()

    def _execute_request(
        self,
        model_name: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Execute a single generation request with a specific model."""
        if self._client == "rest":
            import urllib.request
            import urllib.error
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            payload: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 8192,
                }
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
            response = model_instance.generate_content(
                prompt,
                generation_config={"temperature": temperature},
            )
            return response.text or ""
        else:
            from google.genai import types
            cfg = types.GenerateContentConfig(
                temperature=temperature,
            )
            if system_instruction:
                cfg.system_instruction = system_instruction

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
            "401", "unauthenticated", "invalid api key", "api_key_invalid", "403", "permission_denied"
        ])

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> str:
        """Generate text using Gemini with automatic retry and model fallback."""
        if not self.is_configured():
            raise ValueError(
                "Gemini API Key belum diset! Silakan masukkan API Key Anda di menu Pengaturan atau file .env."
            )

        # Build list of fallback models
        models_to_try = [self.model]
        for candidate in config.DEFAULT_MODELS:
            if candidate not in models_to_try:
                models_to_try.append(candidate)

        last_error = None

        for model_idx, current_model in enumerate(models_to_try):
            if model_idx > 0:
                safe_log(f"[GhostWriter] Beralih ke model cadangan: {current_model}...")

            for attempt in range(max_retries):
                try:
                    return self._execute_request(
                        model_name=current_model,
                        prompt=prompt,
                        system_instruction=system_instruction,
                        temperature=temperature,
                    )
                except Exception as e:
                    last_error = e

                    if self._is_auth_error(e):
                        raise ValueError(f"Gemini API Key tidak valid atau tidak memiliki akses: {e}")

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
            f"Gagal memanggil Gemini setelah mencoba model {models_to_try}. "
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
        )
        return self.extract_json(response_text)

    @staticmethod
    def extract_json(text: str) -> Union[Dict[str, Any], List[Any]]:
        """Extract and parse JSON from text that might contain markdown fences or surrounding comments."""
        if not text or not text.strip():
            raise ValueError("Respons dari LLM kosong.")

        cleaned = text.strip()

        # 1. First attempt: Look for ```json ... ``` code fences anywhere in text
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            candidate = fence_match.group(1).strip()
            # Clean trailing commas before closing braces/brackets
            candidate_cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                return json.loads(candidate_cleaned)
            except json.JSONDecodeError:
                pass

        # 2. Direct parse attempt after stripping outer fences if any
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        stripped = re.sub(r"\n?```$", "", stripped).strip()
        stripped_cleaned = re.sub(r",\s*([\]}])", r"\1", stripped)
        try:
            return json.loads(stripped_cleaned)
        except json.JSONDecodeError:
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
                return json.loads(snippet_cleaned)
            except json.JSONDecodeError:
                pass

        # 4. Repair incomplete / cut-off JSON (e.g. unclosed brackets/braces)
        first_open = -1
        if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
            first_open = start_obj
        elif start_arr != -1:
            first_open = start_arr

        if first_open != -1:
            partial = cleaned[first_open:]
            partial = re.sub(r",\s*$", "", partial.strip())
            open_braces = partial.count("{") - partial.count("}")
            open_brackets = partial.count("[") - partial.count("]")
            repaired = partial + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
            repaired_cleaned = re.sub(r",\s*([\]}])", r"\1", repaired)
            try:
                return json.loads(repaired_cleaned)
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Tidak dapat mem-parsing respons menjadi JSON yang valid:\n{text[:300]}...")
