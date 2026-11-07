"""Interactive wizard for creating and resuming novel projects (manual or from article/document)."""

import time
from typing import Optional, Tuple
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from cli.ui import (
    console,
    print_header,
    display_characters_table,
    display_chapters_table,
)
from core.llm import LLMClient
from core.project import ProjectManager, NovelProject
from core.document_loader import discover_local_documents, load_document_text
from agents.architect import ArchitectAgent
from agents.character_master import CharacterMasterAgent
from agents.outliner import OutlinerAgent
from agents.article_adapter import ArticleAdapterAgent


POPULAR_GENRES = {
    "1": "Fantasi Epik / Sihir",
    "2": "Fiksi Ilmiah (Sci-Fi)",
    "3": "Thriller / Misteri Detektif",
    "4": "Horor & Gaib",
    "5": "Romance / Drama Emosional",
    "6": "Cyberpunk / Distopia",
    "7": "Dark Fantasy / Grimdark (Dewasa)",
    "8": "Romance Dewasa / Drama Intens",
    "9": "Thriller Psikologis / Kriminal Gelap",
    "10": "Bebas / Eksperimental Tanpa Batas",
}


def resume_project_foundation(
    project: NovelProject,
    llm: LLMClient,
    force_all: bool = False,
) -> bool:
    """Complete or resume generating World Bible, Characters, and Outline for a project.

    Preserves any stages already successfully created unless force_all is True.
    """
    meta = project.metadata
    title = meta.get("title", "Tanpa Judul")
    print_header(f"🗺️ Inisiasi Fondasi Novel: {title}", "Merancang World Bible, Karakter, dan Outline Bab")

    missing = project.get_missing_foundation_components()
    if not missing and not force_all:
        console.print("[bold green]✓ Fondasi untuk novel ini sudah lengkap (World Bible, Karakter, dan Outline sudah ada).[/bold green]")
        if not Confirm.ask("Apakah Anda ingin merancang ulang (overwrite) seluruh fondasi novel dari awal?", default=False):
            return True
        force_all = True

    source_tag = f"\n[bold cyan]Sumber Artikel:[/bold cyan] {meta['source_file']}" if meta.get("source_file") else ""
    console.print(Panel(
        f"[bold cyan]Judul:[/bold cyan] {title}\n"
        f"[bold cyan]Genre:[/bold cyan] {meta.get('genre', '-')}\n"
        f"[bold cyan]Tone:[/bold cyan] {meta.get('tone', '-')}\n"
        f"[bold cyan]Premis:[/bold cyan] {meta.get('premise', '-')}\n"
        f"[bold cyan]Target Bab:[/bold cyan] {meta.get('target_chapters', 12)} bab (~{meta.get('target_words_per_chapter', 2000)} kata/bab)"
        f"{source_tag}",
        title="📋 Ringkasan Konsep Novel",
        border_style="cyan",
    ))

    # Phase 1: Architect Agent (Worldbuilding)
    need_world = force_all or not project.is_world_bible_complete()
    if need_world:
        architect = ArchitectAgent(llm)
        try:
            with console.status("[bold cyan]🏛️ Architect Agent sedang merancang Worldbuilding & Lore dunia cerita...[/bold cyan]"):
                world_bible = architect.generate_world_bible(project)
            console.print(Panel(
                f"[bold]Latar Utama:[/bold] {world_bible.get('setting_name')}\n"
                f"[bold]Konsep Inti:[/bold] {world_bible.get('core_concept')}\n"
                f"[bold]Atmosfer:[/bold] {world_bible.get('atmosphere')}\n"
                f"[bold]Aturan / Sistem:[/bold] {world_bible.get('rules_and_systems')}\n"
                f"[bold]Sejarah Masa Lalu:[/bold] {world_bible.get('historical_lore')}",
                title="🏛️ Hasil Worldbuilding (Architect Agent)",
                border_style="green",
            ))
        except Exception as e:
            console.print(f"[bold red]❌ Terjadi kendala saat merancang Worldbuilding:[/bold red] {e}")
            console.print("[yellow]Data konsep proyek Anda tetap tersimpan. Anda dapat melanjutkannya kembali tanpa harus mengulang dari awal.[/yellow]")
            return False
    else:
        console.print(f"[dim green]✓ World Bible sudah ada ('{project.world_bible.get('setting_name', 'Setting')}'), mempertahankan data ini.[/dim green]")

    # Phase 2: Character Master Agent (Character Bible)
    need_chars = force_all or not project.is_characters_complete()
    if need_chars:
        time.sleep(2)
        char_master = CharacterMasterAgent(llm)
        try:
            with console.status("[bold cyan]👥 Character Master Agent sedang mendesain profil psikologis para tokoh...[/bold cyan]"):
                characters = char_master.generate_characters(project)
            console.print("\n")
            display_characters_table(characters)
        except Exception as e:
            console.print(f"[bold red]❌ Terjadi kendala saat merancang Karakter:[/bold red] {e}")
            console.print("[yellow]World Bible Anda sudah berhasil disimpan. Anda dapat melanjutkan tahap Karakter kapan saja tanpa mengulang dari awal.[/yellow]")
            return False
    else:
        console.print(f"[dim green]✓ Profil Karakter sudah ada ({len(project.characters)} tokoh), mempertahankan data ini.[/dim green]")

    # Phase 3: Outliner Agent (Plot & Chapters)
    need_outline = force_all or not project.is_outline_complete()
    if need_outline:
        time.sleep(2)
        outliner = OutlinerAgent(llm)
        try:
            target_chapters = meta.get("target_chapters", 12)
            with console.status(f"[bold cyan]🗺️ Outliner Agent sedang merancang alur Three-Act dan plot {target_chapters} bab...[/bold cyan]"):
                outline = outliner.generate_outline(project)
            console.print("\n")
            console.print(Panel(
                f"[bold]Sinopsis Lengkap:[/bold]\n{outline.get('overall_synopsis', '')}\n\n"
                f"[bold]Struktur Babak (Narrative Arc):[/bold]\n{outline.get('narrative_arc', '')}",
                title="🗺️ Rancangan Alur Cerita Makro",
                border_style="magenta",
            ))
            display_chapters_table(outline.get("chapters", []), project.list_drafted_chapters())
        except Exception as e:
            console.print(f"[bold red]❌ Terjadi kendala saat merancang Outline:[/bold red] {e}")
            console.print("[yellow]World Bible dan Karakter Anda sudah tersimpan aman. Anda dapat mencoba merancang Outline kembali kapan saja tanpa mengulang dari awal.[/yellow]")
            return False
    else:
        console.print(f"[dim green]✓ Outline Bab sudah ada ({len(project.outline.get('chapters', []))} bab), mempertahankan data ini.[/dim green]")

    # Phase 4: Visual Continuity Lock (Visual Bible & Character Visual DNA)
    try:
        from agents.illustrator import IllustratorAgent
        illustrator = IllustratorAgent(llm)
        with console.status("[bold magenta]🧬 Mengunci Visual Bible & Character Visual DNA untuk konsistensi ilustrasi antar-bab...[/bold magenta]"):
            illustrator.ensure_visual_bible(project, force_regenerate=force_all)
        console.print("[dim green]✓ Visual Bible & DNA Fisik Karakter telah dikunci (Siap untuk 3 ilustrasi fotorealistis/bab).[/dim green]")
    except Exception:
        pass

    console.print(
        f"\n[bold green]🎉 Selamat! Fondasi novel '{title}' telah lengkap dan siap ditulis![/bold green]"
    )
    console.print("[dim]Anda sekarang dapat langsung mulai menulis naskah Bab 1 (Menu 3) dan membuat 3 Ilustrasi Bab (Menu 4).[/dim]\n")
    return True


