# ⚡ SSD Memory Ingestion & Organizer Tool

A high-performance Mac CLI tool specifically engineered to process large external SSD backups (e.g. 700GB+ of photos and videos), intelligently sort them into **Year / Month / Location** folders, eliminate duplicate files, and generate an interactive visual HTML report.

---

## 🌟 Key Features

- **🚀 Ultra-Fast SSD Processing**: Runs directly on your Mac, scanning and analyzing thousands of photos per minute at hardware bus speeds.
- **📍 Offline Reverse Geocoding**: Automatically turns GPS coordinates into human-readable city and country folders (e.g., `2023-08_August_Paris_France` or `2024-02_February_Tokyo_Japan`) without requiring an internet connection or getting throttled by API limits.
- **👯 3-Stage Fast Deduplicator**:
  1. *Byte-size filter* (filters 90% of unique files without reading disk)
  2. *64 KB header check* (filters false size collisions)
  3. *Full SHA-256 verification* (detects exact duplicates with 100% mathematical precision).
- **🛡️ 100% Safe (Dry-Run by Default)**: Always simulates the run first, showing you counts, sizes, and previews before touching a single byte.
- **📁 Safe Copy Mode**: Uses non-destructive `copy` by default, leaving your original SSD backup completely intact.
- **📊 Interactive Visual Report**: Produces an `organize_summary.html` report with interactive charts, monthly timelines, and duplicate audits that opens in Safari or Chrome.

---

## 🛠️ How to Find Your SSD Path on Mac

1. Plug your SSD into your Mac.
2. In your terminal, run:
   ```bash
   ls /Volumes
   ```
   You will see your SSD listed (e.g., `/Volumes/Samsung_T7` or `/Volumes/MyPassport`).
3. Your input path is wherever your photos are located, for example:
   ```text
   /Volumes/Samsung_T7/Phone_Backup
   ```

---

## 🚀 Usage

Navigate to the tool directory:
```bash
cd tools/ssd-organizer
```

### Step 1: Run a Safe Dry-Run Preview across Multiple Folders
You can pass multiple folders simultaneously (e.g. `Akshit`, `Akshit mobile backup`, and `Div`). The tool will crawl all three and find duplicate photos across all of them in a single pass:
```bash
node tools/ssd-organizer/dist/index.js \
  -i "/Volumes/DIVAKSHSSD/Akshit" "/Volumes/DIVAKSHSSD/Akshit mobile backup" "/Volumes/DIVAKSHSSD/Div" \
  -o "/Volumes/DIVAKSHSSD/Organized_Memories"
```

### Step 2: Open the Visual Report
After the preview finishes, open the generated report in Safari:
```bash
open "/Volumes/DIVAKSHSSD/Organized_Memories/organize_summary.html"
```
You can review the detected trip locations, monthly photo counts, and cross-folder duplicates found.

### Step 3: Execute the Organization
When you are satisfied with the preview, add the `--execute` flag:
```bash
node tools/ssd-organizer/dist/index.js \
  -i "/Volumes/DIVAKSHSSD/Akshit" "/Volumes/DIVAKSHSSD/Akshit mobile backup" "/Volumes/DIVAKSHSSD/Div" \
  -o "/Volumes/DIVAKSHSSD/Organized_Memories" \
  --execute
```
*(By default, this **copies** files. If you want to move them instead to save space on the drive, add `-a move`)*.

---

## ⚙️ Command-Line Options

| Option | Description | Default |
| :--- | :--- | :--- |
| `-i, --input <path>` | Path to your unorganized photos on SSD | **Required** |
| `-o, --output <path>` | Destination path for organized memories | **Required** |
| `-e, --execute` | Perform actual copy or move | `false` (Safe dry-run preview) |
| `-a, --action <copy\|move>` | Whether to copy or move files | `copy` |
| `--no-dedup` | Skip duplicate detection | `false` (Deduplication enabled) |
| `--no-geo` | Skip reverse geocoding to city/country | `false` (Geocoding enabled) |
| `--no-report` | Skip generating HTML summary report | `false` (Report enabled) |
| `-v, --verbose` | Show verbose per-file logs | `false` |

---

## 📂 Target Organized Folder Layout

```text
Organized_Memories/
├── 2022/
│   ├── 2022-06_June_London_United_Kingdom/
│   │   ├── 2022-06-12_14-30-05_IMG_1024.heic
│   │   └── 2022-06-12_18-12-40_IMG_1025.heic
│   └── 2022-12_December_New_York_USA/
├── 2023/
│   ├── 2023-07_July_Paris_France/
│   └── 2023-08_August/                 <-- Photos without GPS coordinates
├── _Duplicates/                        <-- Exact duplicates isolated for review
│   └── 2023/
│       └── 2023-08_August/
└── organize_summary.html               <-- Interactive visual report
```
