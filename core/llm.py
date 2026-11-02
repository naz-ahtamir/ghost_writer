"""LLM client interface supporting Google Gemini."""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Union

import config


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
        except Exception as e:
            # Fallback to google-generativeai if genai fails
            try:
                import google.generativeai as gai
                gai.configure(api_key=self.api_key)
                self._client = "legacy"
            except Exception as e2:
                self._client = None

    def is_configured(self) -> bool:
        """Check if an API key is provided and client initialized."""
        return bool(self.api_key and self._client)

    def set_api_key(self, api_key: str, model: Optional[str] = None) -> None:
        """Update API key and reinitialize."""
        self.api_key = api_key.strip()
        if model:
            self.model = model
        self._init_client()

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> str:
        """Generate text using Gemini."""
        if not self.is_configured():
            raise ValueError(
                "Gemini API Key belum diset! Silakan masukkan API Key Anda di menu Pengaturan atau file .env."
            )

        last_error = None
        for attempt in range(max_retries):
            try:
                if self._client == "legacy":
                    import google.generativeai as gai
                    model_instance = gai.GenerativeModel(
                        model_name=self.model,
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
                        model=self.model,
                        contents=prompt,
                        config=cfg,
                    )
                    return response.text or ""
            except Exception as e:
                last_error = e
                # Wait briefly before retrying (exponential backoff)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Gagal memanggil Gemini setelah {max_retries} percobaan: {last_error}")

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
        """Extract and parse JSON from text that might contain markdown fences."""
        cleaned = text.strip()

        # Remove markdown code fences if present (```json ... ``` or ``` ...)
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        # Direct parse attempt
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Search for first JSON object {...} or array [...]
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if match:
            candidate = match.group(1)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Tidak dapat mem-parsing respons menjadi JSON yang valid:\n{text[:300]}...")