def _prompt_article_input() -> Optional[Tuple[str, str]]:
    """Prompt the user to select a discovered file, enter a file path, or paste article text.

    Returns (article_text, source_filename) or None if cancelled.
    """
    console.print("\n[bold cyan]📄 Upload / Impor Artikel atau Dokumen Sumber[/bold cyan]")
    console.print("[dim]Format yang didukung: .txt, .md, .docx, .pdf, .odt, .html (atau tempel teks langsung)[/dim]")

    discovered = discover_local_documents(max_files=12)
    if discovered:
        table = Table(title="📂 File Dokumen yang Terdeteksi di Perangkat Anda", border_style="cyan")
        table.add_column("No", justify="center", style="bold cyan")
        table.add_column("Nama File", style="bold white")
        table.add_column("Format", justify="center", style="green")
        table.add_column("Lokasi Folder", style="dim")

        for idx, p in enumerate(discovered, 1):
            table.add_row(str(idx), p.name, p.suffix.lower(), str(p.parent))
        console.print(table)
        console.print(
            "[dim]💡 Ketik nomor file di atas (misal '1'), ketik path file lengkap, "
            "atau ketik 'paste' untuk menempelkan teks artikel langsung.[/dim]"
        )
    else:
        console.print(
            "[dim]💡 Ketik path/lokasi file dokumen (misal: /sdcard/Download/artikel.docx atau ~/Downloads/berita.txt), "
            "atau ketik 'paste' untuk menempelkan teks artikel langsung.[/dim]"
        )

    while True:
        raw_input = Prompt.ask(
            "\n[bold cyan]Pilih Nomor File / Path File / 'paste' ('b' untuk batal)[/bold cyan]",
            default="1" if discovered else "paste",
        ).strip()

        if raw_input.lower() in ("b", "batal", "cancel"):
            return None

        if raw_input.lower() in ("paste", "p", "teks", "manual"):
            console.print(
                "\n[bold yellow]📋 Tempel (Paste) Teks Artikel Anda di bawah ini.[/bold yellow]\n"
                "[dim]Setelah selesai menempelkan seluruh paragraf, ketik baris baru bertuliskan[/dim] [bold green]SELESAI[/bold green] [dim]lalu tekan Enter:[/dim]"
            )
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line.strip().upper() in ("SELESAI", "DONE", "EOF"):
                    if lines:
                        break
                lines.append(line)
            full_text = "\n".join(lines).strip()
            if not full_text:
                console.print("[red]Teks artikel masih kosong. Silakan coba lagi.[/red]")
                continue
            return full_text, "Teks Artikel (Paste)"

        # Check if user entered a number from discovered files
        target_path_str = raw_input
        if raw_input.isdigit() and discovered:
            choice_idx = int(raw_input)
            if 1 <= choice_idx <= len(discovered):
                target_path_str = str(discovered[choice_idx - 1])
            else:
                console.print(f"[yellow]Nomor harus antara 1 hingga {len(discovered)}.[/yellow]")
                continue

        try:
            text, stats = load_document_text(target_path_str)
            preview = " ".join(text.split()[:60])
            console.print(Panel(
                f"[bold green]✓ File berhasil dibaca![/bold green]\n"
                f"• [bold]Nama File:[/bold] {stats['filename']}\n"
                f"• [bold]Panjang Teks:[/bold] {stats['words']} kata ({stats['characters']} karakter)\n"
                f"• [bold]Cuplikan Awal:[/bold] [dim]{preview}...[/dim]",
                title="📄 Dokumen Sumber Terbaca",
                border_style="green",
            ))
            return text, stats["filename"]
        except Exception as e:
            console.print(f"[bold red]❌ Gagal membaca file:[/bold red] {e}")
            console.print("[dim]Silakan masukkan lokasi file yang benar atau ketik 'paste' untuk menempelkan isi artikel.[/dim]")


