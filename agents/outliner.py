"""Outliner Agent: Constructs narrative arcs and chapter-by-chapter plotlines."""

import json
from typing import Any, Dict
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import OUTLINER_SYSTEM, OUTLINER_USER_TEMPLATE


class OutlinerAgent:
    """Agent responsible for narrative structure, pacing, and chapter plotting."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate_outline(self, project: NovelProject) -> Dict[str, Any]:
        """Generate full outline and chapter breakdown."""
        meta = project.metadata
        lang = meta.get("language", "Indonesian")

        # Format characters summary
        char_lines = []
        for c in project.characters:
            name = c.get("name", "Tanpa Nama")
            role = c.get("role", "Tokoh")
            goal = c.get("external_goal", "")
            flaw = c.get("flaw", "")
            char_lines.append(f"- {name} ({role}): Goal: {goal} | Kelemahan: {flaw}")
        chars_summary = "\n".join(char_lines) or "Belum ada daftar karakter spesifik."

        world_summary = (
            f"Setting: {project.world_bible.get('setting_name', '')}\n"
            f"Konsep: {project.world_bible.get('core_concept', '')}\n"
            f"Lore: {project.world_bible.get('historical_lore', '')}"
        )

        target_chapters = int(meta.get("target_chapters", 12))

        system_prompt = OUTLINER_SYSTEM.format(language=lang)
        user_prompt = OUTLINER_USER_TEMPLATE.format(
            title=meta.get("title", ""),
            genre=meta.get("genre", ""),
            tone=meta.get("tone", ""),
            premise=meta.get("premise", ""),
            target_chapters=target_chapters,
            characters_summary=chars_summary,
            setting_summary=world_summary,
        )

        outline_data = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.7,
        )

        if not isinstance(outline_data, dict):
            outline_data = {"overall_synopsis": "", "narrative_arc": "", "chapters": []}

        chapters = outline_data.get("chapters", [])
        if not isinstance(chapters, list):
            chapters = []
            outline_data["chapters"] = chapters

        # Mark all chapters as planned initially and ensure chapter_number
        for idx, ch in enumerate(chapters, 1):
            if "chapter_number" not in ch:
                ch["chapter_number"] = idx
            if "status" not in ch:
                ch["status"] = "planned"

        # If LLM generated fewer chapters than target_chapters, pad missing chapters
        if len(chapters) < target_chapters:
            setting_default = project.world_bible.get("setting_name", "Latar Utama")
            pov_default = chapters[0].get("pov_character", "Protagonis") if chapters else "Protagonis"
            for num in range(len(chapters) + 1, target_chapters + 1):
                chapters.append({
                    "chapter_number": num,
                    "title": f"Bab {num}: Perjalanan Lanjutan",
                    "pov_character": pov_default,
                    "setting": setting_default,
                    "summary": f"Kelanjutan alur cerita menuju resolusi klimaks Bab {num}.",
                    "conflict": "Konflik dan rintangan lanjutan.",
                    "turning_point": "Titik balik perkembangan cerita.",
                    "status": "planned",
                })

        project.save_outline(outline_data)
        return outline_data
