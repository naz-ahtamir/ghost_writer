# 🖋️ GhostWriter: AI Multi-Agent Novel Writing Engine

**GhostWriter** is a comprehensive artificial intelligence novel-writing engine built on a **Multi-Agent Architecture**. Designed specifically for authors and storytellers, it assists across the entire creative lifecycle—from brainstorming premise ideas and adapting non-fiction articles/documents, to worldbuilding (*world bible*), deep character psychology & visual DNA (*character bible*), scene-by-scene beat planning, literary prose drafting (*Show, Don't Tell*), continuity auditing, consistent photorealistic DSLR chapter illustrations (FLUX.1 Realism), and publication-ready multi-format compilation into **Interactive HTML E-Book Reader**, **Microsoft Word (.docx)** with embedded images, and **Markdown (.md)**.

Powered by premier models: **xAI Grok** for rich literary depth and nuanced prose, alongside **Google Gemini** (Gemini 2.5 Flash / Gemini 1.5 Pro) with ultra-large context windows to preserve long-term plot continuity without amnesia.

---

## 👥 Creative AI Multi-Agent Team

1. **🏛️ Architect Agent (Worldbuilder & Lore Engine)**
   - Constructs deep world lore, sensory atmospheres, magic/technology systems, faction hierarchies, cultural history, and geopolitical tensions.
2. **👤 Character Master Agent (Character Psychology & Visual Bible)**
   - Crafts 3-dimensional character profiles: internal needs, external goals, fatal flaws, distinctive voice/dialogue style, and locks in immutable physical visual DNA (eye color, facial structure, hairstyles, signature wardrobe, distinctive scars).
3. **🗺️ Plot Outliner Agent (Narrative Architecture)**
   - Formulates macro narrative arcs using the classic Three-Act Structure, breaking the saga into compelling chapters with distinct turning points and emotional hooks.
4. **📋 Scene Planner Agent (Micro-beats Planner)**
   - Deconstructs each chapter into 3–5 narrative beats (*scene beats*), balancing sensory details, escalating conflict, and pacing rhythm.
5. **✍️ Prose Writer Agent (Novelist Maestro)**
   - Writes chapter prose beat-by-beat utilizing strict *Show, Don't Tell* principles, deep sensory immersion, authentic dialogue, and gripping emotional pacing.
6. **🔍 Continuity & Style Editor Agent (Critic & Revisor)**
   - Evaluates drafts against world lore, identifies plot holes and factual inconsistencies, grades manuscript quality (1–100), and auto-revises prose according to editorial feedback.
7. **🎨 Illustrator Agent (FLUX.1 DSLR Realism & Visual Bible DNA Lock)**
   - Extracts 3 key cinematic scene moments per chapter (Opening, Midpoint confrontation, Climax) and renders photorealistic DSLR-grade illustrations (35mm/50mm prime lenses, f/4–f/5.6), showcasing dynamic physical poses, emotional expressions, and rich environmental backgrounds without arbitrary censorship.
8. **📦 Novel Exporter**
   - Compiles all drafted chapters and rendered illustrations into a single ready-to-read manuscript in **Microsoft Word (.docx)** with natively embedded JPEG imagery, **Interactive HTML E-Book Reader** (100% offline with Base64 images), and clean **Markdown (.md)**.

---

## 🎨 Realistic & Uncensored Chapter Illustrations

GhostWriter features an advanced multi-provider illustration pipeline:
- **3 Illustrations per Chapter:** Strategic placement at the Opening, Midpoint turning point, and Chapter Climax.
- **Visual Consistency (Visual Bible DNA Lock):** Key characters maintain identical facial traits, ethnicity, eye color, hairstyle, and attire across all chapters.
- **DSLR Photographic Framing:** Dynamic full-body poses, physical interactions, and deep background environments mimicking real 35mm/50mm camera captures (preventing excessive blurry close-up headshots).
- **Anti-Refusal & Anti-Censorship Adaptation:** Automatically adapts sensitive/intense scene prompts into evocative artistic descriptions to ensure reliable rendering without losing narrative intent.
- **Universal Word & Browser Compatibility:** Automatic on-the-fly conversion to standard RGB JPEG (via Pillow, ffmpeg, or proxy fallback) to guarantee flawless display in Microsoft Word, WPS Office, and mobile browsers.

---

## ⚡ xAI Grok Token Efficiency & Prompt Caching

GhostWriter includes advanced token optimization tailored for the **xAI Grok** engine:

1. **200k Context Boundary Guard (`prompt_tokens`):**
   - Telemetry tracks `prompt_tokens` on every API response.
   - If context approaches or exceeds 200k (alert threshold $\ge$ 160k tokens), the system issues warnings, performs intelligent middle-text pruning (*smart context pruning*) to keep system prompts and current beats intact, and enforces `reasoning_effort="low"` to reduce output tokens.
2. **Sticky Routing & Prompt Cache Hit (`x-grok-conv-id` & `reasoning_content`):**
   - Every novel project is bound to a consistent HTTP header: `x-grok-conv-id: gw-proj-<slug>`, ensuring consecutive requests route to the exact same xAI GPU server node where the prefix KV cache resides.
   - Real-time `cached_tokens` monitoring reports cache hit rates (saving up to 80%+ in costs and latency).
   - Preserves `reasoning_content` in assistant message history so the server-side KV cache prefix is never broken across turns.
3. **Explicit Low Reasoning Effort (`reasoning_effort: low`):**
   - Structured JSON workflows (worldbuilding, character generation, scene outline, beats planning) explicitly invoke `reasoning_effort="low"`, saving hundreds to thousands of reasoning output tokens per request.
   - Can be toggled (`low`, `medium`, `high`) in **Menu 9: AI Settings**.

---

## 🚀 System Requirements & Installation

GhostWriter runs on **Python 3.10+**.

Install all required dependencies:

```bash
pip install -r requirements.txt
```

### 📱 Android (Termux) Guide

GhostWriter is purpose-built and optimized for running on Android via Termux:

1. **Grant Storage Permission:**
   Run this command once so GhostWriter can write exported manuscripts directly to your public storage:
   ```bash
   termux-setup-storage
   ```
   All exported manuscripts and rendered illustrations are automatically copied to:  
   `/sdcard/Download/GhostWriter/<novel-slug>/`  
   (Accessible immediately from your phone's File Manager, Gallery, WPS Office, or Microsoft Word).

2. **Recommended Termux Packages:**
   ```bash
   pkg install termux-tools termux-api ffmpeg
   ```
   - `termux-open`: Directly opens DOCX manuscripts and HTML readers in your native Android apps without `file://` URI permission errors.
   - `termux-wake-lock`: Keeps the local background reader HTTP server active when switching to Chrome.
   - `ffmpeg`: Enables high-speed CLI conversion of illustration images into standard JPEG format.

---

## 🔑 API Key Configuration (Grok & Gemini)

GhostWriter supports two premier AI providers:
1. **xAI Grok (Prioritized):** Obtain your API key at [xAI Console](https://console.x.ai).
2. **Google Gemini (Free Tier Available):** Obtain your API key at [Google AI Studio](https://aistudio.google.com/app/apikey).

Configure your keys interactively within the application menu or define them in a `.env` file:

```env
AI_PROVIDER=grok
GROK_API_KEY=xai-...
GROK_MODEL=grok-3
GROK_REASONING_EFFORT=low
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash
NOVEL_DEFAULT_LANGUAGE=Indonesian
```

---

## 📖 How to Run GhostWriter

Launch the interactive CLI:

```bash
python main.py
```

### Interactive Menu Overview:
```
=== GHOSTWRITER MAIN MENU ===
  1. 🌟 Create New Novel Project (Interactive Wizard / File Import)
  2. 📂 Open & Manage Novel Projects (Open / Delete)
  3. ✍️ Write / Continue Chapter (Scene Planner + Prose Writer)
  4. 🎨 Generate & Manage Chapter Illustrations (3 Consistent DSLR Illustrations)
  5. 🔍 Audit & Edit Chapter (Continuity & Style Editor)
  6. 📖 Read Chapter in Terminal
  7. 👥 View & Manage Characters, World Bible, & Outline
  8. 📦 Export Novel + Illustrations (HTML Reader, Word .docx, & Markdown)
  9. ⚙️ AI Settings (Grok / Gemini / Reasoning Effort / Image Engine)
  10. 🚪 Exit
```

---

## 📁 Project Directory Structure

Every novel project is saved locally in its dedicated directory under `projects/`:

```
projects/
└── novel_title/
    ├── metadata.json           # Title, genre, premise, target chapters
    ├── world_bible.json        # Setting lore, rules, atmosphere, history
    ├── characters.json         # Character profiles, visual DNA, goals, flaws
    ├── outline.json            # Act structure, chapter outlines, and turning points
    ├── chapters/
    │   ├── chapter_01.md       # Prose manuscript for Chapter 1
    │   ├── chapter_01_beats.json
    │   └── chapter_01_audit.json
    ├── illustrations/
    │   ├── chapter_01_illustrations.json  # Scene illustration blueprints & prompts
    │   ├── chapter_01_illus_01.jpg        # Scene 1: Opening
    │   ├── chapter_01_illus_02.jpg        # Scene 2: Midpoint
    │   └── chapter_01_illus_03.jpg        # Scene 3: Climax
    └── exports/
        ├── novel_title.html    # Interactive Illustrated E-Book Web Reader
        ├── novel_title.docx    # Microsoft Word manuscript with embedded JPEGs
        └── novel_title.md      # Consolidated full-manuscript Markdown
```

---

## 🧪 Running Unit Tests

To verify all system subsystems (project lifecycle, planning, prose generation, FLUX.1 prompts, JPEG normalization, Grok token efficiency, and multi-format exports):

```bash
python tests/test_novel_system.py
```
