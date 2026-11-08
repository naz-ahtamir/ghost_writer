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
from cli.chapter_flow import (
    write_chapter_flow,
    audit_chapter_flow,
    view_chapter_flow,
    illustrate_chapter_flow,
)
from core.llm import LLMClient
from core.project import ProjectManager, NovelProject
from agents.exporter import (
    NovelExporter,
    get_local_reader_url,
    open_file_in_viewer,
    sync_project_to_public_downloads,
)


def manage_settings(llm: LLMClient) -> None:
    """Configure AI provider, API key, and model."""
    print_header("⚙️ Pengaturan AI Engine & Model", "Konfigurasi xAI Grok / Google Gemini")

    prov = llm.provider
    prov_name = "xAI Grok (Prioritas)" if prov == "grok" else "Google Gemini"
    curr_key = llm.api_key or "[Belum Diisi]"
    img_prov = config.get_image_provider()
    img_model = config.get_image_model(img_prov)
    grok_effort = config.get_grok_reasoning_effort()
    usage_stats = llm.get_cumulative_usage()

    console.print(f"[bold]Provider AI Teks saat ini:[/bold] [bold cyan]{prov_name}[/bold cyan]")
    console.print(f"[bold]Model Teks saat ini:[/bold] [bold green]{llm.model}[/bold green]")
    console.print(f"[bold]API Key saat ini:[/bold] {curr_key}")
    console.print(f"[bold]Intensitas Penalaran Grok:[/bold] [bold yellow]{grok_effort.upper()}[/bold yellow] [dim]('low' sangat hemat token & cepat)[/dim]")
    console.print(f"[bold]Engine Ilustrasi Gambar:[/bold] [bold magenta]{img_prov.upper()}[/bold magenta] [dim]({img_model})[/dim]")

    if usage_stats.get("requests_count", 0) > 0:
        p_tok = usage_stats["prompt_tokens"]
        c_tok = usage_stats["cached_tokens"]
        hit_pct = usage_stats["cache_hit_rate"]
        out_tok = usage_stats["completion_tokens"]
        r_tok = usage_stats["reasoning_tokens"]
        tot_tok = usage_stats["total_tokens"]
        console.print(
            f"[bold dim]📊 Penggunaan Token Sesi ({usage_stats['requests_count']} request):[/bold dim] "
            f"[dim]Prompt: {p_tok:,} (Cached: {c_tok:,} | {hit_pct:.1f}%) | "
            f"Output: {out_tok:,} (Reasoning: {r_tok:,}) | Total: {tot_tok:,}[/dim]"
        )

    console.print("\n[bold cyan]Opsi Pengaturan:[/bold cyan]")
    console.print("  [white]1.[/white] Ganti Provider AI Teks (xAI Grok / Google Gemini)")
    console.print("  [white]2.[/white] Masukkan / Ubah API Key")
    console.print("  [white]3.[/white] Ganti Model AI Teks")
    console.print("  [white]4.[/white] Ganti Engine & Model Ilustrasi Gambar (Flux Realism Uncensored / Grok / Gemini / Local SD)")
    console.print("  [white]5.[/white] Atur Intensitas Penalaran Grok (Reasoning Effort: low / medium / high)")
    console.print("  [white]6.[/white] Reset Statistik Penggunaan Token Sesi")
    console.print("  [white]7.[/white] Kembali")

    opt = Prompt.ask("\nPilih opsi", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")
    if opt == "1":
        new_prov = "gemini" if prov == "grok" else "grok"
        new_name = "Google Gemini" if new_prov == "gemini" else "xAI Grok"
        if Confirm.ask(f"Beralih ke provider [bold cyan]{new_name}[/bold cyan]?", default=True):
            new_key = config.get_api_key(new_prov)
            new_model = config.get_active_model(new_prov)
            config.save_settings(provider=new_prov, api_key=new_key, model=new_model)
            llm.set_provider(new_prov, api_key=new_key, model=new_model)
            console.print(f"[bold green]✓ Provider berhasil diubah ke {new_name}![/bold green]")

    elif opt == "2":
        prov_label = "xAI (Grok)" if llm.provider == "grok" else "Google Gemini"
        url_help = "https://console.x.ai" if llm.provider == "grok" else "https://aistudio.google.com/app/apikey"
        console.print(f"[dim]Dapatkan key di: {url_help}[/dim]")
        new_key = Prompt.ask(f"[bold cyan]Masukkan {prov_label} API Key baru[/bold cyan]")
        if new_key.strip():
            config.save_settings(provider=llm.provider, api_key=new_key.strip(), model=llm.model)
            llm.set_api_key(new_key.strip(), llm.model)
            console.print(f"[bold green]✓ {prov_label} API Key berhasil disimpan![/bold green]")

    elif opt == "3":
        if llm.provider == "grok" and llm.api_key:
            from core.llm import fetch_available_grok_models
            with console.status("[bold cyan]Memeriksa model aktif di akun xAI Anda...[/bold cyan]"):
                live = fetch_available_grok_models(llm.api_key)
            models = live if live else config.get_models_for_provider(llm.provider)
        elif llm.provider == "gemini" and llm.api_key:
            from core.llm import fetch_available_gemini_models
            with console.status("[bold cyan]Memeriksa model aktif di akun Google Gemini Anda...[/bold cyan]"):
                live = fetch_available_gemini_models(llm.api_key)
            models = live if live else config.get_models_for_provider(llm.provider)
        else:
            models = config.get_models_for_provider(llm.provider)
        console.print(f"\nPilihan Model {prov_name} yang tersedia:")
        for idx, m in enumerate(models, 1):
            console.print(f"  {idx}. [cyan]{m}[/cyan]")
        choice = IntPrompt.ask("Pilih nomor model", default=1)
        if 1 <= choice <= len(models):
            selected_model = models[choice - 1]
            config.save_settings(provider=llm.provider, api_key=llm.api_key, model=selected_model)
            llm.model = selected_model
            console.print(f"[bold green]✓ Model diubah ke: {selected_model}[/bold green]")

    elif opt == "4":
        console.print("\n[bold cyan]Pilih Engine Pembuat Gambar Ilustrasi:[/bold cyan]")
        console.print("  [white]1.[/white] [bold green]Pollinations Flux Realism[/bold green] (Gratis Tanpa API Key, Fotorealistis, Seed-Consistent, Safe=False Uncensored)")
        console.print("  [white]2.[/white] [bold cyan]xAI Grok Image[/bold cyan] (grok-2-image via GROK_API_KEY)")
        console.print("  [white]3.[/white] [bold blue]Google Gemini / Imagen 3[/bold blue] (via GEMINI_API_KEY)")
        console.print("  [white]4.[/white] [bold magenta]Local Stable Diffusion WebUI / Forge API[/bold magenta] (100% Lokal & Uncensored)")
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
        console.print(f"[bold green]✓ Engine Ilustrasi diubah ke: {chosen_prov.upper()} ({chosen_model})[/bold green]")

    elif opt == "5":
        console.print("\n[bold cyan]Atur Intensitas Penalaran xAI Grok (Reasoning Effort):[/bold cyan]")
        console.print("  [bold green]1. Low[/bold green]    - [bold](Rekomendasi Utama)[/bold] Sangat hemat token, respons cepat, cocok untuk novel & JSON.")
        console.print("  [bold yellow]2. Medium[/bold yellow] - Keseimbangan penalaran standar.")
        console.print("  [bold red]3. High[/bold red]   - Penalaran mendalam maksimum (memakai ratusan token output ekstra).")
        eff_choice = Prompt.ask("Pilih level reasoning effort", choices=["1", "2", "3"], default="1")
        eff_map = {"1": "low", "2": "medium", "3": "high"}
        chosen_eff = eff_map[eff_choice]
        config.save_grok_reasoning_effort(chosen_eff)
        console.print(f"[bold green]✓ Intensitas penalaran Grok berhasil diatur ke: {chosen_eff.upper()}[/bold green]")

    elif opt == "6":
        llm.reset_cumulative_usage()
        console.print("[bold green]✓ Statistik penggunaan token sesi berhasil di-reset![/bold green]")


def delete_project_flow(current_project: Optional[NovelProject] = None) -> Optional[NovelProject]:
    """Interactive flow to permanently delete an existing novel project."""
    projects = ProjectManager.list_projects()
    if not projects:
        console.print("[yellow]Belum ada proyek novel yang tersimpan untuk dihapus.[/yellow]")
        return current_project

    table = Table(title="🗑️ Hapus Proyek Novel", border_style="red")
    table.add_column("No", justify="center", style="bold red")
    table.add_column("Judul Novel", style="bold white")
    table.add_column("Genre", style="green")
    table.add_column("Penulis", style="yellow")
    table.add_column("Folder (Slug)", style="dim")

    for idx, p in enumerate(projects, 1):
        table.add_row(
            str(idx),
            p.get("title", "Tanpa Judul"),
            p.get("genre", "-"),
            p.get("author", "-"),
            p.get("slug", "-"),
        )
    console.print(table)

    raw_choice = Prompt.ask("\nPilih nomor proyek yang ingin DIHAPUS (atau 'b' untuk batal)", default="b").strip()
    if raw_choice.lower() in ("b", "batal", "0", ""):
        console.print("[dim]Penghapusan proyek dibatalkan.[/dim]")
        return current_project

    if raw_choice.isdigit():
        idx = int(raw_choice)
        if 1 <= idx <= len(projects):
            target = projects[idx - 1]
            slug = target.get("slug", "")
            title = target.get("title", slug)

            confirm = Confirm.ask(
                f"[bold red]⚠️ PERINGATAN: Apakah Anda yakin ingin menghapus seluruh data novel '{title}' secara permanen?[/bold red]",
                default=False
            )
            if confirm:
                if ProjectManager.delete_project(slug):
                    console.print(f"[bold green]✓ Proyek '{title}' berhasil dihapus dari perangkat![/bold green]")
                    if current_project and current_project.project_dir.name == slug:
                        console.print("[dim yellow]📍 Proyek aktif saat ini telah di-reset (kosong).[/dim yellow]")
                        return None
                else:
                    console.print(f"[bold red]❌ Gagal menghapus folder proyek '{slug}'.[/bold red]")
            else:
                console.print("[yellow]Penghapusan dibatalkan.[/yellow]")
        else:
            console.print("[yellow]Nomor proyek di luar daftar.[/yellow]")
    else:
        console.print("[yellow]Pilihan tidak valid.[/yellow]")

    return current_project


def select_existing_project(llm: Optional[LLMClient] = None, current_project: Optional[NovelProject] = None) -> Optional[NovelProject]:
    """Display list of projects and load selected one, or offer deletion."""
    projects = ProjectManager.list_projects()
    if not projects:
        console.print("[yellow]Belum ada proyek novel yang tersimpan. Silakan buat proyek baru terlebih dahulu.[/yellow]")
        return current_project

    table = Table(title="📚 Daftar Proyek Novel", border_style="cyan")
    table.add_column("No", justify="center", style="bold cyan")
    table.add_column("Judul Novel", style="bold white")
    table.add_column("Genre", style="green")
    table.add_column("Penulis", style="yellow")
    table.add_column("Status Bab & Fondasi", justify="center")

    loaded_projects = []
    for idx, p in enumerate(projects, 1):
        slug = p.get("slug", "")
        project_obj = ProjectManager.load_project(slug)
        loaded_projects.append(project_obj)
        drafted_count = len(project_obj.list_drafted_chapters())
        target_ch = project_obj.metadata.get("target_chapters", 0)

        if not project_obj.is_foundation_complete():
            status_desc = "[bold yellow]⚠️ Fondasi Belum Lengkap[/bold yellow]"
        else:
            status_desc = f"[bold green]{drafted_count}/{target_ch}[/bold green] bab ditulis"

        table.add_row(
            str(idx),
            p.get("title", "Tanpa Judul"),
            p.get("genre", "-"),
            p.get("author", "-"),
            status_desc,
        )

    console.print(table)
    raw_choice = Prompt.ask(
        f"\nPilih nomor proyek untuk dibuka [1-{len(loaded_projects)}] (ketik 'h' untuk Hapus Proyek, 'b' untuk Batal)",
        default="1"
    ).strip()

    if raw_choice.lower() in ("h", "hapus", "delete", "d"):
        return delete_project_flow(current_project)

    if raw_choice.lower() in ("b", "batal", "0", ""):
        return current_project

    if raw_choice.isdigit():
        choice = int(raw_choice)
        if 1 <= choice <= len(loaded_projects):
            project = loaded_projects[choice - 1]
            console.print(f"[bold green]✓ Proyek '{project.metadata.get('title')}' berhasil dibuka![/bold green]")
            if not project.is_foundation_complete():
                missing = ", ".join(project.get_missing_foundation_components())
                console.print(f"[bold yellow]⚠️ Perhatian: Fondasi novel ini belum lengkap ({missing}).[/bold yellow]")
                if llm and Confirm.ask("Apakah Anda ingin melengkapi fondasi novel sekarang?", default=True):
                    from cli.wizard import resume_project_foundation
                    resume_project_foundation(project, llm)
            return project

    console.print("[yellow]Pilihan nomor proyek tidak valid.[/yellow]")
    return current_project


def show_world_and_characters(project: NovelProject, llm: Optional[LLMClient] = None) -> None:
    """View world lore, character bible, and outline, with option to resume or regenerate."""
    print_header(f"📖 World Lore, Karakter & Alur - {project.metadata.get('title')}")

    # World details
    if project.is_world_bible_complete():
        wb = project.world_bible
        console.print(Panel(
            f"[bold cyan]Latar:[/bold cyan] {wb.get('setting_name')}\n"
            f"[bold cyan]Atmosfer:[/bold cyan] {wb.get('atmosphere')}\n"
            f"[bold cyan]Aturan / Sistem:[/bold cyan] {wb.get('rules_and_systems')}\n"
            f"[bold cyan]Sejarah / Lore:[/bold cyan] {wb.get('historical_lore')}",
            title="🏛️ World Bible",
            border_style="blue",
        ))
    else:
        console.print(Panel("[dim yellow]World Bible belum dibuat untuk proyek ini.[/dim yellow]", title="🏛️ World Bible", border_style="yellow"))

    # Characters table
    if project.is_characters_complete():
        display_characters_table(project.characters)
    else:
        console.print("[dim yellow]👥 Profil Karakter belum dibuat untuk proyek ini.[/dim yellow]")

    # Outline summary
    if project.is_outline_complete():
        chapters = project.outline.get("chapters", [])
        display_chapters_table(chapters, project.list_drafted_chapters())
    else:
        console.print("[dim yellow]🗺️ Outline Bab belum dibuat untuk proyek ini.[/dim yellow]")

    # Management options
    if not project.is_foundation_complete():
        missing = ", ".join(project.get_missing_foundation_components())
        console.print(f"\n[bold yellow]⚠️ Fondasi novel ini belum lengkap: {missing}[/bold yellow]")
        if llm and Confirm.ask("Apakah Anda ingin melengkapi fondasi yang belum ada sekarang?", default=True):
            from cli.wizard import resume_project_foundation
            resume_project_foundation(project, llm, force_all=False)
    else:
        if llm and Confirm.ask("\nApakah Anda ingin merancang ulang (regenerate) seluruh fondasi novel ini?", default=False):
            from cli.wizard import resume_project_foundation
            resume_project_foundation(project, llm, force_all=True)


def export_novel_flow(project: NovelProject) -> None:
    """Export the novel to markdown and docx."""
    drafted = project.list_drafted_chapters()
    if not drafted:
        console.print("[red]Belum ada bab yang selesai ditulis untuk diekspor.[/red]")
        return

    console.print("\n[bold cyan]Pilih format ekspor:[/bold cyan]")
    console.print("  [white]1.[/white] 📘 Word (.docx) saja")
    console.print("  [white]2.[/white] 📄 Markdown (.md) saja")
    console.print("  [white]3.[/white] 🌐 HTML Reader (.html) saja")
    console.print("  [white]4.[/white] 📦 Semua format")
    fmt_choice = Prompt.ask("Pilih format (1-4)", choices=["1", "2", "3", "4"], default="3")
    fmt_map = {
        "1": ["docx"],
        "2": ["md"],
        "3": ["html"],
        "4": ["md", "docx", "html"],
    }
    formats = fmt_map[fmt_choice]

    exporter = NovelExporter(project)
    with console.status(f"[bold cyan]📦 Mengompilasi naskah & ilustrasi ke: {', '.join(formats).upper()}...[/bold cyan]"):
        results = exporter.export_selected(formats, sync_public=False)
        public_dir = sync_project_to_public_downloads(project)

    illus_ch_count = len(project.list_illustrated_chapters())
    public_info = (
        f"📲 [bold yellow]Folder Download HP (Bisa dibuka di File Manager/Galeri):[/bold yellow]\n"
        f"   [bold green]{public_dir}[/bold green]\n\n"
        if public_dir
        else ""
    )

    labels = {"docx": "📘 File Word (DOCX)", "md": "📄 File Markdown (MD)", "html": "🌐 File HTML Reader"}
    file_lines = "".join(
        f"{labels[k]}: [dim]{results[k].name}[/dim]\n" for k in ("docx", "md", "html") if k in results
    )
    local_url = get_local_reader_url(results["html"]) if "html" in results else ""
    link_info = (
        f"🌐 [bold]Link Baca di Browser:[/bold]\n   [bold cyan]{local_url}[/bold cyan]\n\n" if local_url else ""
    )

    console.print(Panel(
        f"[bold green]✓ Novel berhasil diekspor![/bold green]\n\n"
        f"{link_info}"
        f"{public_info}"
        f"{file_lines}"
        f"[dim]Total bab yang diekspor: {len(drafted)} bab ({illus_ch_count} bab memiliki ilustrasi).[/dim]",
        title="🎉 Ekspor Berhasil",
        border_style="green",
    ))

    # Offer to open the first exported file (HTML preferred)
    open_target = results.get("html") or results.get("docx") or results.get("md")
    if open_target and Confirm.ask(f"[bold yellow]Buka {open_target.name} sekarang?[/bold yellow]", default=True):
        opened = open_file_in_viewer(open_target)
        console.print(f"[bold green]✓ Membuka:[/bold green] [bold cyan]{opened}[/bold cyan]")


def check_api_key_prompt(llm: LLMClient) -> None:
    """Ensure active provider API key is present, prompt if missing."""
    if not llm.api_key:
        if llm.provider == "grok":
            console.print(Panel(
                "[bold yellow]⚠️ xAI (Grok) API Key Belum Ditemukan![/bold yellow]\n\n"
                "GhostWriter diprioritaskan menggunakan engine [bold cyan]xAI Grok[/bold cyan] untuk sastra dan prosa terbaik.\n"
                "Dapatkan xAI API Key di: [cyan]https://console.x.ai[/cyan]\n\n"
                "[dim]💡 Jika ingin beralih ke Google Gemini (Gratis), ketik 'gemini' di bawah.[/dim]",
                title="🔑 Konfigurasi AI Engine (Grok)",
                border_style="yellow",
            ))
            key = Prompt.ask("[bold cyan]Masukkan xAI (Grok) API Key (atau 'gemini' untuk ganti provider)[/bold cyan]", default="")
            if key.strip().lower() == "gemini":
                llm.set_provider("gemini")
                gemini_key = config.get_api_key("gemini")
                config.save_settings(provider="gemini", api_key=gemini_key, model=llm.model)
                check_api_key_prompt(llm)
                return
            elif key.strip():
                config.save_settings(provider="grok", api_key=key.strip(), model=llm.model)
                llm.set_api_key(key.strip())
                console.print("[bold green]✓ xAI Grok API Key berhasil disimpan![/bold green]\n")
        else:
            console.print(Panel(
                "[bold yellow]⚠️ Google Gemini API Key Belum Ditemukan![/bold yellow]\n\n"
                "Dapatkan Gemini API Key gratis di: [cyan]https://aistudio.google.com/app/apikey[/cyan]",
                title="🔑 Konfigurasi AI Engine (Gemini)",
                border_style="yellow",
            ))
            key = Prompt.ask("[bold cyan]Masukkan Gemini API Key Anda (atau tekan Enter untuk lewati)[/bold cyan]", default="")
            if key.strip():
                config.save_settings(provider="gemini", api_key=key.strip(), model=llm.model)
                llm.set_api_key(key.strip())
                console.print("[bold green]✓ Gemini API Key berhasil disimpan![/bold green]\n")


def main() -> None:
    """Application main loop."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print_banner()

    llm = LLMClient()
    check_api_key_prompt(llm)

    current_project: Optional[NovelProject] = None

    while True:
        # Display active AI engine
        prov_label = "xAI Grok (Prioritas)" if llm.provider == "grok" else "Google Gemini"
        console.print(f"[bold blue]🤖 AI Engine:[/bold blue] [bold cyan]{prov_label}[/bold cyan] [dim]({llm.model})[/dim]")

        # Display current project status bar
        if current_project:
            title = current_project.metadata.get("title", "Tanpa Judul")
            drafted_count = len(current_project.list_drafted_chapters())
            illus_count = len(current_project.list_illustrated_chapters())
            total_target = current_project.metadata.get("target_chapters", 0)

            if not current_project.is_foundation_complete():
                missing = ", ".join(current_project.get_missing_foundation_components())
                status_desc = f"[bold yellow]⚠️ Belum Siap: {missing}[/bold yellow]"
            else:
                status_desc = (
                    f"[bold green]{drafted_count}/{total_target} bab ditulis[/bold green] | "
                    f"[bold magenta]{illus_count} bab berilustrasi[/bold magenta]"
                )

            console.print(
                f"[bold magenta]📍 Proyek Aktif:[/bold magenta] [bold white]{title}[/bold white] "
                f"({status_desc})"
            )
        else:
            console.print("[dim]Belum ada proyek aktif yang dipilih.[/dim]")

        console.print("\n[bold cyan]=== MENU UTAMA GHOSTWRITER ===[/bold cyan]")
        console.print("  [bold white]1.[/bold white] 🌟 Buat Proyek Novel Baru (Ide Manual / Upload File Artikel)")
        console.print("  [bold white]2.[/bold white] 📂 Buka & Kelola Proyek Novel (Buka / Hapus)")
        console.print("  [bold white]3.[/bold white] ✍️ Tulis / Lanjutkan Bab (Scene Planner + Prose Writer)")
        console.print("  [bold white]4.[/bold white] 🎨 Buat & Kelola Ilustrasi Bab (3 Ilustrasi Realistis, Konsisten & Tanpa Sensor)")
        console.print("  [bold white]5.[/bold white] 🔍 Audit & Edit Bab (Continuity & Style Editor)")
        console.print("  [bold white]6.[/bold white] 📖 Baca Naskah Bab di Terminal")
        console.print("  [bold white]7.[/bold white] 👥 Lihat & Kelola Karakter, World Bible, & Outline")
        console.print("  [bold white]8.[/bold white] 📦 Export Novel + Ilustrasi (Markdown & Word .docx)")
        console.print("  [bold white]9.[/bold white] ⚙️ Pengaturan AI (Grok / Gemini / Engine Ilustrasi)")
        console.print("  [bold white]10.[/bold white] 🚪 Keluar")

        choice = Prompt.ask(
            "\n[bold green]Pilih opsi (1-10)[/bold green]",
            choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            default="1",
        )

        if choice == "1":
            try:
                created = run_new_novel_wizard(llm)
                if created is not None:
                    current_project = created
                    llm.bind_project(current_project)
            except Exception as e:
                console.print(f"[bold red]Terjadi kesalahan saat membuat novel:[/bold red] {e}")

        elif choice == "2":
            current_project = select_existing_project(llm, current_project)
            if current_project is not None:
                llm.bind_project(current_project)

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
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu (Opsi 1 atau 2).[/yellow]")
            else:
                try:
                    illustrate_chapter_flow(current_project, llm)
                except Exception as e:
                    console.print(f"[bold red]Terjadi kesalahan saat mengelola ilustrasi bab:[/bold red] {e}")

        elif choice == "5":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                try:
                    audit_chapter_flow(current_project, llm)
                except Exception as e:
                    console.print(f"[bold red]Terjadi kesalahan saat audit bab:[/bold red] {e}")

        elif choice == "6":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                view_chapter_flow(current_project)

        elif choice == "7":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                show_world_and_characters(current_project, llm)

        elif choice == "8":
            if not current_project:
                console.print("[yellow]Buka atau buat proyek novel terlebih dahulu.[/yellow]")
            else:
                try:
                    export_novel_flow(current_project)
                except Exception as e:
                    console.print(f"[bold red]Terjadi kesalahan saat ekspor:[/bold red] {e}")

        elif choice == "9":
            manage_settings(llm)

        elif choice == "10":
            console.print("\n[bold cyan]Terima kasih telah menggunakan GhostWriter AI! Selamat berkarya.[/bold cyan] 🖋️\n")
            break

        console.print("\n" + "─" * 60 + "\n")


if __name__ == "__main__":
    main()
