# 📸 Memories Vault Organizer & Cleaner

A high-performance, privacy-first, offline media management system engineered to organize, deduplicate, curate, and browse massive personal photo and video archives (95,000+ files across 15+ years) on external SSDs and local drives.

---

## 🌟 Overview

Personal photo collections often grow into sprawling, unorganized dumps spread across phones, backup hard drives, and cloud exports. **Memories Vault Organizer** solves this with a two-part suite:

1. **🚀 Native Web Organizer (`cleaner_server.py` + `cleaner_ui.html`)**: An ultra-responsive local web application inspired by Apple Photos, designed for lightning-fast browsing, multi-select triage, Canon RAW previewing, and non-destructive folder organization.
2. **⚡ Batch Ingestion & Geocoding Engine (`ssd-organizer`)**: A high-speed CLI tool that ingests raw backups, performs offline reverse-geocoding, eliminates exact duplicates via SHA-256 hashing, and structures files into standardized `YYYY/YYYY-MM_Month_City_Country` archives.
3. **🔄 Vault Synchronization & Ingestion Pipeline**: Dedicated scripts for syncing external hard drives, importing Apple Photos libraries, and restructuring folder trees safely.

---

## 🏗️ Architecture

```
memories-organizer/
├── tools/
│   ├── mac-native-organizer/             # Local Web Organizer & Triage App
│   │   ├── cleaner_server.py             # Multi-threaded Python HTTP backend
│   │   ├── cleaner_ui.html               # Responsive Apple Photos-style web UI
│   │   ├── launch_cleaner.command        # 1-click macOS desktop launcher
│   │   ├── sync_hd_to_ssd.py             # 3-stage HD-to-SSD master consolidator
│   │   ├── ingest_photoslibrary.py       # Apple Photos .photoslibrary importer
│   │   ├── restructure_vault.py          # Year/Month/Trip hierarchy standardizer
│   │   ├── refine_vault.py               # Deep subfolder reorganization
│   │   └── organize_mac.py               # Local Mac media classifier
│   └── ssd-organizer/                    # TypeScript CLI for batch ingestion
│       ├── src/                          # TypeScript source code
│       ├── dist/                         # Compiled JavaScript CLI executable
│       ├── package.json                  # Node.js dependencies
│       └── README.md                     # CLI documentation
├── .gitignore                            # Repository ignore rules
├── SPECIFICATION.md                      # Detailed technical specification
└── README.md                             # Project overview & guide
```

---

## ✨ Key Capabilities

### 1. Apple Photos-Inspired Web Interface
- **Zero Framework Overhead**: Built with pure vanilla JavaScript, modern CSS Grid/Flexbox, and native browser APIs.
- **Glassmorphic Dark UI**: Translucent navigation bars, blurred floating docks, smooth zoom scaling, and iOS-native styling.
- **Infinite Virtualized Scroll**: Renders media in non-blocking slices of 36 items, ensuring silky 60fps scrolling across 10,000+ items per folder.
- **Media Type Filter**: Instant 0ms client-side switching between **📸 Photos**, **🎬 Videos**, and **📂 All Media** with live count badges.

### 2. Cool & Low-Power Processing
- **Apple Silicon Efficiency Cores**: Image operations and subprocesses are reniced (`nice -n 15`) to run cool and silent on low-power efficiency cores.
- **Hardware-Throttled Semaphore**: Concurrency is strictly clamped to a 2-worker semaphore, preventing CPU fan noise and thermal throttling.
- **Pure-Python RAW Previews**: Extracts full-resolution camera JPEGs embedded in Canon `.CR2`, `.CR3`, and `.DNG` sensor files directly from raw file bytes in ~0.04s, avoiding heavy multi-second raw debayering.
- **In-Memory Stat Caching**: Avoids thousands of repetitive filesystem `stat()` calls, slashing directory load times from seconds to under 0.05s.

### 3. Dynamic Album Discovery & Folder Organization
- **Smart Top-Level Discovery**: Automatically discovers both Year archives (`2009`-`2026`) and user-created custom albums (`👶 Ishanvi`, `💍 Marriage`, `✈️ Trips`, `🇮🇳 India`, `🎡 London Events`, `🐶 Popcorn`, `👨‍👩‍👧 Family`).
- **Dynamic Vault-Wide Search**: The "Move To..." modal (`M`) indexes 480+ directories and subdirectories across the entire vault.
- **On-the-Fly Folder Creation**: Create new folders or subfolders directly from the UI, with or without items selected.
- **1-Click Folder Jumps**: Toast notifications include an **`[ Open <Folder> → ]`** button to immediately jump to the newly organized folder.

