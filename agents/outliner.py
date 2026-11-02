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

        system_prompt = OUTLINER_SYSTEM.format(language=lang)
        user_prompt = OUTLINER_USER_TEMPLATE.format(
            title=meta.get("title", ""),
            genre=meta.get("genre", ""),
            tone=meta.get("tone", ""),
            premise=meta.get("premise", ""),
            target_chapters=meta.get("target_chapters", 12),
            characters_summary=chars_summary,
            setting_summary=world_summary,
        )

        outline_data = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.7,
        )

        # Mark all chapters as planned initially
        if "chapters" in outline_data:
            for ch in outline_data["chapters"]:
                if "status" not in ch:
                    ch["status"] = "planned"

        project.save_outline(outline_data)
        return outline_data
