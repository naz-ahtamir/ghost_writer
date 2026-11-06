"""Unit tests for GhostWriter Novel System."""

import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import pytest
except ImportError:
    pytest = None

from core.project import NovelProject, ProjectManager, slugify
from agents.exporter import NovelExporter


def test_slugify():
    assert slugify("Cakrawala yang Hilang: Episode 1!") == "cakrawala_yang_hilang_episode_1"
    assert slugify("Simple Title") == "simple_title"


def test_project_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        proj_dir = tmp_path / "test_novel"

        proj = NovelProject(proj_dir)
        proj.save_metadata({
            "title": "Misteri Lembah Kabut",
            "author": "Rian",
            "genre": "Misteri",
            "premise": "Sebuah kasus pembunuhan di desa terisolasi.",
            "language": "Indonesian",
            "target_chapters": 5,
        })

        assert proj.metadata["title"] == "Misteri Lembah Kabut"

        # World Bible
        proj.save_world_bible({
            "setting_name": "Lembah Kabut",
            "atmosphere": "Dingin, mencekam, sering berkabut tebal",
            "rules_and_systems": "Tidak ada sinyal ponsel, hukum adat kuat",
        })
        assert proj.world_bible["setting_name"] == "Lembah Kabut"

        # Characters
        characters = [
            {
                "name": "Arga",
                "role": "Protagonist",
                "flaw": "Trauma masa lalu",
                "external_goal": "Menemukan adiknya yang hilang",
                "speech_mannerism": "Bicara singkat dan terukur",
            },
            {
                "name": "Bagas",
                "role": "Antagonist",
                "flaw": "Gila kendali",
                "external_goal": "Menyembunyikan rahasia desa",
                "speech_mannerism": "Penuh kiasan licik",
            }
        ]
        proj.save_characters(characters)
        assert len(proj.characters) == 2

        # Outline
        outline = {
            "overall_synopsis": "Arga tiba di desa dan menyadari ada yang salah.",
            "chapters": [
                {
                    "chapter_number": 1,
                    "title": "Kedatangan yang Dingin",
                    "pov_character": "Arga",
                    "status": "planned"
                },
                {
                    "chapter_number": 2,
                    "title": "Jejak Darah di Salju",
                    "pov_character": "Arga",
                    "status": "planned"
                }
            ]
        }
        proj.save_outline(outline)
        assert len(proj.outline["chapters"]) == 2

        # Chapter Drafting
        beats = [
            {"beat_number": 1, "beat_name": "Tiba di perbatasan", "goal": "Masuk desa"},
            {"beat_number": 2, "beat_name": "Pertemuan mencurigakan", "obstacle": "Dihadang tetua"}
        ]
        prose_ch1 = "# Bab 1: Kedatangan yang Dingin\n\nKabut turun perlahan menelan lembah..."
        proj.save_chapter(1, prose_ch1, beats=beats)

        assert proj.get_chapter(1) == prose_ch1
        assert len(proj.get_chapter_beats(1)) == 2
        assert proj.list_drafted_chapters() == [1]

        # Continuity summary
        summary = proj.get_continuity_summary(up_to_chapter=2)
        assert "Kedatangan yang Dingin" in summary

        # Test Exporter
        exporter = NovelExporter(proj)
        md_file, docx_file = exporter.export_all()

        assert md_file.exists()
        assert docx_file.exists()
        assert md_file.stat().st_size > 0
        assert docx_file.stat().st_size > 0


