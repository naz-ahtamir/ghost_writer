"""Illustrator Agent: Plans and renders 3 consistent, photorealistic, uncensored illustrations per chapter."""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import config
from core.image_gen import (
    DEFAULT_NEGATIVE_PROMPT,
    ImageGeneratorClient,
    compute_deterministic_seed,
)
from core.llm import LLMClient
from core.project import NovelProject
from core.prompts import (
    CHAPTER_ILLUSTRATIONS_USER_TEMPLATE,
    ILLUSTRATOR_SYSTEM,
    VISUAL_BIBLE_SYSTEM,
    VISUAL_BIBLE_USER_TEMPLATE,
)

DEFAULT_STYLE_ANCHOR = (
    "Candid live-action DSLR photograph shot on Sony A7R V, 35mm f/2.8 lens, "
    "medium-wide three-quarter body shot showing expressive body pose and detailed background environment, "
    "authentic human facial expression, natural skin texture with visible pores, "
    "realistic clothing fabric folds, crisp environmental depth, photorealistic cinematic film still, raw camera photo, 8k"
)

SLOT_ROLES = [
    ("opening", "Pembuka Bab (Establishing Scene)"),
    ("middle", "Konflik Inti (Mid-Chapter Escalation)"),
    ("climax", "Klimaks / Titik Balik (Chapter Climax)"),
]

# Fallback dictionary to translate common Indonesian character/scene descriptors into English for FLUX.1
ID_TO_EN_VISUAL_TERMS = [
    (r"\bpria\b|\blaki-laki\b|\bcowok\b", "man"),
    (r"\bwanita\b|\bperempuan\b|\bcewek\b", "woman"),
    (r"\bmuda\b", "young"),
    (r"\bremaja\b", "young adult"),
    (r"\bdewasa\b", "adult"),
    (r"\brambut hitam\b", "dark black hair"),
    (r"\brambut panjang\b", "long flowing hair"),
    (r"\brambut pendek\b", "short textured hair"),
    (r"\bmata tajam\b|\btatapan tajam\b", "intense piercing gaze"),
    (r"\bkulit sawo matang\b", "warm tan natural skin"),
    (r"\bkulit putih\b|\bkulit cerah\b", "fair natural skin"),
    (r"\brahang tegas\b", "sharp defined jawline"),
    (r"\btubuh atletis\b|\bberotot\b", "athletic toned physique"),
    (r"\blangsing\b|\bsemampai\b", "slender graceful figure"),
    (r"\bjaket kulit\b", "dark leather jacket"),
    (r"\bkemeja\b", "tailored button-down shirt"),
    (r"\bgaun\b", "flowing dress"),
    (r"\bkamar tidur\b|\bkamar\b", "dimly lit bedroom interior with bed and warm lamp"),
    (r"\bruang tamu\b|\bruangan\b", "detailed indoor room interior with furniture and windows"),
    (r"\bjalanan\b|\bkota\b", "atmospheric city street with architectural depth"),
    (r"\bhujan\b", "rain-slicked surfaces and falling rain"),
    (r"\bmalam\b", "nighttime dramatic lighting"),
    (r"\bmemeluk\b|\bpelukan\b", "embracing closely with hands on waist and shoulders"),
    (r"\bberdiri\b", "standing in dynamic posture"),
    (r"\bduduk\b", "sitting with expressive body language"),
]


def _enrich_english_visual_description(text: str) -> str:
    """Ensure fallback Indonesian visual phrases are accompanied by clear English terms for FLUX.1."""
    if not text:
        return ""
    result = text
    for pattern, eng in ID_TO_EN_VISUAL_TERMS:
        result = re.sub(pattern, eng, result, flags=re.IGNORECASE)
    return result


