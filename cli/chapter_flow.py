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
from agents.illustrator import IllustratorAgent


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

    # Automatically generate & render 3 Consistent Realistic Illustrations for this chapter
    if Confirm.ask(
        f"\n[bold magenta]🎨 Generate & Render 3 Ilustrasi Bab {ch_num} (Konsisten, Fotorealistis & Sensor Terendah) sekarang?[/bold magenta]",
        default=True,
    ):
        illustrator = IllustratorAgent(llm)
        with console.status("[bold cyan]🧬 Mengunci Visual Bible & Character Visual DNA...[/bold cyan]"):
            illustrator.ensure_visual_bible(project)
        with console.status(f"[bold magenta]🎨 Merancang 3 adegan ilustrasi Bab {ch_num} (Opening, Tengah, Klimaks)...[/bold magenta]"):
            illustrations = illustrator.plan_chapter_illustrations(project, ch_info, custom_direction=custom_direction)

        status_ctx = console.status("[bold magenta]Me-render 3 file gambar ilustrasi...[/bold magenta]")
        status_ctx.start()
        try:
            def _auto_render_cb(slot_num: int, total: int, item: Dict[str, Any]) -> None:
                s_title = item.get("scene_title", f"Ilustrasi {slot_num}")
                status_ctx.update(f"[bold magenta]🎨 Me-render Ilustrasi {slot_num}/{total}: \"{s_title}\"...[/bold magenta]")
                console.print(f"  [cyan]→ Rendering Ilustrasi {slot_num}/{total}:[/cyan] [bold white]{s_title}[/bold white]")

            illustrations = illustrator.render_chapter_illustrations(
                project=project,
                chapter_num=ch_num,
                illustrations=illustrations,
                progress_callback=_auto_render_cb,
            )
        finally:
            status_ctx.stop()

        prose_with_illus = IllustratorAgent.inject_illustrations_into_markdown(prose, illustrations)
        project.save_chapter(ch_num, prose_with_illus)
        display_illustrations_list(illustrations, ch_num)
        console.print(f"[bold green]✓ 3 Ilustrasi Bab {ch_num} berhasil di-generate dan disisipkan ke naskah![/bold green]")

        if Confirm.ask("[bold cyan]Ingin mengedit pose/prompt atau me-render ulang salah satu ilustrasi di Studio Ilustrasi?[/bold cyan]", default=False):
            illustrate_chapter_flow(project, llm, specific_chapter=ch_num)

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
    illus_list = project.get_chapter_illustrations(num)
    if illus_list:
        display_illustrations_list(illus_list, num)


def display_illustrations_list(illustrations: List[Dict[str, Any]], ch_num: int) -> None:
    """Display the 3 chapter illustrations (Opening, Middle, Climax) with prompts and file paths."""
    from pathlib import Path
    console.print(f"\n[bold magenta]🎨 Daftar 3 Ilustrasi Bab {ch_num} (Konsisten, Realistis & Tanpa Sensor):[/bold magenta]")
    for idx, item in enumerate(illustrations, 1):
        num = item.get("illustration_number", idx)
        role_label = item.get("slot_label") or item.get("slot_role", f"Slot {num}")
        title = item.get("scene_title", f"Ilustrasi {num}")
        caption = item.get("caption", "")
        chars = ", ".join(item.get("characters_present", [])) or "-"
        camera = item.get("camera_shot", "")
        pose = item.get("pose_and_action", "")
        seed = item.get("seed", "-")
        img_path = item.get("image_path", "")
        status = item.get("status", "planned")
        engine = item.get("engine", "-")

        file_exists = bool(img_path and Path(img_path).exists())
        status_badge = (
            f"[bold green]✓ File Gambar Siap ({engine})[/bold green]"
            if file_exists and status == "rendered"
            else f"[bold yellow]🖼️ Storyboard Frame ({Path(img_path).name})[/bold yellow]"
            if file_exists
            else "[dim yellow]Belum Di-render ke Gambar[/dim yellow]"
        )

        console.print(
            Panel(
                f"[bold cyan]Judul Visual:[/bold cyan] {title}  |  [bold]Posisi:[/bold] {role_label}\n"
                f"[bold cyan]Status Render:[/bold cyan] {status_badge}  |  [bold]Seed Konsistensi:[/bold] {seed}\n"
                f"[bold cyan]File Gambar:[/bold cyan] [underline]{img_path}[/underline]\n"
                f"[bold cyan]Tokoh di Frame (Visual DNA Terkunci):[/bold cyan] {chars}\n"
                f"[bold cyan]Kamera & Lensa:[/bold cyan] {camera}\n"
                f"[bold cyan]Pose & Aksi (Uncensored):[/bold cyan] {pose}\n"
                f"[bold yellow]Caption Buku:[/bold yellow] [italic]\"{caption}\"[/italic]\n"
                f"[dim]Full Prompt: {item.get('image_prompt', '')[:260]}...[/dim]",
                title=f"🖼️ Ilustrasi {num}/3 — {title}",
                border_style="magenta",
            )
        )