### 4. Advanced Selection & Triage System
- **Marquee Drag-to-Select**: Click-and-drag a rubber-band selection box over the photo grid to select dozens of photos in one motion.
- **Shift + Click Range**: Select contiguous ranges between any two photos.
- **Full Triage Keyboard Shortcuts**:
  - `I` — Instant move to `Ishanvi` album
  - `M` — Open "Move To..." modal with folder picker & search
  - `D` or `Delete` — Stage selected photos into Trash
  - `Z` or `U` — Instant Undo (restores trashed or moved items)
  - `Space` — Open Fullscreen Lightbox preview
  - `Arrow Left` / `Arrow Right` — Navigate lightbox
  - `Cmd + A` — Select all rendered photos
  - `Esc` — Deselect all or exit lightbox / modal

### 5. 100% Non-Destructive Safety
- Trashed items are never permanently deleted from disk; they are staged into `_Review_Trash/`.
- Every trash and move operation is tracked in an in-memory `UNDO_HISTORY` stack, allowing instant one-key reversal (`Z`).
- The Trash folder can be audited directly from the top bar before emptying.

---

## 🚀 Quick Start

### Prerequisites
- macOS 11.0+ (Tested on macOS Sequoia / Apple Silicon & Intel)
- Python 3.9+ (Installed via Anaconda, Homebrew, or macOS Command Line Tools)
- Node.js 18+ (Only required if running the `ssd-organizer` CLI tool)

### Starting the Web Organizer
From the repository root, run:
```bash
python3 tools/mac-native-organizer/cleaner_server.py
```
Or double-click the desktop launcher:
```bash
./tools/mac-native-organizer/launch_cleaner.command
```
The server will start locally and automatically open your default browser to:
**`http://localhost:8888`**

### Running the Batch Ingestion CLI
To ingest and deduplicate external folders into the master vault:
```bash
node tools/ssd-organizer/dist/index.js \
  -i "/Volumes/Backup_Drive/Photos" \
  -o "/Volumes/DIVAKSHSSD/Organized_Memories" \
  --execute
```

---

## ⌨️ Keyboard Shortcuts Reference

| Shortcut | Context | Action |
| :--- | :--- | :--- |
| `Click + Drag` | Grid View | Rubber-band marquee drag selection |
| `Shift + Click` | Grid View | Select contiguous range of photos |
| `Cmd + A` | Grid View | Select all rendered photos |
| `Esc` | Anywhere | Deselect all / Close Lightbox / Close Modal |
| `Space` | Grid View | Open highlighted photo in Fullscreen Lightbox |
| `→` / `L` | Lightbox | Next photo / video |
| `←` / `H` | Lightbox | Previous photo / video |
| `I` | Grid or Lightbox | Move selected / current photo to **Ishanvi** |
| `M` | Grid or Lightbox | Open **Move To...** modal |
| `D` / `Backspace` | Grid or Lightbox | Move to **_Review_Trash** |
| `Z` / `U` | Grid or Lightbox | **Undo** last move or trash action |

---

## 📁 Vault Directory Structure

```text
/Volumes/DIVAKSHSSD/Organized_Memories/
├── Ishanvi/                     # Curated album (Album, Namkaran, UK, etc.)
├── Marriage/                    # Curated / custom album
├── Trips/                       # Trips album (International, UK, etc.)
├── India/                       # Regional trips & family events
├── Events_London/               # London festivals & excursions
├── Popcorn/                     # Pet memories
├── 2026/                        # Chronological Year Archive
│   ├── 2026-01_January/
│   └── 2026-02_February_Trip/
├── 2025/
├── 2024/
│   └── ...
├── 2009/
├── _Review_Trash/               # Staged safety trash (can be reviewed/restored)
└── .cleaner_cache/              # Low-power hardware thumbnail caches
    ├── thumbs/                  # 360px grid thumbnails
    └── previews/                # 1920px high-resolution RAW previews
```

---

## 🛡️ License

Private repository for personal media preservation and vault management.
