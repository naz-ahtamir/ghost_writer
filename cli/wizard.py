"""Interactive wizard for creating a new novel project."""

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


def run_new_novel_wizard(llm: LLMClient) -> NovelProject:
    """Guide the user through generating a new novel from scratch."""
    print_header("✨ Buat Proyek Novel Baru", "Langkah demi langkah merancang konsep, dunia, karakter, dan alur cerita")

    title = Prompt.ask("[bold cyan]Judul Novel[/bold cyan]", default="Cakrawala yang Hilang")
    author = Prompt.ask("[bold cyan]Nama Penulis[/bold cyan]", default="Penulis")

    console.print("\n[dim]Pilih Genre populer atau ketik genre kustom Anda:[/dim]")
    console.print("[dim]1. Fantasi Epik / Sihir  |  2. Fiksi Ilmiah (Sci-Fi)  |  3. Thriller / Misteri Detektif\n4. Horor & Gaib  |  5. Romance / Drama Emosional  |  6. Cyberpunk / Distopia[/dim]")
    genre_input = Prompt.ask("[bold cyan]Genre[/bold cyan]", default="Fantasi Epik")

    tone = Prompt.ask(
        "[bold cyan]Tone / Nuansa Cerita[/bold cyan] (misal: Gelap & Realistis, Epik & Penuh Harapan, dsb)",
        default="Gelap, misterius, dan penuh intrik politik",
    )

    console.print("\n[bold yellow]Tuliskan Premis / Ide Dasar Cerita Anda:[/bold yellow]")
    console.print("[dim]Contoh: Di sebuah kota terapung yang kehabisan sumber daya sihir, seorang detektif mantan prajurit menemukan pembunuhan bangsawan yang mengungkap konspirasi bahwa kota mereka sengaja diarahkan jatuh ke laut.[/dim]")
    premise = Prompt.ask("[bold cyan]Premis Cerita[/bold cyan]")

    target_chapters = IntPrompt.ask("[bold cyan]Target Jumlah Bab[/bold cyan]", default=12)
    target_words = IntPrompt.ask("[bold cyan]Target Kata per Bab[/bold cyan]", default=2000)

    # Create project record
    project = ProjectManager.create_project(
        title=title,
        author=author,
        genre=genre_input,
        tone=tone,
        premise=premise,
        target_chapters=target_chapters,
        target_words_per_chapter=target_words,
    )

    console.print(f"\n[bold green]✓ Proyek '{title}' berhasil diinisialisasi![/bold green]\n")

    # Phase 1: Architect Agent (Worldbuilding)
    architect = ArchitectAgent(llm)
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

    # Phase 2: Character Master Agent (Character Bible)
    char_master = CharacterMasterAgent(llm)
    with console.status("[bold cyan]👥 Character Master Agent sedang mendesain profil psikologis para tokoh...[/bold cyan]"):
        characters = char_master.generate_characters(project)

    console.print("\n")
    display_characters_table(characters)

    # Phase 3: Outliner Agent (Plot & Chapters)
    outliner = OutlinerAgent(llm)
    with console.status("[bold cyan]🗺️ Outliner Agent sedang merancang struktur Three-Act dan plot bab-demi-bab...[/bold cyan]"):
        outline = outliner.generate_outline(project)

    console.print("\n")
    console.print(Panel(
        f"[bold]Sinopsis Lengkap:[/bold]\n{outline.get('overall_synopsis', '')}\n\n"
        f"[bold]Struktur Babak (Narrative Arc):[/bold]\n{outline.get('narrative_arc', '')}",
        title="🗺️ Rancangan Alur Cerita Makro",
        border_style="magenta",
    ))

    display_chapters_table(outline.get("chapters", []), [])

    console.print(
        f"\n[bold green]🎉 Selamat! Fondasi novel '{title}' telah selesai dirancang oleh tim AI Agent.[/bold green]"
    )
    console.print("[dim]Anda sekarang dapat mulai menulis naskah Bab 1 atau mengedit profil karakter.[/dim]\n")
    return project
