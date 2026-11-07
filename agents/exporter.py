"""Novel Exporter: Compiles manuscript and chapter illustrations into Markdown, DOCX (with embedded OpenXML images), and HTML."""

import base64
import functools
import html
import http.server
import io
import os
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config
from core.image_gen import ImageGeneratorClient, normalize_to_jpeg_bytes
from core.project import NovelProject
from agents.illustrator import IllustratorAgent

_READER_SERVER_PORT: Optional[int] = None
_READER_SERVER_LOCK = threading.Lock()
_STORAGE_SETUP_ATTEMPTED = False


class _QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Quiet HTTP handler serving config.PROJECTS_DIR for mobile/Termux browser access."""

    def log_message(self, format: str, *args: Any) -> None:
        pass


class _ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _is_port_listening(port: int) -> bool:
    """Check if 127.0.0.1:port is actively accepting TCP connections."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def ensure_local_reader_server() -> int:
    """Start a persistent detached background HTTP server serving PROJECTS_DIR so 127.0.0.1 stays alive on Android."""
    global _READER_SERVER_PORT
    with _READER_SERVER_LOCK:
        if _READER_SERVER_PORT is not None and _is_port_listening(_READER_SERVER_PORT):
            return _READER_SERVER_PORT

        projects_root = str(config.PROJECTS_DIR.resolve())

        # Acquire Termux wake-lock if available so Android does not freeze the background server when switching to Chrome
        if shutil.which("termux-wake-lock"):
            try:
                subprocess.Popen(
                    ["termux-wake-lock"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

        for port in range(8765, 8810):
            if _is_port_listening(port):
                _READER_SERVER_PORT = port
                return port

            # 1. Try spawning a detached background process (survives exiting main.py on Android Termux)
            try:
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "http.server",
                        str(port),
                        "--bind",
                        "127.0.0.1",
                        "--directory",
                        projects_root,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
                for _ in range(8):
                    time.sleep(0.08)
                    if _is_port_listening(port):
                        _READER_SERVER_PORT = port
                        return port
            except Exception:
                pass

            # 2. Fallback to multi-threaded in-process HTTP server
            try:
                handler_cls = functools.partial(_QuietHTTPHandler, directory=projects_root)
                httpd = _ThreadingTCPServer(("127.0.0.1", port), handler_cls)
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                _READER_SERVER_PORT = port
                return port
            except OSError:
                continue

        raise RuntimeError("Tidak dapat membuka port lokal untuk Web Reader.")


def get_local_reader_url(file_path: Path) -> str:
    """Convert a project file path inside PROJECTS_DIR into an http://127.0.0.1:PORT/... URL."""
    file_path = Path(file_path).resolve()
    projects_root = config.PROJECTS_DIR.resolve()
    port = ensure_local_reader_server()
    try:
        rel = file_path.relative_to(projects_root)
        rel_url = "/".join(urllib.parse.quote(part) for part in rel.parts)
        return f"http://127.0.0.1:{port}/{rel_url}"
    except ValueError:
        return file_path.as_uri()


def _is_termux_environment() -> bool:
    """Detect whether we are running inside Android Termux."""
    return (
        "com.termux" in str(Path.home())
        or "TERMUX_VERSION" in os.environ
        or Path("/data/data/com.termux").exists()
    )


def sync_project_to_public_downloads(project: NovelProject) -> Optional[Path]:
    """Copy exported novel files (.html, .docx, .md) and illustrations (.jpg) into Android public Download/GhostWriter/."""
    global _STORAGE_SETUP_ATTEMPTED
    home = Path.home()
    candidates = [
        Path("/sdcard/Download"),
        Path("/storage/emulated/0/Download"),
        home / "storage" / "downloads",
        home / "storage" / "shared" / "Download",
        Path("/sdcard/Documents"),
        Path("/storage/emulated/0/Documents"),
        home / "Downloads",
        home / "Download",
    ]

    target_base: Optional[Path] = None
    for cand in candidates:
        try:
            if cand.exists() and cand.is_dir() and os.access(str(cand), os.W_OK):
                target_base = cand
                break
        except Exception:
            continue

    # If on Termux and storage permission hasn't been granted yet, trigger termux-setup-storage once
    if target_base is None and _is_termux_environment() and not _STORAGE_SETUP_ATTEMPTED:
        _STORAGE_SETUP_ATTEMPTED = True
        if shutil.which("termux-setup-storage"):
            try:
                subprocess.run(
                    ["termux-setup-storage"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                )
                time.sleep(1.0)
                for cand in candidates:
                    if cand.exists() and cand.is_dir() and os.access(str(cand), os.W_OK):
                        target_base = cand
                        break
            except Exception:
                pass

    if target_base is None:
        return None

    try:
        dest_dir = target_base / "GhostWriter" / project.project_dir.name
        dest_illus = dest_dir / "illustrations"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_illus.mkdir(parents=True, exist_ok=True)

        # Copy all exported files (.html, .docx, .md)
        if project.exports_dir.exists():
            for item in project.exports_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, dest_dir / item.name)

        # Copy all rendered illustrations (.jpg, .png)
        if project.illustrations_dir.exists():
            for img in project.illustrations_dir.iterdir():
                if img.is_file():
                    shutil.copy2(img, dest_illus / img.name)

        # Trigger Android media scanner so Gallery & File Manager immediately list the new files
        if shutil.which("termux-media-scan"):
            try:
                subprocess.Popen(
                    ["termux-media-scan", "-r", str(dest_dir)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

        return dest_dir
    except Exception:
        return None


def _get_mime_type(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if ext in (".html", ".htm"):
        return "text/html"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".md":
        return "text/markdown"
    return "*/*"


def open_file_in_viewer(file_path: Path, prefer_native_app: bool = True) -> str:
    """Open a file (.docx, .html, .jpg) on Android Termux or Desktop without 127.0.0.1 or file:// errors."""
    file_path = Path(file_path).resolve()
    mime_type = _get_mime_type(file_path)

    # Check if a public copy exists in /sdcard/Download/GhostWriter/...
    public_copy: Optional[Path] = None
    for pub_root in (
        Path("/sdcard/Download/GhostWriter"),
        Path("/storage/emulated/0/Download/GhostWriter"),
        Path.home() / "storage" / "downloads" / "GhostWriter",
    ):
        try:
            cand = pub_root / file_path.parent.parent.name / file_path.name
            if cand.exists():
                public_copy = cand
                break
            cand_illus = pub_root / file_path.parent.parent.name / "illustrations" / file_path.name
            if cand_illus.exists():
                public_copy = cand_illus
                break
        except Exception:
            continue

    target_local_file = public_copy or file_path

    # Start background HTTP server as backup for HTML files
    local_url = ""
    try:
        local_url = get_local_reader_url(file_path)
    except Exception:
        local_url = str(target_local_file)

    # 1. On Android Termux: pass the LOCAL FILE PATH (NOT file:// and NOT 127.0.0.1) to `termux-open`
    # `termux-open <filepath>` uses Termux's built-in ContentProvider (`content://com.termux.documents/...`),
    # which opens .docx in Word/WPS/Docs, .html in Chrome/HTML Viewer, and .jpg in Gallery 100% offline!
    if shutil.which("termux-open") and prefer_native_app:
        try:
            subprocess.Popen(
                ["termux-open", "--view", "--content-type", mime_type, str(target_local_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return str(target_local_file)
        except Exception:
            try:
                subprocess.Popen(
                    ["termux-open", str(target_local_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return str(target_local_file)
            except Exception:
                pass

    # 2. Termux Share API fallback (`termux-share -a view`)
    if shutil.which("termux-share") and prefer_native_app:
        try:
            subprocess.Popen(
                ["termux-share", "-a", "view", "-c", mime_type, str(target_local_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return str(target_local_file)
        except Exception:
            pass

    # 3. Termux URL opener for HTML reader via persistent background server
    if shutil.which("termux-open-url") and local_url.startswith("http"):
        try:
            subprocess.Popen(
                ["termux-open-url", local_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return local_url
        except Exception:
            pass

    # 4. Linux Desktop (xdg-open)
    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(
                ["xdg-open", str(target_local_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return str(target_local_file)
        except Exception:
            pass

    # 5. Python webbrowser fallback
    try:
        webbrowser.open(local_url or target_local_file.as_uri())
    except Exception:
        pass

    return str(target_local_file)


class NovelExporter:
    """Exports completed novel chapters and their 3 illustrations to single-file formats (.docx, .html, .md)."""

    def __init__(self, project: NovelProject):
        self.project = project

    def get_exportable_chapters(self) -> List[int]:
        """Return sorted union of all drafted chapters and all illustrated chapters."""
        drafted = set(self.project.list_drafted_chapters())
        illustrated = set(self.project.list_illustrated_chapters())
        # Also detect any chapter_XX_illus_YY.jpg files directly in illustrations_dir
        if self.project.illustrations_dir.exists():
            for f in self.project.illustrations_dir.glob("chapter_*_illus_*.jpg"):
                m = re.match(r"chapter_(\d+)_illus_\d+\.jpg", f.name)
                if m:
                    illustrated.add(int(m.group(1)))
        return sorted(drafted | illustrated)

    def ensure_chapter_illustrations_rendered(self, chapter_num: int) -> List[Dict[str, Any]]:
        """Ensure that all planned illustrations for a chapter have actual rendered .jpg files on disk."""
        illustrations = self.project.get_chapter_illustrations(chapter_num)
        if not illustrations:
            # Check if raw image files exist in illustrations_dir even without json metadata
            found_items: List[Dict[str, Any]] = []
            for idx in range(1, 4):
                cand_img = self.project.get_illustration_image_path(chapter_num, idx, ext=".jpg")
                if cand_img.exists() and cand_img.stat().st_size > 0:
                    found_items.append({
                        "illustration_number": idx,
                        "scene_title": f"Ilustrasi {idx} (Bab {chapter_num})",
                        "caption": f"Ilustrasi {idx} — Bab {chapter_num}",
                        "image_path": str(cand_img),
                        "status": "rendered",
                    })
            return found_items

        missing_slots: List[int] = []
        for idx, item in enumerate(illustrations, 1):
            slot_num = int(item.get("illustration_number", idx))
            raw_path = item.get("image_path") or str(self.project.get_illustration_image_path(chapter_num, slot_num))
            resolved = self._resolve_illustration_path(raw_path)
            if not resolved or not resolved.exists() or resolved.stat().st_size < 100:
                missing_slots.append(slot_num)

        if missing_slots:
            try:
                illustrator = IllustratorAgent(llm=None, image_client=ImageGeneratorClient())
                illustrations = illustrator.render_chapter_illustrations(
                    project=self.project,
                    chapter_num=chapter_num,
                    illustrations=illustrations,
                    slots_to_render=missing_slots,
                )
            except Exception:
                pass

        return illustrations

    def export_all(self) -> Tuple[Path, Path]:
        """Export novel to Markdown, DOCX (with embedded photos), and Illustrated HTML Reader, plus sync to Downloads."""
        for ch_num in self.get_exportable_chapters():
            self.ensure_chapter_illustrations_rendered(ch_num)
        md_path = self.export_markdown()
        docx_path = self.export_docx()
        self.export_html()
        sync_project_to_public_downloads(self.project)
        return md_path, docx_path

    def _get_chapter_markdown_with_illustrations(self, chapter_num: int) -> str:
        """Return chapter markdown with its 3 illustrations embedded at Opening, Middle, and Climax."""
        raw_content = self.project.get_chapter(chapter_num) or ""
        illustrations = self.ensure_chapter_illustrations_rendered(chapter_num)
        if not raw_content.strip():
            outline_chapters = {
                ch.get("chapter_number"): ch.get("title", f"Bab {ch.get('chapter_number')}")
                for ch in self.project.outline.get("chapters", [])
            }
            ch_title = outline_chapters.get(chapter_num, f"Bab {chapter_num}")
            raw_content = f"# Bab {chapter_num}: {ch_title}"

        if illustrations:
            return IllustratorAgent.inject_illustrations_into_markdown(
                prose=raw_content,
                illustrations=illustrations,
                relative_dir="../illustrations",
            )
        return raw_content

    def export_markdown(self) -> Path:
        """Export entire novel (including chapter illustrations) to a single clean Markdown file."""
        meta = self.project.metadata
        title = meta.get("title", "Novel")
        author = meta.get("author", "Penulis")
        genre = meta.get("genre", "")
        premise = meta.get("premise", "")

        lines = [
            f"# {title}",
            f"**Penulis:** {author}  ",
            f"**Genre:** {genre}  ",
            "",
            "## Sinopsis",
            f"> {premise}",
            "",
            "---",
            "",
            "## Daftar Bab",
            "",
        ]

        chapter_nums = self.get_exportable_chapters()
        outline_chapters = {
            ch.get("chapter_number"): ch.get("title", f"Bab {ch.get('chapter_number')}")
            for ch in self.project.outline.get("chapters", [])
        }

        for num in chapter_nums:
            ch_title = outline_chapters.get(num, f"Bab {num}")
            lines.append(f"- [Bab {num}: {ch_title}](#bab-{num})")

        lines.append("\n---\n")

        for num in chapter_nums:
            content = self._get_chapter_markdown_with_illustrations(num)
            lines.append(content)
            lines.append("\n\n---\n")

        file_path = self.project.exports_dir / f"{self.project.project_dir.name}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return file_path

    def _resolve_illustration_path(self, md_img_ref: str) -> Optional[Path]:
        """Resolve an image path referenced in Markdown relative to exports_dir, project_dir, or illustrations_dir."""
        if not md_img_ref:
            return None
        ref_clean = md_img_ref.strip()
        candidates = [
            Path(ref_clean),
            (self.project.exports_dir / ref_clean),
            (self.project.project_dir / ref_clean.lstrip("./")),
            (self.project.illustrations_dir / Path(ref_clean).name),
        ]
        for cand in candidates:
            try:
                if cand.exists() and cand.is_file():
                    return cand.resolve()
            except Exception:
                continue
        return None

    def _prepare_docx_image_bytes(self, img_path: Path) -> Tuple[bytes, str]:
        """Read image bytes and convert to standard RGB JPEG (or PNG/WebP) so Word always renders it."""
        raw_bytes = img_path.read_bytes()
        normalized = normalize_to_jpeg_bytes(raw_bytes)
        if normalized.startswith(b"\xff\xd8\xff"):
            # If the file on disk was previously WebP saved as .jpg, upgrade it in place
            if not raw_bytes.startswith(b"\xff\xd8\xff") and img_path.suffix.lower() in (".jpg", ".jpeg"):
                try:
                    img_path.write_bytes(normalized)
                except Exception:
                    pass
            return normalized, ".jpg"
        if normalized.startswith(b"\x89PNG"):
            return normalized, ".png"
        if normalized.startswith(b"RIFF"):
            return normalized, ".webp"
        return normalized, (img_path.suffix.lower() or ".jpg")

    def export_docx(self) -> Path:
        """Export entire novel (with embedded chapter illustrations) to a formatted Word Document (.docx)."""
        file_path = self.project.exports_dir / f"{self.project.project_dir.name}.docx"
        try:
            import docx
            from docx.shared import Inches, Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            return self._export_docx_openxml_fallback(file_path)

        try:
            doc = docx.Document()

            meta = self.project.metadata
            title = meta.get("title", "Novel")
            author = meta.get("author", "Penulis")
            genre = meta.get("genre", "")

            for section in doc.sections:
                section.top_margin = Inches(1)
                section.bottom_margin = Inches(1)
                section.left_margin = Inches(1)
                section.right_margin = Inches(1)

            title_para = doc.add_paragraph()
            title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title_run = title_para.add_run(f"\n\n\n{title}\n")
            title_run.font.name = "Georgia"
            title_run.font.size = Pt(28)
            title_run.bold = True

            author_para = doc.add_paragraph()
            author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            author_run = author_para.add_run(f"Karya: {author}\n\n")
            author_run.font.name = "Georgia"
            author_run.font.size = Pt(14)
            author_run.font.italic = True

            genre_para = doc.add_paragraph()
            genre_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            genre_run = genre_para.add_run(f"Genre: {genre}\n\n\n")
            genre_run.font.name = "Georgia"
            genre_run.font.size = Pt(11)
            genre_run.font.color.rgb = RGBColor(120, 120, 120)

            doc.add_page_break()

            chapter_nums = self.get_exportable_chapters()
            img_pattern = re.compile(r"^!\[(.*?)\]\((.*?)\)$")

            for i, num in enumerate(chapter_nums):
                content = self._get_chapter_markdown_with_illustrations(num)
                lines = content.split("\n")

                for line in lines:
                    line_str = line.strip()
                    if not line_str or line_str.startswith("<!-- GHOSTWRITER_ILLUSTRATION"):
                        continue

                    img_match = img_pattern.match(line_str)
                    if img_match:
                        alt_text, img_ref = img_match.group(1), img_match.group(2)
                        img_file = self._resolve_illustration_path(img_ref)
                        if img_file and img_file.exists():
                            img_bytes, _ = self._prepare_docx_image_bytes(img_file)
                            pic_para = doc.add_paragraph()
                            pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            pic_run = pic_para.add_run()
                            pic_run.add_picture(io.BytesIO(img_bytes), width=Inches(5.8))
                            continue

                    if line_str.startswith("# "):
                        heading_text = line_str.replace("# ", "").strip()
                        h = doc.add_heading(heading_text, level=1)
                        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        for r in h.runs:
                            r.font.name = "Georgia"
                            r.font.size = Pt(18)
                            r.bold = True
                    elif line_str.startswith("## "):
                        subheading = line_str.replace("## ", "").strip()
                        h = doc.add_heading(subheading, level=2)
                        for r in h.runs:
                            r.font.name = "Georgia"
                            r.font.size = Pt(14)
                    elif line_str in ["***", "---", "* * *"]:
                        sep = doc.add_paragraph("* * *")
                        sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        for r in sep.runs:
                            r.font.name = "Georgia"
                            r.font.size = Pt(12)
                    elif line_str.startswith("*") and line_str.endswith("*") and len(line_str) > 2:
                        cap_text = line_str.strip("*").strip()
                        cp = doc.add_paragraph()
                        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        cp.paragraph_format.space_after = Pt(12)
                        cr = cp.add_run(cap_text)
                        cr.font.name = "Georgia"
                        cr.font.size = Pt(10)
                        cr.font.italic = True
                    else:
                        p = doc.add_paragraph()
                        p.paragraph_format.line_spacing = 1.25
                        p.paragraph_format.space_after = Pt(6)
                        run = p.add_run(line_str)
                        run.font.name = "Georgia"
                        run.font.size = Pt(11)

                if i < len(chapter_nums) - 1:
                    doc.add_page_break()

            doc.save(str(file_path))
            return file_path
        except Exception:
            # If python-docx fails on any image header, fall back to our native OpenXML builder
            return self._export_docx_openxml_fallback(file_path)

    def _export_docx_openxml_fallback(self, file_path: Path) -> Path:
        """Zero-dependency OpenXML (.docx) generator with full <w:drawing> embedded photos for Word/WPS/Docs."""
        meta = self.project.metadata
        title = html.escape(meta.get("title", "Novel"))
        author = html.escape(meta.get("author", "Penulis"))
        genre = html.escape(meta.get("genre", ""))

        body_paragraphs: List[str] = [
            (
                '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="720" w:after="240"/></w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:b/><w:sz w:val="56"/></w:rPr><w:t>{title}</w:t></w:r></w:p>'
            ),
            (
                '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="160"/></w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:i/><w:sz w:val="28"/></w:rPr><w:t>Karya: {author}</w:t></w:r></w:p>'
            ),
            (
                '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="480"/></w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:color w:val="666666"/><w:sz w:val="22"/></w:rPr><w:t>Genre: {genre}</w:t></w:r></w:p>'
            ),
            '<w:p><w:r><w:br w:type="page"/></w:r></w:p>',
        ]

        media_blobs: List[Tuple[str, bytes]] = []
        rels_entries: List[str] = []
        img_counter = 0
        img_pattern = re.compile(r"^!\[(.*?)\]\((.*?)\)$")

        # 6.0 inches x 3.375 inches (16:9 widescreen) in OpenXML EMUs (1 inch = 914400 EMUs)
        cx_emu = 5486400
        cy_emu = 3086100

        chapter_nums = self.get_exportable_chapters()
        for ch_idx, num in enumerate(chapter_nums):
            content = self._get_chapter_markdown_with_illustrations(num)
            for line in content.split("\n"):
                line_str = line.strip()
                if not line_str or line_str.startswith("<!-- GHOSTWRITER_ILLUSTRATION"):
                    continue

                img_match = img_pattern.match(line_str)
                if img_match:
                    alt_text, img_ref = img_match.group(1), img_match.group(2)
                    resolved = self._resolve_illustration_path(img_ref)
                    if resolved and resolved.exists():
                        img_bytes, ext = self._prepare_docx_image_bytes(resolved)
                        img_counter += 1
                        r_id = f"rIdImg{img_counter}"
                        media_name = f"image{img_counter}{ext}"
                        media_blobs.append((f"word/media/{media_name}", img_bytes))
                        rels_entries.append(
                            f'<Relationship Id="{r_id}" '
                            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                            f'Target="media/{media_name}"/>'
                        )
                        esc_descr = html.escape(alt_text or f"Ilustrasi {img_counter}")
                        drawing_p = (
                            '<w:p>'
                            '<w:pPr><w:jc w:val="center"/><w:spacing w:before="240" w:after="80"/></w:pPr>'
                            '<w:r>'
                            '<w:drawing>'
                            '<wp:inline distT="0" distB="0" distL="0" distR="0">'
                            f'<wp:extent cx="{cx_emu}" cy="{cy_emu}"/>'
                            '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
                            f'<wp:docPr id="{img_counter}" name="Picture {img_counter}" descr="{esc_descr}"/>'
                            '<wp:cNvGraphicFramePr>'
                            '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
                            '</wp:cNvGraphicFramePr>'
                            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                            '<pic:nvPicPr>'
                            f'<pic:cNvPr id="{img_counter}" name="{media_name}" descr="{esc_descr}"/>'
                            '<pic:cNvPicPr/>'
                            '</pic:nvPicPr>'
                            '<pic:blipFill>'
                            f'<a:blip r:embed="{r_id}"/>'
                            '<a:stretch><a:fillRect/></a:stretch>'
                            '</pic:blipFill>'
                            '<pic:spPr>'
                            '<a:xfrm>'
                            '<a:off x="0" y="0"/>'
                            f'<a:ext cx="{cx_emu}" cy="{cy_emu}"/>'
                            '</a:xfrm>'
                            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
                            '</pic:spPr>'
                            '</pic:pic>'
                            '</a:graphicData>'
                            '</a:graphic>'
                            '</wp:inline>'
                            '</w:drawing>'
                            '</w:r>'
                            '</w:p>'
                        )
                        body_paragraphs.append(drawing_p)
                        continue

                if line_str.startswith("# "):
                    esc_h1 = html.escape(line_str[2:].strip())
                    body_paragraphs.append(
                        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="360" w:after="240"/></w:pPr>'
                        f'<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:b/><w:sz w:val="36"/></w:rPr><w:t>{esc_h1}</w:t></w:r></w:p>'
                    )
                elif line_str.startswith("## "):
                    esc_h2 = html.escape(line_str[3:].strip())
                    body_paragraphs.append(
                        '<w:p><w:pPr><w:spacing w:before="240" w:after="140"/></w:pPr>'
                        f'<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:b/><w:sz w:val="28"/></w:rPr><w:t>{esc_h2}</w:t></w:r></w:p>'
                    )
                elif line_str in ("***", "---", "* * *"):
                    body_paragraphs.append(
                        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="180" w:after="180"/></w:pPr>'
                        '<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:sz w:val="24"/></w:rPr><w:t>* * *</w:t></w:r></w:p>'
                    )
                elif line_str.startswith("*") and line_str.endswith("*") and len(line_str) > 2:
                    esc_cap = html.escape(line_str.strip("*").strip())
                    body_paragraphs.append(
                        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="40" w:after="240"/></w:pPr>'
                        f'<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:i/><w:color w:val="555555"/><w:sz w:val="20"/></w:rPr><w:t>{esc_cap}</w:t></w:r></w:p>'
                    )
                else:
                    esc_p = html.escape(line_str)
                    body_paragraphs.append(
                        '<w:p><w:pPr><w:spacing w:after="140" w:line="300" w:lineRule="auto"/></w:pPr>'
                        f'<w:r><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:sz w:val="22"/></w:rPr><w:t>{esc_p}</w:t></w:r></w:p>'
                    )

            if ch_idx < len(chapter_nums) - 1:
                body_paragraphs.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

        sect_pr = (
            '<w:sectPr>'
            '<w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>'
            '</w:sectPr>'
        )

        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<w:body>{"".join(body_paragraphs)}{sect_pr}</w:body></w:document>'
        )
        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="jpg" ContentType="image/jpeg"/>'
            '<Default Extension="jpeg" ContentType="image/jpeg"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            '<Default Extension="webp" ContentType="image/webp"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        )
        root_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            '</Relationships>'
        )
        doc_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(rels_entries)}'
            '</Relationships>'
        )

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", root_rels_xml)
            zf.writestr("word/document.xml", document_xml)
            zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
            for arc_name, blob in media_blobs:
                zf.writestr(arc_name, blob)

        return file_path

    def export_html(self, specific_chapter: Optional[int] = None) -> Path:
        """Export an interactive, self-contained Illustrated Web Reader (.html) with Base64 embedded images."""
        meta = self.project.metadata
        title = html.escape(meta.get("title", "Novel"))
        author = html.escape(meta.get("author", "Penulis"))
        genre = html.escape(meta.get("genre", ""))
        premise = html.escape(meta.get("premise", ""))

        if specific_chapter is not None:
            chapter_nums = [specific_chapter]
            out_name = f"{self.project.project_dir.name}_bab_{specific_chapter:02d}_reader.html"
        else:
            chapter_nums = self.get_exportable_chapters()
            out_name = f"{self.project.project_dir.name}.html"

        img_pattern = re.compile(r"^!\[(.*?)\]\((.*?)\)$")
        chapters_html_blocks: List[str] = []
        toc_links: List[str] = []

        outline_chapters = {
            ch.get("chapter_number"): ch.get("title", f"Bab {ch.get('chapter_number')}")
            for ch in self.project.outline.get("chapters", [])
        }

        for num in chapter_nums:
            ch_title = html.escape(outline_chapters.get(num, f"Bab {num}"))
            toc_links.append(f'<li><a href="#bab-{num}">Bab {num}: {ch_title}</a></li>')

            content = self._get_chapter_markdown_with_illustrations(num)
            lines = content.split("\n")
            ch_elements: List[str] = [f'<section class="chapter" id="bab-{num}">']

            for line in lines:
                line_str = line.strip()
                if not line_str or line_str.startswith("<!-- GHOSTWRITER_ILLUSTRATION"):
                    continue

                img_match = img_pattern.match(line_str)
                if img_match:
                    alt_text, img_ref = img_match.group(1), img_match.group(2)
                    resolved = self._resolve_illustration_path(img_ref)
                    img_src = html.escape(img_ref)
                    if resolved and resolved.exists():
                        try:
                            img_bytes, ext = self._prepare_docx_image_bytes(resolved)
                            b64_data = base64.b64encode(img_bytes).decode("ascii")
                            mime = "image/png" if ext == ".png" else ("image/webp" if ext == ".webp" else "image/jpeg")
                            img_src = f"data:{mime};base64,{b64_data}"
                        except Exception:
                            pass
                    img_name = resolved.name if resolved else Path(img_ref).name
                    ch_elements.append(
                        f'<figure class="illustration-frame">'
                        f'<img src="{img_src}" alt="{html.escape(alt_text)}" loading="lazy"/>'
                        f'<figcaption class="illus-title">{html.escape(alt_text)} '
                        f'&nbsp;|&nbsp; <a href="{img_src}" download="{html.escape(img_name)}" style="color:#9ece6a;text-decoration:none;">📥 Simpan Gambar (.jpg)</a>'
                        f'</figcaption>'
                        f'</figure>'
                    )
                    continue

                if line_str.startswith("# "):
                    h_txt = html.escape(line_str[2:].strip())
                    ch_elements.append(f'<h2 class="chapter-title">{h_txt}</h2>')
                elif line_str.startswith("## "):
                    h2_txt = html.escape(line_str[3:].strip())
                    ch_elements.append(f'<h3>{h2_txt}</h3>')
                elif line_str in ("***", "---", "* * *"):
                    ch_elements.append('<div class="scene-sep">* &nbsp; * &nbsp; *</div>')
                elif line_str.startswith("*") and line_str.endswith("*") and len(line_str) > 2:
                    cap_txt = html.escape(line_str.strip("*").strip())
                    ch_elements.append(f'<p class="illus-caption">“{cap_txt}”</p>')
                else:
                    ch_elements.append(f'<p>{html.escape(line_str)}</p>')

            ch_elements.append("</section>")
            chapters_html_blocks.append("\n".join(ch_elements))

        slug_name = html.escape(self.project.project_dir.name)
        full_html = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — GhostWriter Illustrated Reader</title>
  <style>
    :root {{
      --bg: #0f1117;
      --card: #181b24;
      --text: #e6e8ee;
      --muted: #9aa3b5;
      --accent: #7aa2f7;
      --border: #2a3040;
    }}
    body.light {{
      --bg: #f7f4ed;
      --card: #ffffff;
      --text: #22242a;
      --muted: #626875;
      --accent: #3b5bdb;
      --border: #e2dccf;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: 'Georgia', 'Times New Roman', serif;
      line-height: 1.85;
      font-size: 18px;
      transition: background 0.25s, color 0.25s;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 50;
      background: var(--card);
      border-bottom: 1px solid var(--border);
      padding: 12px 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: space-between;
      align-items: center;
      font-family: system-ui, sans-serif;
    }}
    .btn {{
      background: var(--accent);
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
      text-decoration: none;
      display: inline-block;
    }}
    .btn-dl {{
      background: #2ac3de;
      color: #0f1117;
    }}
    .container {{
      max-width: 820px;
      margin: 36px auto;
      padding: 0 20px 80px;
    }}
    .hero {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 36px 28px;
      text-align: center;
      margin-bottom: 36px;
    }}
    .hero h1 {{ margin: 0 0 10px; font-size: 2.2rem; color: var(--accent); }}
    .hero .meta {{ color: var(--muted); font-style: italic; margin-bottom: 18px; }}
    .hero .premise {{ font-size: 1rem; color: var(--text); text-align: left; background: rgba(122,162,247,0.07); padding: 16px; border-radius: 8px; }}
    .dl-bar {{
      margin-top: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: center;
      font-family: system-ui, sans-serif;
    }}
    .toc {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px 28px;
      margin-bottom: 40px;
      font-family: system-ui, sans-serif;
    }}
    .toc h3 {{ margin-top: 0; color: var(--accent); }}
    .toc ul {{ padding-left: 20px; margin: 0; }}
    .toc a {{ color: var(--text); text-decoration: none; }}
    .toc a:hover {{ color: var(--accent); text-decoration: underline; }}
    .chapter {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 40px 34px;
      margin-bottom: 48px;
      box-shadow: 0 8px 28px rgba(0,0,0,0.22);
    }}
    .chapter-title {{
      text-align: center;
      font-size: 1.85rem;
      color: var(--accent);
      margin-top: 0;
      margin-bottom: 32px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }}
    .chapter p {{ margin: 0 0 1.25em; text-align: justify; }}
    .scene-sep {{ text-align: center; color: var(--muted); margin: 28px 0; font-size: 1.2rem; }}
    .illustration-frame {{
      margin: 34px 0 10px;
      text-align: center;
      background: #08090d;
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(0,0,0,0.45);
    }}
    .illustration-frame img {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .illus-title {{
      font-family: system-ui, sans-serif;
      font-size: 0.85rem;
      color: var(--accent);
      padding: 10px 14px 6px;
      font-weight: 600;
      letter-spacing: 0.03em;
    }}
    .illus-caption {{
      text-align: center !important;
      font-style: italic;
      color: var(--muted);
      font-size: 0.95rem;
      margin-top: 4px !important;
      margin-bottom: 30px !important;
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <div><strong>🖋️ {title}</strong> <span style="color:var(--muted);font-size:13px;">| GhostWriter Illustrated Reader</span></div>
    <button class="btn" onclick="document.body.classList.toggle('light')">🌗 Mode Gelap / Terang</button>
  </div>
  <div class="container">
    <div class="hero">
      <h1>{title}</h1>
      <div class="meta">Karya: {author} &nbsp;•&nbsp; Genre: {genre}</div>
      <div class="premise">{premise}</div>
      <div class="dl-bar">
        <a class="btn btn-dl" href="{slug_name}.docx" download="{slug_name}.docx">📘 Download Word (.docx)</a>
        <a class="btn btn-dl" href="{ html.escape(out_name) }" download="{ html.escape(out_name) }">🌐 Download E-Book (.html)</a>
        <a class="btn btn-dl" href="{slug_name}.md" download="{slug_name}.md">📄 Download Markdown (.md)</a>
      </div>
    </div>
    <div class="toc">
      <h3>📑 Daftar Bab & Ilustrasi</h3>
      <ul>
        {"".join(toc_links)}
      </ul>
    </div>
    {"".join(chapters_html_blocks)}
  </div>
</body>
</html>"""

        file_path = self.project.exports_dir / out_name
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        sync_project_to_public_downloads(self.project)
        return file_path