def edit_visual_bible_interactively(project: NovelProject, illustrator: IllustratorAgent) -> None:
    """Allow the user to inspect and customize Character Visual DNA and Style Anchor."""
    vb = illustrator.ensure_visual_bible(project)
    while True:
        reg = vb.get("character_visual_registry", [])
        reg_lines = []
        for idx, c in enumerate(reg, 1):
            reg_lines.append(
                f"[bold yellow]{idx}. {c.get('name')}[/bold yellow] (Seed: {c.get('character_seed')})\n"
                f"   [white]Visual DNA:[/white] {c.get('visual_dna')}"
            )
        reg_text = "\n".join(reg_lines) or "Belum ada karakter."

        console.print(
            Panel(
                f"[bold cyan]Preset Gaya:[/bold cyan] {vb.get('visual_style_preset')}\n"
                f"[bold cyan]Master Seed Proyek:[/bold cyan] {vb.get('master_seed')}\n"
                f"[bold cyan]Style Anchor Tags:[/bold cyan] {vb.get('style_anchor_tags')}\n"
                f"[bold cyan]Lighting & Color Grading:[/bold cyan] {vb.get('color_grading_and_lighting')}\n\n"
                f"[bold green]🧬 Character Visual DNA (Terkunci di Semua Bab):[/bold green]\n{reg_text}",
                title="🧬 Visual Bible & Konsistensi Karakter",
                border_style="green",
            )
        )

        console.print("  [white]1.[/white] Ubah Visual DNA Karakter tertentu (Wajah, Tubuh, Rambut, Pakaian)")
        console.print("  [white]2.[/white] Ubah Style Anchor / Gaya Fotorealistis & Pencahayaan")
        console.print("  [white]3.[/white] Generate Ulang Visual Bible otomatis dengan AI")
        console.print("  [white]4.[/white] Selesai & Kembali")

        ch = Prompt.ask("Pilih opsi", choices=["1", "2", "3", "4"], default="4")
        if ch == "4":
            break
        elif ch == "1" and reg:
            c_idx = IntPrompt.ask(f"Pilih nomor karakter (1-{len(reg)})", default=1)
            if 1 <= c_idx <= len(reg):
                target = reg[c_idx - 1]
                target["visual_dna"] = Prompt.ask(
                    f"Visual DNA Bahasa Inggris untuk {target.get('name')}",
                    default=target.get("visual_dna", ""),
                )
                # Sync back to project.characters
                for pc in project.characters:
                    if pc.get("name", "").strip().lower() == target.get("name", "").strip().lower():
                        pc["visual_dna"] = target["visual_dna"]
                project.save_characters(project.characters)
                project.save_visual_bible(vb)
                console.print(f"[bold green]✓ Visual DNA '{target.get('name')}' berhasil dikunci![/bold green]")
        elif ch == "2":
            vb["style_anchor_tags"] = Prompt.ask("Style Anchor Tags (English)", default=vb.get("style_anchor_tags", ""))
            vb["color_grading_and_lighting"] = Prompt.ask(
                "Lighting & Color Grading (English)",
                default=vb.get("color_grading_and_lighting", ""),
            )
            project.save_visual_bible(vb)
            console.print("[bold green]✓ Style Anchor berhasil diperbarui![/bold green]")
        elif ch == "3":
            with console.status("[bold cyan]🎨 Menyusun ulang Visual Bible & Character DNA...[/bold cyan]"):
                vb = illustrator.ensure_visual_bible(project, force_regenerate=True)
            console.print("[bold green]✓ Visual Bible berhasil diperbarui![/bold green]")