def run_article_to_novel_wizard(llm: LLMClient) -> Optional[NovelProject]:
    """Guide the user through uploading an article/document and expanding it into a full novel."""
    print_header(
        "📄 Kembangkan Artikel / Dokumen Menjadi Novel",
        "Unggah file (.txt, .md, .docx, .pdf) atau tempel artikel untuk diubah menjadi struktur novel utuh",
    )

    loaded = _prompt_article_input()
    if not loaded:
        console.print("[dim]Pembuatan novel dari artikel dibatalkan.[/dim]")
        return None

    article_text, source_filename = loaded
    author = Prompt.ask("[bold cyan]Nama Penulis[/bold cyan]", default="Penulis")
    custom_direction = Prompt.ask(
        "[bold yellow]Arahan Sudut Pandang / Fokus Cerita (opsional)[/bold yellow] "
        "[dim](misal: 'fokus pada perjuangan sang ayah', atau tekan Enter agar dirancang otomatis oleh AI)[/dim]",
        default="",
    )

    adapter = ArticleAdapterAgent(llm)
    try:
        with console.status("[bold cyan]🧠 Article Adapter Agent sedang menganalisis artikel & merancang cetak biru novel...[/bold cyan]"):
            blueprint = adapter.analyze_article(
                article_text=article_text,
                custom_direction=custom_direction,
            )
    except Exception as e:
        console.print(f"[bold yellow]⚠️ Analisis otomatis terkendala ({e}). Menggunakan mode ekstraksi langsung.[/bold yellow]")
        snippet = " ".join(article_text.split()[:200])
        blueprint = {
            "suggested_title": "Jejak di Balik Peristiwa",
            "genre": "Drama Emosional / Realisme",
            "tone": "Mendalam, realistis, dan emosional",
            "source_summary": snippet,
            "premise": f"{custom_direction}\n\nIntisari Artikel: {snippet}".strip(),
            "combined_premise": f"{custom_direction}\n\nIntisari Artikel: {snippet}".strip(),
            "recommended_chapters": 14,
            "recommended_words_per_chapter": 2000,
            "adaptation_notes": "Rekomendasi standar 14 bab (~2000 kata/bab).",
        }

    console.print(Panel(
        f"[bold cyan]Ide Judul Novel:[/bold cyan] {blueprint['suggested_title']}\n"
        f"[bold cyan]Rekomendasi Genre:[/bold cyan] {blueprint['genre']}\n"
        f"[bold cyan]Tone / Nuansa:[/bold cyan] {blueprint['tone']}\n\n"
        f"[bold yellow]📌 Intisari Fakta Artikel:[/bold yellow]\n{blueprint['source_summary']}\n\n"
        f"[bold green]📖 Premis Novel Hasil Pengembangan:[/bold green]\n{blueprint['premise']}\n\n"
        f"[bold magenta]📐 Rekomendasi Ukuran Ideal:[/bold magenta] "
        f"{blueprint['recommended_chapters']} Bab × ~{blueprint['recommended_words_per_chapter']} kata/bab\n"
        f"[dim]({blueprint['adaptation_notes']})[/dim]",
        title="✨ Cetak Biru Adaptasi Artikel ke Novel",
        border_style="green",
    ))

    console.print("[dim]Tekan Enter untuk menerima rekomendasi AI di atas, atau ketik perubahan Anda:[/dim]")
    title = Prompt.ask("[bold cyan]Judul Novel[/bold cyan]", default=blueprint["suggested_title"])
    genre = Prompt.ask("[bold cyan]Genre Novel[/bold cyan]", default=blueprint["genre"])
    tone = Prompt.ask("[bold cyan]Tone / Nuansa[/bold cyan]", default=blueprint["tone"])
    target_chapters = IntPrompt.ask(
        "[bold cyan]Target Jumlah Bab (Ideal: 12-20 bab)[/bold cyan]",
        default=blueprint["recommended_chapters"],
    )
    target_words = IntPrompt.ask(
        "[bold cyan]Target Kata per Bab (Ideal: 1800-2500 kata)[/bold cyan]",
        default=blueprint["recommended_words_per_chapter"],
    )

    project = ProjectManager.create_project(
        title=title,
        author=author,
        genre=genre,
        tone=tone,
        premise=blueprint["combined_premise"],
        target_chapters=target_chapters,
        target_words_per_chapter=target_words,
    )
    project.save_source_article(
        article_text=article_text,
        source_filename=source_filename,
        source_summary=blueprint["source_summary"],
    )

    console.print(f"\n[bold green]✓ Proyek adaptasi artikel '{title}' berhasil dibuat dan dokumen sumber tersimpan![/bold green]\n")

    resume_project_foundation(project, llm)
    return project


