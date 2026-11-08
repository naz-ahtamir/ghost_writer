"""Unit tests for GhostWriter Novel System."""

import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

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


def test_grok_token_efficiency_and_caching():
    from core.llm import LLMClient
    import config
    import json
    import io
    from unittest.mock import patch, MagicMock

    client = LLMClient(api_key="xai-test-key", provider="grok")

    # 1. Verify sticky routing conversation ID
    assert client.conversation_id.startswith("gw-")
    client.set_conversation_id("custom-session-99")
    assert client.conversation_id == "custom-session-99"

    # 2. Verify context pruning when text approaches/exceeds 200k boundary
    giant_text = "Narasi panjang sekali. " * 20000
    assert len(giant_text) > 400000
    pruned = client.prune_context(giant_text, max_chars=360000)
    assert len(pruned) < len(giant_text)
    assert "PERINGATAN EFISIENSI TOKEN" in pruned

    # 3. Verify format_chat_message preserves reasoning_content
    asst_msg = client.format_chat_message("assistant", "Hasil naskah bab.", "analisis_penalaran_internal")
    assert asst_msg["role"] == "assistant"
    assert asst_msg["content"] == "Hasil naskah bab."
    assert asst_msg["reasoning_content"] == "analisis_penalaran_internal"

    # 4. Mock xAI response and verify headers (x-grok-conv-id) and payload (reasoning_effort: "low")
    captured_requests = []

    def mock_urlopen(req, timeout=120, context=None):
        captured_requests.append(req)
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        fake_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "{\"genre\": \"Sci-Fi\"}",
                        "reasoning_content": "step 1: identify genre..."
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 1250,
                "completion_tokens": 150,
                "total_tokens": 1400,
                "prompt_tokens_details": {
                    "cached_tokens": 1000
                },
                "completion_tokens_details": {
                    "reasoning_tokens": 40
                }
            }
        }
        mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        res_json = client.generate_json(
            prompt="Klasifikasikan genre",
            system_instruction="Anda adalah kurator fiksi ilmiah",
        )
        assert res_json == {"genre": "Sci-Fi"}
        assert len(captured_requests) == 1

        sent_req = captured_requests[0]
        # Check header x-grok-conv-id
        assert sent_req.headers.get("X-grok-conv-id") == "custom-session-99" or sent_req.get_header("X-grok-conv-id") == "custom-session-99"

        # Check payload: generate_json defaults to low reasoning effort
        payload = json.loads(sent_req.data.decode("utf-8"))
        assert payload.get("reasoning_effort") == "low"
        assert payload.get("reasoning", {}).get("effort") == "low"

        # Verify telemetry extraction
        usage = client.get_last_usage()
        assert usage["prompt_tokens"] == 1250
        assert usage["cached_tokens"] == 1000
        assert usage["completion_tokens"] == 150
        assert usage["reasoning_tokens"] == 40
        assert usage["cache_hit_rate"] == 80.0
        assert client.last_reasoning_content == "step 1: identify genre..."

        cum_usage = client.get_cumulative_usage()
        assert cum_usage["requests_count"] == 1
        assert cum_usage["prompt_tokens"] == 1250
        assert cum_usage["cached_tokens"] == 1000

    # 5. Verify 200k boundary alert & auto low reasoning effort
    def mock_large_urlopen(req, timeout=120, context=None):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        fake_response = {
            "choices": [{"message": {"role": "assistant", "content": "Bab lanjutan"}}],
            "usage": {
                "prompt_tokens": 185000,
                "completion_tokens": 800,
                "total_tokens": 185800,
                "prompt_tokens_details": {"cached_tokens": 170000},
                "completion_tokens_details": {"reasoning_tokens": 50}
            }
        }
        mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_large_urlopen):
        client.generate(prompt="Lanjutkan bab 35...")
        assert client.context_near_limit is True

    # On next call, client automatically enforces low effort due to context_near_limit
    captured_subsequent = []
    def mock_subsequent_urlopen(req, timeout=120, context=None):
        captured_subsequent.append(req)
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        fake_response = {
            "choices": [{"message": {"role": "assistant", "content": "Bab 36"}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600}
        }
        mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_subsequent_urlopen):
        client.generate(prompt="Bab 36...", reasoning_effort="high")
        payload = json.loads(captured_subsequent[0].data.decode("utf-8"))
        assert payload.get("reasoning_effort") == "low"


