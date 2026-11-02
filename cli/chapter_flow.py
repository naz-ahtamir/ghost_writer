"""Chapter drafting, scene planning, audit, and editing workflow."""

from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, IntPrompt, Confirm
from cli.ui import (
    console,
    print_header,
    display_chapters_table,
    display_audit_panel,
)
from core.llm import LLMClient
from core.project import NovelProject
from agents.scene_planner import ScenePlannerAgent
from agents.writer import WriterAgent
from agents.editor import EditorAgent


def select_chapter_info(project: NovelProject) -> dict:
    """Prompt user to select a chapter from the outline."""
    chapters = project.outline.get("chapters", [])
    if not chapters:
        console.print("[red]Outline bab belum tersedia dalam proyek ini.[/red]")
        return {}

    drafted = project.list_drafted_chapters()
    display_chapters_table(chapters, drafted)

    # Suggest next undrafted chapter
    default_ch = 1
    for ch in chapters:
        if ch.get("chapter_number") not in drafted:
            default_ch = ch.get("chapter_number", 1)
            break

    ch_num = IntPrompt.ask("\n[bold cyan]Pilih Nomor Bab[/bold cyan]", default=default_ch)
    for ch in chapters:
        if ch.get("chapter_number") == ch_num:
            return ch

    # Fallback placeholder if not found
    return {
        "chapter_number": ch_num,
        "title": f"Bab {ch_num}",
        "pov_character": "Protagonis",
        "setting": "Latar Utama",
        "summary": "Peristiwa penting bab ini",
        "conflict": "Konflik utama",
        "turning_point": "Titik balik cerita",
    }


def write_chapter_flow(project: NovelProject, llm: LLMClient) -> None:
    """Execute the full drafting flow for a chapter."""
    ch_info = select_chapter_info(project)
    if not ch_info:
        return

    ch_num = ch_info.get("chapter_number", 1)
    ch_title = ch_info.get("title", f"Bab {ch_num}")

    print_header(f"✍️ Menulis Bab {ch_num}: {ch_title}", f"POV: {ch_info.get('pov_character')} | Lokasi: {ch_info.get('setting')}")

    # Check if chapter already drafted
    existing = project.get_chapter(ch_num)
    if existing:
        if not Confirm.ask(f"[bold yellow]Bab {ch_num} sudah pernah ditulis. Apakah Anda ingin menulis ulang dari awal?[/bold yellow]", default=False):
            return

    # Step 1: Scene Planner Agent
    planner = ScenePlannerAgent(llm)
    with console.status(f"[bold cyan]📋 Scene Planner Agent sedang merancang ketukan adegan (beats) untuk Bab {ch_num}...[/bold cyan]"):
        beats = planner.generate_beats(project, ch_info)

    console.print("\n[bold green]📋 Rencana Ketukan Adegan (Scene Beats):[/bold green]")
    for b in beats:
        num = b.get("beat_number", "-")
        name = b.get("beat_name", "Adegan")
        goal = b.get("goal", "")
        obstacle = b.get("obstacle", "")
        sensory = b.get("sensory_details", "")
        console.print(f"  [bold cyan]Beat {num}: {name}[/bold cyan]")
        console.print(f"    [dim]• Target: {goal} | Hambatan: {obstacle}[/dim]")
        if sensory:
            console.print(f"    [dim italic]• Panca Indera: {sensory}[/dim italic]")

    if not Confirm.ask("\n[bold green]Lanjutkan penulisan naskah lengkap oleh Prose Writer Agent?[/bold green]", default=True):
        return

    # Step 2: Prose Writer Agent
    writer = WriterAgent(llm)
    with console.status(f"[bold magenta]✍️ Prose Writer Agent sedang menyusun naskah Bab {ch_num} dengan gaya sastra...[/bold magenta]"):
        prose = writer.write_chapter(project, ch_info, beats)

    word_count = len(prose.split())
    console.print(f"\n[bold green]🎉 Bab {ch_num}: {ch_title} selesai ditulis! ({word_count} kata)[/bold green]\n")

    # Preview options
    if Confirm.ask("[bold cyan]Tampilkan naskah bab di layar terminal sekarang?[/bold cyan]", default=True):
        console.print(Panel(Markdown(prose), title=f"📖 Naskah Bab {ch_num}: {ch_title}", border_style="blue"))

    # Offer immediate audit
    if Confirm.ask("\n[bold yellow]Lakukan audit kontinuitas & gaya bahasa dengan Editor Agent sekarang?[/bold yellow]", default=True):
        audit_chapter_flow(project, llm, ch_num)


