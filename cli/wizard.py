"""Interactive wizard for creating and resuming novel projects."""

import time
from typing import Optional
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from cli.ui import (
    console,
    print_header,
    display_characters_table,
    display_chapters_table,
)
from core.llm import LLMClient
from core.project import ProjectManager, NovelProject
from agents.architect import ArchitectAgent
from agents.character_master import CharacterMasterAgent
from agents.outliner import OutlinerAgent


POPULAR_GENRES = {
    "1": "Fantasi Epik / Sihir",
    "2": "Fiksi Ilmiah (Sci-Fi)",
    "3": "Thriller / Misteri Detektif",
    "4": "Horor & Gaib",
    "5": "Romance / Drama Emosional",
    "6": "Cyberpunk / Distopia",
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

    console.print(Panel(
        f"[bold cyan]Judul:[/bold cyan] {title}\n"
        f"[bold cyan]Genre:[/bold cyan] {meta.get('genre', '-')}\n"
        f"[bold cyan]Tone:[/bold cyan] {meta.get('tone', '-')}\n"
        f"[bold cyan]Premis:[/bold cyan] {meta.get('premise', '-')}\n"
        f"[bold cyan]Target Bab:[/bold cyan] {meta.get('target_chapters', 12)} bab (~{meta.get('target_words_per_chapter', 2000)} kata/bab)",
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

    console.print(
        f"\n[bold green]🎉 Selamat! Fondasi novel '{title}' telah lengkap dan siap ditulis![/bold green]"
    )
    console.print("[dim]Anda sekarang dapat langsung mulai menulis naskah Bab 1 lewat Menu 3.[/dim]\n")
    return True


def run_new_novel_wizard(llm: LLMClient) -> NovelProject:
    """Guide the user through generating a new novel from scratch."""
    print_header("✨ Buat Proyek Novel Baru", "Langkah demi langkah merancang konsep, dunia, karakter, dan alur cerita")

    title = Prompt.ask("[bold cyan]Judul Novel[/bold cyan]", default="Cakrawala yang Hilang")
    author = Prompt.ask("[bold cyan]Nama Penulis[/bold cyan]", default="Penulis")

    console.print("\n[dim]Pilih Genre populer atau ketik genre kustom Anda:[/dim]")
    console.print("[dim]1. Fantasi Epik / Sihir  |  2. Fiksi Ilmiah (Sci-Fi)  |  3. Thriller / Misteri Detektif\n4. Horor & Gaib  |  5. Romance / Drama Emosional  |  6. Cyberpunk / Distopia[/dim]")
    genre_input = Prompt.ask("[bold cyan]Genre[/bold cyan]", default="Fantasi Epik")
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

    target_chapters = IntPrompt.ask("[bold cyan]Target Jumlah Bab[/bold cyan]", default=12)
    target_words = IntPrompt.ask("[bold cyan]Target Kata per Bab[/bold cyan]", default=2000)

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
