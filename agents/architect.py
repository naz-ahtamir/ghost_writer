"""Architect Agent: Handles worldbuilding, lore, rules, and core concepts."""

from typing import Any, Dict
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import ARCHITECT_SYSTEM, ARCHITECT_USER_TEMPLATE


class ArchitectAgent:
    """Agent responsible for setting, atmosphere, lore, and world rules."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate_world_bible(self, project: NovelProject) -> Dict[str, Any]:
        """Generate a complete world bible based on project metadata."""
        meta = project.metadata
        lang = meta.get("language", "Indonesian")

        system_prompt = ARCHITECT_SYSTEM.format(language=lang)
        user_prompt = ARCHITECT_USER_TEMPLATE.format(
            title=meta.get("title", "Tanpa Judul"),
            genre=meta.get("genre", "Fantasi / Fiksi Ilmiah"),
            tone=meta.get("tone", "Misterius dan Epik"),
            premise=meta.get("premise", ""),
            target_audience=meta.get("target_audience", "Umum"),
        )

        world_data = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.7,
        )

        project.save_world_bible(world_data)
        return world_data
