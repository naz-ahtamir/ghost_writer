# 🖋️ GhostWriter: AI Multi-Agent Novel Writing Engine

**GhostWriter** adalah sistem kecerdasan buatan berbasis *Multi-Agent Architecture* yang dirancang khusus untuk membantu penulis menyusun novel bergenre apa pun—dari tahap pematangan ide premis atau adaptasi artikel/dokumen, perancangan dunia (*worldbuilding*), pengembangan karakter mendalam (*character bible*), penyusunan alur adegan (*plot beats*), penulisan prosa bab sastra (*prose drafting*), evaluasi audit kontinuitas, pembuatan ilustrasi bab fotorealistik konsisten (FLUX.1 DSLR Realism), hingga ekspor naskah ke **HTML Visual Reader**, **Word (.docx)** dengan gambar tertanam, dan **Markdown (.md)**.

Didukung oleh model pilihan: **xAI Grok** untuk sastra & prosa mendalam serta **Google Gemini** (Gemini 2.5 Flash / Gemini 1.5 Pro) dengan jendela konteks raksasa untuk menjaga memori plot secara sempurna.

---

## 👥 Tim AI Agen Kreatif (Multi-Agent Team)

1. **🏛️ Architect Agent (Worldbuilder & Lore Engine)**
   - Merancang latar dunia, atmosfer visual, aturan sistem sihir/teknologi, tatanan faksi, dan sejarah masa lalu yang memicu konflik.
2. **👤 Character Master Agent (Psikologi Tokoh & Visual Bible)**
   - Menyusun profil karakter 3 dimensi: penampilan fisik spesifik, motivasi batin (*internal need*), tujuan konkret (*external goal*), luka masa lalu (*fatal flaw*), serta gaya dialog/bicara unik. Mengunci fitur DNA visual (warna mata, bentuk wajah, pakaian khas, bekas luka).
3. **🗺️ Plot Outliner Agent (Struktur Naratif)**
   - Merancang alur cerita makro dengan struktur babak (*Three-Act Structure*) dan membagi cerita menjadi bab-bab dengan *turning point* yang memikat.
4. **📋 Scene Planner Agent (Micro-beats Planner)**
   - Memecah setiap bab menjadi 3-5 ketukan adegan (*scene beats*) agar ritme penceritaan terjaga dan dinamis.
5. **✍️ Prose Writer Agent (Novelist Maestro)**
   - Menulis prosa bab demi bab dengan prinsip *Show, Don't Tell*, fokus detail panca indera, dialog berbobot, dan pacing yang hidup.
6. **🔍 Continuity & Style Editor Agent (Kritikus & Editor)**
   - Mengevaluasi draf naskah, mendeteksi *plothole* atau inkonsistensi fakta, memberi skor kualitas (1-100), dan merevisi naskah secara otomatis.
7. **🎨 Illustrator Agent (FLUX.1 DSLR Realism & Visual Bible DNA Lock)**
   - Mengambil 3 momen adegan kunci per bab (Awal, Tengah, Klimaks) dan merender ilustrasi fotorealistik standar lensa kamera DSLR (35mm/50mm, f/4-f/5.6), memperlihatkan pose tubuh dinamis dan latar lingkungan detail tanpa sensor berlebih.
8. **📦 Novel Exporter**
   - Mengompilasi seluruh bab dan ilustrasi menjadi manuskrip siap cetak Microsoft Word (**DOCX** dengan gambar JPEG asli tertanam), **Illustrated HTML Reader** interaktif offline, dan naskah **Markdown (.md)**.

---

## 🎨 Fitur Ilustrasi Bab Realistis & Bebas Sensor

GhostWriter dilengkapi engine ilustrasi bab canggih:
- **3 Ilustrasi per Bab:** Momen pembuka, titik tengah (konfrontasi/momen emosional), dan klimaks bab.
- **Konsistensi Visual (Visual Bible Lock):** Karakter utama mempertahankan wajah, etnis, warna mata, gaya rambut, dan pakaian yang konsisten antar-bab.
- **Framing DSLR Realistis:** Pose tubuh dinamis, interaksi fisik, dan latar belakang kaya detail seperti jepretan kamera sungguhan (menghindari foto kepala *close-up blur* berlebih).
- **Anti-Refusal & Anti-Censor:** Prompt adegan intens/sensitif diadaptasi otomatis agar diterima oleh AI image generator tanpa membatalkan konteks artistik adegan.
- **Kompatibilitas Penuh Word & Browser:** Konversi otomatis ke JPEG standar RGB (via Pillow / ffmpeg / proxy) agar gambar tidak rusak atau hilang saat dibuka di Microsoft Word maupun browser HP.

---

## 🚀 Persyaratan Sistem & Instalasi

Proyek ini siap dijalankan dengan **Python 3.10+**.

Pasang semua dependensi:

```bash
pip install -r requirements.txt
```

### 📱 Panduan Khusus Pengguna Android (Termux)

GhostWriter dioptimalkan secara khusus agar nyaman digunakan di Android Termux:

1. **Akses Penyimpanan Eksternal:**
   Jalankan perintah ini sekali agar GhostWriter dapat menyalin hasil ekspor langsung ke folder publik HP Anda:
   ```bash
   termux-setup-storage
   ```
   Hasil ekspor dan ilustrasi akan otomatis tersedia di:  
   `/sdcard/Download/GhostWriter/<nama-novel>/`  
   (bisa dibuka langsung lewat aplikasi File Manager, Galeri, WPS Office, atau Microsoft Word).

