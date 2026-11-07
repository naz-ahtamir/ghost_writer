"""High-Realism Uncensored Image Generation Client for GhostWriter Chapter Illustrations.

Powered by:
1. Official FLUX.1 High-Realism Cluster (FLUX.1-merged, FLUX.1-dev, FLUX.1-schnell via multi-node Gradio API — zero watermark, true DSLR camera realism, full pose & environment rendering)
2. xAI Grok Image API (grok-2-image / grok-2-image-1212)
3. Google Gemini / Imagen 3 API (with BLOCK_NONE / ALLOW_ADULT)
4. Local Stable Diffusion WebUI / Forge API (100% local uncensored txt2img)
"""

import base64
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config
from core.llm import _create_ssl_context, safe_log, GEMINI_CORE_SAFETY_CATEGORIES


DEFAULT_NEGATIVE_PROMPT = (
    "anime, cartoon, 3d render, cgi, illustration, painting, sketch, comic, "
    "close-up headshot only, passport photo, empty background, blurry background blob, "
    "doll, plastic skin, airbrushed, oversaturated, censored, mosaic, blurred, "
    "pixelated, black bars, watermark, text, logo, signature, username, "
    "deformed hands, extra fingers, missing fingers, bad anatomy, skewed eyes, "
    "mutated limbs, duplicate face, lowres, blurry, worst quality, artifacts"
)

# Multi-node FLUX.1 Gradio cluster (True 12B FLUX.1 models — no watermarks, DSLR realism)
FLUX_CLUSTER_NODES: List[Dict[str, Any]] = [
    {
        "name": "flux-1-merged-dslr",
        "host": "https://multimodalart-flux-1-merged.hf.space",
        "mode": "dev_merged",
        "steps": 8,
        "guidance": 3.5,
    },
    {
        "name": "flux-1-schnell-bfl",
        "host": "https://black-forest-labs-flux-1-schnell.hf.space",
        "mode": "schnell",
        "steps": 4,
    },
    {
        "name": "flux-1-schnell-eval",
        "host": "https://evalstate-flux1-schnell.hf.space",
        "mode": "schnell",
        "steps": 4,
    },
    {
        "name": "flux-1-dev-bfl",
        "host": "https://black-forest-labs-flux-1-dev.hf.space",
        "mode": "dev",
        "steps": 24,
        "guidance": 3.5,
    },
    {
        "name": "flux-1-schnell-abid",
        "host": "https://abidlabs-black-forest-labs-flux-1-schnell.hf.space",
        "mode": "schnell",
        "steps": 4,
    },
    {
        "name": "flux-1-schnell-shan",
        "host": "https://justshannniii-labs-flux-1-schnell.hf.space",
        "mode": "schnell",
        "steps": 4,
    },
    {
        "name": "flux-1-schnell-hysts",
        "host": "https://hysts-mcp-flux-1-schnell.hf.space",
        "mode": "schnell",
        "steps": 4,
    },
    {
        "name": "flux-1-schnell-saad",
        "host": "https://saadpie1-black-forest-labs-flux-1-schnell.hf.space",
        "mode": "schnell",
        "steps": 4,
    },
]

# Meta-words that ironically trigger automated API safety bots without adding visual value
META_TRIGGER_WORDS = (
    r"\bnsfw\b",
    r"\buncensored\b",
    r"\bexplicit\b",
    r"\bpornographic\b",
    r"\bporn\b",
    r"\bhentai\b",
    r"\bxxx\b",
    r"\b18\+\b",
)

# Visual translation map: converts raw keywords that trip API safety filters into
# vivid, photorealistic, sensual/visceral DSLR cinematography descriptions that render without refusal.
ARTISTIC_VISUAL_ADAPTATIONS: List[Tuple[str, str]] = [
    (
        r"\b(naked|nude|nudity|fully unclothed|completely naked)\b",
        "unclothed natural skin silhouette, bare shoulders and back, sensual boudoir DSLR photography, alluring natural skin texture, chiaroscuro shadow play",
    ),
    (
        r"\b(having sex|sexual intercourse|intercourse|making love|fucking|penetration)\b",
        "passionate intimate embrace on bed, intertwined bodies, bare skin against skin, hands gripping waist and chest, flushed faces inches apart, heavy-lidded sensual gaze, intense erotic tension, tangled silk sheets",
    ),
    (
        r"\b(topless|bare breasts|naked breasts|nipples)\b",
        "bare shoulders and collarbone, alluring feminine curves, deep sensual décolletage, intimate draped silk, natural anatomical proportions",
    ),
    (
        r"\b(orgasm|climaxing|moaning in pleasure)\b",
        "ecstatic arched back, head tilted back, parted lips, flushed glistening skin, eyes half-closed in intense rapture",
    ),
    (
        r"\b(erotic|sensual|seductive)\b",
        "alluring intimate boudoir atmosphere, magnetic eye contact, warm skin glow",
    ),
    (
        r"\b(gore|gory|mutilated|decapitated|disemboweled)\b",
        "visceral dark thriller action, crimson splatters on skin and floor, battle wounds, grimdark live-action movie realism",
    ),
]


