"""Novel Exporter: Compiles manuscript into Markdown and DOCX."""

from pathlib import Path
from typing import Dict, List, Tuple
from core.project import NovelProject


class NovelExporter:
    """Exports completed novel chapters to single-file formats."""

    def __init__(self, project: NovelProject):
        self.project = project

    def export_all(self) -> Tuple[Path, Path]:
        """Export novel to both Markdown and DOCX formats."""
        md_path = self.export_markdown()
        docx_path = self.export_docx()
        return md_path, docx_path

    def export_markdown(self) -> Path:
        """Export entire novel to a single clean Markdown file."""
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
            content = self.project.get_chapter(num) or ""
            lines.append(content)
            lines.append("\n\n---\n")

        file_path = self.project.exports_dir / f"{self.project.project_dir.name}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return file_path

    def export_docx(self) -> Path:
        """Export entire novel to a formatted Word Document (.docx)."""
        import docx
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

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

        # Add Chapters
        drafted_nums = self.project.list_drafted_chapters()
        for i, num in enumerate(drafted_nums):
            content = self.project.get_chapter(num) or ""
            lines = content.split("\n")

            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                if line_str.startswith("# "):
                    # Chapter Heading
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
                    # Scene separator
                    sep = doc.add_paragraph("* * *")
                    sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for r in sep.runs:
                        r.font.name = "Georgia"
                        r.font.size = Pt(12)
                else:
                    # Normal narrative paragraph
                    p = doc.add_paragraph()
                    p.paragraph_format.line_spacing = 1.25
                    p.paragraph_format.space_after = Pt(6)
                    run = p.add_run(line_str)
                    run.font.name = "Georgia"
                    run.font.size = Pt(11)

            # Add page break between chapters (except last chapter)
            if i < len(drafted_nums) - 1:
                doc.add_page_break()

        file_path = self.project.exports_dir / f"{self.project.project_dir.name}.docx"
        doc.save(str(file_path))
        return file_path
