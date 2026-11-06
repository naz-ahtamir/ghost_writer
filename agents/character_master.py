"""Character Master Agent: Designs psychological character bibles and dynamics."""

from typing import Any, Dict, List
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import CHARACTER_SYSTEM, CHARACTER_USER_TEMPLATE


class CharacterMasterAgent:
    """Agent responsible for designing complex 3D characters."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate_characters(self, project: NovelProject) -> List[Dict[str, Any]]:
        """Generate full cast of characters based on premise and world lore."""
        meta = project.metadata
        lang = meta.get("language", "Indonesian")

        world_summary = (
            f"Setting: {project.world_bible.get('setting_name', 'Dunia Cerita')}. "
            f"Atmosfer: {project.world_bible.get('atmosphere', '')}. "
            f"Aturan/Sistem: {project.world_bible.get('rules_and_systems', '')}"
        )

        system_prompt = CHARACTER_SYSTEM.format(language=lang)
        user_prompt = CHARACTER_USER_TEMPLATE.format(
            premise=meta.get("premise", ""),
            genre=meta.get("genre", ""),
            tone=meta.get("tone", ""),
            setting_summary=world_summary,
        )

        characters_data = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.75,
        )

        if isinstance(characters_data, dict):
            unpacked = None
            for key in ("characters", "cast", "tokoh", "daftar_karakter", "data"):
                if isinstance(characters_data.get(key), list):
                    unpacked = characters_data[key]
                    break
            if unpacked is None:
                for val in characters_data.values():
                    if isinstance(val, list) and val:
                        unpacked = val
                        break
            characters_data = unpacked if unpacked is not None else [characters_data]

        if not isinstance(characters_data, list):
            characters_data = [characters_data]

        project.save_characters(characters_data)
        return characters_data