def test_document_loader_and_article_adapter():
    import zipfile
    from core.document_loader import load_document_text
    from agents.article_adapter import ArticleAdapterAgent

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Plain text / markdown article
        txt_file = tmp_path / "artikel_berita.txt"
        txt_file.write_text(
            "Seorang nelayan tua di pesisir timur berjuang menyelamatkan desanya dari proyek reklamasi ilegal.",
            encoding="utf-8",
        )
        loaded_txt, stats_txt = load_document_text(str(txt_file))
        assert "nelayan tua" in loaded_txt
        assert stats_txt["words"] > 5

        # 2. Zero-dependency .docx extraction via zipfile XML
        docx_file = tmp_path / "kisah_nyata.docx"
        sample_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            "<w:p><w:r><w:t>Paragraf pertama artikel dari dokumen Word.</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Paragraf kedua berisi konflik utama.</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
        with zipfile.ZipFile(docx_file, "w") as zf:
            zf.writestr("word/document.xml", sample_xml)

        loaded_docx, stats_docx = load_document_text(str(docx_file))
        assert "Paragraf pertama artikel" in loaded_docx
        assert "konflik utama" in loaded_docx

        # 3. ArticleAdapterAgent with mock LLM
        class DummyAdapterLLM:
            def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.65):
                return {
                    "suggested_title": "Ombak Terakhir di Pesisir Timur",
                    "genre": "Drama Sosial / Thriller",
                    "tone": "Emosional dan menegangkan",
                    "source_summary": "Nelayan tua melawan sindikat reklamasi ilegal.",
                    "premise": "Pak Darma harus memilih antara uang kompensasi atau masa depan laut desanya.",
                    "recommended_chapters": 14,
                    "recommended_words_per_chapter": 2000,
                    "adaptation_notes": "14 bab ideal untuk membangun eskalasi konflik warga.",
                }

        adapter = ArticleAdapterAgent(DummyAdapterLLM())
        blueprint = adapter.analyze_article(loaded_txt, custom_direction="Fokus pada keluarga nelayan")
        assert blueprint["suggested_title"] == "Ombak Terakhir di Pesisir Timur"
        assert blueprint["recommended_chapters"] == 14
        assert "Nelayan tua" in blueprint["combined_premise"]

        # 4. Saving source article in NovelProject
        proj = NovelProject(tmp_path / "novel_adaptasi")
        proj.save_metadata({"title": blueprint["suggested_title"]})
        proj.save_source_article(loaded_txt, source_filename="artikel_berita.txt", source_summary=blueprint["source_summary"])
        assert proj.get_source_article() == loaded_txt
        assert proj.metadata["source_file"] == "artikel_berita.txt"
        assert "Nelayan tua" in proj.metadata["source_summary"]


