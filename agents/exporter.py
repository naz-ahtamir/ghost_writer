"""Novel Exporter: Compiles manuscript and chapter illustrations into Markdown and DOCX."""

import html
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.project import NovelProject
from agents.illustrator import IllustratorAgent


class NovelExporter:
    """Exports completed novel chapters and their 3 illustrations to single-file formats."""

    def __init__(self, project: NovelProject):
        self.project = project

    def export_all(self) -> Tuple[Path, Path]:
        """Export novel to both Markdown and DOCX formats."""
        md_path = self.export_markdown()
        docx_path = self.export_docx()
        return md_path, docx_path

    def _get_chapter_markdown_with_illustrations(self, chapter_num: int) -> str:
        """Return chapter markdown with its 3 illustrations embedded at Opening, Middle, and Climax."""
        raw_content = self.project.get_chapter(chapter_num) or ""
        illustrations = self.project.get_chapter_illustrations(chapter_num)
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

        drafted_nums = self.project.list_drafted_chapters()
        outline_chapters = {
            ch.get("chapter_number"): ch.get("title", f"Bab {ch.get('chapter_number')}")
            for ch in self.project.outline.get("chapters", [])
        }

        for num in drafted_nums:
            ch_title = outline_chapters.get(num, f"Bab {num}")
            lines.append(f"- [Bab {num}: {ch_title}](#bab-{num})")

        lines.append("\n---\n")

        for num in drafted_nums:
            content = self._get_chapter_markdown_with_illustrations(num)
            lines.append(content)
            lines.append("\n\n---\n")

        file_path = self.project.exports_dir / f"{self.project.project_dir.name}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return file_path

    def _resolve_illustration_path(self, md_img_ref: str) -> Optional[Path]:
        """Resolve an image path referenced in Markdown relative to exports_dir or project_dir."""
        ref_clean = md_img_ref.strip()
        candidates = [
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

    def export_docx(self) -> Path:
        """Export entire novel (with embedded chapter illustrations) to a formatted Word Document (.docx)."""
        file_path = self.project.exports_dir / f"{self.project.project_dir.name}.docx"
        try:
            import docx
            from docx.shared import Inches, Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            return self._export_docx_openxml_fallback(file_path)

        doc = docx.Document()

        meta = self.project.metadata
        title = meta.get("title", "Novel")
        author = meta.get("author", "Penulis")
        genre = meta.get("genre", "")

        # Set standard margins (1 inch)
        for section in doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        # Title Page
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

        # Add Chapters + Illustrations
        drafted_nums = self.project.list_drafted_chapters()
        img_pattern = re.compile(r"^!\[(.*?)\]\((.*?)\)$")

        for i, num in enumerate(drafted_nums):
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
                        try:
                            pic_para = doc.add_paragraph()
                            pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            pic_run = pic_para.add_run()
                            pic_run.add_picture(str(img_file), width=Inches(5.5))
                            continue
                        except Exception:
                            pass
                    # Fallback caption if image file couldn't be decoded
                    cap_p = doc.add_paragraph()
                    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap_r = cap_p.add_run(f"[Ilustrasi: {alt_text}]")
                    cap_r.font.name = "Georgia"
                    cap_r.font.size = Pt(10)
                    cap_r.font.italic = True
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
                    # Italic caption paragraph
                    cap_text = line_str.strip("*").strip()
                    cp = doc.add_paragraph()
                    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cp.paragraph_format.space_after = Pt(10)
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

            if i < len(drafted_nums) - 1:
                doc.add_page_break()

        doc.save(str(file_path))
        return file_path

    def _export_docx_openxml_fallback(self, file_path: Path) -> Path:
        """Zero-dependency OpenXML (.docx) generator when python-docx is not installed."""
        meta = self.project.metadata
        title = html.escape(meta.get("title", "Novel"))
        author = html.escape(meta.get("author", "Penulis"))
        genre = html.escape(meta.get("genre", ""))

        body_paragraphs: List[str] = [
            f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="52"/></w:rPr><w:t>{title}</w:t></w:r></w:p>',
            f'<w:p><w:r><w:rPr><w:i/><w:sz w:val="28"/></w:rPr><w:t>Karya: {author} | Genre: {genre}</w:t></w:r></w:p>',
        ]

        media_files: List[Tuple[str, Path]] = []
        rels_entries: List[str] = []
        img_counter = 0
        img_pattern = re.compile(r"^!\[(.*?)\]\((.*?)\)$")

        for num in self.project.list_drafted_chapters():
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
                        img_counter += 1
                        r_id = f"rIdImg{img_counter}"
                        media_name = f"image{img_counter}{resolved.suffix.lower() or '.jpg'}"
                        media_files.append((f"word/media/{media_name}", resolved))
                        rels_entries.append(
                            f'<Relationship Id="{r_id}" '
                            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                            f'Target="media/{media_name}"/>'
                        )
                    esc_alt = html.escape(f"[Ilustrasi: {alt_text} ({Path(img_ref).name})]")
                    body_paragraphs.append(
                        f'<w:p><w:r><w:rPr><w:i/></w:rPr><w:t>{esc_alt}</w:t></w:r></w:p>'
                    )
                    continue

                esc_line = html.escape(line_str.lstrip("#").strip())
                if line_str.startswith("#"):
                    body_paragraphs.append(
                        f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="36"/></w:rPr><w:t>{esc_line}</w:t></w:r></w:p>'
                    )
                else:
                    body_paragraphs.append(
                        f'<w:p><w:r><w:t>{esc_line}</w:t></w:r></w:p>'
                    )

        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<w:body>{"".join(body_paragraphs)}</w:body></w:document>'
        )
        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="jpg" ContentType="image/jpeg"/>'
            '<Default Extension="jpeg" ContentType="image/jpeg"/>'
            '<Default Extension="png" ContentType="image/png"/>'
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

        with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", root_rels_xml)
            zf.writestr("word/document.xml", document_xml)
            zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
            for arc_name, src_path in media_files:
                zf.write(src_path, arc_name)

        return file_path