2. **Paket Pendukung Termux (Sangat Disarankan):**
   ```bash
   pkg install termux-tools termux-api ffmpeg
   ```
   - `termux-open`: Membuka file naskah Word (.docx) atau HTML Reader langsung ke aplikasi Android terkait tanpa error izin `file://`.
   - `termux-wake-lock`: Mencegah server reader lokal tertidur saat beralih ke Chrome.
   - `ffmpeg`: Mengonversi gambar ilustrasi menjadi format JPEG berstandar tinggi.

---

## 🔑 Konfigurasi API Key (Grok & Gemini)

GhostWriter mendukung dua provider AI teks utama:
1. **xAI Grok (Prioritas):** Dapatkan API Key di [xAI Console](https://console.x.ai).
2. **Google Gemini (Gratis):** Dapatkan API Key di [Google AI Studio](https://aistudio.google.com/app/apikey).

Anda dapat memasukkan API Key secara interaktif dari menu aplikasi atau menyimpannya di file `.env`:

```env
GROK_API_KEY=xai-...
GROK_MODEL=grok-3
GROK_REASONING_EFFORT=low
GEMINI_API_KEY=AIzaSy...
AI_PROVIDER=grok
NOVEL_DEFAULT_LANGUAGE=Indonesian
```

---

## ⚡ Efisiensi Token & Prompt Caching xAI Grok

GhostWriter dilengkapi optimasi token tingkat lanjut untuk engine **xAI Grok**:

1. **Pemantauan Batas Konteks 200k (`prompt_tokens`):**
   - Telemetri `prompt_tokens` dicatat pada setiap panggilan API.
   - Jika konteks mendekati 200k (threshold $\ge$ 160k token) atau melewatinya, sistem otomatis memberikan peringatan, memangkas riwayat teks bab tengah secara cerdas (*smart context pruning*), dan memaksa *reasoning effort* ke level `low`.
2. **Sticky Routing & Prompt Cache Hit (`x-grok-conv-id` & `reasoning_content`):**
   - Setiap proyek novel diikat ke header konsisten `x-grok-conv-id` (`gw-proj-<nama-novel>`), memastikan request selalu diarahkan ke node server backend yang sama di infrastruktur xAI.
   - Field `cached_tokens` dipantau untuk memastikan cache hit rate tinggi.
   - Jejak `reasoning_content` dari respons asisten otomatis disertakan kembali pada percakapan riwayat agar prefix cache xAI tidak terputus.
3. **Pengurangan Intensitas Penalaran (`reasoning_effort: low`):**
   - Secara default disetel ke `low` untuk tugas-tugas pemformatan JSON, perancangan karakter, worldbuilding, dan outline bab.
   - Menghemat ratusan hingga ribuan *reasoning output tokens* per request tanpa mengurangi kualitas sastra.
   - Dapat diatur kapan saja di **Menu 9: Pengaturan AI**.

---

## 📖 Cara Menjalankan Aplikasi

Jalankan perintah berikut di terminal:

```bash
python main.py
```

### Navigasi Menu Interaktif:
```
=== MENU UTAMA GHOSTWRITER ===
  1. 🌟 Buat Proyek Novel Baru (Ide Manual / Upload File Artikel)
  2. 📂 Buka & Kelola Proyek Novel (Buka / Hapus)
  3. ✍️ Tulis / Lanjutkan Bab (Scene Planner + Prose Writer)
  4. 🎨 Buat & Kelola Ilustrasi Bab (3 Ilustrasi Realistis, Konsisten & Tanpa Sensor)
  5. 🔍 Audit & Edit Bab (Continuity & Style Editor)
  6. 📖 Baca Naskah Bab di Terminal
  7. 👥 Lihat & Kelola Karakter, World Bible, & Outline
  8. 📦 Export Novel + Ilustrasi (HTML Reader, Word .docx, & Markdown)
  9. ⚙️ Pengaturan AI (Grok / Gemini / Engine Ilustrasi)
  10. 🚪 Keluar
```

---

## 📁 Struktur Penyimpanan Proyek

Setiap novel disimpan dalam folder tersendiri di dalam direktori `projects/`:

```
projects/
└── judul_novel/
    ├── metadata.json           # Judul, genre, premis, target bab
    ├── world_bible.json        # Latar, atmosfer, aturan dunia, lore sejarah
    ├── characters.json         # Karakter, DNA visual, motivasi, flaw
    ├── outline.json            # Struktur babak dan rencana bab
    ├── chapters/
    │   ├── chapter_01.md       # Naskah prosa Bab 1
    │   ├── chapter_01_beats.json
    │   └── chapter_01_audit.json
    ├── illustrations/
    │   ├── chapter_01_illustrations.json  # Rencana prompt ilustrasi
    │   ├── chapter_01_illus_01.jpg        # Foto adegan 1 (Awal)
    │   ├── chapter_01_illus_02.jpg        # Foto adegan 2 (Tengah)
    │   └── chapter_01_illus_03.jpg        # Foto adegan 3 (Klimaks)
    └── exports/
        ├── judul_novel.html    # E-Book Web Reader interaktif + gambar offline
        ├── judul_novel.docx    # Dokumen Word dengan gambar tertanam
        └── judul_novel.md      # Naskah utuh gabungan Markdown
```

---

## 🧪 Menjalankan Pengujian (Unit Tests)

Untuk memverifikasi seluruh komponen (manajemen proyek, planner, prompt ilustrasi DSLR, konversi JPEG, dan ekspor dokumen):

```bash
python tests/test_novel_system.py
```
