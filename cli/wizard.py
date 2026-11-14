"""Interactive wizard for creating and resuming novel projects (manual or from article/document)."""

import time
from typing import Any, Dict, List, Optional, Tuple
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
        if Confirm.ask("[bold cyan]Buka Studio Edit Bebas (Edit Bab, Karakter, Cerita, atau World Bible)?[/bold cyan]", default=True):
            manage_foundation_studio(project, llm)
        return True

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
    if Confirm.ask(
        "[bold yellow]✏️ Ingin mengedit bebas Bab, Karakter, Cerita Utama, atau World Bible sebelum mulai menulis?[/bold yellow]",
        default=False,
    ):
        manage_foundation_studio(project, llm)
    console.print("[dim]Anda sekarang dapat langsung mulai menulis naskah Bab (Menu 3) dan membuat 3 Ilustrasi Bab (Menu 4).[/dim]\n")
    return True


def edit_story_metadata_interactively(project: NovelProject) -> None:
    """Allow the user to freely edit the novel's title, genre, tone, premise, and word targets."""
    meta = project.metadata
    console.print(Panel(
        f"[bold cyan]Judul:[/bold cyan] {meta.get('title', '-')}\n"
        f"[bold cyan]Penulis:[/bold cyan] {meta.get('author', 'Penulis')}\n"
        f"[bold cyan]Genre:[/bold cyan] {meta.get('genre', '-')}\n"
        f"[bold cyan]Tone / Nuansa:[/bold cyan] {meta.get('tone', '-')}\n"
        f"[bold cyan]Target Bab:[/bold cyan] {meta.get('target_chapters', 12)} bab\n"
        f"[bold cyan]Target Kata / Bab:[/bold cyan] {meta.get('target_words_per_chapter', 3000)} kata\n\n"
        f"[bold yellow]Premis / Cerita Utama:[/bold yellow]\n{meta.get('premise', '-')}",
        title="📝 Edit Cerita Utama, Premis & Target Bab",
        border_style="cyan",
    ))
    console.print("[dim]Tekan Enter pada bagian yang tidak ingin diubah:[/dim]")
    new_title = Prompt.ask("[bold cyan]Judul Novel[/bold cyan]", default=str(meta.get("title", "")))
    new_author = Prompt.ask("[bold cyan]Nama Penulis[/bold cyan]", default=str(meta.get("author", "Penulis")))
    new_genre = Prompt.ask("[bold cyan]Genre[/bold cyan]", default=str(meta.get("genre", "")))
    new_tone = Prompt.ask("[bold cyan]Tone / Nuansa[/bold cyan]", default=str(meta.get("tone", "")))
    new_premise = Prompt.ask("[bold cyan]Premis / Cerita Utama[/bold cyan]", default=str(meta.get("premise", "")))
    new_target_ch = IntPrompt.ask(
        "[bold cyan]Target Jumlah Bab[/bold cyan]",
        default=int(meta.get("target_chapters", 12)),
    )
    new_target_words = IntPrompt.ask(
        "[bold cyan]Target Kata per Bab (Rekomendasi novel panjang & detail: 2500-4000 kata)[/bold cyan]",
        default=int(meta.get("target_words_per_chapter", 3000)),
    )

    project.save_metadata({
        "title": new_title.strip() or meta.get("title", "Novel"),
        "author": new_author.strip() or "Penulis",
        "genre": new_genre.strip(),
        "tone": new_tone.strip(),
        "premise": new_premise.strip(),
        "target_chapters": max(1, new_target_ch),
        "target_words_per_chapter": max(500, new_target_words),
    })
    console.print("[bold green]✓ Cerita utama, premis, dan target panjang bab berhasil disimpan![/bold green]")