def edit_illustrations_interactively(
    project: NovelProject,
    ch_num: int,
    illustrations: List[Dict[str, Any]],
    illustrator: IllustratorAgent,
) -> List[Dict[str, Any]]:
    """Allow the user to customize any of the 3 chapter illustrations freely without censorship."""
    while True:
        display_illustrations_list(illustrations, ch_num)
        console.print("\n[bold cyan]Menu Kustomisasi Ilustrasi Bab (100% Bebas Tanpa Sensor):[/bold cyan]")
        console.print("  [white]1.[/white] Edit Ilustrasi 1 (Pembuka Bab)")
        console.print("  [white]2.[/white] Edit Ilustrasi 2 (Konflik Tengah Bab)")
        console.print("  [white]3.[/white] Edit Ilustrasi 3 (Klimaks Akhir Bab)")
        console.print("  [white]4.[/white] Selesai & Simpan Rencana Ilustrasi")

        sub = Prompt.ask("Pilih nomor (1-4)", choices=["1", "2", "3", "4"], default="4")
        if sub == "4":
            break
        slot_idx = int(sub) - 1
        if 0 <= slot_idx < len(illustrations):
            target = illustrations[slot_idx]
            console.print(f"\n[bold magenta]--- Edit Ilustrasi {slot_idx + 1}: {target.get('scene_title')} ---[/bold magenta]")
            target["scene_title"] = Prompt.ask("Judul Singkat Adegan", default=target.get("scene_title", ""))
            target["caption"] = Prompt.ask("Caption Naratif di Buku", default=target.get("caption", ""))
            chars_str = ", ".join(target.get("characters_present", []))
            new_chars = Prompt.ask("Tokoh yang Tampil (pisahkan koma)", default=chars_str)
            target["characters_present"] = [c.strip() for c in new_chars.split(",") if c.strip()]
            target["camera_shot"] = Prompt.ask("Kamera & Lensa (English)", default=target.get("camera_shot", ""))
            target["pose_and_action"] = Prompt.ask(
                "Pose Fisik, Ekspresi & Aksi Detail (English - Bebas Tanpa Sensor)",
                default=target.get("pose_and_action", ""),
            )
            target["environment_and_lighting"] = Prompt.ask(
                "Latar Ruang & Pencahayaan (English)",
                default=target.get("environment_and_lighting", ""),
            )
            target["seed"] = IntPrompt.ask("Seed Konsistensi Gambar", default=int(target.get("seed", 1000)))
            target["image_prompt"] = illustrator.compose_consistent_prompt(project, target)
            project.save_chapter_illustrations(ch_num, illustrations)
            console.print(f"[bold green]✓ Ilustrasi {slot_idx + 1} berhasil diperbarui dengan Character Visual DNA terkunci![/bold green]")

    return illustrations


