"""Document loader utility for importing articles/files (.txt, .md, .docx, .pdf, .odt, .html) into GhostWriter."""

import html
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_EXTENSIONS = (".txt", ".md", ".docx", ".pdf", ".odt", ".html", ".htm", ".json")


def discover_local_documents(max_files: int = 15) -> List[Path]:
    """Scan common project and user folders (including Android/Termux Downloads) for document files."""
    search_dirs: List[Path] = []
    cwd = Path.cwd()
    search_dirs.append(cwd)

    uploads_dir = cwd / "articles"
    if uploads_dir.exists():
        search_dirs.append(uploads_dir)

    home = Path.home()
    for sub in ("Downloads", "Download", "Documents", "Dokumen", "storage/downloads", "storage/shared/Download"):
        candidate = home / sub
        if candidate.exists() and candidate.is_dir():
            search_dirs.append(candidate)

    # Standard Android / Termux shared storage paths
    for android_path in ("/sdcard/Download", "/sdcard/Documents", "/storage/emulated/0/Download", "/storage/emulated/0/Documents"):
        p = Path(android_path)
        if p.exists() and p.is_dir():
            search_dirs.append(p)

    seen_paths = set()
    found_files: List[Tuple[float, Path]] = []

    excluded_names = {"requirements.txt", "readme.md", "metadata.json", "world_bible.json", "characters.json", "outline.json"}

    for directory in search_dirs:
        try:
            for item in directory.iterdir():
                if not item.is_file():
                    continue
                if item.name.lower() in excluded_names or item.name.startswith("."):
                    continue
                if item.suffix.lower() in SUPPORTED_EXTENSIONS:
                    resolved = str(item.resolve())
                    if resolved not in seen_paths:
                        seen_paths.add(resolved)
                        try:
                            mtime = item.stat().st_mtime
                        except Exception:
                            mtime = 0.0
                        found_files.append((mtime, item))
        except Exception:
            continue

    # Sort by most recently modified first
    found_files.sort(key=lambda x: x[0], reverse=True)
    return [f[1] for f in found_files[:max_files]]


def _extract_docx_text(file_path: Path) -> str:
    """Extract text from a .docx file using python-docx if available, or standard library zipfile+xml."""
    try:
        import docx
        doc = docx.Document(str(file_path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception:
        pass

    # Zero-dependency fallback: parse word/document.xml inside .docx zip archive
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                raise ValueError("File .docx tidak memiliki word/document.xml yang valid.")
            xml_bytes = zf.read("word/document.xml")
            root = ET.fromstring(xml_bytes)
            paragraphs: List[str] = []
            for elem in root.iter():
                if elem.tag.endswith("}p"):
                    texts = [
                        node.text
                        for node in elem.iter()
                        if node.tag.endswith("}t") and node.text
                    ]
                    para_str = "".join(texts).strip()
                    if para_str:
                        paragraphs.append(para_str)
            return "\n\n".join(paragraphs)
    except Exception as e:
        raise ValueError(f"Gagal membaca file Word (.docx): {e}")


def _extract_odt_text(file_path: Path) -> str:
    """Extract text from an OpenDocument (.odt) file via built-in zipfile+xml."""
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            xml_bytes = zf.read("content.xml")
            root = ET.fromstring(xml_bytes)
            paragraphs: List[str] = []
            for elem in root.iter():
                if elem.tag.endswith("}p") or elem.tag.endswith("}h"):
                    para_str = "".join(elem.itertext()).strip()
                    if para_str:
                        paragraphs.append(para_str)
            return "\n\n".join(paragraphs)
    except Exception as e:
        raise ValueError(f"Gagal membaca file ODT: {e}")


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text from a .pdf file using available Python libraries or pdftotext CLI."""
    # 1. Try pypdf / PyPDF2
    for mod_name in ("pypdf", "PyPDF2"):
        try:
            mod = __import__(mod_name)
            reader = mod.PdfReader(str(file_path))
            pages = []
            for page in reader.pages:
                txt = page.extract_text() or ""
                if txt.strip():
                    pages.append(txt.strip())
            if pages:
                return "\n\n".join(pages)
        except Exception:
            pass

    # 2. Try PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(str(file_path))
        pages = [page.get_text("text").strip() for page in doc if page.get_text("text").strip()]
        if pages:
            return "\n\n".join(pages)
    except Exception:
        pass

    # 3. Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(str(file_path)) as pdf:
            pages = [(p.extract_text() or "").strip() for p in pdf.pages]
            pages = [p for p in pages if p]
            if pages:
                return "\n\n".join(pages)
    except Exception:
        pass

    # 4. Try pdftotext command line utility (common on Linux and Termux poppler)
    try:
        res = subprocess.run(
            ["pdftotext", str(file_path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    raise ValueError(
        "Untuk membaca file PDF, silakan instal 'pypdf' (pip install pypdf) atau gunakan file .txt / .docx / .md."
    )


def _strip_html(raw_html: str) -> str:
    """Strip HTML tags and decode entities into clean readable text."""
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p>", "\n\n", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


def load_document_text(file_path_str: str) -> Tuple[str, Dict[str, int]]:
    """Read a document file and return (cleaned_text, stats_dict).

    Supports: .txt, .md, .docx, .pdf, .odt, .html, .htm, .json
    """
    cleaned_path_str = file_path_str.strip().strip('"').strip("'")
    path = Path(os.path.expanduser(cleaned_path_str))

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"Path yang dimasukkan adalah folder, bukan file: {path}")

    ext = path.suffix.lower()

    if ext == ".docx":
        text = _extract_docx_text(path)
    elif ext == ".odt":
        text = _extract_odt_text(path)
    elif ext == ".pdf":
        text = _extract_pdf_text(path)
    elif ext in (".html", ".htm"):
        raw = _read_text_with_fallback(path)
        text = _strip_html(raw)
    else:
        text = _read_text_with_fallback(path)

    text = text.strip()
    if not text:
        raise ValueError(f"File '{path.name}' kosong atau tidak memiliki teks yang dapat dibaca.")

    word_count = len(text.split())
    char_count = len(text)
    return text, {
        "words": word_count,
        "characters": char_count,
        "filename": path.name,
    }


def _read_text_with_fallback(path: Path) -> str:
    """Read plain text file with UTF-8 and fallback encodings."""
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()