def edit_world_bible_interactively(project: NovelProject) -> None:
    """Allow the user to freely edit the World Bible without regenerating from scratch."""
    wb = dict(project.world_bible or {})
    console.print(Panel(
        f"[bold cyan]Nama Latar Utama:[/bold cyan] {wb.get('setting_name', '-')}\n"
        f"[bold cyan]Era / Waktu:[/bold cyan] {wb.get('time_period', '-')}\n"
        f"[bold cyan]Konsep Inti:[/bold cyan] {wb.get('core_concept', '-')}\n"
        f"[bold cyan]Atmosfer & Nuansa Sensorik:[/bold cyan] {wb.get('atmosphere', '-')}\n"
        f"[bold cyan]Aturan Dunia / Sistem:[/bold cyan] {wb.get('rules_and_systems', '-')}\n"
        f"[bold cyan]Sejarah / Lore Masa Lalu:[/bold cyan] {wb.get('historical_lore', '-')}",
        title="🏛️ Edit World Bible (Latar & Lore Dunia)",
        border_style="green",
    ))
    console.print("[dim]Tekan Enter untuk mempertahankan isi saat ini, atau ketik isi baru:[/dim]")
    wb["setting_name"] = Prompt.ask("[bold cyan]Nama Latar Utama[/bold cyan]", default=str(wb.get("setting_name", "")))
    wb["time_period"] = Prompt.ask("[bold cyan]Era / Periode Waktu[/bold cyan]", default=str(wb.get("time_period", "")))
    wb["core_concept"] = Prompt.ask("[bold cyan]Konsep Inti Dunia[/bold cyan]", default=str(wb.get("core_concept", "")))
    wb["atmosphere"] = Prompt.ask("[bold cyan]Atmosfer & Detail Sensorik Dunia[/bold cyan]", default=str(wb.get("atmosphere", "")))
    wb["rules_and_systems"] = Prompt.ask("[bold cyan]Aturan Dunia / Sistem Sosial / Kekuasaan[/bold cyan]", default=str(wb.get("rules_and_systems", "")))
    wb["historical_lore"] = Prompt.ask("[bold cyan]Sejarah / Peristiwa Masa Lalu Penting[/bold cyan]", default=str(wb.get("historical_lore", "")))

    project.save_world_bible(wb)
    console.print("[bold green]✓ Perubahan World Bible berhasil disimpan![/bold green]")