def run_new_novel_wizard(llm: LLMClient) -> Optional[NovelProject]:
    """Guide the user through generating a new novel from scratch or from an article file."""
    print_header("✨ Buat Proyek Novel Baru", "Mulai dari ide/premis manual atau kembangkan dari file artikel/dokumen")

    console.print("[bold cyan]Pilih Sumber Ide Novel Anda:[/bold cyan]")
    console.print("  [bold green]1.[/bold green] ✍️ Buat dari Ide / Premis Manual")
    console.print("  [bold yellow]2.[/bold yellow] 📄 Upload / Impor File Artikel atau Dokumen (.txt, .md, .docx, .pdf, atau Paste Artikel)")

    mode = Prompt.ask("\nPilih metode (1/2)", choices=["1", "2"], default="1")
    if mode == "2":
        return run_article_to_novel_wizard(llm)

    title = Prompt.ask("[bold cyan]Judul Novel[/bold cyan]", default="Cakrawala yang Hilang")
    author = Prompt.ask("[bold cyan]Nama Penulis[/bold cyan]", default="Penulis")

    console.print("\n[dim]Pilih Genre populer atau ketik genre/tema bebas Anda sendiri:[/dim]")
    console.print(
        "[dim]1. Fantasi Epik / Sihir  |  2. Fiksi Ilmiah (Sci-Fi)  |  3. Thriller / Misteri Detektif\n"
        "4. Horor & Gaib  |  5. Romance / Drama Emosional  |  6. Cyberpunk / Distopia\n"
        "7. Dark Fantasy / Grimdark (Dewasa)  |  8. Romance Dewasa / Drama Intens\n"
        "9. Thriller Psikologis / Kriminal Gelap  |  10. Bebas / Eksperimental Tanpa Batas[/dim]"
    )
    genre_input = Prompt.ask("[bold cyan]Genre (ketik nomor 1-10 atau tulis bebas)[/bold cyan]", default="Fantasi Epik")
    if genre_input.strip() in POPULAR_GENRES:
        genre = POPULAR_GENRES[genre_input.strip()]
    else:
        genre = genre_input.strip()

    tone = Prompt.ask(
        "[bold cyan]Tone / Nuansa Cerita[/bold cyan] (misal: Gelap & Realistis, Epik & Penuh Harapan, dsb)",
        default="Gelap, misterius, dan penuh intrik politik",
    )

    console.print("\n[bold yellow]Tuliskan Premis / Ide Dasar Cerita Anda:[/bold yellow]")
    console.print("[dim]Contoh: Di sebuah kota terapung yang kehabisan sumber daya sihir, seorang detektif mantan prajurit menemukan pembunuhan bangsawan yang mengungkap konspirasi bahwa kota mereka sengaja diarahkan jatuh ke laut.[/dim]")
    premise = Prompt.ask("[bold cyan]Premis Cerita[/bold cyan]")

    target_chapters = IntPrompt.ask("[bold cyan]Target Jumlah Bab (Ideal: 12-20 bab)[/bold cyan]", default=12)
    target_words = IntPrompt.ask("[bold cyan]Target Kata per Bab (Ideal: 1800-2500 kata)[/bold cyan]", default=2000)

    # Create project record on disk
    project = ProjectManager.create_project(
        title=title,
        author=author,
        genre=genre,
        tone=tone,
        premise=premise,
        target_chapters=target_chapters,
        target_words_per_chapter=target_words,
    )

    console.print(f"\n[bold green]✓ Proyek '{title}' berhasil diinisialisasi di disk![/bold green]\n")

    # Run multi-agent generation phases
    resume_project_foundation(project, llm)

    return project