def test_chapter_illustrations_and_visual_consistency():
    from agents.illustrator import IllustratorAgent
    from core.image_gen import ImageGeneratorClient

    class DummyIllusLLM:
        def is_configured(self):
            return True

        def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.5):
            if "character_visual_registry" in prompt:
                return {
                    "visual_style_preset": "Photorealistic Cinematic 8K Film Still",
                    "style_anchor_tags": "photorealistic cinematic film still, ARRI Alexa 65, 35mm anamorphic lens, natural skin pores, 8k raw photo",
                    "color_grading_and_lighting": "moody neo-noir chiaroscuro lighting, warm amber and cold rain reflections",
                    "environment_visual_rules": "rain-slicked dark streets and industrial docks",
                    "negative_prompt": "anime, cartoon, cgi, censored, blurred",
                    "character_visual_registry": [
                        {
                            "name": "Raka",
                            "visual_dna": "Indonesian man, 29 years old, sharp jawline, tan skin, thin scar over left eyebrow, short messy black hair, wearing dark wet leather jacket",
                            "signature_expression_and_posture": "intense piercing gaze, tense athletic posture",
                        },
                        {
                            "name": "Elena",
                            "visual_dna": "Eurasian woman, 26 years old, high cheekbones, emerald green eyes, long wavy raven hair, wearing crimson silk dress and black trench coat",
                            "signature_expression_and_posture": "mysterious confident expression, graceful poise",
                        },
                    ],
                }
            return {
                "illustrations": [
                    {
                        "illustration_number": 1,
                        "slot_role": "opening",
                        "scene_title": "Pertemuan di Dermaga Hujan",
                        "caption": "Raka menunggu di bawah guyuran hujan dermaga saat Elena melangkah keluar dari kabut.",
                        "characters_present": ["Raka", "Elena"],
                        "camera_shot": "Wide cinematic two-shot, 35mm anamorphic lens f/1.8",
                        "pose_and_action": "Raka standing under dim streetlamp facing Elena, rain dripping from their hair, intense eye contact",
                        "environment_and_lighting": "wet wooden pier at midnight, heavy rain, neon reflections on puddles",
                    },
                    {
                        "illustration_number": 2,
                        "slot_role": "middle",
                        "scene_title": "Konfrontasi Tanpa Jarak",
                        "caption": "Elena mencengkeram kerah jaket Raka, membisikkan rahasia berbahaya.",
                        "characters_present": ["Raka", "Elena"],
                        "camera_shot": "Intimate medium close-up, 50mm Prime lens f/1.4, shallow depth of field",
                        "pose_and_action": "Elena pulling Raka close by his leather jacket collar, faces inches apart, raw emotional tension",
                        "environment_and_lighting": "shadowy cargo container alley, dramatic rim lighting on wet skin",
                    },
                    {
                        "illustration_number": 3,
                        "slot_role": "climax",
                        "scene_title": "Tembakan di Ambang Malam",
                        "caption": "Kilatan moncong senjata memecah kegelapan saat Raka melindungi Elena.",
                        "characters_present": ["Raka", "Elena"],
                        "camera_shot": "Dynamic low-angle shot, 35mm lens, motion dan sparks",
                        "pose_and_action": "Raka shielding Elena with his body while drawing his pistol, fierce expression",
                        "environment_and_lighting": "exploding glass and muzzle flash illuminating the dark dock",
                    },
                ]
            }

    class OfflineMockImageClient(ImageGeneratorClient):
        def generate_and_save(self, prompt, output_path, negative_prompt="", seed=None, scene_title="", caption="", **kwargs):
            self._create_storyboard_fallback_image(
                output_path=Path(output_path),
                scene_title=scene_title,
                caption=caption,
                prompt=prompt,
                seed=seed or 12345,
            )
            return {
                "status": "rendered",
                "image_path": str(output_path),
                "engine": "mock:flux-realism",
                "seed": seed or 12345,
            }

    with tempfile.TemporaryDirectory() as tmp_dir:
        proj = NovelProject(Path(tmp_dir) / "illustrated_novel")
        proj.save_metadata({"title": "Bayangan Dermaga", "author": "Penulis", "genre": "Noir Thriller"})
        proj.save_world_bible({"setting_name": "Pelabuhan Utara", "atmosphere": "Gelap dan hujan"})
        proj.save_characters([
            {"name": "Raka", "role": "Protagonist", "appearance": "Pria rahang tegas dengan bekas luka di alis kiri"},
            {"name": "Elena", "role": "Femme Fatale", "appearance": "Wanita bermata hijau zamrud dengan gaun sutra merah"},
        ])
        proj.save_outline({
            "chapters": [{"chapter_number": 1, "title": "Malam di Dermaga", "pov_character": "Raka", "setting": "Dermaga"}]
        })
        sample_prose = (
            "# Bab 1: Malam di Dermaga\n\n"
            "Hujan turun deras membasahi kayu dermaga yang tua.\n\n"
            "Elena muncul dari balik kabut malam dengan tatapan tajam.\n\n"
            "Ketegangan memuncak ketika keduanya saling berhadapan tanpa jarak.\n\n"
            "Suara tembakan tiba-tiba memecah keheningan pelabuhan."
        )
        proj.save_chapter(1, sample_prose)

        illustrator = IllustratorAgent(DummyIllusLLM(), image_client=OfflineMockImageClient())

        # 1. Verify Visual Bible & Character Visual DNA locking
        vb = illustrator.ensure_visual_bible(proj)
        assert proj.is_visual_bible_complete()
        assert len(vb["character_visual_registry"]) == 2
        assert "thin scar over left eyebrow" in proj.characters[0]["visual_dna"]
        assert "emerald green eyes" in proj.characters[1]["visual_dna"]

        # 2. Plan 3 chapter illustrations
        ch_info = proj.outline["chapters"][0]
        planned = illustrator.plan_chapter_illustrations(proj, ch_info, count=3)
        assert len(planned) == 3
        assert [p["slot_role"] for p in planned] == ["opening", "middle", "climax"]
        # Both Raka and Elena's locked Visual DNA must be injected into all 3 prompts for consistency
        for item in planned:
            assert "thin scar over left eyebrow" in item["image_prompt"]
            assert "emerald green eyes" in item["image_prompt"]
            assert "photorealistic cinematic film still" in item["image_prompt"]
            # Ensure close-up / shallow depth of field was automatically upgraded to show body pose + background
            assert "shallow depth of field" not in item["image_prompt"].lower()
            assert "Dynamic expressive body pose and action:" in item["image_prompt"]
            assert "Detailed background environment and atmosphere:" in item["image_prompt"]
            # Pose and background must appear BEFORE the trailing style anchor so FLUX.1's CLIP-L encoder sees them
            assert item["image_prompt"].index("Dynamic expressive body pose") < item["image_prompt"].index("photorealistic cinematic film still")

        # 3. Render 3 illustrations to disk
        rendered = illustrator.render_chapter_illustrations(proj, 1, planned)
        assert len(rendered) == 3
        for idx, item in enumerate(rendered, 1):
            img_p = Path(item["image_path"])
            assert img_p.exists()
            assert img_p.stat().st_size > 0
            assert item["status"] == "rendered"

        assert proj.list_illustrated_chapters() == [1]

        # 4. Inject into Markdown idempotently (no duplicates on second call)
        injected_once = IllustratorAgent.inject_illustrations_into_markdown(sample_prose, rendered)
        injected_twice = IllustratorAgent.inject_illustrations_into_markdown(injected_once, rendered)
        assert injected_once == injected_twice
        assert injected_once.count("chapter_01_illus_01.jpg") == 1
        assert injected_once.count("chapter_01_illus_02.jpg") == 1
        assert injected_once.count("chapter_01_illus_03.jpg") == 1

        # 5. Export to Markdown, DOCX, and Illustrated HTML Reader with embedded illustrations
        exporter = NovelExporter(proj)
        md_file, docx_file = exporter.export_all()
        html_file = exporter.export_html()
        assert md_file.exists() and md_file.stat().st_size > 0
        assert docx_file.exists() and docx_file.stat().st_size > 0
        assert html_file.exists() and html_file.stat().st_size > 0
        md_text = md_file.read_text(encoding="utf-8")
        assert "chapter_01_illus_01.jpg" in md_text
        assert "chapter_01_illus_02.jpg" in md_text
        assert "chapter_01_illus_03.jpg" in md_text
        html_text = html_file.read_text(encoding="utf-8")
        assert "data:image/jpeg;base64," in html_text
        assert "Pertemuan di Dermaga Hujan" in html_text

    # 6. Verify Anti-Refusal Prompt Adaptation & Black-Image Detector
    from core.image_gen import adapt_prompt_for_uncensored_render, is_valid_rendered_image
    raw_trigger_prompt = "NSFW uncensored explicit scene of Raka and Elena naked having sex on the bed"
    adapted_l1 = adapt_prompt_for_uncensored_render(raw_trigger_prompt, level=1)
    assert "nsfw" not in adapted_l1.lower()
    assert "uncensored" not in adapted_l1.lower()
    assert "passionate intimate embrace" in adapted_l1.lower()
    assert "unclothed natural skin silhouette" in adapted_l1.lower()

    # Verify black/blank censored image is rejected by is_valid_rendered_image
    assert is_valid_rendered_image(b"too_short") is False
    try:
        import io
        from PIL import Image
        black_buf = io.BytesIO()
        Image.new("RGB", (256, 256), color=(0, 0, 0)).save(black_buf, format="JPEG")
        assert is_valid_rendered_image(black_buf.getvalue()) is False
    except ImportError:
        pass


    # 7. Verify JPEG Normalization and Local Reader Server
    from core.image_gen import normalize_to_jpeg_bytes
    from agents.exporter import ensure_local_reader_server, get_local_reader_url, open_file_in_viewer
    try:
        from PIL import Image
        png_buf = io.BytesIO()
        Image.new("RGB", (64, 64), color=(30, 60, 90)).save(png_buf, format="PNG")
        converted_jpg = normalize_to_jpeg_bytes(png_buf.getvalue())
        assert converted_jpg.startswith(b"\xff\xd8\xff")
    except ImportError:
        pass

    server_port = ensure_local_reader_server()
    assert isinstance(server_port, int) and 8765 <= server_port <= 8810
    # Files inside config.PROJECTS_DIR get served via http://127.0.0.1:port
    sample_proj_file = config.PROJECTS_DIR / "sample_test" / "test.html"
    assert get_local_reader_url(sample_proj_file).startswith(f"http://127.0.0.1:{server_port}/sample_test/test.html")
    # Files outside return file:// URI fallback
    assert get_local_reader_url(html_file).startswith("file://")
    opened = open_file_in_viewer(html_file, prefer_native_app=False)
    assert opened


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        test_slugify()
        test_project_lifecycle()
        test_project_foundation_completion()
        test_delete_project()
        test_llm_json_extraction_robustness()
        test_grok_and_gemini_provider_switching()
        test_grok_token_efficiency_and_caching()
        test_scene_planner_and_beat_by_beat_writer()
        test_refusal_detection()
        test_document_loader_and_article_adapter()
        test_chapter_illustrations_and_visual_consistency()
        print("All tests passed!")
