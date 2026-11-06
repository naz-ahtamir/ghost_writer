"""Chapter drafting, scene planning, beat customization, audit, and editing workflow."""

from typing import Any, Dict, List, Optional

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


def select_chapter_info(project: NovelProject, llm: Optional[LLMClient] = None) -> dict:
    """Prompt user to select a chapter from the outline."""
    chapters = project.outline.get("chapters", [])
    if not chapters:
        console.print("[bold yellow]⚠️ Outline bab belum tersedia dalam proyek ini (Fondasi cerita belum selesai).[/bold yellow]")
        if llm:
            if Confirm.ask("[bold cyan]Apakah Anda ingin menjalankan AI Agent sekarang untuk melengkapi fondasi (World Bible, Karakter, & Outline)?[/bold cyan]", default=True):
                from cli.wizard import resume_project_foundation
                success = resume_project_foundation(project, llm)
                if success and project.is_outline_complete():
                    chapters = project.outline.get("chapters", [])
                else:
                    return {}
            else:
                return {}
        else:
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


def display_beats_list(beats: List[Dict[str, Any]]) -> None:
    """Render the chapter's scene beats clearly in the terminal."""
    console.print("\n[bold green]📋 Rencana Ketukan Adegan (Scene Beats):[/bold green]")
    for idx, b in enumerate(beats, 1):
        num = b.get("beat_number", idx)
        name = b.get("beat_name", f"Adegan {idx}")
        events = b.get("scene_events") or b.get("description") or b.get("goal", "")
        goal = b.get("goal", "")
        obstacle = b.get("obstacle", "")
        sensory = b.get("sensory_details", "")
        emotion = b.get("emotional_shift", "")
        console.print(f"  [bold cyan]Beat {num}: {name}[/bold cyan]")
        if events:
            console.print(f"    [white]• Kejadian/Aksi : {events}[/white]")
        console.print(f"    [dim]• Tujuan: {goal} | Hambatan: {obstacle}[/dim]")
        if sensory:
            console.print(f"    [dim italic]• Panca Indera: {sensory}[/dim italic]")
        if emotion:
            console.print(f"    [dim yellow]• Perubahan Emosi: {emotion}[/dim yellow]")