def edit_characters_interactively(project: NovelProject) -> None:
    """Interactive menu to freely edit, add, or delete characters."""
    characters: List[Dict[str, Any]] = list(project.characters or [])
    while True:
        console.print("\n")
        if characters:
            display_characters_table(characters)
        else:
            console.print("[yellow]Belum ada karakter di proyek ini.[/yellow]")

        console.print("\n[bold cyan]Menu Edit Karakter:[/bold cyan]")
        console.print("  [bold green]1.[/bold green] ✏️ Ubah Detail Karakter Tertentu (Nama, Peran, Fisik, Sifat, Motivasi, Gaya Bicara)")
        console.print("  [bold yellow]2.[/bold yellow] ➕ Tambah Karakter Baru Secara Manual")
        console.print("  [bold red]3.[/bold red] 🗑️ Hapus Karakter Tertentu")
        console.print("  [bold cyan]4.[/bold cyan] ✅ Selesai & Simpan Perubahan Karakter")

        sub = Prompt.ask("Pilih aksi (1-4)", choices=["1", "2", "3", "4"], default="4")

        if sub == "1":
            if not characters:
                console.print("[yellow]Belum ada karakter untuk diedit.[/yellow]")
                continue
            for idx, c in enumerate(characters, 1):
                console.print(f"  [bold cyan]{idx}.[/bold cyan] {c.get('name', 'Tanpa Nama')} ({c.get('role', '-')})")
            c_idx = IntPrompt.ask(f"Pilih nomor karakter yang ingin diubah (1-{len(characters)})", default=1)
            if 1 <= c_idx <= len(characters):
                target = characters[c_idx - 1]
                console.print(f"\n[bold yellow]Mengedit Karakter #{c_idx}: {target.get('name', '')}[/bold yellow] [dim](Tekan Enter jika tidak diubah)[/dim]")
                target["name"] = Prompt.ask("Nama Karakter", default=str(target.get("name", "")))
                target["role"] = Prompt.ask("Peran (Protagonist / Antagonist / Supporting / dsb)", default=str(target.get("role", "")))
                target["appearance"] = Prompt.ask("Penampilan Fisik & Ciri Khas", default=str(target.get("appearance", "")))
                target["personality"] = Prompt.ask("Sifat & Kepribadian", default=str(target.get("personality", "")))
                target["flaw"] = Prompt.ask("Kelemahan Batin / Flaw", default=str(target.get("flaw", "")))
                target["internal_motivation"] = Prompt.ask("Motivasi Batin / Keinginan Terdalam", default=str(target.get("internal_motivation", "")))
                target["external_goal"] = Prompt.ask("Tujuan Konkret dalam Cerita", default=str(target.get("external_goal", "")))
                target["speech_mannerism"] = Prompt.ask("Gaya Bicara & Dialog Khas", default=str(target.get("speech_mannerism", "")))
                target["backstory"] = Prompt.ask("Masa Lalu (Backstory)", default=str(target.get("backstory", "")))
                project.save_characters(characters)
                console.print(f"[bold green]✓ Karakter '{target['name']}' berhasil diperbarui![/bold green]")
            else:
                console.print("[red]Nomor karakter tidak valid.[/red]")

        elif sub == "2":
            console.print("\n[bold green]➕ Tambah Karakter Baru[/bold green]")
            name = Prompt.ask("Nama Karakter Baru")
            if not name.strip():
                continue
            role = Prompt.ask("Peran (Protagonist / Antagonist / Ally / Mentor / Foil)", default="Supporting")
            appearance = Prompt.ask("Penampilan Fisik & Ciri Khas", default="")
            personality = Prompt.ask("Sifat & Kepribadian", default="")
            flaw = Prompt.ask("Kelemahan Batin / Flaw", default="")
            internal_motivation = Prompt.ask("Motivasi Batin", default="")
            external_goal = Prompt.ask("Tujuan Konkret dalam Cerita", default="")
            speech_mannerism = Prompt.ask("Gaya Bicara Khas", default="Natural dan ekspresif")
            backstory = Prompt.ask("Masa Lalu Singkat (Backstory)", default="")
            characters.append({
                "name": name.strip(),
                "role": role.strip(),
                "archetype": role.strip(),
                "appearance": appearance.strip(),
                "visual_dna": appearance.strip(),
                "personality": personality.strip(),
                "flaw": flaw.strip(),
                "internal_motivation": internal_motivation.strip(),
                "external_goal": external_goal.strip(),
                "speech_mannerism": speech_mannerism.strip(),
                "backstory": backstory.strip(),
            })
            project.save_characters(characters)
            console.print(f"[bold green]✓ Karakter '{name}' berhasil ditambahkan dan disimpan![/bold green]")

        elif sub == "3":
            if not characters:
                continue
            for idx, c in enumerate(characters, 1):
                console.print(f"  [bold cyan]{idx}.[/bold cyan] {c.get('name', 'Tanpa Nama')} ({c.get('role', '-')})")
            del_idx = IntPrompt.ask(f"Pilih nomor karakter yang ingin dihapus (1-{len(characters)})", default=len(characters))
            if 1 <= del_idx <= len(characters):
                removed = characters.pop(del_idx - 1)
                project.save_characters(characters)
                console.print(f"[bold yellow]✓ Karakter '{removed.get('name')}' telah dihapus.[/bold yellow]")

        elif sub == "4":
            project.save_characters(characters)
            console.print("[bold green]✓ Daftar karakter berhasil disimpan![/bold green]")
            break