def test_project_foundation_completion():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        proj_dir = tmp_path / "foundation_novel"
        proj = NovelProject(proj_dir)

        # Initially empty
        assert not proj.is_world_bible_complete()
        assert not proj.is_characters_complete()
        assert not proj.is_outline_complete()
        assert not proj.is_foundation_complete()
        missing = proj.get_missing_foundation_components()
        assert len(missing) == 3

        # Add world bible
        proj.save_world_bible({"setting_name": "Surabaya"})
        assert proj.is_world_bible_complete()
        assert not proj.is_characters_complete()
        assert not proj.is_foundation_complete()
        assert len(proj.get_missing_foundation_components()) == 2

        # Add characters
        proj.save_characters([{"name": "Maya", "role": "Protagonist"}])
        assert proj.is_characters_complete()
        assert not proj.is_outline_complete()
        assert not proj.is_foundation_complete()
        assert len(proj.get_missing_foundation_components()) == 1

        # Add outline
        proj.save_outline({"chapters": [{"chapter_number": 1, "title": "Awal"}]})
        assert proj.is_outline_complete()
        assert proj.is_foundation_complete()
        assert len(proj.get_missing_foundation_components()) == 0


def test_delete_project():
    import config
    # Create a temporary project inside config.PROJECTS_DIR
    proj = ProjectManager.create_project(
        title="Proyek Untuk Dihapus",
        author="Tester",
        genre="Fiksi",
        tone="Ceria",
        premise="Testing delete.",
    )
    slug = proj.project_dir.name
    assert (config.PROJECTS_DIR / slug).exists()

    # Delete the project
    success = ProjectManager.delete_project(slug)
    assert success is True
    assert not (config.PROJECTS_DIR / slug).exists()

    # Deleting non-existent project returns False
    assert ProjectManager.delete_project("non_existent_slug_12345") is False


def test_llm_json_extraction_robustness():
    from core.llm import LLMClient

    # Clean JSON
    assert LLMClient.extract_json('{"key": "value"}') == {"key": "value"}

    # Markdown fence with chatter
    text_with_fences = (
        "Here is your result:\n"
        "```json\n"
        "{\n"
        '  "title": "Cincin",\n'
        '  "count": 22,\n'
        "}\n"
        "```\n"
        "Enjoy!"
    )
    res = LLMClient.extract_json(text_with_fences)
    assert res["title"] == "Cincin"
    assert res["count"] == 22

    # Unclosed / truncated JSON recovery (both object and array nesting)
    truncated_json = '{"overall_synopsis": "Cerita cinta rumit", "chapters": [{"chapter_number": 1, "title": "Pertemuan"}'
    res_trunc = LLMClient.extract_json(truncated_json)
    assert res_trunc["overall_synopsis"] == "Cerita cinta rumit"
    assert res_trunc["chapters"][0]["title"] == "Pertemuan"

    truncated_arr = '[{"beat_number": 1, "beat_name": "Pembuka"}, {"beat_number": 2, "beat_name": "Konflik'
    res_arr = LLMClient.extract_json(truncated_arr)
    assert isinstance(res_arr, list)
    assert len(res_arr) == 2
    assert res_arr[1]["beat_name"] == "Konflik"