def illustrate_chapter_flow(
    project: NovelProject,
    llm: LLMClient,
    specific_chapter: Optional[int] = None,
) -> None:
    """Interactive workflow to plan, customize, render, and embed 3 consistent realistic illustrations per chapter."""
    import config

    if specific_chapter is None:
        ch_info = select_chapter_info(project, llm)
        if not ch_info:
            return
        ch_num = int(ch_info.get("chapter_number", 1))
    else:
        ch_num = specific_chapter
        ch_info = next(
            (ch for ch in project.outline.get("chapters", []) if ch.get("chapter_number") == ch_num),
            {"chapter_number": ch_num, "title": f"Bab {ch_num}"},
        )

    ch_title = ch_info.get("title", f"Bab {ch_num}")
    illustrator = IllustratorAgent(llm)

    print_header(
        f"🎨 Studio Ilustrasi Bab {ch_num}: {ch_title}",
        "3 Ilustrasi per Bab | Konsisten (Visual DNA Lock) | Fotorealistis 8K | Tanpa Sensor",
    )

    # Ensure Visual Bible is ready
    with console.status("[bold cyan]🧬 Memeriksa Visual Bible & Character Visual DNA agar wajah/fisik tokoh konsisten...[/bold cyan]"):
        illustrator.ensure_visual_bible(project)

    illustrations = project.get_chapter_illustrations(ch_num)
    if not illustrations:
        custom_dir = Prompt.ask(
            "\n[bold yellow]Arahan Visual Khusus Bab Ini[/bold yellow] [dim](opsional: tulis suasana/adegan/pose spesifik yang diinginkan, atau tekan Enter)[/dim]",
            default="",
        ).strip()
        with console.status(f"[bold magenta]🎨 Illustrator Agent sedang merancang 3 Ilustrasi Sinematik untuk Bab {ch_num}...[/bold magenta]"):
            illustrations = illustrator.plan_chapter_illustrations(
                project=project,
                chapter_info=ch_info,
                count=config.ILLUSTRATIONS_PER_CHAPTER,
                custom_direction=custom_dir,
            )

    while True:
        display_illustrations_list(illustrations, ch_num)
        img_prov = config.get_image_provider()
        img_model = config.get_image_model(img_prov)
        console.print(
            f"\n[bold blue]🖼️ Image Engine Aktif:[/bold blue] [bold cyan]{img_prov.upper()}[/bold cyan] "
            f"[dim](Model: {img_model} | Resolusi: {config.IMAGE_WIDTH}x{config.IMAGE_HEIGHT} | Safe Filter: OFF)[/dim]"
        )

        console.print("\n[bold cyan]Pilih Aksi Ilustrasi Bab:[/bold cyan]")
        console.print("  [bold green]1.[/bold green] 🚀 Render / Buat File Gambar untuk Ketiga Ilustrasi Sekaligus (3 Gambar .jpg & Sisipkan ke Bab)")
        console.print("  [bold white]2.[/bold white] 🎯 Render Ulang 1 Slot Ilustrasi Tertentu (Pilih Ilustrasi 1, 2, atau 3)")
        console.print("  [bold yellow]3.[/bold yellow] 🛠️ Edit / Kustomisasi Adegan, Pose & Prompt Ilustrasi (100% Bebas Tanpa Sensor)")
        console.print("  [bold cyan]4.[/bold cyan] 🧬 Lihat / Kunci Visual DNA Karakter & Style Fotorealistis (Visual Bible)")
        console.print("  [bold cyan]5.[/bold cyan] 🔄 Rancang Ulang 3 Blueprint Ilustrasi Bab Ini dengan AI")
        console.print("  [bold magenta]6.[/bold magenta] ⚙️ Ganti Engine Pembuat Gambar (Flux Realism Uncensored / Grok Image / Gemini / Local SD)")
        console.print("  [bold red]7.[/bold red] 🚪 Selesai & Kembali")

        action = Prompt.ask("\n[bold green]Pilih aksi (1-7)[/bold green]", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")

        if action == "1":
            status_ctx = console.status("[bold magenta]Menyiapkan rendering 3 ilustrasi fotorealistis...[/bold magenta]")
            status_ctx.start()
            try:
                def on_render_progress(slot_num: int, total: int, item: Dict[str, Any]) -> None:
                    s_title = item.get("scene_title", f"Ilustrasi {slot_num}")
                    status_ctx.update(
                        f"[bold magenta]🎨 Me-render Ilustrasi {slot_num}/{total}: \"{s_title}\" (Seed: {item.get('seed')})...[/bold magenta]"
                    )
                    console.print(f"  [cyan]→ Rendering Ilustrasi {slot_num}/{total}:[/cyan] [bold white]{s_title}[/bold white]")

                illustrations = illustrator.render_chapter_illustrations(
                    project=project,
                    chapter_num=ch_num,
                    illustrations=illustrations,
                    progress_callback=on_render_progress,
                )
            finally:
                status_ctx.stop()

            # Embed illustrations into chapter markdown if chapter prose exists
            existing_prose = project.get_chapter(ch_num)
            if existing_prose:
                updated_prose = IllustratorAgent.inject_illustrations_into_markdown(existing_prose, illustrations)
                project.save_chapter(ch_num, updated_prose)
                console.print(f"\n[bold green]✓ Ketiga ilustrasi berhasil di-render dan disisipkan ke dalam naskah Bab {ch_num}![/bold green]")
            else:
                console.print(f"\n[bold green]✓ Ketiga file gambar ilustrasi Bab {ch_num} berhasil disimpan di folder illustrations/![/bold green]")

        elif action == "2":
            slot_choice = IntPrompt.ask("Pilih nomor Ilustrasi yang ingin di-render ulang (1/2/3)", default=1)
            if 1 <= slot_choice <= len(illustrations):
                if Confirm.ask("Gunakan angka Seed baru (variasi pose baru dengan DNA karakter yang tetap sama)?", default=False):
                    illustrations[slot_choice - 1]["seed"] = int(illustrations[slot_choice - 1].get("seed", 1000)) + 7
                with console.status(f"[bold magenta]🎨 Me-render Ilustrasi {slot_choice}/3...[/bold magenta]"):
                    illustrations = illustrator.render_chapter_illustrations(
                        project=project,
                        chapter_num=ch_num,
                        illustrations=illustrations,
                        slots_to_render=[slot_choice],
                    )
                existing_prose = project.get_chapter(ch_num)
                if existing_prose:
                    project.save_chapter(
                        ch_num,
                        IllustratorAgent.inject_illustrations_into_markdown(existing_prose, illustrations),
                    )
                console.print(f"[bold green]✓ Ilustrasi {slot_choice} berhasil di-render ulang![/bold green]")

        elif action == "3":
            illustrations = edit_illustrations_interactively(project, ch_num, illustrations, illustrator)

        elif action == "4":
            edit_visual_bible_interactively(project, illustrator)
            # Re-sync prompts with updated Visual DNA
            for item in illustrations:
                item["image_prompt"] = illustrator.compose_consistent_prompt(project, item)
            project.save_chapter_illustrations(ch_num, illustrations)

        elif action == "5":
            custom_dir = Prompt.ask("[bold yellow]Masukkan arahan visual baru untuk 3 ilustrasi bab ini[/bold yellow]", default="")
            with console.status(f"[bold magenta]🎨 Merancang ulang 3 Ilustrasi untuk Bab {ch_num}...[/bold magenta]"):
                illustrations = illustrator.plan_chapter_illustrations(
                    project=project,
                    chapter_info=ch_info,
                    count=config.ILLUSTRATIONS_PER_CHAPTER,
                    custom_direction=custom_dir,
                )

        elif action == "6":
            console.print("\n[bold cyan]Pilih Engine Pembuat Gambar Ilustrasi:[/bold cyan]")
            console.print("  [white]1.[/white] [bold green]Pollinations Flux Realism[/bold green] (Gratis Tanpa API Key, Fotorealistis, Seed-Consistent, Safe=False Uncensored)")
            console.print("  [white]2.[/white] [bold cyan]xAI Grok Image[/bold cyan] (grok-2-image via GROK_API_KEY)")
            console.print("  [white]3.[/white] [bold blue]Google Gemini / Imagen 3[/bold blue] (via GEMINI_API_KEY)")
            console.print("  [white]4.[/white] [bold magenta]Local Stable Diffusion WebUI / Forge API[/bold magenta] (100% Lokal & Uncensored via http://127.0.0.1:7860)")
            eng_opt = Prompt.ask("Pilih nomor engine (1-4)", choices=["1", "2", "3", "4"], default="1")
            prov_map = {"1": "pollinations", "2": "grok", "3": "gemini", "4": "local_sd"}
            chosen_prov = prov_map[eng_opt]
            models = config.get_image_models_for_provider(chosen_prov)
            chosen_model = models[0]
            if len(models) > 1:
                for idx, m in enumerate(models, 1):
                    console.print(f"    {idx}. [cyan]{m}[/cyan]")
                m_idx = IntPrompt.ask("Pilih model gambar", default=1)
                if 1 <= m_idx <= len(models):
                    chosen_model = models[m_idx - 1]
            sd_url = config.get_sd_api_url()
            if chosen_prov == "local_sd":
                sd_url = Prompt.ask("Masukkan URL API Stable Diffusion Lokal", default=sd_url)
            config.save_image_settings(chosen_prov, chosen_model, sd_url)
            illustrator.image_client.set_provider(chosen_prov, chosen_model)
            illustrator.image_client.sd_api_url = sd_url
            console.print(f"[bold green]✓ Engine Ilustrasi diubah ke: {chosen_prov.upper()} ({chosen_model})[/bold green]")

        elif action == "7":
            break
