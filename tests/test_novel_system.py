"""Unit tests for GhostWriter Novel System."""

import tempfile
import shutil
from pathlib import Path
import pytest

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

    # Unclosed / truncated JSON recovery
    truncated_json = '{"overall_synopsis": "Cerita cinta rumit", "chapters": [{"chapter_number": 1, "title": "Pertemuan"}'
    res_trunc = LLMClient.extract_json(truncated_json)
    assert res_trunc["overall_synopsis"] == "Cerita cinta rumit"


if __name__ == "__main__":
    pytest.main([__file__])
