"""Editor & Continuity Auditor Agent: Evaluates prose, checks lore, and polishes chapters."""

import json
from typing import Any, Dict, Optional
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import EDITOR_SYSTEM, EDITOR_USER_TEMPLATE, REVISE_PROMPT_TEMPLATE


class EditorAgent:
    """Agent responsible for checking continuity, critique, and refining prose."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def audit_chapter(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        chapter_prose: str,
    ) -> Dict[str, Any]:
        """Perform deep continuity and style audit on a chapter."""
        chap_num = chapter_info.get("chapter_number", 1)
        lang = project.metadata.get("language", "Indonesian")

        # Build characters context
        char_lines = [
            f"- {c.get('name')} ({c.get('role')}): {c.get('personality')}, Flaw: {c.get('flaw')}"
            for c in project.characters
        ]
        characters_context = "\n".join(char_lines)

        world_context = (
            f"Latar: {project.world_bible.get('setting_name')}\n"
            f"Aturan/Hukum: {project.world_bible.get('rules_and_systems')}\n"
        )

        system_prompt = EDITOR_SYSTEM.format(language=lang)
        user_prompt = EDITOR_USER_TEMPLATE.format(
            chapter_number=chap_num,
            chapter_title=chapter_info.get("title", f"Bab {chap_num}"),
            chapter_prose=chapter_prose,
            conflict=chapter_info.get("conflict", ""),
            turning_point=chapter_info.get("turning_point", ""),
            characters_context=characters_context,
            world_context=world_context,
        )

        audit_data = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.3,
        )

        project.save_chapter_audit(chap_num, audit_data)
        return audit_data

    def revise_chapter(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        original_prose: str,
        critique_feedback: str,
        user_instructions: str = "",
    ) -> str:
        """Polish and rewrite chapter prose based on audit critique and user notes."""
        chap_num = chapter_info.get("chapter_number", 1)
        lang = project.metadata.get("language", "Indonesian")

        prompt = REVISE_PROMPT_TEMPLATE.format(
            chapter_number=chap_num,
            chapter_title=chapter_info.get("title", f"Bab {chap_num}"),
            critique_feedback=critique_feedback or "Perbaiki konsistensi dan tingkatkan tensi Show Don't Tell.",
            user_instructions=user_instructions or "Pertahankan esensi cerita namun buat prosa lebih hidup dan padu.",
            original_prose=original_prose,
        )

        revised_prose = self.llm.generate(
            prompt=prompt,
            system_instruction=f"Anda adalah Senior Fiction Editor. Bahasa: {lang}",
            temperature=0.7,
        )

        # Update chapter file
        project.save_chapter(chap_num, revised_prose)
        return revised_prose