def edit_beats_interactively(
    project: NovelProject,
    ch_num: int,
    beats: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Allow the user to freely edit, add, or delete scene beats."""
    while True:
        display_beats_list(beats)
        console.print("\n[bold cyan]Menu Kustomisasi Beat (Mode Bebas):[/bold cyan]")
        console.print("  [white]1.[/white] Ubah isi Beat tertentu")
        console.print("  [white]2.[/white] Tambah Beat baru")
        console.print("  [white]3.[/white] Hapus Beat tertentu")
        console.print("  [white]4.[/white] Selesai & Simpan Beat")

        sub = Prompt.ask("Pilih aksi", choices=["1", "2", "3", "4"], default="4")
        if sub == "4":
            break
        elif sub == "1" and beats:
            b_idx = IntPrompt.ask(f"Pilih nomor Beat yang ingin diubah (1-{len(beats)})", default=1)
            if 1 <= b_idx <= len(beats):
                target = beats[b_idx - 1]
                target["beat_name"] = Prompt.ask("Nama/Judul Beat", default=target.get("beat_name", f"Beat {b_idx}"))
                target["scene_events"] = Prompt.ask(
                    "Rangkaian Kejadian & Aksi Wajib (bebas tanpa sensor)",
                    default=target.get("scene_events", ""),
                )
                target["goal"] = Prompt.ask("Tujuan Karakter di Beat ini", default=target.get("goal", ""))
                target["obstacle"] = Prompt.ask("Hambatan / Konflik", default=target.get("obstacle", ""))
                target["sensory_details"] = Prompt.ask("Detail Panca Indera & Fisik", default=target.get("sensory_details", ""))
                target["emotional_shift"] = Prompt.ask("Perubahan Emosi", default=target.get("emotional_shift", ""))
                console.print(f"[bold green]✓ Beat {b_idx} berhasil diperbarui![/bold green]")
        elif sub == "2":
            new_num = len(beats) + 1
            name = Prompt.ask("Nama/Judul Beat Baru", default=f"Adegan {new_num}")
            events = Prompt.ask("Rangkaian Kejadian & Aksi Wajib di Beat ini")
            goal = Prompt.ask("Tujuan Karakter", default=events)
            obstacle = Prompt.ask("Hambatan / Konflik", default="Ketegangan dan rintangan adegan")
            sensory = Prompt.ask("Detail Panca Indera & Fisik", default="Suasana ruang, gestur fisik, dialog, dan kontak nyata")
            emotion = Prompt.ask("Perubahan Emosi", default="Eskalasi emosi karakter")
            beats.append({
                "beat_number": new_num,
                "beat_name": name,
                "scene_events": events,
                "goal": goal,
                "obstacle": obstacle,
                "sensory_details": sensory,
                "emotional_shift": emotion,
            })
            console.print(f"[bold green]✓ Beat {new_num} berhasil ditambahkan![/bold green]")
        elif sub == "3" and len(beats) > 1:
            b_idx = IntPrompt.ask(f"Pilih nomor Beat yang ingin dihapus (1-{len(beats)})", default=len(beats))
            if 1 <= b_idx <= len(beats):
                removed = beats.pop(b_idx - 1)
                for i, item in enumerate(beats, 1):
                    item["beat_number"] = i
                console.print(f"[yellow]Beat '{removed.get('beat_name')}' dihapus.[/yellow]")

    beats = ScenePlannerAgent.normalize_beats(beats)
    project.save_chapter_beats(ch_num, beats)
    return beats


def create_manual_beats_flow(project: NovelProject, ch_num: int) -> List[Dict[str, Any]]:
    """Allow the user to write their own beats from scratch with 100% freedom."""
    console.print("\n[bold yellow]✍️ Mode Input Beat Manual (100% Bebas Tanpa Sensor)[/bold yellow]")
    console.print("[dim]Masukkan urutan adegan (beat) yang Anda inginkan untuk bab ini.[/dim]")
    count = IntPrompt.ask("Berapa jumlah Beat yang ingin Anda buat?", default=3)
    count = max(1, min(12, count))
    manual_beats: List[Dict[str, Any]] = []
    for i in range(1, count + 1):
        console.print(f"\n[bold cyan]--- Beat {i}/{count} ---[/bold cyan]")
        name = Prompt.ask(f"Judul Beat {i}", default=f"Beat {i}")
        events = Prompt.ask(f"Apa saja kejadian/aksi yang WAJIB ditulis di Beat {i}?")
        goal = Prompt.ask(f"Tujuan karakter di Beat {i} (Enter untuk samakan)", default=events)
        obstacle = Prompt.ask(f"Konflik/Hambatan di Beat {i}", default="Tensi dan rintangan adegan")
        sensory = Prompt.ask(f"Fokus Panca Indera / Fisik di Beat {i}", default="Detail ekspresi, gestur, suara, dan sensasi fisik")
        emotion = Prompt.ask(f"Perubahan Emosi di akhir Beat {i}", default="Emosi semakin intens")
        manual_beats.append({
            "beat_number": i,
            "beat_name": name,
            "scene_events": events,
            "goal": goal,
            "obstacle": obstacle,
            "sensory_details": sensory,
            "emotional_shift": emotion,
        })
    project.save_chapter_beats(ch_num, manual_beats)
    return manual_beats


def write_chapter_flow(project: NovelProject, llm: LLMClient) -> None:
    """Execute the full drafting flow for a chapter with complete beat control."""
    ch_info = select_chapter_info(project, llm)
    if not ch_info:
        return

    ch_num = ch_info.get("chapter_number", 1)
    ch_title = ch_info.get("title", f"Bab {ch_num}")

    print_header(
        f"✍️ Menulis Bab {ch_num}: {ch_title} (Uncensored Mode)",
        f"POV: {ch_info.get('pov_character')} | Lokasi: {ch_info.get('setting')}",
    )

    console.print(Panel(
        f"[bold cyan]Ringkasan Bab:[/bold cyan] {ch_info.get('summary', '-')}\n"
        f"[bold cyan]Konflik Utama:[/bold cyan] {ch_info.get('conflict', '-')}\n"
        f"[bold cyan]Titik Balik Akhir:[/bold cyan] {ch_info.get('turning_point', '-')}",
        title=f"📌 Rencana Bab {ch_num}",
        border_style="cyan",
    ))

    # Check if chapter already drafted
    existing = project.get_chapter(ch_num)
    if existing:
        if not Confirm.ask(f"[bold yellow]Bab {ch_num} sudah pernah ditulis. Apakah Anda ingin menulis ulang?[/bold yellow]", default=False):
            return

    # Optional free-form scenario / custom direction from user
    custom_direction = Prompt.ask(
        "\n[bold yellow]Arahan Bebas / Skenario Khusus Bab Ini[/bold yellow] [dim](opsional: tulis adegan/konflik/momen spesifik yang wajib ada, atau tekan Enter)[/dim]",
        default="",
    ).strip()

    planner = ScenePlannerAgent(llm)
    saved_beats = project.get_chapter_beats(ch_num)

    if saved_beats and not custom_direction:
        if Confirm.ask(f"[bold cyan]Ditemukan {len(saved_beats)} Scene Beats tersimpan untuk Bab {ch_num}. Gunakan beat tersebut?[/bold cyan]", default=True):
            beats = ScenePlannerAgent.normalize_beats(saved_beats, chapter_info=ch_info)
        else:
            with console.status(f"[bold cyan]📋 Scene Planner Agent sedang merancang ketukan adegan (beats) untuk Bab {ch_num}...[/bold cyan]"):
                beats = planner.generate_beats(project, ch_info, custom_direction=custom_direction)
    else:
        with console.status(f"[bold cyan]📋 Scene Planner Agent sedang merancang ketukan adegan (beats) untuk Bab {ch_num}...[/bold cyan]"):
            beats = planner.generate_beats(project, ch_info, custom_direction=custom_direction)

    # Interactive Beat Review & Writing Mode Loop
    beat_by_beat_mode = True
    while True:
        display_beats_list(beats)

        console.print("\n[bold cyan]Pilih Mode Eksekusi Naskah & Kendali Beat:[/bold cyan]")
        console.print("  [bold green]1.[/bold green] ✍️ Tulis Naskah — [bold]Susun Per Beat (Beat-by-Beat)[/bold] [dim](Rekomendasi: Akurat mengikuti tiap Beat, Utuh & Mendalam)[/dim]")
        console.print("  [bold white]2.[/bold white] ⚡ Tulis Naskah — [bold]Susun Sekaligus (Single-Pass)[/bold] [dim](Lebih cepat dalam 1x panggilan)[/dim]")
        console.print("  [bold yellow]3.[/bold yellow] 🛠️ Edit / Tambah / Hapus Beat (Kustomisasi Bebas)")
        console.print("  [bold yellow]4.[/bold yellow] 📝 Buat Beat Manual Sendiri dari Awal (100% Bebas)")
        console.print("  [bold cyan]5.[/bold cyan] 🔄 Generate Ulang Beat oleh AI (Masukkan Arahan Baru)")
        console.print("  [bold red]6.[/bold red] 🚪 Batal / Kembali")

        action = Prompt.ask("\n[bold green]Pilih aksi (1-6)[/bold green]", choices=["1", "2", "3", "4", "5", "6"], default="1")

        if action == "1":
            beat_by_beat_mode = True
            break
        elif action == "2":
            beat_by_beat_mode = False
            break
        elif action == "3":
            beats = edit_beats_interactively(project, ch_num, beats)
        elif action == "4":
            beats = create_manual_beats_flow(project, ch_num)
        elif action == "5":
            custom_direction = Prompt.ask("[bold yellow]Masukkan arahan/skenario baru untuk pembuatan Beat[/bold yellow]", default=custom_direction)
            with console.status(f"[bold cyan]📋 Scene Planner Agent sedang merancang ulang beats untuk Bab {ch_num}...[/bold cyan]"):
                beats = planner.generate_beats(project, ch_info, custom_direction=custom_direction)
        elif action == "6":
            return

    # Step 2: Prose Writer Agent
    writer = WriterAgent(llm)
    if beat_by_beat_mode and len(beats) > 1:
        console.print(f"\n[bold magenta]✍️ Prose Writer Agent menyusun Bab {ch_num} secara berurutan ({len(beats)} Beats)...[/bold magenta]")
        status_ctx = console.status("[bold magenta]Menyiapkan penulisan Beat 1...[/bold magenta]")
        status_ctx.start()
        try:
            def on_beat_progress(idx: int, total: int, beat: Dict[str, Any]) -> None:
                b_name = beat.get("beat_name", f"Beat {idx}")
                status_ctx.update(f"[bold magenta]✍️ Menyusun Beat {idx}/{total}: \"{b_name}\" (Tanpa Sensor)...[/bold magenta]")
                console.print(f"  [cyan]→ Menyusun Beat {idx}/{total}:[/cyan] [bold white]{b_name}[/bold white]")

            prose = writer.write_chapter(
                project=project,
                chapter_info=ch_info,
                beats=beats,
                custom_instructions=custom_direction,
                beat_by_beat=True,
                progress_callback=on_beat_progress,
            )
        finally:
            status_ctx.stop()
    else:
        with console.status(f"[bold magenta]✍️ Prose Writer Agent sedang menyusun naskah Bab {ch_num} berdasarkan blueprint beat...[/bold magenta]"):
            prose = writer.write_chapter(
                project=project,
                chapter_info=ch_info,
                beats=beats,
                custom_instructions=custom_direction,
                beat_by_beat=False,
            )

    word_count = len(prose.split())
    console.print(f"\n[bold green]🎉 Bab {ch_num}: {ch_title} selesai disusun berdasarkan {len(beats)} beat! ({word_count} kata)[/bold green]\n")

    # Preview options
    if Confirm.ask("[bold cyan]Tampilkan naskah bab di layar terminal sekarang?[/bold cyan]", default=True):
        console.print(Panel(Markdown(prose), title=f"📖 Naskah Bab {ch_num}: {ch_title}", border_style="blue"))

    # Offer immediate audit
    if Confirm.ask("\n[bold yellow]Lakukan audit kontinuitas & kepatuhan beat dengan Editor Agent sekarang?[/bold yellow]", default=True):
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
    with console.status(f"[bold cyan]🔍 Editor Agent sedang memeriksa kepatuhan beat, alur logika, dan kualitas prosa...[/bold cyan]"):
        audit_data = editor.audit_chapter(project, ch_info, prose)

    display_audit_panel(audit_data, ch_info.get("title", f"Bab {specific_chapter}"))

    # Revision option
    if Confirm.ask("\n[bold yellow]Ingin Editor Agent memoles / merevisi bab ini secara otomatis berdasarkan catatan audit?[/bold yellow]", default=False):
        user_notes = Prompt.ask("[bold cyan]Catatan / arahan tambahan Anda (opsional, tekan Enter untuk lewati)[/bold cyan]", default="")
        critique_summary = f"Kritik: {audit_data.get('pacing_and_style_critique')}. Saran: {', '.join(audit_data.get('actionable_suggestions', []))}"

        with console.status("[bold magenta]✂️ Editor Agent sedang memoles dan memperkuat naskah bab (Tanpa Sensor)...[/bold magenta]"):
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