def _upgrade_camera_framing_for_pose_and_background(camera_shot: str) -> str:
    """Ensure camera framing always shows body pose and detailed background (never a blurry passport headshot)."""
    if not camera_shot:
        return (
            "Candid live-action DSLR medium-wide three-quarter body shot, "
            "Sony A7R V 35mm f/2.8 lens, deep environmental focus showing full pose and room background"
        )
    cam = camera_shot.strip()
    # Replace close-up / extreme close-up with three-quarter / medium-wide framing so body pose is visible
    cam = re.sub(
        r"\b(extreme\s+close[\s-]*up|tight\s+close[\s-]*up|close[\s-]*up\s+shot|close[\s-]*up|headshot|portrait\s+shot)\b",
        "medium-wide three-quarter body DSLR shot showing torso, hands, pose, and background",
        cam,
        flags=re.IGNORECASE,
    )
    # Replace background-blurring terms with crisp environmental focus
    cam = re.sub(
        r"\b(shallow\s+depth\s+of\s+field|heavy\s+bokeh|blurred\s+background|bokeh\s+background)\b",
        "crisp environmental focus with detailed background architecture",
        cam,
        flags=re.IGNORECASE,
    )
    if "dslr" not in cam.lower() and "sony" not in cam.lower() and "canon" not in cam.lower():
        cam = f"Candid live-action DSLR photograph ({cam})"
    return cam