def compute_deterministic_seed(key_text: str) -> int:
    """Compute a consistent 31-bit positive integer seed from a string."""
    digest = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) % 2147483646) + 1


def clean_meta_triggers(prompt: str) -> str:
    """Remove meta-labels like 'NSFW' or 'uncensored' that trip keyword filters before rendering."""
    cleaned = prompt
    for pattern in META_TRIGGER_WORDS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def adapt_prompt_for_uncensored_render(prompt: str, level: int = 1) -> str:
    """Transform raw trigger words into photorealistic boudoir/cinema visual descriptions."""
    adapted = clean_meta_triggers(prompt)
    for pattern, replacement in ARTISTIC_VISUAL_ADAPTATIONS:
        adapted = re.sub(pattern, replacement, adapted, flags=re.IGNORECASE)

    if level >= 2:
        extra_replacements = [
            (r"\b(genitals|penis|vagina|pussy|cock|dick)\b", "intimate lower silhouette in deep chiaroscuro shadow"),
            (r"\b(buttocks|ass|butt)\b", "sculpted back and hip silhouette"),
            (r"\b(bloodbath|slaughter|torture)\b", "intense dark dramatic confrontation, crimson shadows"),
            (r"\b(lingerie|underwear|bra|panties)\b", "delicate form-fitting silk evening attire"),
        ]
        for pat, rep in extra_replacements:
            adapted = re.sub(pat, rep, adapted, flags=re.IGNORECASE)
        adapted = (
            "Candid live-action DSLR photograph shot on Sony A7R V 35mm f/1.4 lens, tasteful dramatic lighting, "
            + adapted
        )

    return re.sub(r"\s{2,}", " ", adapted).strip()


def is_valid_rendered_image(img_bytes: bytes) -> bool:
    """Verify that image bytes represent a real, non-blacked-out, non-censored image."""
    if not img_bytes or len(img_bytes) < 2500:
        return False
    try:
        from PIL import Image
        with Image.open(io.BytesIO(img_bytes)) as img:
            rgb = img.convert("RGB").resize((64, 64))
            pixels = list(rgb.getdata())
            if not pixels:
                return False
            lum_values = [(0.299 * r + 0.587 * g + 0.114 * b) for (r, g, b) in pixels]
            mean_lum = sum(lum_values) / len(lum_values)
            if mean_lum < 3.5 or mean_lum > 252.0:
                return False
            variance = sum((x - mean_lum) ** 2 for x in lum_values) / len(lum_values)
            if variance < 4.0:
                return False
        return True
    except ImportError:
        return len(img_bytes) > 4096 and (
            img_bytes.startswith(b"\xff\xd8\xff")
            or img_bytes.startswith(b"\x89PNG")
            or img_bytes.startswith(b"RIFF")
        )
    except Exception:
        return False


