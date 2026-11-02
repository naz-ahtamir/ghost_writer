"""Main interactive CLI entry point for GhostWriter AI."""

import os
import sys
from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm

import config
from cli.ui import (
    console,
    print_banner,
    print_header,
    display_characters_table,
    display_chapters_table,
)
from cli.wizard import run_new_novel_wizard
from cli.chapter_flow import write_chapter_flow, audit_chapter_flow, view_chapter_flow
from core.llm import LLMClient
from core.project import ProjectManager, NovelProject
from agents.exporter import NovelExporter


def manage_settings(llm: LLMClient) -> None:
    """Configure API key and Gemini model."""
    print_header("⚙️ Pengaturan Gemini & Model", "Konfigurasi API Key dan model LLM")

    curr_key = config.get_api_key()
    masked_key = curr_key[:8] + "..." + curr_key[-4:] if len(curr_key) > 12 else (curr_key or "[Belum Diisi]")
    console.print(f"[bold]API Key saat ini:[/bold] {masked_key}")
    console.print(f"[bold]Model saat ini:[/bold] {llm.model}")

    if Confirm.ask("\nApakah Anda ingin memperbarui Gemini API Key?", default=False):
        new_key = Prompt.ask("[bold cyan]Masukkan Gemini API Key baru[/bold cyan]")
        if new_key.strip():
            config.save_api_key(new_key.strip(), llm.model)
            llm.set_api_key(new_key.strip(), llm.model)
            console.print("[bold green]✓ API Key berhasil disimpan ke file .env![/bold green]")

    if Confirm.ask("\nApakah Anda ingin mengganti Model Gemini?", default=False):
        console.print("\nPilihan Model yang tersedia:")
        for idx, m in enumerate(config.DEFAULT_MODELS, 1):
            console.print(f"  {idx}. [cyan]{m}[/cyan]")
        choice = IntPrompt.ask("Pilih nomor model", default=1)
        if 1 <= choice <= len(config.DEFAULT_MODELS):
            selected_model = config.DEFAULT_MODELS[choice - 1]
            config.save_api_key(llm.api_key, selected_model)
            llm.model = selected_model
            console.print(f"[bold green]✓ Model diubah ke: {selected_model}[/bold green]")


def select_existing_project() -> Optional[NovelProject]:
    """Display list of projects and load selected one."""
    projects = ProjectManager.list_projects()
    if not projects:
        console.print("[yellow]Belum ada proyek novel yang tersimpan. Silakan buat proyek baru terlebih dahulu.[/yellow]")
        return None

    table = Table(title="📚 Daftar Proyek Novel", border_style="cyan")
    table.add_column("No", justify="center", style="bold cyan")
    table.add_column("Judul Novel", style="bold white")
    table.add_column("Genre", style="green")
    table.add_column("Penulis", style="yellow")
    table.add_column("Status Bab", justify="center")

    for idx, p in enumerate(projects, 1):
        slug = p.get("slug", "")
        proj_dir = config.PROJECTS_DIR / slug
        drafted_count = len(list((proj_dir / "chapters").glob("chapter_*.md")))
        table.add_row(
            str(idx),
            p.get("title", "Tanpa Judul"),
            p.get("genre", "-"),
            p.get("author", "-"),
            f"[bold green]{drafted_count}[/bold green] bab ditulis",
        )

    console.print(table)
    choice = IntPrompt.ask("\nPilih nomor proyek untuk dibuka", default=1)
    if 1 <= choice <= len(projects):
        slug = projects[choice - 1]["slug"]
        project = ProjectManager.load_project(slug)
        console.print(f"[bold green]✓ Proyek '{project.metadata.get('title')}' berhasil dibuka![/bold green]")
        return project

    return None


def show_world_and_characters(project: NovelProject) -> None:
    """View world lore and character bible."""
    print_header(f"📖 World Lore & Karakter - {project.metadata.get('title')}")

    # World details
    wb = project.world_bible
    console.print(Panel(
        f"[bold cyan]Latar:[/bold cyan] {wb.get('setting_name')}\n"
        f"[bold cyan]Atmosfer:[/bold cyan] {wb.get('atmosphere')}\n"
        f"[bold cyan]Aturan / Sistem:[/bold cyan] {wb.get('rules_and_systems')}\n"
        f"[bold cyan]Sejarah / Lore:[/bold cyan] {wb.get('historical_lore')}",
        title="🏛️ World Bible",
        border_style="blue",
    ))

    # Characters table
    display_characters_table(project.characters)