class IllustratorAgent:
    """Agent responsible for visual continuity (Visual Bible) and 3 chapter illustrations."""

    def __init__(
        self,
        llm: LLMClient,
        image_client: Optional[ImageGeneratorClient] = None,
    ):
        self.llm = llm
        self.image_client = image_client or ImageGeneratorClient()

    def ensure_visual_bible(
        self,
        project: NovelProject,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """Ensure the project has a locked Visual Bible and Character Visual DNA registry."""
        if project.is_visual_bible_complete() and not force_regenerate:
            # Ensure any newly added characters are synced into the registry
            self._sync_characters_with_visual_bible(project)
            return project.visual_bible

        meta = project.metadata
        lang = meta.get("language", "Indonesian")
        wb = project.world_bible or {}

        world_context = (
            f"Setting: {wb.get('setting_name', 'Dunia Cerita')}\n"
            f"Time Period: {wb.get('time_period', 'Kontemporer / Sesuai Cerita')}\n"
            f"Atmosphere: {wb.get('atmosphere', 'Sinematik dan dramatis')}\n"
            f"Rules/Systems: {wb.get('rules_and_systems', '')}"
        )

        chars_slim = []
        for c in project.characters:
            chars_slim.append({
                "name": c.get("name", "Tokoh"),
                "role": c.get("role", ""),
                "appearance": c.get("appearance", ""),
                "visual_dna": c.get("visual_dna", ""),
                "personality": c.get("personality", ""),
            })

        visual_data: Dict[str, Any] = {}
        if self.llm and self.llm.is_configured():
            try:
                sys_prompt = VISUAL_BIBLE_SYSTEM.format(language=lang)
                user_prompt = VISUAL_BIBLE_USER_TEMPLATE.format(
                    title=meta.get("title", "Novel"),
                    genre=meta.get("genre", "Drama / Fiksi"),
                    tone=meta.get("tone", "Realistis & Mendalam"),
                    world_context=world_context,
                    characters_json=json.dumps(chars_slim, ensure_ascii=False, indent=2),
                )
                raw = self.llm.generate_json(
                    prompt=user_prompt,
                    system_instruction=sys_prompt,
                    temperature=0.5,
                )
                if isinstance(raw, dict):
                    visual_data = raw
            except Exception:
                visual_data = {}

        master_seed = compute_deterministic_seed(project.project_dir.name)
        style_anchor = visual_data.get("style_anchor_tags") or DEFAULT_STYLE_ANCHOR
        if "photorealistic" not in style_anchor.lower():
            style_anchor = f"{DEFAULT_STYLE_ANCHOR}, {style_anchor}"

        registry_map: Dict[str, Dict[str, Any]] = {}
        raw_registry = visual_data.get("character_visual_registry", [])
        if isinstance(raw_registry, list):
            for entry in raw_registry:
                if isinstance(entry, dict) and entry.get("name"):
                    registry_map[entry["name"].strip().lower()] = entry

        final_registry: List[Dict[str, Any]] = []
        characters_updated = False

        for c in project.characters:
            c_name = c.get("name", "Tokoh").strip()
            c_key = c_name.lower()
            matched = registry_map.get(c_key, {})

            dna = (
                matched.get("visual_dna")
                or c.get("visual_dna")
                or self._build_fallback_character_dna(c, wb)
            ).strip()

            posture = matched.get(
                "signature_expression_and_posture",
                "expressive realistic gaze, natural anatomical posture",
            )
            char_seed = compute_deterministic_seed(f"{project.project_dir.name}:{c_name}")

            if c.get("visual_dna") != dna:
                c["visual_dna"] = dna
                characters_updated = True

            final_registry.append({
                "name": c_name,
                "role": c.get("role", ""),
                "visual_dna": dna,
                "signature_expression_and_posture": posture,
                "character_seed": char_seed,
            })

        if characters_updated:
            project.save_characters(project.characters)

        complete_visual_bible = {
            "visual_style_preset": visual_data.get(
                "visual_style_preset", "Photorealistic Cinematic 8K Film Still (Uncensored)"
            ),
            "style_anchor_tags": style_anchor,
            "color_grading_and_lighting": visual_data.get(
                "color_grading_and_lighting",
                f"cinematic chiaroscuro lighting, rich natural shadows, atmospheric {wb.get('atmosphere', 'mood')}",
            ),
            "environment_visual_rules": visual_data.get(
                "environment_visual_rules",
                f"hyper-detailed realistic environment set in {wb.get('setting_name', 'the story world')}",
            ),
            "negative_prompt": visual_data.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT,
            "master_seed": master_seed,
            "character_visual_registry": final_registry,
        }

        project.save_visual_bible(complete_visual_bible)
        return complete_visual_bible

    def _sync_characters_with_visual_bible(self, project: NovelProject) -> None:
        """Ensure all characters in project.characters exist in visual_bible registry and upgrade legacy style anchor."""
        vb = project.visual_bible
        registry = vb.get("character_visual_registry", [])
        if not isinstance(registry, list):
            registry = []
        existing_names = {
            item.get("name", "").strip().lower(): item
            for item in registry
            if isinstance(item, dict)
        }
        changed = False
        old_anchor = vb.get("style_anchor_tags", "")
        if "shallow depth of field" in old_anchor.lower():
            vb["style_anchor_tags"] = re.sub(
                r"\bshallow\s+depth\s+of\s+field\b",
                "medium-wide three-quarter body framing, crisp environmental background detail",
                old_anchor,
                flags=re.IGNORECASE,
            )
            changed = True

        for c in project.characters:
            c_name = c.get("name", "").strip()
            if not c_name:
                continue
            key = c_name.lower()
            if key not in existing_names:
                dna = c.get("visual_dna") or self._build_fallback_character_dna(c, project.world_bible)
                c["visual_dna"] = dna
                registry.append({
                    "name": c_name,
                    "role": c.get("role", ""),
                    "visual_dna": dna,
                    "signature_expression_and_posture": "expressive realistic gaze, natural posture",
                    "character_seed": compute_deterministic_seed(f"{project.project_dir.name}:{c_name}"),
                })
                changed = True
            else:
                # Sync DNA if character table has updated visual_dna
                if c.get("visual_dna") and existing_names[key].get("visual_dna") != c["visual_dna"]:
                    existing_names[key]["visual_dna"] = c["visual_dna"]
                    changed = True
                elif not c.get("visual_dna") and existing_names[key].get("visual_dna"):
                    c["visual_dna"] = existing_names[key]["visual_dna"]
                    changed = True

        if changed:
            vb["character_visual_registry"] = registry
            project.save_characters(project.characters)
            project.save_visual_bible(vb)

    @staticmethod
    def _build_fallback_character_dna(char: Dict[str, Any], world_bible: Dict[str, Any]) -> str:
        """Construct a detailed photorealistic character DNA string from character profile fields."""
        name = char.get("name", "Character")
        raw_appearance = char.get("appearance", "distinctive realistic facial features, natural skin texture")
        appearance = _enrich_english_visual_description(raw_appearance)
        role = _enrich_english_visual_description(char.get("role", "lead character"))
        return (
            f"{name} ({role}, realistic human appearance: {appearance}, "
            f"consistent facial bone structure, expressive eyes, natural skin pores)"
        )

    def get_character_dna_map(self, project: NovelProject) -> Dict[str, Dict[str, Any]]:
        """Return lowercase name -> character visual registry dict."""
        vb = self.ensure_visual_bible(project)
        dna_map: Dict[str, Dict[str, Any]] = {}
        for item in vb.get("character_visual_registry", []):
            if isinstance(item, dict) and item.get("name"):
                dna_map[item["name"].strip().lower()] = item
        return dna_map

    def compose_consistent_prompt(
        self,
        project: NovelProject,
        illus_item: Dict[str, Any],
    ) -> str:
        """Assemble a natural English DSLR photography prompt prioritizing Pose, Expression, Background, and Character DNA."""
        vb = self.ensure_visual_bible(project)
        style_anchor = vb.get("style_anchor_tags", DEFAULT_STYLE_ANCHOR)
        lighting_anchor = vb.get("color_grading_and_lighting", "")
        dna_map = self.get_character_dna_map(project)

        raw_camera = illus_item.get("camera_shot", "").strip()
        camera = _upgrade_camera_framing_for_pose_and_background(raw_camera)
        pose = _enrich_english_visual_description(illus_item.get("pose_and_action", "").strip())
        env = _enrich_english_visual_description(illus_item.get("environment_and_lighting", "").strip())
        raw_prompt = illus_item.get("image_prompt", "").strip()

        # Collect locked DNA for characters present in this illustration
        chars_present = illus_item.get("characters_present", [])
        if isinstance(chars_present, str):
            chars_present = [c.strip() for c in chars_present.split(",") if c.strip()]

        dna_segments: List[str] = []
        for ch_name in chars_present:
            ch_key = ch_name.strip().lower()
            matched = dna_map.get(ch_key)
            if not matched:
                for k, v in dna_map.items():
                    if ch_key in k or k in ch_key:
                        matched = v
                        break
            if matched and matched.get("visual_dna"):
                dna_str = matched["visual_dna"].strip()
                dna_segments.append(f"{matched['name']} ({dna_str})")

        # Token priority for FLUX.1 (CLIP-L reads first 77 tokens; T5-XXL reads up to 512 tokens):
        # 1. DSLR Camera Framing (medium-wide / three-quarter body shot + deep focus)
        # 2. Expressive Body Pose, Action, Hands, & Facial Expression
        # 3. Detailed Background Setting & Lighting
        # 4. Locked Character Visual DNA
        # 5. Master Style Anchor & Color/Lighting Rules
        parts: List[str] = [camera]
        if pose:
            parts.append(
                f"Dynamic expressive body pose and action: {pose}"
            )
        elif raw_prompt:
            parts.append(raw_prompt)

        if env:
            parts.append(
                f"Detailed background environment and atmosphere: {env}"
            )

        if dna_segments:
            parts.append("Featuring " + " and ".join(dna_segments))

        if lighting_anchor and lighting_anchor.lower() not in env.lower():
            parts.append(lighting_anchor)

        if style_anchor:
            parts.append(style_anchor)

        combined = ". ".join(p.strip().rstrip(".") for p in parts if p and p.strip()) + "."
        return combined

    def compute_slot_seed(
        self,
        project: NovelProject,
        chapter_num: int,
        illus_num: int,
        characters_present: Optional[List[str]] = None,
    ) -> int:
        """Compute a consistent seed anchored to the project and primary character."""
        vb = self.ensure_visual_bible(project)
        master_seed = int(vb.get("master_seed", compute_deterministic_seed(project.project_dir.name)))
        dna_map = self.get_character_dna_map(project)

        if characters_present:
            first_char = str(characters_present[0]).strip().lower()
            for k, v in dna_map.items():
                if first_char == k or first_char in k or k in first_char:
                    return int(v.get("character_seed", master_seed)) + (chapter_num * 10) + illus_num

        return master_seed + (chapter_num * 100) + illus_num

    @staticmethod
    def extract_illustrations_list(raw_data: Any) -> List[Dict[str, Any]]:
        """Unpack illustrations array from any JSON structure returned by LLM."""
        if isinstance(raw_data, list):
            return [x for x in raw_data if isinstance(x, dict)]
        if isinstance(raw_data, dict):
            for key in ("illustrations", "scenes", "images", "ilustrasi", "frames", "data"):
                val = raw_data.get(key)
                if isinstance(val, list):
                    return [x for x in val if isinstance(x, dict)]
            for val in raw_data.values():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return val
            if "image_prompt" in raw_data or "scene_title" in raw_data:
                return [raw_data]
        return []

    def normalize_illustrations(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        raw_list: List[Dict[str, Any]],
        target_count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Ensure exactly target_count (default 3) structured, consistent illustrations per chapter."""
        chap_num = int(chapter_info.get("chapter_number", 1))
        chap_title = chapter_info.get("title", f"Bab {chap_num}")
        pov_char = chapter_info.get("pov_character") or (
            project.characters[0].get("name", "Protagonis") if project.characters else "Protagonis"
        )
        setting = chapter_info.get("setting") or project.world_bible.get("setting_name", "Lokasi Utama")
        vb = self.ensure_visual_bible(project)
        neg_default = vb.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
        saved_beats = project.get_chapter_beats(chap_num) or []

        normalized: List[Dict[str, Any]] = []
        for idx in range(1, target_count + 1):
            role_code, role_label = SLOT_ROLES[(idx - 1) % len(SLOT_ROLES)]
            src = raw_list[idx - 1] if idx - 1 < len(raw_list) else {}

            # Map slot index (1=opening, 2=middle, 3=climax) to corresponding chapter beat if available
            matched_beat: Dict[str, Any] = {}
            if saved_beats:
                if idx == 1:
                    matched_beat = saved_beats[0]
                elif idx == target_count:
                    matched_beat = saved_beats[-1]
                else:
                    matched_beat = saved_beats[len(saved_beats) // 2]

            chars_present = src.get("characters_present") or [pov_char]
            if isinstance(chars_present, str):
                chars_present = [c.strip() for c in chars_present.split(",") if c.strip()]

            beat_title = matched_beat.get("beat_name", "")
            beat_events = matched_beat.get("scene_events") or matched_beat.get("goal", "")
            beat_sensory = matched_beat.get("sensory_details", "")

            default_titles = {
                1: beat_title or f"Awal Adegan di {setting}",
                2: beat_title or f"Ketegangan Konflik Bab {chap_num}",
                3: beat_title or f"Puncak Klimaks: {chap_title}",
            }
            default_poses = {
                1: f"{pov_char} in dynamic three-quarter body posture inside {setting}, {beat_events}, {beat_sensory}, expressive hand gestures, authentic facial emotion, natural skin texture".strip(", "),
                2: f"Expressive physical interaction and body language involving {', '.join(chars_present)}, {beat_events}, {beat_sensory}, visible torso and hands, intense emotional eye contact".strip(", "),
                3: f"Climactic dramatic full/three-quarter body pose for {', '.join(chars_present)}, {beat_events}, {beat_sensory}, high emotional and physical intensity, visceral facial expression".strip(", "),
            }
            default_cameras = {
                1: "Candid live-action DSLR medium-wide environmental shot, Sony A7R V 28mm f/2.8 lens, showing full body pose and crisp surrounding architecture",
                2: "Candid live-action DSLR three-quarter body two-shot, Canon EOS R5 35mm f/2.8 lens, showing body posture, hand gestures, expressive faces, and detailed room background",
                3: "Dynamic live-action DSLR medium-full body shot, low-angle 35mm f/2.8 lens, capturing full physical action, intense facial expression, and dramatic environmental lighting",
            }

            item: Dict[str, Any] = {
                "illustration_number": idx,
                "slot_role": src.get("slot_role") or role_code,
                "slot_label": role_label,
                "scene_title": (src.get("scene_title") or default_titles.get(idx, f"Ilustrasi {idx}")).strip(),
                "caption": (
                    src.get("caption")
                    or f"Ilustrasi {idx} — {src.get('scene_title') or default_titles.get(idx, chap_title)}"
                ).strip(),
                "characters_present": chars_present,
                "camera_shot": (src.get("camera_shot") or default_cameras.get(idx, default_cameras[2])).strip(),
                "pose_and_action": (src.get("pose_and_action") or default_poses.get(idx, default_poses[2])).strip(),
                "environment_and_lighting": (
                    src.get("environment_and_lighting")
                    or f"Detailed {setting} environment, {vb.get('color_grading_and_lighting', 'dramatic realistic lighting')}"
                ).strip(),
                "image_prompt": (src.get("image_prompt") or "").strip(),
                "negative_prompt": (src.get("negative_prompt") or neg_default).strip(),
                "seed": int(
                    src.get("seed")
                    or self.compute_slot_seed(project, chap_num, idx, chars_present)
                ),
                "image_path": src.get("image_path") or str(project.get_illustration_image_path(chap_num, idx)),
                "status": src.get("status", "planned"),
                "engine": src.get("engine", ""),
            }

            # Lock consistent DNA and photorealistic style anchor into image_prompt
            item["image_prompt"] = self.compose_consistent_prompt(project, item)
            normalized.append(item)

        return normalized

    def plan_chapter_illustrations(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        count: int = config.ILLUSTRATIONS_PER_CHAPTER,
        custom_direction: str = "",
    ) -> List[Dict[str, Any]]:
        """Generate 3 consistent, realistic, uncensored illustration blueprints for a chapter."""
        chap_num = int(chapter_info.get("chapter_number", 1))
        chap_title = chapter_info.get("title", f"Bab {chap_num}")
        lang = project.metadata.get("language", "Indonesian")

        vb = self.ensure_visual_bible(project)
        dna_lines = []
        for entry in vb.get("character_visual_registry", []):
            dna_lines.append(
                f"  • {entry.get('name')} ({entry.get('role', 'Tokoh')}): {entry.get('visual_dna')}"
            )
        character_dna_list = "\n".join(dna_lines) or "  • Gunakan deskripsi fisik tokoh utama secara konsisten."

        # Gather chapter prose and/or beats for accurate visual adaptation
        prose = project.get_chapter(chap_num) or ""
        beats = project.get_chapter_beats(chap_num) or []

        context_parts: List[str] = []
        if beats:
            beat_lines = []
            for b in beats:
                beat_lines.append(
                    f"- Beat {b.get('beat_number')}: {b.get('beat_name')} | "
                    f"Kejadian: {b.get('scene_events', b.get('goal', ''))} | "
                    f"Sensorik: {b.get('sensory_details', '')}"
                )
            context_parts.append("SCENE BEATS BAB INI:\n" + "\n".join(beat_lines))

        if prose:
            # Take beginning, middle, and ending excerpts of chapter prose
            words = prose.split()
            if len(words) <= 900:
                context_parts.append(f"NASKAH BAB:\n{prose}")
            else:
                third = len(words) // 3
                opening_snip = " ".join(words[:300])
                mid_snip = " ".join(words[third:third + 300])
                end_snip = " ".join(words[-300:])
                context_parts.append(
                    f"CUPLIKAN AWAL BAB:\n{opening_snip}\n\n"
                    f"CUPLIKAN TENGAH BAB:\n{mid_snip}\n\n"
                    f"CUPLIKAN AKHIR / KLIMAKS BAB:\n{end_snip}"
                )
        else:
            context_parts.append(
                f"RINGKASAN BAB: {chapter_info.get('summary', '')}\n"
                f"KONFLIK: {chapter_info.get('conflict', '')}\n"
                f"TITIK BALIK: {chapter_info.get('turning_point', '')}"
            )

        chapter_content_context = "\n\n".join(context_parts)

        raw_list: List[Dict[str, Any]] = []
        if self.llm and self.llm.is_configured():
            sys_prompt = ILLUSTRATOR_SYSTEM.format(language=lang)
            user_prompt = CHAPTER_ILLUSTRATIONS_USER_TEMPLATE.format(
                illustration_count=count,
                chapter_number=chap_num,
                chapter_title=chap_title,
                pov_character=chapter_info.get("pov_character", "Protagonis"),
                setting=chapter_info.get("setting", ""),
                conflict=chapter_info.get("conflict", ""),
                turning_point=chapter_info.get("turning_point", ""),
                custom_direction=custom_direction.strip() or "Visualisasikan secara fotorealistis, ekspresif, konsisten, dan tanpa sensor sesuai naskah.",
                style_anchor_tags=vb.get("style_anchor_tags", DEFAULT_STYLE_ANCHOR),
                color_grading_and_lighting=vb.get("color_grading_and_lighting", ""),
                environment_visual_rules=vb.get("environment_visual_rules", ""),
                character_dna_list=character_dna_list,
                chapter_content_context=chapter_content_context,
                language=lang,
            )
            try:
                raw_json = self.llm.generate_json(
                    prompt=user_prompt,
                    system_instruction=sys_prompt,
                    temperature=0.65,
                )
                raw_list = self.extract_illustrations_list(raw_json)
            except Exception:
                # Second-chance anti-refusal retry using structured beat summary & art-house cinema framing
                try:
                    fallback_context = (
                        f"RINGKASAN BAB: {chapter_info.get('summary', '')}\n"
                        f"KONFLIK: {chapter_info.get('conflict', '')}\n"
                        f"TITIK BALIK: {chapter_info.get('turning_point', '')}"
                    )
                    if beats:
                        fallback_context += "\nBEATS: " + " | ".join(
                            f"Beat {b.get('beat_number')}: {b.get('beat_name')} ({b.get('goal', '')})"
                            for b in beats
                        )
                    retry_prompt = CHAPTER_ILLUSTRATIONS_USER_TEMPLATE.format(
                        illustration_count=count,
                        chapter_number=chap_num,
                        chapter_title=chap_title,
                        pov_character=chapter_info.get("pov_character", "Protagonis"),
                        setting=chapter_info.get("setting", ""),
                        conflict=chapter_info.get("conflict", ""),
                        turning_point=chapter_info.get("turning_point", ""),
                        custom_direction=(
                            "Gunakan bahasa fotografi sinematik R-rated Art-House & Boudoir tingkat tinggi "
                            "(fokus pada tatapan mata, tekstur kulit alami, siluet tubuh, pencahayaan chiaroscuro, "
                            "dan keintiman/ketegangan emosional)."
                        ),
                        style_anchor_tags=vb.get("style_anchor_tags", DEFAULT_STYLE_ANCHOR),
                        color_grading_and_lighting=vb.get("color_grading_and_lighting", ""),
                        environment_visual_rules=vb.get("environment_visual_rules", ""),
                        character_dna_list=character_dna_list,
                        chapter_content_context=fallback_context,
                        language=lang,
                    )
                    raw_json = self.llm.generate_json(
                        prompt=retry_prompt,
                        system_instruction=sys_prompt,
                        temperature=0.6,
                    )
                    raw_list = self.extract_illustrations_list(raw_json)
                except Exception:
                    raw_list = []

        illustrations = self.normalize_illustrations(
            project=project,
            chapter_info=chapter_info,
            raw_list=raw_list,
            target_count=count,
        )
        project.save_chapter_illustrations(chap_num, illustrations)
        return illustrations

    def render_chapter_illustrations(
        self,
        project: NovelProject,
        chapter_num: int,
        illustrations: Optional[List[Dict[str, Any]]] = None,
        slots_to_render: Optional[List[int]] = None,
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Render the actual image files (.jpg) for the chapter's illustrations and save metadata."""
        if illustrations is None:
            illustrations = project.get_chapter_illustrations(chapter_num)
        if not illustrations:
            ch_info = next(
                (ch for ch in project.outline.get("chapters", []) if ch.get("chapter_number") == chapter_num),
                {"chapter_number": chapter_num, "title": f"Bab {chapter_num}"},
            )
            illustrations = self.plan_chapter_illustrations(project, ch_info)

        total = len(illustrations)
        for idx, item in enumerate(illustrations, 1):
            slot_num = int(item.get("illustration_number", idx))
            if slots_to_render and slot_num not in slots_to_render:
                continue

            if progress_callback:
                progress_callback(slot_num, total, item)

            # Ensure prompt always has locked Character Visual DNA and Style Anchor
            item["image_prompt"] = self.compose_consistent_prompt(project, item)
            out_path = project.get_illustration_image_path(chapter_num, slot_num, ext=".jpg")

            render_res = self.image_client.generate_and_save(
                prompt=item["image_prompt"],
                output_path=out_path,
                negative_prompt=item.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT),
                seed=int(item.get("seed", self.compute_slot_seed(project, chapter_num, slot_num))),
                scene_title=item.get("scene_title", f"Bab {chapter_num} - Ilustrasi {slot_num}"),
                caption=item.get("caption", ""),
            )

            item["image_path"] = render_res["image_path"]
            item["status"] = render_res["status"]
            item["engine"] = render_res["engine"]
            item["seed"] = render_res["seed"]
            project.save_chapter_illustrations(chapter_num, illustrations)

        return illustrations

    @staticmethod
    def strip_injected_illustrations(prose: str) -> str:
        """Remove previously embedded GhostWriter illustration blocks from chapter markdown."""
        if not prose:
            return ""
        cleaned = re.sub(
            r"\n*<!-- GHOSTWRITER_ILLUSTRATION_START -->[\s\S]*?<!-- GHOSTWRITER_ILLUSTRATION_END -->\n*",
            "\n\n",
            prose,
        )
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    @classmethod
    def inject_illustrations_into_markdown(
        cls,
        prose: str,
        illustrations: List[Dict[str, Any]],
        relative_dir: str = "../illustrations",
    ) -> str:
        """Embed the 3 illustrations at Opening, Middle, and Climax positions of a chapter's Markdown."""
        clean_prose = cls.strip_injected_illustrations(prose)
        if not illustrations:
            return clean_prose

        def _format_md_block(item: Dict[str, Any]) -> str:
            raw_img_path = item.get("image_path") or f"chapter_01_illus_{int(item.get('illustration_number', 1)):02d}.jpg"
            img_file = Path(raw_img_path).name
            rel_path = f"{relative_dir}/{img_file}" if relative_dir else img_file
            raw_title = item.get("scene_title") or f"Ilustrasi {item.get('illustration_number', 1)}"
            title = re.sub(r"[\[\]\r\n]+", " ", str(raw_title)).strip()
            raw_caption = item.get("caption") or title
            caption = re.sub(r"[\r\n\*]+", " ", str(raw_caption)).strip()
            return (
                f"<!-- GHOSTWRITER_ILLUSTRATION_START -->\n"
                f"![{title}]({rel_path})\n"
                f"*{caption}*\n"
                f"<!-- GHOSTWRITER_ILLUSTRATION_END -->"
            )

        paragraphs = [p.strip() for p in clean_prose.split("\n\n") if p.strip()]
        if not paragraphs:
            return "\n\n".join(_format_md_block(item) for item in illustrations)

        # Compute target paragraph insertion indices for 3 slots (Opening, Middle, Climax)
        n_paras = len(paragraphs)
        # Keep heading at index 0 intact
        opening_idx = min(2, n_paras) if n_paras >= 2 else 1
        middle_idx = max(opening_idx + 1, n_paras // 2) if n_paras >= 4 else n_paras
        climax_idx = n_paras  # After the climax / final paragraph

        insertion_points = [opening_idx, middle_idx, climax_idx]
        blocks_by_pos: Dict[int, List[str]] = {}

        for idx, item in enumerate(illustrations):
            if idx < len(insertion_points):
                pos = min(insertion_points[idx], n_paras)
            else:
                pos = n_paras
            blocks_by_pos.setdefault(pos, []).append(_format_md_block(item))

        result_parts: List[str] = []
        for i, para in enumerate(paragraphs):
            if i in blocks_by_pos and i > 0:
                result_parts.extend(blocks_by_pos.pop(i))
            result_parts.append(para)

        for remaining_pos in sorted(blocks_by_pos.keys()):
            result_parts.extend(blocks_by_pos[remaining_pos])

        return "\n\n".join(result_parts)
