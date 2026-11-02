"""Rich UI helpers and styling for GhostWriter CLI."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt, IntPrompt, Confirm
from typing import Any, Dict, List, Optional

console = Console()


def print_banner() -> None:
    """Print application welcome banner."""
    banner = """
   ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗██╗    ██╗██████╗ ██╗████████╗███████╗██████╗ 
  ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝██║    ██║██╔══██╗██║╚══██╔══╝██╔════╝██╔══██╗
  ██║  ███╗███████║██║   ██║███████╗   ██║   ██║ █╗ ██║██████╔╝██║   ██║   █████╗  ██████╔╝
  ██║   ██║██╔══██║██║   ██║╚════██║   ██║   ██║███╗██║██╔══██╗██║   ██║   ██╔══╝  ██╔══██╗
  ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   ╚███╔███╔╝██║  ██║██║   ██║   ███████╗██║  ██║
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
              AI Multi-Agent Novel Writing Engine  |  Powered by Google Gemini
    """
    console.print(Panel(banner, style="bold cyan", border_style="bright_blue"))


def print_header(title: str, subtitle: Optional[str] = None) -> None:
    """Print a section header."""
    text = f"[bold white]{title}[/bold white]"
    if subtitle:
        text += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(text, border_style="cyan"))


def display_characters_table(characters: List[Dict[str, Any]]) -> None:
    """Display character profiles in a formatted table."""
    table = Table(title="👥 Daftar Karakter (Character Bible)", border_style="cyan")
    table.add_column("Nama", style="bold yellow")
    table.add_column("Peran", style="bold green")
    table.add_column("Motivasi & Goal", style="white")
    table.add_column("Flaw / Kelemahan", style="red")
    table.add_column("Gaya Bicara", style="dim")

    for c in characters:
        table.add_row(
            c.get("name", "N/A"),
            c.get("role", "N/A"),
            f"{c.get('external_goal', '')}\n[dim]({c.get('internal_motivation', '')})[/dim]",
            c.get("flaw", "N/A"),
            c.get("speech_mannerism", "N/A"),
        )
    console.print(table)


def display_chapters_table(chapters: List[Dict[str, Any]], drafted_nums: List[int]) -> None:
    """Display novel chapters outline in a formatted table."""
    table = Table(title="🗺️ Outline Bab Novel", border_style="magenta")
    table.add_column("Bab", justify="center", style="bold cyan")
    table.add_column("Judul", style="bold white")
    table.add_column("POV", style="yellow")
    table.add_column("Status", justify="center")
    table.add_column("Ringkasan Cerita", style="dim")

    for ch in chapters:
        num = ch.get("chapter_number", 0)
        is_drafted = num in drafted_nums
        status_tag = "[bold green]✓ Selesai[/bold green]" if is_drafted else "[dim yellow]Drafting...[/dim yellow]"

        table.add_row(
            str(num),
            ch.get("title", f"Bab {num}"),
            ch.get("pov_character", "N/A"),
            status_tag,
            ch.get("summary", "")[:80] + ("..." if len(ch.get("summary", "")) > 80 else ""),
        )
    console.print(table)


def display_audit_panel(audit: Dict[str, Any], chapter_title: str) -> None:
    """Display chapter critique and continuity audit."""
    score = audit.get("score", 0)
    score_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"

    content = f"[bold {score_color}]Skor Kualitas: {score}/100[/bold {score_color}]\n\n"
    content += f"[bold]Ulasan Umum:[/bold]\n{audit.get('summary_review', '')}\n\n"

    strengths = "\n".join([f"• {s}" for s in audit.get("strengths", [])])
    content += f"[bold green]Kekuatan Naskah:[/bold green]\n{strengths}\n\n"

    issues = "\n".join([f"• {i}" for i in audit.get("continuity_issues", [])])
    content += f"[bold red]Catatan Kontinuitas & Plothole:[/bold red]\n{issues}\n\n"

    critique = audit.get("pacing_and_style_critique", "")
    content += f"[bold cyan]Kritik Pacing & Gaya Bahasa:[/bold cyan]\n{critique}\n\n"

    suggestions = "\n".join([f"• {s}" for s in audit.get("actionable_suggestions", [])])
    content += f"[bold yellow]Saran Revisi Konkret:[/bold yellow]\n{suggestions}"

    console.print(Panel(content, title=f"🔍 Laporan Audit Editor - {chapter_title}", border_style="cyan"))
