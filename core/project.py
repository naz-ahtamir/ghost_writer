"""Project and persistent state manager for novels."""

import datetime
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import config


def slugify(text: str) -> str:
    """Convert title to filesystem-safe folder name."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_") or "novel_project"


class NovelProject:
    """Manages files, data, and chapters for a single novel project."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.chapters_dir = self.project_dir / "chapters"
        self.exports_dir = self.project_dir / "exports"

        self.metadata_path = self.project_dir / "metadata.json"
        self.world_bible_path = self.project_dir / "world_bible.json"
        self.characters_path = self.project_dir / "characters.json"
        self.outline_path = self.project_dir / "outline.json"

        # Ensure directories exist
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.chapters_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        self.metadata: Dict[str, Any] = {}
        self.world_bible: Dict[str, Any] = {}
        self.characters: List[Dict[str, Any]] = []
        self.outline: Dict[str, Any] = {}

        self.load()

    def load(self) -> None:
        """Load all project files from disk."""
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

        if self.world_bible_path.exists():
            with open(self.world_bible_path, "r", encoding="utf-8") as f:
                self.world_bible = json.load(f)

        if self.characters_path.exists():
            with open(self.characters_path, "r", encoding="utf-8") as f:
                self.characters = json.load(f)

        if self.outline_path.exists():
            with open(self.outline_path, "r", encoding="utf-8") as f:
                self.outline = json.load(f)

    def is_world_bible_complete(self) -> bool:
        """Check if world bible has essential data."""
        if not self.world_bible:
            return False
        return bool(self.world_bible.get("setting_name") or self.world_bible.get("core_concept"))

    def is_characters_complete(self) -> bool:
        """Check if character list is populated."""
        return bool(isinstance(self.characters, list) and len(self.characters) > 0)

    def is_outline_complete(self) -> bool:
        """Check if outline has planned chapters."""
        chapters = self.outline.get("chapters", [])
        return bool(isinstance(chapters, list) and len(chapters) > 0)

    def is_foundation_complete(self) -> bool:
        """Check if world lore, characters, and chapter outline are all ready."""
        return (
            self.is_world_bible_complete()
            and self.is_characters_complete()
            and self.is_outline_complete()
        )

    def get_missing_foundation_components(self) -> List[str]:
        """Return list of human-readable missing components."""
        missing = []
        if not self.is_world_bible_complete():
            missing.append("World Bible (Latar & Lore)")
        if not self.is_characters_complete():
            missing.append("Daftar Karakter")
        if not self.is_outline_complete():
            missing.append("Outline Bab")
        return missing

    def _update_stage(self) -> None:
        """Update stage based on current project artifacts."""
        target_ch = self.metadata.get("target_chapters", 0)
        drafted_ch = len(self.list_drafted_chapters())

        if target_ch > 0 and drafted_ch >= target_ch:
            self.metadata["stage"] = "completed"
        elif drafted_ch > 0:
            self.metadata["stage"] = "writing"
        elif self.is_foundation_complete():
            self.metadata["stage"] = "outline_ready"
        elif self.is_world_bible_complete() and self.is_characters_complete():
            self.metadata["stage"] = "characters_designed"
        elif self.is_world_bible_complete():
            self.metadata["stage"] = "world_designed"
        else:
            self.metadata["stage"] = "created"

    def save_metadata(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Save project metadata."""
        if data:
            self.metadata.update(data)
        self.metadata["updated_at"] = datetime.datetime.now().isoformat()
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def save_world_bible(self, data: Dict[str, Any]) -> None:
        """Save world lore and rules."""
        self.world_bible = data
        with open(self.world_bible_path, "w", encoding="utf-8") as f:
            json.dump(self.world_bible, f, indent=2, ensure_ascii=False)
        self._update_stage()
        self.save_metadata()

    def save_characters(self, data: List[Dict[str, Any]]) -> None:
        """Save character profiles."""
        self.characters = data
        with open(self.characters_path, "w", encoding="utf-8") as f:
            json.dump(self.characters, f, indent=2, ensure_ascii=False)
        self._update_stage()
        self.save_metadata()

    def save_outline(self, data: Dict[str, Any]) -> None:
        """Save narrative plot and chapters outline."""
        self.outline = data
        with open(self.outline_path, "w", encoding="utf-8") as f:
            json.dump(self.outline, f, indent=2, ensure_ascii=False)
        self._update_stage()
        self.save_metadata()

    def get_chapter_file(self, chapter_num: int) -> Path:
        """Path to chapter markdown file."""
        return self.chapters_dir / f"chapter_{chapter_num:02d}.md"

    def get_chapter_beats_file(self, chapter_num: int) -> Path:
        """Path to chapter scene beats json file."""
        return self.chapters_dir / f"chapter_{chapter_num:02d}_beats.json"

    def get_chapter_audit_file(self, chapter_num: int) -> Path:
        """Path to chapter audit report json file."""
        return self.chapters_dir / f"chapter_{chapter_num:02d}_audit.json"

    def save_chapter_beats(
        self,
        chapter_num: int,
        beats: List[Dict[str, Any]],
    ) -> None:
        """Save chapter scene beats independently."""
        beats_file = self.get_chapter_beats_file(chapter_num)
        with open(beats_file, "w", encoding="utf-8") as f:
            json.dump(beats, f, indent=2, ensure_ascii=False)

    def save_chapter(
        self,
        chapter_num: int,
        content: str,
        beats: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Save chapter content and beats."""
        chap_file = self.get_chapter_file(chapter_num)
        with open(chap_file, "w", encoding="utf-8") as f:
            f.write(content)

        if beats:
            self.save_chapter_beats(chapter_num, beats)

        # Update outline status if chapter exists in outline
        if "chapters" in self.outline:
            for ch in self.outline["chapters"]:
                if ch.get("chapter_number") == chapter_num:
                    ch["status"] = "drafted"
                    break
            self.save_outline(self.outline)

    def save_chapter_audit(self, chapter_num: int, audit_data: Dict[str, Any]) -> None:
        """Save audit report for chapter."""
        audit_file = self.get_chapter_audit_file(chapter_num)
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2, ensure_ascii=False)

    def get_chapter(self, chapter_num: int) -> Optional[str]:
        """Read chapter markdown text."""
        chap_file = self.get_chapter_file(chapter_num)
        if chap_file.exists():
            with open(chap_file, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def get_chapter_beats(self, chapter_num: int) -> Optional[List[Dict[str, Any]]]:
        """Read chapter beats."""
        beats_file = self.get_chapter_beats_file(chapter_num)
        if beats_file.exists():
            with open(beats_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def get_chapter_audit(self, chapter_num: int) -> Optional[Dict[str, Any]]:
        """Read chapter audit."""
        audit_file = self.get_chapter_audit_file(chapter_num)
        if audit_file.exists():
            with open(audit_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_drafted_chapters(self) -> List[int]:
        """Return list of chapter numbers that have been drafted."""
        numbers = []
        for file in sorted(self.chapters_dir.glob("chapter_*.md")):
            m = re.match(r"chapter_(\d+)\.md", file.name)
            if m:
                numbers.append(int(m.group(1)))
        return sorted(numbers)

    def get_continuity_summary(self, up_to_chapter: Optional[int] = None) -> str:
        """Generate a compact summary of prior chapters to feed into prompt context."""
        drafted = self.list_drafted_chapters()
        if up_to_chapter is not None:
            drafted = [num for num in drafted if num < up_to_chapter]

        if not drafted:
            return "Belum ada bab sebelumnya. Ini adalah bab pertama."

        summary_lines = []
        outline_chapters = {
            ch.get("chapter_number"): ch.get("title", f"Bab {ch.get('chapter_number')}")
            for ch in self.outline.get("chapters", [])
        }

        for num in drafted:
            title = outline_chapters.get(num, f"Bab {num}")
            text = self.get_chapter(num) or ""
            # Take last ~400 words or a summary to capture recent events
            words = text.split()
            last_snippet = " ".join(words[-200:]) if len(words) > 200 else text
            summary_lines.append(f"### {title} (Bab {num})")
            summary_lines.append(f"Perkembangan penting / Cuplikan akhir bab:\n...{last_snippet}...\n")

        return "\n".join(summary_lines)


class ProjectManager:
    """Manages finding, listing, and creating novel projects."""

    @staticmethod
    def list_projects() -> List[Dict[str, Any]]:
        """List all existing novel projects."""
        projects = []
        if not config.PROJECTS_DIR.exists():
            return projects

        for item in sorted(config.PROJECTS_DIR.iterdir()):
            if item.is_dir() and (item / "metadata.json").exists():
                try:
                    with open(item / "metadata.json", "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["slug"] = item.name
                    meta["path"] = str(item)
                    projects.append(meta)
                except Exception:
                    pass
        return projects

    @staticmethod
    def create_project(
        title: str,
        author: str,
        genre: str,
        tone: str,
        premise: str,
        target_audience: str = "Dewasa / Bebas Tanpa Sensor (Uncensored)",
        language: str = "Indonesian",
        target_chapters: int = 15,
        target_words_per_chapter: int = 2000,
    ) -> NovelProject:
        """Create a new novel project on disk."""
        slug = slugify(title)
        project_dir = config.PROJECTS_DIR / slug

        # If slug exists, add counter
        counter = 1
        original_dir = project_dir
        while project_dir.exists():
            project_dir = config.PROJECTS_DIR / f"{original_dir.name}_{counter}"
            counter += 1

        project_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now().isoformat()
        metadata = {
            "title": title,
            "slug": project_dir.name,
            "author": author or "Anonymous",
            "genre": genre,
            "tone": tone,
            "premise": premise,
            "target_audience": target_audience,
            "language": language,
            "target_chapters": target_chapters,
            "target_words_per_chapter": target_words_per_chapter,
            "created_at": now,
            "updated_at": now,
            "stage": "created",
        }

        with open(project_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return NovelProject(project_dir)

    @staticmethod
    def load_project(slug: str) -> NovelProject:
        """Load an existing project by slug name."""
        project_dir = config.PROJECTS_DIR / slug
        if not project_dir.exists():
            raise FileNotFoundError(f"Proyek '{slug}' tidak ditemukan.")
        return NovelProject(project_dir)

    @staticmethod
    def delete_project(slug: str) -> bool:
        """Delete a novel project directory permanently from disk."""
        import shutil
        project_dir = config.PROJECTS_DIR / slug
        if project_dir.exists() and project_dir.is_dir():
            shutil.rmtree(project_dir)
            return True
        return False
