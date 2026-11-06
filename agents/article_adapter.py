"""Article Adapter Agent: Analyzes an article or document and transforms it into a novel blueprint."""

from typing import Any, Dict
from core.llm import LLMClient
from core.prompts import ARTICLE_ADAPTER_SYSTEM, ARTICLE_ADAPTER_USER_TEMPLATE


class ArticleAdapterAgent:
    """Agent responsible for turning raw article/document text into a structured novel concept."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def analyze_article(
        self,
        article_text: str,
        custom_direction: str = "",
        language: str = "Indonesian",
    ) -> Dict[str, Any]:
        """Analyze article text and return structured novel adaptation blueprint."""
        trimmed_text = article_text.strip()
        if len(trimmed_text) > 25000:
            trimmed_text = trimmed_text[:25000] + "\n...[Teks dipotong agar sesuai kapasitas konteks]..."

        system_prompt = ARTICLE_ADAPTER_SYSTEM.format(language=language)
        user_prompt = ARTICLE_ADAPTER_USER_TEMPLATE.format(
            custom_direction=custom_direction.strip() or "Kembangkan menjadi novel yang dramatis, mendalam, dan memikat.",
            article_text=trimmed_text,
        )

        raw = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.65,
        )

        if not isinstance(raw, dict):
            raw = {}

        rec_chapters = raw.get("recommended_chapters", 14)
        try:
            rec_chapters = max(6, min(40, int(rec_chapters)))
        except Exception:
            rec_chapters = 14

        rec_words = raw.get("recommended_words_per_chapter", 2000)
        try:
            rec_words = max(1000, min(4000, int(rec_words)))
        except Exception:
            rec_words = 2000

        source_summary = str(raw.get("source_summary", "")).strip()
        premise = str(raw.get("premise", "")).strip()
        if not premise:
            snippet = " ".join(trimmed_text.split()[:150])
            premise = f"Adaptasi novel dari artikel: {snippet}"

        if source_summary and source_summary not in premise:
            combined_premise = f"{premise}\n\n[Fakta & Konteks Artikel Sumber]: {source_summary}"
        else:
            combined_premise = premise

        return {
            "suggested_title": str(raw.get("suggested_title") or "Jejak di Balik Berita").strip(),
            "genre": str(raw.get("genre") or "Drama Emosional / Realisme").strip(),
            "tone": str(raw.get("tone") or "Mendalam, realistis, dan penuh ketegangan emosional").strip(),
            "source_summary": source_summary,
            "premise": premise,
            "combined_premise": combined_premise,
            "recommended_chapters": rec_chapters,
            "recommended_words_per_chapter": rec_words,
            "adaptation_notes": str(
                raw.get("adaptation_notes")
                or f"Direkomendasikan {rec_chapters} bab (~{rec_words} kata/bab) agar alur tetap fokus dan tajam."
            ).strip(),
        }