def audit_chapter_flow(project: NovelProject, llm: LLMClient, specific_chapter: int = None) -> None:
    """Run Editor Agent audit on a chapter and offer revision."""
    drafted = project.list_drafted_chapters()
    if not drafted:
        console.print("[red]Belum ada bab yang selesai ditulis. Tulis bab terlebih dahulu.[/red]")
        return

    if specific_chapter is None:
        console.print(f"[dim]Bab yang tersedia: {drafted}[/dim]")
        specific_chapter = IntPrompt.ask("[bold cyan]Pilih Nomor Bab untuk diaudit[/bold cyan]", default=drafted[-1])

    if specific_chapter not in drafted:
        console.print(f"[red]Bab {specific_chapter} belum ditulis.[/red]")
        return

    prose = project.get_chapter(specific_chapter) or ""
    ch_info = next(
        (ch for ch in project.outline.get("chapters", []) if ch.get("chapter_number") == specific_chapter),
        {"chapter_number": specific_chapter, "title": f"Bab {specific_chapter}"},
    )

    editor = EditorAgent(llm)
    with console.status(f"[bold cyan]🔍 Editor Agent sedang memeriksa alur logika, plothole, dan kualitas prosa...[/bold cyan]"):
        audit_data = editor.audit_chapter(project, ch_info, prose)

    display_audit_panel(audit_data, ch_info.get("title", f"Bab {specific_chapter}"))

    # Revision option
    if Confirm.ask("\n[bold yellow]Ingin Editor Agent memoles / merevisi bab ini secara otomatis berdasarkan catatan audit?[/bold yellow]", default=False):
        user_notes = Prompt.ask("[bold cyan]Catatan / arahan tambahan Anda (opsional, tekan Enter untuk lewati)[/bold cyan]", default="")
        critique_summary = f"Kritik: {audit_data.get('pacing_and_style_critique')}. Saran: {', '.join(audit_data.get('actionable_suggestions', []))}"

        with console.status("[bold magenta]✂️ Editor Agent sedang memoles dan memperhalus naskah bab...[/bold magenta]"):
            revised_prose = editor.revise_chapter(
                project=project,
                chapter_info=ch_info,
                original_prose=prose,
                critique_feedback=critique_summary,
                user_instructions=user_notes,
            )

        new_count = len(revised_prose.split())
        console.print(f"\n[bold green]✓ Naskah Bab {specific_chapter} berhasil direvisi dan disimpan! ({new_count} kata)[/bold green]")

        if Confirm.ask("[bold cyan]Lihat naskah hasil revisi?[/bold cyan]", default=True):
            console.print(Panel(Markdown(revised_prose), title=f"✨ Naskah Hasil Revisi - Bab {specific_chapter}", border_style="green"))


def view_chapter_flow(project: NovelProject) -> None:
    """Read a drafted chapter with rich markdown formatting."""
    drafted = project.list_drafted_chapters()
    if not drafted:
        console.print("[red]Belum ada bab yang ditulis dalam proyek ini.[/red]")
        return

    console.print(f"[dim]Bab yang tersedia: {drafted}[/dim]")
    num = IntPrompt.ask("[bold cyan]Pilih Nomor Bab untuk dibaca[/bold cyan]", default=drafted[0])
    text = project.get_chapter(num)
    if not text:
        console.print(f"[red]Bab {num} belum ada naskahnya.[/red]")
        return

    console.print(Panel(Markdown(text), title=f"📖 Tampilan Bab {num}", border_style="cyan"))