def edit_single_chapter_plan_interactively(project: NovelProject, ch_info: Dict[str, Any]) -> Dict[str, Any]:
    """Edit a single chapter's plan (title, POV, setting, summary, conflict, turning_point) and persist to outline."""
    ch_num = ch_info.get("chapter_number", 1)
    console.print(Panel(
        f"[bold cyan]Judul Bab {ch_num}:[/bold cyan] {ch_info.get('title', '-')}\n"
        f"[bold cyan]Karakter POV:[/bold cyan] {ch_info.get('pov_character', '-')}\n"
        f"[bold cyan]Lokasi / Setting:[/bold cyan] {ch_info.get('setting', '-')}\n"
        f"[bold cyan]Ringkasan Alur Bab:[/bold cyan] {ch_info.get('summary', '-')}\n"
        f"[bold cyan]Konflik Utama:[/bold cyan] {ch_info.get('conflict', '-')}\n"
        f"[bold cyan]Titik Balik Akhir (Ending Bab):[/bold cyan] {ch_info.get('turning_point', '-')}",
        title=f"✏️ Edit Rencana Bab {ch_num}",
        border_style="yellow",
    ))
    console.print("[dim]Tekan Enter pada bagian yang tidak ingin diubah:[/dim]")
    ch_info["title"] = Prompt.ask(f"[bold cyan]Judul Bab {ch_num}[/bold cyan]", default=str(ch_info.get("title", f"Bab {ch_num}")))
    ch_info["pov_character"] = Prompt.ask("[bold cyan]Karakter POV (Sudut Pandang)[/bold cyan]", default=str(ch_info.get("pov_character", "")))
    ch_info["setting"] = Prompt.ask("[bold cyan]Lokasi / Setting Utama Bab[/bold cyan]", default=str(ch_info.get("setting", "")))
    ch_info["summary"] = Prompt.ask("[bold cyan]Ringkasan Cerita / Kejadian Bab Ini[/bold cyan]", default=str(ch_info.get("summary", "")))
    ch_info["conflict"] = Prompt.ask("[bold cyan]Konflik Utama Bab Ini[/bold cyan]", default=str(ch_info.get("conflict", "")))
    ch_info["turning_point"] = Prompt.ask("[bold cyan]Titik Balik Akhir / Cliffhanger Bab Ini[/bold cyan]", default=str(ch_info.get("turning_point", "")))

    # Persist into project.outline
    outline = dict(project.outline or {})
    chapters = list(outline.get("chapters", []))
    updated = False
    for idx, c in enumerate(chapters):
        if c.get("chapter_number") == ch_num:
            chapters[idx] = ch_info
            updated = True
            break
    if not updated:
        chapters.append(ch_info)
    outline["chapters"] = chapters
    project.save_outline(outline)
    console.print(f"[bold green]✓ Rencana Bab {ch_num}: '{ch_info['title']}' berhasil disimpan![/bold green]")
    return ch_info


