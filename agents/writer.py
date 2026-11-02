"""Writer Agent: Drafts full chapter prose beat-by-beat."""

import json
from typing import Any, Dict, List, Optional
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import WRITER_SYSTEM, WRITER_USER_TEMPLATE


class WriterAgent:
    """Agent responsible for writing the actual chapter prose."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def write_chapter(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        beats: List[Dict[str, Any]],
    ) -> str:
        """Draft prose for the specified chapter based on beats and world lore."""
        chap_num = chapter_info.get("chapter_number", 1)
        meta = project.metadata
        lang = meta.get("language", "Indonesian")
        target_words = meta.get("target_words_per_chapter", 2000)

        # Build character profiles context
        char_context_parts = []
        for c in project.characters:
            char_context_parts.append(
                f"- Nama: {c.get('name')}\n"
                f"  Peran: {c.get('role')}\n"
                f"  Ciri Fisik: {c.get('appearance')}\n"
                f"  Sifat & Flaw: {c.get('personality')} (Flaw: {c.get('flaw')})\n"
                f"  Gaya Bicara: {c.get('speech_mannerism')}\n"
            )
        characters_context = "\n".join(char_context_parts)

        # Build world lore context
        world_context = (
            f"Latar Utama: {project.world_bible.get('setting_name')}\n"
            f"Atmosfer: {project.world_bible.get('atmosphere')}\n"
            f"Aturan Khusus: {project.world_bible.get('rules_and_systems')}\n"
        )

        continuity_summary = project.get_continuity_summary(up_to_chapter=chap_num)
        beats_json = json.dumps(beats, indent=2, ensure_ascii=False)

        system_prompt = WRITER_SYSTEM.format(language=lang)
        user_prompt = WRITER_USER_TEMPLATE.format(
            chapter_number=chap_num,
            chapter_title=chapter_info.get("title", f"Bab {chap_num}"),
            pov_character=chapter_info.get("pov_character", "Protagonis"),
            setting=chapter_info.get("setting", ""),
            conflict=chapter_info.get("conflict", ""),
            turning_point=chapter_info.get("turning_point", ""),
            target_words=target_words,
            beats_json=beats_json,
            characters_context=characters_context,
            world_context=world_context,
            continuity_summary=continuity_summary,
        )

        chapter_prose = self.llm.generate(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.75,
        )

        # Save to project
        project.save_chapter(chap_num, chapter_prose, beats=beats)
        return chapter_prose
