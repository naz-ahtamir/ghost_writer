"""Scene Planner Agent: Plans micro-beats for individual chapters."""

from typing import Any, Dict, List
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import SCENE_PLANNER_SYSTEM, SCENE_PLANNER_USER_TEMPLATE


class ScenePlannerAgent:
    """Agent responsible for structuring a single chapter into 3-5 scene beats."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate_beats(self, project: NovelProject, chapter_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate scene beats for a specific chapter."""
        chap_num = chapter_info.get("chapter_number", 1)
        meta = project.metadata
        lang = meta.get("language", "Indonesian")

        continuity_summary = project.get_continuity_summary(up_to_chapter=chap_num)

        system_prompt = SCENE_PLANNER_SYSTEM.format(language=lang)
        user_prompt = SCENE_PLANNER_USER_TEMPLATE.format(
            chapter_number=chap_num,
            chapter_title=chapter_info.get("title", f"Bab {chap_num}"),
            chapter_summary=chapter_info.get("summary", ""),
            pov_character=chapter_info.get("pov_character", "Protagonis"),
            setting=chapter_info.get("setting", ""),
            conflict=chapter_info.get("conflict", ""),
            turning_point=chapter_info.get("turning_point", ""),
            continuity_summary=continuity_summary,
        )

        beats_data = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.65,
        )

        if isinstance(beats_data, dict) and "beats" in beats_data:
            beats_data = beats_data["beats"]

        if not isinstance(beats_data, list):
            beats_data = [beats_data]

        return beats_data