def edit_outline_and_chapters_interactively(project: NovelProject) -> None:
    """Interactive menu to freely edit any chapter's outline, add/remove chapters, or edit overall synopsis."""
    outline = dict(project.outline or {})
    chapters: List[Dict[str, Any]] = list(outline.get("chapters", []))

    while True:
        console.print("\n")
        if outline.get("overall_synopsis") or outline.get("narrative_arc"):
            console.print(Panel(
                f"[bold cyan]Sinopsis Umum:[/bold cyan]\n{outline.get('overall_synopsis', '-')}\n\n"
                f"[bold cyan]Struktur Tiga Babak (Narrative Arc):[/bold cyan]\n{outline.get('narrative_arc', '-')}",
                title="🗺️ Alur Cerita Makro",
                border_style="magenta",
            ))
        if chapters:
            display_chapters_table(chapters, project.list_drafted_chapters())
        else:
            console.print("[yellow]Belum ada daftar bab di dalam Outline.[/yellow]")

        console.print("\n[bold cyan]Menu Edit Bab & Outline Alur:[/bold cyan]")
        console.print("  [bold green]1.[/bold green] ✏️ Edit Rencana Bab Tertentu (Judul, POV, Lokasi, Cerita, Konflik, Ending Bab)")
        console.print("  [bold yellow]2.[/bold yellow] 📖 Edit Sinopsis Umum & Struktur Tiga Babak (Narrative Arc)")
        console.print("  [bold yellow]3.[/bold yellow] ➕ Tambah Bab Baru ke Outline")
        console.print("  [bold red]4.[/bold red] 🗑️ Hapus Bab Tertentu dari Outline")
        console.print("  [bold cyan]5.[/bold cyan] ✅ Selesai & Simpan Outline")

        sub = Prompt.ask("Pilih aksi (1-5)", choices=["1", "2", "3", "4", "5"], default="5")

        if sub == "1":
            if not chapters:
                console.print("[yellow]Belum ada bab untuk diedit. Pilih 3 untuk menambah bab.[/yellow]")
                continue
            ch_num = IntPrompt.ask(f"Masukkan Nomor Bab yang ingin diedit (1-{len(chapters)})", default=1)
            target_ch = next((c for c in chapters if c.get("chapter_number") == ch_num), None)
            if not target_ch and 1 <= ch_num <= len(chapters):
                target_ch = chapters[ch_num - 1]
            if target_ch:
                edit_single_chapter_plan_interactively(project, target_ch)
                outline = dict(project.outline or {})
                chapters = list(outline.get("chapters", []))
            else:
                console.print("[red]Nomor bab tidak ditemukan.[/red]")

        elif sub == "2":
            outline["overall_synopsis"] = Prompt.ask(
                "[bold cyan]Sinopsis Umum Keseluruhan Novel[/bold cyan]",
                default=str(outline.get("overall_synopsis", "")),
            )
            outline["narrative_arc"] = Prompt.ask(
                "[bold cyan]Struktur Tiga Babak (Narrative Arc)[/bold cyan]",
                default=str(outline.get("narrative_arc", "")),
            )
            outline["chapters"] = chapters
            project.save_outline(outline)
            console.print("[bold green]✓ Sinopsis umum & struktur babak berhasil disimpan![/bold green]")

        elif sub == "3":
            new_num = len(chapters) + 1
            console.print(f"\n[bold green]➕ Menambahkan Bab #{new_num}[/bold green]")
            default_pov = project.characters[0].get("name", "Protagonis") if project.characters else "Protagonis"
            default_set = project.world_bible.get("setting_name", "Lokasi Utama")
            new_ch = {
                "chapter_number": new_num,
                "title": Prompt.ask("Judul Bab Baru", default=f"Bab {new_num}"),
                "pov_character": Prompt.ask("Karakter POV", default=default_pov),
                "setting": Prompt.ask("Lokasi / Setting", default=default_set),
                "summary": Prompt.ask("Ringkasan Alur / Kejadian Bab Ini", default=""),
                "conflict": Prompt.ask("Konflik Utama Bab Ini", default=""),
                "turning_point": Prompt.ask("Titik Balik Akhir / Cliffhanger Bab Ini", default=""),
                "status": "planned",
            }
            chapters.append(new_ch)
            outline["chapters"] = chapters
            project.save_outline(outline)
            project.save_metadata({"target_chapters": len(chapters)})
            console.print(f"[bold green]✓ Bab {new_num}: '{new_ch['title']}' berhasil ditambahkan![/bold green]")

        elif sub == "4":
            if len(chapters) <= 1:
                console.print("[yellow]Minimal harus ada 1 bab dalam outline.[/yellow]")
                continue
            del_num = IntPrompt.ask(f"Masukkan Nomor Bab yang ingin dihapus (1-{len(chapters)})", default=len(chapters))
            if 1 <= del_num <= len(chapters):
                removed = chapters.pop(del_num - 1)
                for idx, c in enumerate(chapters, 1):
                    c["chapter_number"] = idx
                outline["chapters"] = chapters
                project.save_outline(outline)
                project.save_metadata({"target_chapters": len(chapters)})
                console.print(f"[bold yellow]✓ Bab '{removed.get('title')}' dihapus dan urutan nomor bab telah dirapikan.[/bold yellow]")

        elif sub == "5":
            outline["chapters"] = chapters
            project.save_outline(outline)
            console.print("[bold green]✓ Outline bab berhasil disimpan![/bold green]")
            break


