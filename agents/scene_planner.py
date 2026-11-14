"""Scene Planner Agent: Plans micro-beats for individual chapters."""

from typing import Any, Dict, List, Union
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import SCENE_PLANNER_SYSTEM, SCENE_PLANNER_USER_TEMPLATE


class ScenePlannerAgent:
    """Agent responsible for structuring a single chapter into 3-5 scene beats."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    @staticmethod
    def extract_beats_list(raw_data: Union[Dict[str, Any], List[Any]]) -> List[Dict[str, Any]]:
        """Robustly unpack a list of beat dicts from any JSON structure returned by LLM."""
        if isinstance(raw_data, list):
            items = raw_data
        elif isinstance(raw_data, dict):
            # Look for common beat list keys first
            items = None
            for key in ("beats", "scene_beats", "beat_sheet", "chapter_beats", "scenes", "adegan", "data"):
                val = raw_data.get(key)
                if isinstance(val, list):
                    items = val
                    break
            # Fallback: find any key whose value is a list of dicts
            if items is None:
                for val in raw_data.values():
                    if isinstance(val, list) and val:
                        items = val
                        break
            # If the dict itself is a single beat object
            if items is None:
                items = [raw_data]
        else:
            items = []

        return ScenePlannerAgent.normalize_beats(items)

    @staticmethod
    def normalize_beats(beats: List[Any], chapter_info: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Ensure every beat is a well-formed dict with all required fields."""
        normalized: List[Dict[str, Any]] = []
        for idx, b in enumerate(beats, 1):
            if isinstance(b, str):
                normalized.append({
                    "beat_number": idx,
                    "beat_name": f"Beat {idx}",
                    "scene_events": b.strip(),
                    "goal": "Menggerakkan alur adegan maju",
                    "obstacle": "Ketegangan dalam situasi adegan",
                    "sensory_details": "Suasana lokasi, ekspresi wajah, dan gestur fisik",
                    "emotional_shift": "Perkembangan emosi sesuai kejadian",
                })
            elif isinstance(b, dict):
                beat_num = b.get("beat_number") or b.get("number") or b.get("no") or idx
                beat_name = (
                    b.get("beat_name")
                    or b.get("title")
                    or b.get("name")
                    or b.get("judul")
                    or f"Adegan {idx}"
                )
                goal = b.get("goal") or b.get("tujuan") or b.get("objective") or ""
                obstacle = b.get("obstacle") or b.get("conflict") or b.get("hambatan") or b.get("konflik") or ""
                scene_events = (
                    b.get("scene_events")
                    or b.get("events")
                    or b.get("description")
                    or b.get("action")
                    or b.get("summary")
                    or b.get("kejadian")
                    or f"{goal}. {obstacle}".strip(". ")
                )
                sensory = (
                    b.get("sensory_details")
                    or b.get("sensory")
                    or b.get("panca_indera")
                    or "Detail visual, suara, aroma, dan sensasi fisik secara nyata"
                )
                emotional = (
                    b.get("emotional_shift")
                    or b.get("emotion")
                    or b.get("emosi")
                    or "Perubahan tensi emosional karakter"
                )
                normalized.append({
                    "beat_number": int(beat_num) if str(beat_num).isdigit() else idx,
                    "beat_name": str(beat_name).strip(),
                    "scene_events": str(scene_events).strip(),
                    "goal": str(goal).strip() or str(scene_events).strip(),
                    "obstacle": str(obstacle).strip() or "Konflik dan ketegangan adegan",
                    "sensory_details": str(sensory).strip(),
                    "emotional_shift": str(emotional).strip(),
                })

        # Fallback if LLM returned empty list
        if not normalized and chapter_info:
            summary = chapter_info.get("summary", "Peristiwa utama bab")
            conflict = chapter_info.get("conflict", "Konflik utama bab")
            turning_point = chapter_info.get("turning_point", "Titik balik akhir bab")
            normalized = [
                {
                    "beat_number": 1,
                    "beat_name": "Pembuka & Pembangunan Atmosfer",
                    "scene_events": f"Memulai adegan di {chapter_info.get('setting', 'lokasi')}: {summary}",
                    "goal": "Masuk ke situasi awal bab",
                    "obstacle": "Ketegangan awal yang menghadang karakter",
                    "sensory_details": "Suasana ruang, pencahayaan, suara sekitar, dan sensasi fisik",
                    "emotional_shift": "Dari waspada menjadi terlibat penuh",
                },
                {
                    "beat_number": 2,
                    "beat_name": "Eskalasi Konflik Inti",
                    "scene_events": f"Konfrontasi dan gesekan utama: {conflict}",
                    "goal": "Menghadapi rintangan utama di bab ini",
                    "obstacle": conflict,
                    "sensory_details": "Detak jantung, tatapan tajam, gestur tubuh, dan dialog intens",
                    "emotional_shift": "Tensi memuncak drastis",
                },
                {
                    "beat_number": 3,
                    "beat_name": "Klimaks Bab & Titik Balik",
                    "scene_events": f"Puncak adegan yang berujung pada: {turning_point}",
                    "goal": "Menuntaskan konfrontasi atau mengambil keputusan krusial",
                    "obstacle": "Konsekuensi langsung yang tak terhindarkan",
                    "sensory_details": "Napas memburu, keheningan setelah badai, detail viseral",
                    "emotional_shift": turning_point,
                },
            ]

        # Re-number sequentially 1..N
        for i, item in enumerate(normalized, 1):
            item["beat_number"] = i

        return normalized

    def generate_beats(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        custom_direction: str = "",
    ) -> List[Dict[str, Any]]:
        """Generate scene beats for a specific chapter."""
        chap_num = chapter_info.get("chapter_number", 1)
        meta = project.metadata
        lang = meta.get("language", "Indonesian")

        continuity_summary = project.get_continuity_summary(up_to_chapter=chap_num)

        system_prompt = SCENE_PLANNER_SYSTEM.format(language=lang)
        user_prompt = SCENE_PLANNER_USER_TEMPLATE.format(
            chapter_number=chap_num,
            chapter_title=chapter_info.get("title", f"Bab {chap_num}"),
            genre=meta.get("genre", "Fiksi"),
            tone=meta.get("tone", "Realistis"),
            premise=meta.get("premise", ""),
            chapter_summary=chapter_info.get("summary", ""),
            pov_character=chapter_info.get("pov_character", "Protagonis"),
            setting=chapter_info.get("setting", ""),
            conflict=chapter_info.get("conflict", ""),
            turning_point=chapter_info.get("turning_point", ""),
            custom_direction=custom_direction.strip() or "Ikuti alur dan konflik bab secara mendalam, berani, dan tanpa sensor.",
            continuity_summary=continuity_summary,
        )

        beats_data = self.llm.generate_json(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.65,
        )

        beats = self.extract_beats_list(beats_data)
        beats = self.normalize_beats(beats, chapter_info=chapter_info)
        project.save_chapter_beats(chap_num, beats)
        return beats