def export_novel_flow(project: NovelProject) -> None:
    """Export the novel to markdown and docx."""
    drafted = project.list_drafted_chapters()
    if not drafted:
        console.print("[red]Belum ada bab yang selesai ditulis untuk diekspor.[/red]")
        return

    exporter = NovelExporter(project)
    with console.status("[bold cyan]📦 Mengompilasi naskah novel ke Markdown dan Word (.docx)...[/bold cyan]"):
        md_file, docx_file = exporter.export_all()

    console.print(Panel(
        f"[bold green]✓ Novel berhasil diekspor![/bold green]\n\n"
        f"📄 [bold]File Markdown:[/bold] [cyan]{md_file}[/cyan]\n"
        f"📘 [bold]File Word (DOCX):[/bold] [cyan]{docx_file}[/cyan]\n\n"
        f"[dim]Total bab yang diekspor: {len(drafted)} bab.[/dim]",
        title="🎉 Ekspor Berhasil",
        border_style="green",
    ))


def check_api_key_prompt(llm: LLMClient) -> None:
    """Ensure Gemini API key is present, prompt if missing."""
    if not llm.api_key:
        console.print(Panel(
            "[bold yellow]⚠️ Gemini API Key Belum Ditemukan![/bold yellow]\n\n"
            "Untuk menggunakan agen AI dalam merancang dan menulis novel,\n"
            "Anda memerlukan Gemini API Key (Bisa didapatkan gratis di https://aistudio.google.com/app/apikey).",
            border_style="yellow",
        ))
        key = Prompt.ask("[bold cyan]Masukkan Gemini API Key Anda sekarang (atau tekan Enter untuk lewati)[/bold cyan]", default="")
        if key.strip():
            config.save_api_key(key.strip(), llm.model)
            llm.set_api_key(key.strip())
            console.print("[bold green]✓ API Key berhasil disimpan![/bold green]\n")


def main() -> None:
    """Application main loop."""
    print_banner()

    llm = LLMClient()
    check_api_key_prompt(llm)

    current_project: Optional[NovelProject] = None

    while True:
        # Display current project status bar
        if current_project:
            title = current_project.metadata.get("title", "Tanpa Judul")
            drafted_count = len(current_project.list_drafted_chapters())
            total_target = current_project.metadata.get("target_chapters", 0)
            console.print(
                f"[bold magenta]📍 Proyek Aktif:[/bold magenta] [bold white]{title}[/bold white] "
                f"([green]{drafted_count}/{total_target} bab[/green])"
            )
        else:
            console.print("[dim]Belum ada proyek aktif yang dipilih.[/dim]")

        console.print("\n[bold cyan]=== MENU UTAMA GHOSTWRITER ===[/bold cyan]")
        console.print("  [bold white]1.[/bold white] 🌟 Buat Proyek Novel Baru (Wizard Multi-Agen)")
        console.print("  [bold white]2.[/bold white] 📂 Buka Proyek Novel yang Ada")
        console.print("  [bold white]3.[/bold white] ✍️ Tulis / Lanjutkan Bab (Scene Planner + Prose Writer)")
        console.print("  [bold white]4.[/bold white] 🔍 Audit & Edit Bab (Continuity & Style Editor)")
        console.print("  [bold white]5.[/bold white] 📖 Baca Naskah Bab di Terminal")
        console.print("  [bold white]6.[/bold white] 👥 Lihat Karakter & World Bible")
        console.print("  [bold white]7.[/bold white] 📦 Export Novel (Markdown & Word .docx)")
        console.print("  [bold white]8.[/bold white] ⚙️ Pengaturan API Key & Model")
        console.print("  [bold white]9.[/bold white] 🚪 Keluar")

        choice = Prompt.ask("\n[bold green]Pilih opsi (1-9)[/bold green]", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"], default="1")

        if choice == "1":
            try:
                current_project = run_new_novel_wizard(llm)
            except Exception as e:
                console.print(f"[bold red]Terjadi kesalahan saat membuat novel:[/bold red] {e}")

        elif choice == "2":
            proj = select_existing_project()
            if proj:
                current_project = proj

        elif choice == "3":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu (Opsi 1 atau 2).[/yellow]")
            else:
                try:
                    write_chapter_flow(current_project, llm)
                except Exception as e:
                    console.print(f"[bold red]Terjadi kesalahan saat menulis bab:[/bold red] {e}")

        elif choice == "4":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                try:
                    audit_chapter_flow(current_project, llm)
                except Exception as e:
                    console.print(f"[bold red]Terjadi kesalahan saat audit bab:[/bold red] {e}")

        elif choice == "5":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                view_chapter_flow(current_project)

        elif choice == "6":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                show_world_and_characters(current_project)

        elif choice == "7":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                try:
                    export_novel_flow(current_project)
                except Exception as e:
                    console.print(f"[bold red]Terjadi kesalahan saat ekspor:[/bold red] {e}")

        elif choice == "8":
            manage_settings(llm)

        elif choice == "9":
            console.print("\n[bold cyan]Terima kasih telah menggunakan GhostWriter AI! Selamat berkarya.[/bold cyan] 🖋️\n")
            break

        console.print("\n" + "─" * 60 + "\n")


if __name__ == "__main__":
    main()
