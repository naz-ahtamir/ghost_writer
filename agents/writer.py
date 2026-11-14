"""Writer Agent: Drafts full chapter prose beat-by-beat or via structured blueprint."""

import re
from typing import Any, Callable, Dict, List, Optional
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import WRITER_SYSTEM, WRITER_USER_TEMPLATE, WRITER_BEAT_TEMPLATE
from agents.scene_planner import ScenePlannerAgent


class WriterAgent:
    """Agent responsible for writing the actual chapter prose strictly following scene beats."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    @staticmethod
    def format_beats_blueprint(beats: List[Dict[str, Any]], target_words: int = 2000) -> str:
        """Format beats list into a clear, sequential narrative blueprint for the LLM."""
        if not beats:
            return "Belum ada beat spesifik. Susun alur bab dari pembuka, eskalasi konflik, hingga titik balik."

        total = len(beats)
        words_per_beat = max(350, int(target_words / max(1, total)))
        lines: List[str] = []
        for idx, b in enumerate(beats, 1):
            num = b.get("beat_number", idx)
            name = b.get("beat_name", f"Adegan {idx}")
            events = b.get("scene_events") or b.get("description") or b.get("goal", "")
            goal = b.get("goal", "")
            obstacle = b.get("obstacle", "")
            sensory = b.get("sensory_details", "")
            emotion = b.get("emotional_shift", "")
            lines.append(
                f"[BEAT {num}/{total}: {name}] (Target: ~{words_per_beat} kata)\n"
                f"  • Kejadian & Aksi Wajib : {events}\n"
                f"  • Tujuan Karakter       : {goal}\n"
                f"  • Hambatan / Konflik    : {obstacle}\n"
                f"  • Detail Panca Indera   : {sensory}\n"
                f"  • Perubahan Emosi       : {emotion}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _clean_beat_continuation(beat_text: str, chap_num: int, chap_title: str) -> str:
        """Remove accidental chapter title or beat header repetition from Beat 2..N."""
        cleaned = beat_text.strip()
        # Remove leading markdown chapter title if repeated in subsequent beats
        cleaned = re.sub(
            rf"^#\s*Bab\s*{chap_num}\b.*?\n+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        # Remove leading "## Beat X..." or "**Beat X...**" if the LLM added a beat subheader
        cleaned = re.sub(
            r"^(?:#{1,4}\s*|\*\*\s*)Beat\s*\d+[^\n]*\n+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        return cleaned

    def _build_contexts(self, project: NovelProject) -> tuple[str, str]:
        """Build character and world lore strings from project."""
        char_context_parts = []
        for c in project.characters:
            char_context_parts.append(
                f"- Nama: {c.get('name')}\n"
                f"  Peran: {c.get('role')}\n"
                f"  Ciri Fisik: {c.get('appearance')}\n"
                f"  Sifat & Flaw: {c.get('personality')} (Flaw: {c.get('flaw')})\n"
                f"  Motivasi Dalam: {c.get('internal_motivation', '')}\n"
                f"  Gaya Bicara: {c.get('speech_mannerism')}\n"
            )
        characters_context = "\n".join(char_context_parts) or "Ikuti karakter sesuai deskripsi bab."

        world_context = (
            f"Latar Utama: {project.world_bible.get('setting_name')}\n"
            f"Atmosfer: {project.world_bible.get('atmosphere')}\n"
            f"Aturan Khusus: {project.world_bible.get('rules_and_systems')}\n"
        )
        source_summary = project.metadata.get("source_summary", "")
        if source_summary:
            world_context += f"Referensi Artikel Sumber: {source_summary}\n"
        return characters_context, world_context

    def write_chapter(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        beats: List[Dict[str, Any]],
        custom_instructions: str = "",
        beat_by_beat: bool = True,
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
    ) -> str:
        """Draft prose for the specified chapter strictly based on beats and world lore."""
        chap_num = chapter_info.get("chapter_number", 1)
        chap_title = chapter_info.get("title", f"Bab {chap_num}")
        meta = project.metadata
        lang = meta.get("language", "Indonesian")
        target_words = int(meta.get("target_words_per_chapter", 2000))

        normalized_beats = ScenePlannerAgent.normalize_beats(beats, chapter_info=chapter_info)
        characters_context, world_context = self._build_contexts(project)
        continuity_summary = project.get_continuity_summary(up_to_chapter=chap_num)
        beats_blueprint = self.format_beats_blueprint(normalized_beats, target_words=target_words)
        system_prompt = WRITER_SYSTEM.format(language=lang)
        user_notes = custom_instructions.strip() or "Tulis secara utuh, mendalam, ekspresif, dan tanpa sensor sesuai tiap beat."

        if beat_by_beat and len(normalized_beats) > 1:
            total_beats = len(normalized_beats)
            words_per_beat = max(400, int(target_words / total_beats))
            accumulated_parts: List[str] = []

            for idx, beat in enumerate(normalized_beats, 1):
                if progress_callback:
                    progress_callback(idx, total_beats, beat)

                if idx == 1:
                    heading_instruction = (
                        f"Awali langsung dengan judul bab `# Bab {chap_num}: {chap_title}` "
                        f"lalu tulis paragraf pembuka Beat 1."
                    )
                    prev_text = "(Ini adalah Beat 1 / awal bab. Belum ada paragraf sebelumnya di bab ini.)"
                else:
                    heading_instruction = (
                        "JANGAN menulis ulang judul `# Bab ...`. Lanjutkan langsung paragraf baru "
                        "yang menyambung mulus dari kalimat terakhir Beat sebelumnya."
                    )
                    joined_so_far = "\n\n".join(accumulated_parts)
                    words_so_far = joined_so_far.split()
                    tail_words = " ".join(words_so_far[-450:]) if len(words_so_far) > 450 else joined_so_far
                    prev_text = f"...{tail_words}"

                if idx < total_beats:
                    next_beat = normalized_beats[idx]
                    next_beat_hint = f"Beat {idx + 1}: {next_beat.get('beat_name', '')}"
                else:
                    next_beat_hint = "Akhir Bab (tuntaskan Beat terakhir ini tepat pada Titik Balik Akhir Bab)"

                beat_prompt = WRITER_BEAT_TEMPLATE.format(
                    chapter_number=chap_num,
                    chapter_title=chap_title,
                    language=lang,
                    genre=meta.get("genre", "Fiksi"),
                    tone=meta.get("tone", "Realistis"),
                    premise=meta.get("premise", ""),
                    chapter_summary=chapter_info.get("summary", ""),
                    beat_number=idx,
                    total_beats=total_beats,
                    pov_character=chapter_info.get("pov_character", "Protagonis"),
                    setting=chapter_info.get("setting", ""),
                    conflict=chapter_info.get("conflict", ""),
                    turning_point=chapter_info.get("turning_point", ""),
                    custom_instructions=user_notes,
                    all_beats_overview=beats_blueprint,
                    beat_name=beat.get("beat_name", f"Adegan {idx}"),
                    scene_events=beat.get("scene_events", beat.get("goal", "")),
                    goal=beat.get("goal", ""),
                    obstacle=beat.get("obstacle", ""),
                    sensory_details=beat.get("sensory_details", ""),
                    emotional_shift=beat.get("emotional_shift", ""),
                    target_beat_words=words_per_beat,
                    characters_context=characters_context,
                    world_context=world_context,
                    continuity_summary=continuity_summary,
                    previous_beats_text=prev_text,
                    heading_instruction=heading_instruction,
                    next_beat_hint=next_beat_hint,
                )

                beat_prose = self.llm.generate(
                    prompt=beat_prompt,
                    system_instruction=system_prompt,
                    temperature=0.75,
                )

                if idx == 1:
                    cleaned_part = beat_prose.strip()
                    if not cleaned_part.startswith("#"):
                        cleaned_part = f"# Bab {chap_num}: {chap_title}\n\n{cleaned_part}"
                else:
                    cleaned_part = self._clean_beat_continuation(beat_prose, chap_num, chap_title)

                if cleaned_part:
                    accumulated_parts.append(cleaned_part)
                    # Save incremental progress after each beat
                    project.save_chapter(
                        chap_num,
                        "\n\n".join(accumulated_parts),
                        beats=normalized_beats,
                    )

            chapter_prose = "\n\n".join(accumulated_parts)
            project.save_chapter(chap_num, chapter_prose, beats=normalized_beats)
            return chapter_prose

        # Single-pass structured mode
        user_prompt = WRITER_USER_TEMPLATE.format(
            chapter_number=chap_num,
            chapter_title=chap_title,
            genre=meta.get("genre", "Fiksi"),
            tone=meta.get("tone", "Realistis"),
            premise=meta.get("premise", ""),
            chapter_summary=chapter_info.get("summary", ""),
            pov_character=chapter_info.get("pov_character", "Protagonis"),
            setting=chapter_info.get("setting", ""),
            conflict=chapter_info.get("conflict", ""),
            turning_point=chapter_info.get("turning_point", ""),
            target_words=target_words,
            custom_instructions=user_notes,
            beats_json=beats_blueprint,
            characters_context=characters_context,
            world_context=world_context,
            continuity_summary=continuity_summary,
        )

        chapter_prose = self.llm.generate(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.75,
        )

        project.save_chapter(chap_num, chapter_prose, beats=normalized_beats)
        return chapter_prose