def test_scene_planner_and_beat_by_beat_writer():
    from agents.scene_planner import ScenePlannerAgent
    from agents.writer import WriterAgent

    # Test unpacking beats from various JSON shapes (e.g. Grok json_object mode)
    raw_custom_key = {
        "scene_beats": [
            {
                "beat_number": 1,
                "beat_name": "Malam di Pelabuhan",
                "scene_events": "Raka tiba di dermaga gelap dan bertemu informan.",
                "goal": "Mendapatkan dokumen rahasia",
                "obstacle": "Informan meminta bayaran dua kali lipat",
                "sensory_details": "Bau amis laut, kabut dingin, derit kayu dermaga",
                "emotional_shift": "Dari waspada menjadi marah",
            },
            {
                "beat_number": 2,
                "beat_name": "Penyergapan",
                "scene_events": "Terdengar tembakan dari balik kontainer dan Raka membalas serangan.",
                "goal": "Bertahan hidup dan membawa koper",
                "obstacle": "Dua penembak bayaran mengepung jalan keluar",
                "sensory_details": "Kilatan moncong senjata, bau mesiu, darah hangat",
                "emotional_shift": "Adrenalin memuncak dan nekat",
            },
        ]
    }
    extracted = ScenePlannerAgent.extract_beats_list(raw_custom_key)
    assert len(extracted) == 2
    assert extracted[0]["beat_name"] == "Malam di Pelabuhan"
    assert "dermaga gelap" in extracted[0]["scene_events"]

    # Mock LLM to verify beat-by-beat execution in WriterAgent
    class DummyLLM:
        def __init__(self):
            self.calls = []

        def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.7) -> str:
            self.calls.append(prompt)
            beat_idx = len(self.calls)
            if beat_idx == 1:
                return "# Bab 1: Pertemuan Gelap\n\nParagraf pembuka dermaga yang dingin dan mencekam."
            return f"# Bab 1: Pertemuan Gelap\n\nParagraf lanjutan untuk beat ke-{beat_idx} yang intens."

    with tempfile.TemporaryDirectory() as tmp_dir:
        proj = NovelProject(Path(tmp_dir) / "beat_novel")
        proj.save_metadata({"title": "Test Beat", "target_words_per_chapter": 1600})
        proj.save_world_bible({"setting_name": "Jakarta Gelap", "atmosphere": "Noir", "rules_and_systems": "Hukum jalanan"})
        proj.save_characters([{"name": "Raka", "role": "Protagonist", "flaw": "Brutal"}])

        dummy_llm = DummyLLM()
        writer = WriterAgent(dummy_llm)
        progress_steps = []

        prose = writer.write_chapter(
            project=proj,
            chapter_info={
                "chapter_number": 1,
                "title": "Pertemuan Gelap",
                "pov_character": "Raka",
                "setting": "Pelabuhan",
                "conflict": "Penyergapan",
                "turning_point": "Informan tewas",
            },
            beats=extracted,
            beat_by_beat=True,
            progress_callback=lambda idx, total, b: progress_steps.append((idx, total, b["beat_name"])),
        )

        # Must have called LLM once per beat (2 beats = 2 calls)
        assert len(dummy_llm.calls) == 2
        assert len(progress_steps) == 2
        assert progress_steps[0] == (1, 2, "Malam di Pelabuhan")
        assert progress_steps[1] == (2, 2, "Penyergapan")
        # Duplicate '# Bab 1...' header from Beat 2 must be stripped cleanly
        assert prose.count("# Bab 1: Pertemuan Gelap") == 1
        assert "Paragraf pembuka dermaga" in prose
        assert "Paragraf lanjutan untuk beat ke-2" in prose
        assert len(proj.get_chapter_beats(1)) == 2


def test_refusal_detection():
    from core.llm import LLMClient

    assert LLMClient._is_refusal_response("") is True
    assert LLMClient._is_refusal_response("Maaf, saya tidak dapat memenuhi permintaan ini karena melanggar kebijakan.") is True
    assert LLMClient._is_refusal_response("Sebagai AI, saya tidak bisa menulis adegan dewasa.") is True
    assert LLMClient._is_refusal_response("I'm sorry, I cannot fulfill this request.") is True
    assert LLMClient._is_refusal_response("# Bab 1: Malam Berdarah\n\nHujan mengguyur aspal jalanan...") is False


def test_grok_and_gemini_provider_switching():
    from core.llm import LLMClient
    import config

    # Test Grok initialization (default prioritized)
    client = LLMClient(api_key="xai-test-key", provider="grok")
    assert client.provider == "grok"
    assert client.model in config.GROK_MODELS
    assert client.is_configured() is True
    assert client._client == "grok_rest"

    # Test switching to Gemini
    client.set_provider("gemini", api_key="fake-gemini-key")
    assert client.provider == "gemini"
    assert client.model in config.GEMINI_MODELS
    assert client.is_configured() is True

    # Test switching back to Grok
    client.set_provider("grok")
    assert client.provider == "grok"


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        test_slugify()
        test_project_foundation_completion()
        test_delete_project()
        test_llm_json_extraction_robustness()
        test_grok_and_gemini_provider_switching()
        test_scene_planner_and_beat_by_beat_writer()
        test_refusal_detection()
        print("All tests passed!")
