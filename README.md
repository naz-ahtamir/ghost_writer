# 🖋️ GhostWriter: AI Multi-Agent Novel Writing Engine

**GhostWriter** adalah sistem kecerdasan buatan berbasis *Multi-Agent Architecture* yang dirancang khusus untuk membantu penulis menyusun novel bergenre apa pun—dari tahap pematangan ide premis, perancangan dunia (*worldbuilding*), pengembangan karakter mendalam (*character bible*), penyusunan *plot beat-by-beat*, penulisan prosa bab sastra (*prose drafting*), hingga audit kontinuitas dan ekspor naskah ke **Word (.docx)** dan **Markdown**.

Didukung oleh model **Google Gemini** (Gemini 2.5 Flash / Gemini 1.5 Pro) dengan jendela konteks raksasa (1M+ token) untuk menjaga ingatan plot dan konsistensi cerita secara sempurna tanpa amnesia.

---

## 👥 Tim AI Agen Kreatif (Multi-Agent Team)

1. **🏛️ Architect Agent (Worldbuilder & Lore Engine)**
   - Merancang latar dunia, atmosfer visual & cuaca, aturan sistem sihir/teknologi, tatanan faksi, dan sejarah masa lalu yang memicu konflik.
2. **👤 Character Master Agent (Psikologi Tokoh)**
   - Menyusun profil karakter 3 dimensi: penampilan fisik, motivasi batin (*internal need*), tujuan konkret (*external goal*), luka masa lalu (*fatal flaw*), serta gaya dialog/bicara unik.
3. **🗺️ Plot Outliner Agent (Struktur Naratif)**
   - Merancang alur cerita makro dengan struktur babak (*Three-Act Structure*) dan membagi cerita menjadi bab-bab dengan *turning point* yang memikat.
4. **📋 Scene Planner Agent (Micro-beats Planner)**
   - Memecah setiap bab menjadi 3-5 ketukan adegan (*scene beats*) agar ritme penceritaan terjaga dan tidak membosankan.
5. **✍️ Prose Writer Agent (Novelist Maestro)**
   - Menulis prosa bab demi bab dengan prinsip *Show, Don't Tell*, fokus detail panca indera, dialog berbobot, dan pacing yang hidup.
6. **🔍 Continuity & Style Editor Agent (Kritikus & Editor)**
   - Mengevaluasi draf naskah, mendeteksi *plothole* atau inkonsistensi fakta, memberi skor kualitas (1-100), dan dapat merevisi naskah secara otomatis berdasarkan arahan penulis.
7. **📦 Novel Exporter**
   - Mengompilasi seluruh bab yang telah selesai menjadi satu manuskrip utuh siap baca atau siap kirim ke penerbit dalam format **Markdown (.md)** dan **Microsoft Word (.docx)** berformat standar buku.

---

## 🚀 Persyaratan Sistem & Instalasi

Proyek ini telah dikonfigurasi dan siap dijalankan dengan **Python 3.11+**.

Semua dependensi utama (`rich`, `google-genai`, `python-docx`, `pydantic`, `python-dotenv`) sudah terpasang. Jika ingin memasang ulang:

```bash
pip install -r requirements.txt
```

---

## 🔑 Konfigurasi Gemini API Key

GhostWriter menggunakan model **Google Gemini** yang dapat diperoleh secara gratis:
1. Dapatkan API Key di [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Anda dapat langsung memasukkan API Key saat aplikasi dijalankan, atau memasukkannya ke dalam file `.env`:

```env
GEMINI_API_KEY=AIzaSy...your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
NOVEL_DEFAULT_LANGUAGE=Indonesian
```

> **Model yang Didukung:**
> - `gemini-2.5-flash` (Rekomendasi utama: sangat cepat, cerdas, dan efisien)
> - `gemini-2.0-flash`
> - `gemini-1.5-flash`
> - `gemini-1.5-pro` (Untuk kedalaman sastra dan analisis narasi sangat kompleks)

---

## 📖 Cara Menjalankan Aplikasi

Jalankan perintah berikut di terminal:

```bash
python main.py
```

### Navigasi Menu Interaktif:
```
=== MENU UTAMA GHOSTWRITER ===
  1. 🌟 Buat Proyek Novel Baru (Wizard Multi-Agen)
  2. 📂 Buka Proyek Novel yang Ada
  3. ✍️ Tulis / Lanjutkan Bab (Scene Planner + Prose Writer)
  4. 🔍 Audit & Edit Bab (Continuity & Style Editor)
  5. 📖 Baca Naskah Bab di Terminal
  6. 👥 Lihat Karakter & World Bible
  7. 📦 Export Novel (Markdown & Word .docx)
  8. ⚙️ Pengaturan API Key & Model
  9. 🚪 Keluar
```

---

## 📁 Struktur Penyimpanan Proyek

Setiap novel disimpan dalam folder tersendiri di dalam direktori `projects/`:

```
projects/
└── cakrawala_yang_hilang/
    ├── metadata.json           # Informasi judul, genre, penulis, target bab
    ├── world_bible.json        # Latar, aturan dunia, lore sejarah
    ├── characters.json         # Karakter, motivasi, flaw, gaya bicara
    ├── outline.json            # Sinopsis umum, babak, dan outline bab
    ├── chapters/
    │   ├── chapter_01.md       # Naskah prosa Bab 1
    │   ├── chapter_01_beats.json # Ketukan adegan Bab 1
    │   └── chapter_01_audit.json # Laporan audit dan review editor
    └── exports/
        ├── cakrawala_yang_hilang.md    # Naskah utuh gabungan Markdown
        └── cakrawala_yang_hilang.docx  # Manuskrip siap cetak Microsoft Word
```

Progres Anda tersimpan secara lokal dan otomatis, sehingga Anda dapat berhenti dan melanjutkan penulisan kapan saja.

---

## 🧪 Menjalankan Pengujian (Unit Tests)

Untuk memverifikasi fungsi penyimpanan dan ekspor dokumen:

```bash
python -m pytest tests/test_novel_system.py
```