def regenerate_foundation_part_interactively(project: NovelProject, llm: LLMClient) -> None:
    """Allow selective AI generation of ONLY a missing/chosen component without wiping everything else."""
    console.print("\n[bold cyan]🤖 Generate Bagian Tertentu dengan AI (Tanpa Mereset Semuanya):[/bold cyan]")
    console.print("  [bold green]1.[/bold green] ⚡ Lengkapi Hanya Bagian yang Masih Kosong")
    console.print("  [bold yellow]2.[/bold yellow] 🏛️ Generate Ulang HANYA World Bible (Karakter & Bab Tetap Aman)")
    console.print("  [bold yellow]3.[/bold yellow] 👥 Generate Ulang HANYA Daftar Karakter (World Bible & Bab Tetap Aman)")
    console.print("  [bold yellow]4.[/bold yellow] 🗺️ Generate Ulang HANYA Outline Bab (World Bible & Karakter Tetap Aman)")
    console.print("  [bold red]5.[/bold red] 🔄 Generate Ulang Seluruh Fondasi dari Awal (Reset Semua)")
    console.print("  [bold cyan]6.[/bold cyan] 🚪 Batal")

    choice = Prompt.ask("Pilih opsi (1-6)", choices=["1", "2", "3", "4", "5", "6"], default="1")
    if choice == "6":
        return
    elif choice == "1":
        missing = project.get_missing_foundation_components()
        if not missing:
            console.print("[bold green]✓ Seluruh komponen fondasi sudah terisi lengkap! Tidak ada yang perlu di-generate ulang.[/bold green]")
            return
        resume_project_foundation(project, llm, force_all=False)
    elif choice == "2":
        architect = ArchitectAgent(llm)
        with console.status("[bold cyan]🏛️ Architect Agent sedang merancang ulang World Bible...[/bold cyan]"):
            architect.generate_world_bible(project)
        console.print("[bold green]✓ World Bible berhasil diperbarui tanpa menghapus Karakter & Bab![/bold green]")
    elif choice == "3":
        char_master = CharacterMasterAgent(llm)
        with console.status("[bold cyan]👥 Character Master Agent sedang merancang ulang Karakter...[/bold cyan]"):
            char_master.generate_characters(project)
        console.print("[bold green]✓ Daftar Karakter berhasil diperbarui tanpa menghapus World Bible & Bab![/bold green]")
    elif choice == "4":
        outliner = OutlinerAgent(llm)
        with console.status("[bold cyan]🗺️ Outliner Agent sedang merancang ulang Outline Bab...[/bold cyan]"):
            outliner.generate_outline(project)
        console.print("[bold green]✓ Outline Bab berhasil diperbarui tanpa menghapus World Bible & Karakter![/bold green]")
    elif choice == "5":
        if Confirm.ask("[bold red]Yakin ingin mereset seluruh World Bible, Karakter, dan Outline dari awal?[/bold red]", default=False):
            resume_project_foundation(project, llm, force_all=True)