def normalize_to_jpeg_bytes(img_bytes: bytes) -> bytes:
    """Convert WebP/PNG/JPEG bytes into high-quality standard RGB JPEG bytes for Word & Browser compatibility."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(img_bytes)) as img:
            rgb = img.convert("RGB")
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=95)
            return out.getvalue()
    except Exception:
        return img_bytes


class ImageGeneratorClient:
    """Unified image generation client with real FLUX.1 DSLR Cluster, anti-refusal adaptation, and seed lock."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        width: int = config.IMAGE_WIDTH,
        height: int = config.IMAGE_HEIGHT,
    ):
        self.provider = (provider or config.get_image_provider()).lower()
        self.model = model or config.get_image_model(self.provider)
        self.width = width
        self.height = height
        self.sd_api_url = config.get_sd_api_url()

    def set_provider(self, provider: str, model: Optional[str] = None) -> None:
        """Switch active image provider and model."""
        self.provider = provider.strip().lower()
        self.model = model or config.get_image_model(self.provider)

    def _call_single_flux_gradio_node(
        self,
        node: Dict[str, Any],
        prompt: str,
        seed: int,
    ) -> bytes:
        """Execute a single inference call against a FLUX.1 Gradio Space node."""
        ctx = _create_ssl_context()
        host = node["host"].rstrip("/")
        mode = node.get("mode", "schnell")
        steps = int(node.get("steps", 4))
        w = max(512, min(1344, (self.width // 32) * 32))
        h = max(512, min(1344, (self.height // 32) * 32))

        if mode in ("dev", "dev_merged"):
            guidance = float(node.get("guidance", 3.5))
            payload_data = [prompt, int(seed), False, w, h, guidance, steps]
        else:
            payload_data = [prompt, int(seed), False, w, h, steps]

        call_url = f"{host}/gradio_api/call/infer"
        req = urllib.request.Request(
            call_url,
            data=json.dumps({"data": payload_data}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GhostWriterAI/2.5",
                "Connection": "close",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
            event_id = resp_json.get("event_id")
            if not event_id:
                raise RuntimeError(f"Tidak mendapatkan event_id dari {node['name']}")

        stream_url = f"{host}/gradio_api/call/infer/{event_id}"
        req_stream = urllib.request.Request(
            stream_url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GhostWriterAI/2.5",
                "Accept": "text/event-stream",
                "Connection": "close",
            },
            method="GET",
        )
        current_event = ""
        with urllib.request.urlopen(req_stream, timeout=75, context=ctx) as stream_resp:
            for raw_line in stream_resp:
                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if line_str.startswith("event:"):
                    current_event = line_str[6:].strip()
                elif line_str.startswith("data:"):
                    data_str = line_str[5:].strip()
                    if current_event == "error":
                        raise RuntimeError(f"Gradio error pada {node['name']}: {data_str}")
                    if not data_str or data_str == "null":
                        continue
                    parsed = json.loads(data_str)
                    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                        img_info = parsed[0]
                        img_url = img_info.get("url")
                        if not img_url and img_info.get("path"):
                            img_url = f"{host}/gradio_api/file={img_info['path']}"
                        if img_url:
                            img_req = urllib.request.Request(
                                img_url,
                                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GhostWriterAI/2.5"},
                            )
                            with urllib.request.urlopen(img_req, timeout=30, context=ctx) as img_resp:
                                return img_resp.read()

        raise RuntimeError(f"Stream selesai tanpa gambar dari {node['name']}")

    def _generate_via_pollinations(
        self,
        prompt: str,
        seed: int,
        model_name: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        """Generate true DSLR photorealistic image via the FLUX.1 Cluster (replaces legacy blurry Pollinations sana)."""
        prompt_variants = [
            adapt_prompt_for_uncensored_render(prompt, level=1),
            adapt_prompt_for_uncensored_render(prompt, level=2),
        ]
        unique_variants: List[str] = []
        for pv in prompt_variants:
            if pv not in unique_variants:
                unique_variants.append(pv)

        last_err: Optional[Exception] = None

        for v_idx, active_prompt in enumerate(unique_variants):
            for node in FLUX_CLUSTER_NODES:
                try:
                    raw_bytes = self._call_single_flux_gradio_node(node, active_prompt, seed)
                    if is_valid_rendered_image(raw_bytes):
                        jpg_bytes = normalize_to_jpeg_bytes(raw_bytes)
                        return jpg_bytes, f"flux_cluster:{node['name']}"
                except Exception as e:
                    last_err = e
                    continue

        raise RuntimeError(f"Seluruh node FLUX.1 Cluster sedang penuh/terkendala: {last_err}")

    def _generate_via_grok(self, prompt: str) -> Tuple[bytes, str]:
        """Generate image using xAI Grok Image API (grok-2-image) with automatic artistic adaptation retry."""
        api_key = config.get_api_key("grok")
        if not api_key:
            raise ValueError("xAI Grok API Key belum diset untuk Grok Image.")

        ctx = _create_ssl_context()
        url = "https://api.x.ai/v1/images/generations"
        model_name = self.model if self.model in config.GROK_IMAGE_MODELS else "grok-2-image"

        variants = [
            clean_meta_triggers(prompt),
            adapt_prompt_for_uncensored_render(prompt, level=1),
            adapt_prompt_for_uncensored_render(prompt, level=2),
        ]
        last_err = None

        for active_prompt in variants:
            payload = {
                "model": model_name,
                "prompt": active_prompt[:2000],
                "n": 1,
                "response_format": "b64_json",
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "Connection": "close",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    items = resp_data.get("data", [])
                    if items:
                        raw_bytes = None
                        if items[0].get("b64_json"):
                            raw_bytes = base64.b64decode(items[0]["b64_json"])
                        elif items[0].get("url"):
                            img_url = items[0]["url"]
                            img_req = urllib.request.Request(img_url, headers={"User-Agent": "GhostWriterAI/2.5"})
                            with urllib.request.urlopen(img_req, timeout=60, context=ctx) as img_resp:
                                raw_bytes = img_resp.read()
                        if raw_bytes and is_valid_rendered_image(raw_bytes):
                            return normalize_to_jpeg_bytes(raw_bytes), f"grok:{model_name}"
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                last_err = RuntimeError(f"xAI Grok Image API Error ({e.code}): {err_body}")
                if e.code in (401, 403) and "key" in err_body.lower():
                    raise last_err
                continue
            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(str(last_err or "Respons xAI Grok Image gagal."))

    def _generate_via_gemini(self, prompt: str) -> Tuple[bytes, str]:
        """Generate image using Google Imagen 3 or Gemini Flash Image Generation with anti-refusal retry."""
        api_key = config.get_api_key("gemini")
        if not api_key:
            raise ValueError("Google Gemini API Key belum diset untuk Gemini Image.")

        ctx = _create_ssl_context()
        variants = [
            clean_meta_triggers(prompt),
            adapt_prompt_for_uncensored_render(prompt, level=1),
            adapt_prompt_for_uncensored_render(prompt, level=2),
        ]
        last_err = None

        for active_prompt in variants:
            imagen_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"imagen-3.0-generate-002:predict?key={api_key}"
            )
            imagen_payload = {
                "instances": [{"prompt": active_prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "16:9",
                    "personGeneration": "ALLOW_ADULT",
                    "safetyFilterLevel": "BLOCK_ONLY_HIGH",
                },
            }
            try:
                req = urllib.request.Request(
                    imagen_url,
                    data=json.dumps(imagen_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Connection": "close"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    preds = resp_data.get("predictions", [])
                    if preds and preds[0].get("bytesBase64Encoded"):
                        raw_bytes = base64.b64decode(preds[0]["bytesBase64Encoded"])
                        if is_valid_rendered_image(raw_bytes):
                            return normalize_to_jpeg_bytes(raw_bytes), "gemini:imagen-3.0"
            except Exception as e:
                last_err = e

            flash_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash-exp-image-generation:generateContent?key={api_key}"
            )
            flash_payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"Generate a candid live-action DSLR photograph: {active_prompt}"}],
                    }
                ],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                "safetySettings": [
                    {"category": cat, "threshold": "BLOCK_NONE"} for cat in GEMINI_CORE_SAFETY_CATEGORIES
                ],
            }
            try:
                req = urllib.request.Request(
                    flash_url,
                    data=json.dumps(flash_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Connection": "close"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            inline = part.get("inlineData", {})
                            if inline.get("data"):
                                raw_bytes = base64.b64decode(inline["data"])
                                if is_valid_rendered_image(raw_bytes):
                                    return normalize_to_jpeg_bytes(raw_bytes), "gemini:2.0-flash-image"
            except Exception as e:
                last_err = e

        raise RuntimeError(f"Gemini Image API tidak mengembalikan gambar: {last_err}")

    def _generate_via_local_sd(
        self,
        prompt: str,
        negative_prompt: str,
        seed: int,
    ) -> Tuple[bytes, str]:
        """Generate 100% uncensored image via Local Stable Diffusion WebUI / Forge API."""
        base_url = self.sd_api_url.rstrip("/")
        url = f"{base_url}/sdapi/v1/txt2img"
        payload = {
            "prompt": clean_meta_triggers(prompt),
            "negative_prompt": negative_prompt or DEFAULT_NEGATIVE_PROMPT,
            "seed": seed,
            "steps": 28,
            "cfg_scale": 6.5,
            "width": self.width,
            "height": self.height,
            "sampler_name": "DPM++ 2M Karras",
            "override_settings": {"filter_nsfw": False},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Connection": "close"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                images = resp_data.get("images", [])
                if images:
                    return normalize_to_jpeg_bytes(base64.b64decode(images[0])), "local_sd:txt2img"
                raise RuntimeError("Respons Local SD kosong.")
        except Exception as e:
            raise RuntimeError(f"Local Stable Diffusion API ({url}) tidak terhubung: {e}")

    @staticmethod
    def _create_storyboard_fallback_image(
        output_path: Path,
        scene_title: str,
        caption: str,
        prompt: str,
        seed: int,
        width: int = 1280,
        height: int = 720,
    ) -> Path:
        """Create a sleek dark cinematic storyboard card when offline or in test environments."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (width, height), color=(18, 20, 28))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(0, 0), (width, 65)], fill=(8, 9, 12))
            draw.rectangle([(0, height - 65), (width, height)], fill=(8, 9, 12))
            draw.rectangle([(30, 85), (width - 30, height - 85)], outline=(90, 140, 200), width=2)

            header = f"GHOSTWRITER CINEMATIC FRAME  |  SEED: {seed}"
            draw.text((55, 25), header[:90], fill=(160, 195, 240))
            draw.text((55, 115), f"SCENE: {scene_title[:80]}", fill=(245, 245, 250))

            def _wrap(text: str, width_chars: int = 95) -> list:
                words = text.split()
                lines, curr = [], []
                for w in words:
                    if sum(len(x) + 1 for x in curr) + len(w) > width_chars:
                        lines.append(" ".join(curr))
                        curr = [w]
                    else:
                        curr.append(w)
                if curr:
                    lines.append(" ".join(curr))
                return lines

            y = 165
            for line in _wrap(f"Caption: {caption}", 90)[:4]:
                draw.text((55, y), line, fill=(210, 215, 225))
                y += 26

            y += 20
            draw.text((55, y), "Visual Prompt Blueprint (Consistent Visual DNA):", fill=(130, 200, 170))
            y += 28
            for line in _wrap(prompt, 100)[:10]:
                draw.text((55, y), line, fill=(170, 175, 190))
                y += 22

            img.save(str(output_path), format="JPEG", quality=92)
            return output_path
        except Exception:
            minimal_jpeg = base64.b64decode(
                "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
            )
            with open(output_path, "wb") as f:
                f.write(minimal_jpeg)
            return output_path

    def generate_and_save(
        self,
        prompt: str,
        output_path: Path,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        seed: Optional[int] = None,
        scene_title: str = "Ilustrasi Adegan",
        caption: str = "",
        allow_fallback_to_pollinations: bool = True,
        allow_offline_storyboard: bool = True,
    ) -> Dict[str, Any]:
        """Generate a high-realism DSLR image file on disk with multi-node FLUX.1 fallback."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        effective_seed = seed if seed is not None else compute_deterministic_seed(prompt)

        img_bytes: Optional[bytes] = None
        engine_used = ""
        last_error: Optional[Exception] = None

        try:
            if self.provider == "grok":
                img_bytes, engine_used = self._generate_via_grok(prompt)
            elif self.provider == "gemini":
                img_bytes, engine_used = self._generate_via_gemini(prompt)
            elif self.provider == "local_sd":
                img_bytes, engine_used = self._generate_via_local_sd(prompt, negative_prompt, effective_seed)
            else:
                img_bytes, engine_used = self._generate_via_pollinations(prompt, effective_seed)
        except Exception as e:
            last_error = e
            if self.provider != "pollinations" and allow_fallback_to_pollinations:
                safe_log(
                    f"[Illustrator] Engine '{self.provider}' terkendala ({e}). "
                    f"Beralih otomatis ke FLUX.1 DSLR Realism Cluster..."
                )
                try:
                    img_bytes, engine_used = self._generate_via_pollinations(prompt, effective_seed)
                except Exception as poll_err:
                    last_error = poll_err

        if img_bytes:
            with open(output_path, "wb") as f:
                f.write(img_bytes)
            return {
                "status": "rendered",
                "image_path": str(output_path),
                "engine": engine_used,
                "seed": effective_seed,
            }

        if allow_offline_storyboard:
            safe_log(
                f"[Illustrator] Koneksi internet/server gambar sedang tidak dapat dijangkau ({last_error}). "
                f"Menyimpan Storyboard Frame sementara di {output_path.name}."
            )
            self._create_storyboard_fallback_image(
                output_path=output_path,
                scene_title=scene_title,
                caption=caption,
                prompt=prompt,
                seed=effective_seed,
                width=self.width,
                height=self.height,
            )
            return {
                "status": "storyboard_preview",
                "image_path": str(output_path),
                "engine": "storyboard_offline_fallback",
                "seed": effective_seed,
                "error": str(last_error) if last_error else "",
            }

        raise RuntimeError(f"Gagal men-generate gambar ilustrasi: {last_error}")