def manage_foundation_studio(project: NovelProject, llm: LLMClient) -> None:
    """Interactive studio to freely view and edit story premise, World Bible, characters, and chapters."""
    while True:
        meta = project.metadata
        wb = project.world_bible
        console.print("\n")
        print_header(
            f"🛠️ Studio Edit Cerita, Karakter & Bab: {meta.get('title', 'Novel')}",
            "Bebas ubah cerita utama, karakter, aturan dunia, dan rencana tiap bab kapan saja tanpa generate ulang dari awal",
        )
        console.print(Panel(
            f"[bold cyan]Judul & Genre:[/bold cyan] {meta.get('title', '-')} ({meta.get('genre', '-')} | {meta.get('tone', '-')})\n"
            f"[bold cyan]Target Ukuran:[/bold cyan] {meta.get('target_chapters', 12)} Bab × ~{meta.get('target_words_per_chapter', 3000)} kata/bab\n"
            f"[bold cyan]Premis Cerita:[/bold cyan] {meta.get('premise', '-')}\n\n"
            f"[bold green]🏛️ Latar Dunia:[/bold green] {wb.get('setting_name', 'Belum diatur')} — {wb.get('core_concept', '-')}\n"
            f"[bold yellow]👥 Jumlah Karakter:[/bold yellow] {len(project.characters)} tokoh  |  "
            f"[bold magenta]🗺️ Jumlah Bab di Outline:[/bold magenta] {len(project.outline.get('chapters', []))} bab",
            title="📋 Ringkasan Proyek Saat Ini",
            border_style="cyan",
        ))

        console.print("[bold cyan]Pilih Bagian yang Ingin Anda Edit / Kelola:[/bold cyan]")
        console.print("  [bold green]1.[/bold green] 🗺️ [bold]Edit Bab-Bab & Outline Alur[/bold] (Ubah Judul Bab, POV, Cerita Bab, Konflik, Tambah/Hapus Bab)")
        console.print("  [bold green]2.[/bold green] 👥 [bold]Edit / Tambah / Hapus Karakter[/bold] (Ubah Nama, Peran, Fisik, Sifat, Motivasi, Gaya Bicara)")
        console.print("  [bold green]3.[/bold green] 📝 [bold]Edit Cerita Utama, Premis, Genre & Target Panjang Kata per Bab[/bold]")
        console.print("  [bold green]4.[/bold green] 🏛️ [bold]Edit World Bible[/bold] (Ubah Nama Lokasi, Atmosfer, Aturan Dunia, Sejarah)")
        console.print("  [bold yellow]5.[/bold yellow] 👁️ Lihat Tabel Lengkap Karakter & Daftar Seluruh Bab")
        console.print("  [bold magenta]6.[/bold magenta] 🤖 Generate dengan AI (Hanya Bagian Tertentu / Tanpa Reset Semua)")
        console.print("  [bold cyan]7.[/bold cyan] ✅ Selesai & Kembali")

        action = Prompt.ask("\n[bold green]Pilih menu (1-7)[/bold green]", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")

        if action == "1":
            edit_outline_and_chapters_interactively(project)
        elif action == "2":
            edit_characters_interactively(project)
        elif action == "3":
            edit_story_metadata_interactively(project)
        elif action == "4":
            edit_world_bible_interactively(project)
        elif action == "5":
            if wb:
                console.print(Panel(
                    f"[bold]Nama Setting:[/bold] {wb.get('setting_name', '-')}\n"
                    f"[bold]Konsep Inti:[/bold] {wb.get('core_concept', '-')}\n"
                    f"[bold]Atmosfer:[/bold] {wb.get('atmosphere', '-')}\n"
                    f"[bold]Aturan & Sistem:[/bold] {wb.get('rules_and_systems', '-')}\n"
                    f"[bold]Sejarah:[/bold] {wb.get('historical_lore', '-')}",
                    title="🏛️ Worldbuilding Lore",
                    border_style="green",
                ))
            if project.characters:
                display_characters_table(project.characters)
            if project.outline.get("chapters"):
                display_chapters_table(project.outline.get("chapters", []), project.list_drafted_chapters())
        elif action == "6":
            regenerate_foundation_part_interactively(project, llm)
        elif action == "7":
            break


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
            "recommended_words_per_chapter": 3000,
            "adaptation_notes": "Rekomendasi standar 14 bab (~3000 kata/bab untuk kualitas novel mendalam).",
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
        "[bold cyan]Target Kata per Bab (Ideal novel panjang & detail: 2500-4000 kata)[/bold cyan]",
        default=max(2500, int(blueprint.get("recommended_words_per_chapter", 3000))),
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
    target_words = IntPrompt.ask("[bold cyan]Target Kata per Bab (Ideal novel panjang & detail: 2500-4000 kata)[/bold cyan]", default=3000)

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
