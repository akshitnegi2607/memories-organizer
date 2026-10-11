#!/usr/bin/env python3
"""
Memories Vault Cleaner & Organizer — iOS Photos Web Server
1. Runs a high-performance local HTTP server on http://localhost:8888 (or 8889).
2. Directly reads & organizes /Volumes/DIVAKSHSSD/Organized_Memories.
3. Native Hardware RAW Support:
   - Decodes Canon .CR2, .CR3, .DNG, .NEF, .ARW using macOS hardware acceleration (sips).
   - Generates 360px grid thumbnails and 1920px high-res lightbox previews on the fly!
4. Full Subfolder Navigation:
   - Trips -> International (Switzerland, France, Mauritius, Thailand...), UK (Scotland, Cornwall...)
   - India -> Lucknow, Pune, Goa, Varanasi, Delhi NCR, Kanpur...
   - Ishanvi -> Album, Namkaran, UK, Welcome...
   - Years (2017-2026) -> Months & Trip Folders
5. Rapid Curation & Moving:
   - Quick 1-Key Move to Ishanvi (hotkey 'I')
   - "Move To..." modal with folder picker & on-the-fly folder creation (hotkey 'M')
   - Batch move of selected photos
6. Safe non-destructive operations with instant Undo (hotkey 'Z').
"""

import os
import sys
import json
import shutil
import urllib.parse
import mimetypes
import webbrowser
import subprocess
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

import threading
import time

VAULT_ROOT = "/Volumes/DIVAKSHSSD/Organized_Memories"
TRASH_ROOT = os.path.join(VAULT_ROOT, "_Review_Trash")
THUMB_CACHE = os.path.join(VAULT_ROOT, ".cleaner_cache", "thumbs")
PREVIEW_CACHE = os.path.join(VAULT_ROOT, ".cleaner_cache", "previews")
RAW_SYMLINKS = "/tmp/cleaner_raw_symlinks"

MEDIA_EXTS = {
    '.jpg', '.jpeg', '.png', '.heic', '.mov', '.mp4', '.m4v',
    '.webp', '.gif', '.cr2', '.cr3', '.dng', '.tif', '.tiff', '.avif',
    '.nef', '.arw'
}

VIDEO_EXTS = {'.mov', '.mp4', '.m4v', '.avi'}
RAW_EXTS = {'.cr2', '.cr3', '.dng', '.nef', '.arw'}

HTML_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleaner_ui.html")

UNDO_HISTORY = []

# Concurrency Throttling: Max 2 thumbnail conversions simultaneously to keep CPU cool and silent
THUMB_SEMAPHORE = threading.Semaphore(2)

# Album & Photos memory cache: Prevents repeated 95,000 file disk scans
ALBUM_CACHE = None
ALBUM_CACHE_TIME = 0
PHOTOS_CACHE = {}

def invalidate_album_cache():
    global ALBUM_CACHE, ALBUM_CACHE_TIME, PHOTOS_CACHE
    ALBUM_CACHE = None
    ALBUM_CACHE_TIME = 0
    PHOTOS_CACHE.clear()

def get_album_list():
    global ALBUM_CACHE, ALBUM_CACHE_TIME
    now = time.time()
    if ALBUM_CACHE is not None and (now - ALBUM_CACHE_TIME < 300):
        return ALBUM_CACHE[0], ALBUM_CACHE[1]

    if not os.path.exists(VAULT_ROOT):
        return [], 0

    albums = []
    
    # Priority & metadata for well-known albums
    KNOWN_ALBUMS = {
        "ishanvi": ("👶", "Ishanvi", 0),
        "marriage": ("💍", "Marriage", 1),
        "wedding": ("💍", "Wedding", 1),
        "trips": ("✈️", "Trips", 2),
        "india": ("🇮🇳", "India", 3),
        "events_london": ("🎡", "London Events", 4),
        "popcorn": ("🐶", "Popcorn", 5),
        "family": ("👨‍👩‍👧", "Family", 6),
        "favorites": ("⭐", "Favorites", 7),
    }

    # 1. Discover all top-level directories in VAULT_ROOT
    year_folders = []
    custom_folders = []

    try:
        items = sorted(os.listdir(VAULT_ROOT))
    except Exception:
        items = []

    for item in items:
        if item.startswith('.') or item == '_Review_Trash':
            continue
        p = os.path.join(VAULT_ROOT, item)
        if not os.path.isdir(p):
            continue

        if item.isdigit() and len(item) == 4:
            year_folders.append(item)
        else:
            custom_folders.append(item)

    # Sort albums: Curated first in priority order, then other custom albums alphabetically
    def album_sort_key(name):
        low = name.lower()
        if low in KNOWN_ALBUMS:
            return (0, KNOWN_ALBUMS[low][2], name)
        return (1, 10, name.lower())

    custom_folders.sort(key=album_sort_key)

    # Add custom and curated albums FIRST so the user sees their organized folders immediately!
    for folder_name in custom_folders:
        p = os.path.join(VAULT_ROOT, folder_name)
        low = folder_name.lower()
        if low in KNOWN_ALBUMS:
            icon, title, _ = KNOWN_ALBUMS[low]
        else:
            icon = "📁"
            title = folder_name.replace('_', ' ')

        count = count_media_in_dir(p)
        albums.append({
            "id": folder_name,
            "title": title,
            "icon": icon,
            "count": count,
            "has_subfolders": True,
            "type": "custom"
        })

    # 2. Add Year folders (descending)
    for yr in sorted(year_folders, reverse=True):
        count = count_media_in_dir(os.path.join(VAULT_ROOT, yr))
        albums.append({
            "id": yr,
            "title": yr,
            "icon": "📅",
            "count": count,
            "has_subfolders": True,
            "type": "year"
        })

    # 3. Trash folder
    trash_count = count_media_in_dir(TRASH_ROOT)
    albums.append({
        "id": "_Review_Trash",
        "title": "Trash",
        "icon": "🗑️",
        "count": trash_count,
        "has_subfolders": False,
        "type": "trash"
    })

    ALBUM_CACHE = (albums, trash_count)
    ALBUM_CACHE_TIME = now
    return albums, trash_count

def count_media_in_dir(directory):
    if not os.path.exists(directory):
        return 0
    total = 0
    try:
        for root, dirs, files in os.walk(directory):
            if "_Review_Trash" in root and directory != TRASH_ROOT:
                continue
            if ".cleaner_cache" in root:
                continue
            for f in files:
                if f.startswith('.'):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext in MEDIA_EXTS:
                    total += 1
    except Exception:
        pass
    return total

def get_subfolders_for_album(album_id):
    target_dir = os.path.join(VAULT_ROOT, album_id)
    if not os.path.exists(target_dir):
        return []

    subfolders = []
    
    if album_id.isdigit():
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for i, m_name in enumerate(month_names, 1):
            m_code = f"{i:02d}"
            subfolders.append({
                "id": f"month:{m_code}",
                "title": m_name,
                "rel_path": "",
                "type": "month"
            })
        
        try:
            for item in sorted(os.listdir(target_dir)):
                p = os.path.join(target_dir, item)
                if os.path.isdir(p) and not item.startswith('.'):
                    c = count_media_in_dir(p)
                    title = item
                    if "_" in item:
                        tokens = item.split("_")
                        if len(tokens) >= 3:
                            title = " ".join(tokens[2:])
                    subfolders.append({
                        "id": f"folder:{item}",
                        "title": title,
                        "rel_path": item,
                        "count": c,
                        "type": "folder"
                    })
        except Exception:
            pass

        return subfolders

    # Non-year albums (e.g. Marriage, Ishanvi, Trips, India, Popcorn, etc.)
    for root, dirs, files in os.walk(target_dir):
        if ".cleaner_cache" in root or "_Review_Trash" in root:
            continue
        rel = os.path.relpath(root, target_dir)
        if rel == '.':
            continue

        c = count_media_in_dir(root)
        parts = rel.split(os.sep)
        display_title = parts[-1]
        if len(parts) > 1:
            display_title = f"{parts[-1]} ({parts[0]})"

        subfolders.append({
            "id": rel,
            "title": display_title,
            "rel_path": rel,
            "count": c,
            "type": "folder"
        })

    subfolders.sort(key=lambda x: x["title"])
    return subfolders

def get_all_destination_folders():
    if not os.path.exists(VAULT_ROOT):
        return []

    destinations = set()

    try:
        # 1. Discover all directories inside VAULT_ROOT (top level and nested)
        for item in sorted(os.listdir(VAULT_ROOT)):
            if item.startswith('.') or item == '_Review_Trash':
                continue
            p = os.path.join(VAULT_ROOT, item)
            if os.path.isdir(p):
                destinations.add(item)
                for root, dirs, files in os.walk(p):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '_Review_Trash' and d != '.cleaner_cache']
                    rel = os.path.relpath(root, VAULT_ROOT)
                    if rel != '.' and len(rel.split(os.sep)) <= 3:
                        destinations.add(rel)
    except Exception as e:
        print(f"Error scanning destinations: {e}")

    # 2. Ensure years 2009 to 2026 are included
    for yr in range(2026, 2008, -1):
        destinations.add(str(yr))

    # Priority sorting: Curated top-level albums first, other albums, subfolders, then years descending
    curated_prio = {
        "ishanvi": 0,
        "marriage": 1,
        "wedding": 1,
        "trips": 2,
        "india": 3,
        "events_london": 4,
        "popcorn": 5,
        "family": 6
    }

    def sort_key(f):
        is_year = f.isdigit() and len(f) == 4
        if is_year:
            return (2, -int(f), f)
        parts = f.split(os.sep)
        if len(parts) == 1:
            prio = curated_prio.get(f.lower(), 10)
            return (0, prio, f.lower())
        else:
            parent = parts[0].lower()
            prio = curated_prio.get(parent, 10)
            return (1, prio, f.lower())

    return sorted(list(destinations), key=sort_key)

def scan_photos(album_id, subfolder="All", month="All"):
    cache_key = (album_id, subfolder, month)
    if cache_key in PHOTOS_CACHE:
        return PHOTOS_CACHE[cache_key]

    results = []
    
    if subfolder and subfolder != "All":
        if subfolder.startswith("folder:"):
            folder_name = subfolder[7:]
            target_dir = os.path.join(VAULT_ROOT, album_id, folder_name)
        elif subfolder.startswith("month:"):
            target_dir = os.path.join(VAULT_ROOT, album_id)
            month = subfolder[6:]
        else:
            target_dir = os.path.join(VAULT_ROOT, album_id, subfolder)
    else:
        target_dir = os.path.join(VAULT_ROOT, album_id)

    if not os.path.exists(target_dir):
        return results

    month_filter = None
    if month and month != "All" and month.isdigit():
        month_filter = f"-{month.zfill(2)}_"

    for root, dirs, files in os.walk(target_dir):
        if ".cleaner_cache" in root:
            continue
        rel_root = os.path.relpath(root, VAULT_ROOT)
        
        if month_filter and album_id.isdigit() and (not subfolder or subfolder == "All" or subfolder.startswith("month:")):
            folder_base = os.path.basename(root)
            if month_filter not in folder_base:
                continue

        location = ""
        parts = rel_root.split(os.sep)
        if len(parts) > 1:
            last_folder = parts[-1]
            if "_" in last_folder:
                tokens = last_folder.split("_")
                if len(tokens) >= 3:
                    location = " ".join(tokens[2:])
            elif "Trips" in parts or "India" in parts:
                location = " • ".join(parts[1:])

        for f in sorted(files):
            if f.startswith('.'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in MEDIA_EXTS:
                continue

            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, VAULT_ROOT)

            # Fast date display from standardized vault filename without slow disk stat calls
            date_display = ""
            if len(f) >= 10 and f[4] == '-' and f[7] == '-':
                date_display = f[:10]

            results.append({
                "path": rel_path,
                "filename": f,
                "size_mb": "",
                "location": location,
                "date_display": date_display,
                "is_video": ext in VIDEO_EXTS,
                "is_raw": ext in RAW_EXTS
            })

    results.sort(key=lambda x: x["filename"])
    PHOTOS_CACHE[cache_key] = results
    return results

def extract_raw_embedded_jpeg(raw_path):
    """
    Ultra-fast pure-Python extraction of embedded full-resolution camera JPEG.
    Canon CR2/CR3 stores an 18MP-30MP camera-processed JPEG inside the first 8MB.
    Takes ~0.05s vs 2.5s for sips raw debayering, eliminating CPU fan noise!
    """
    try:
        with open(raw_path, 'rb') as f:
            # Most Canon/Nikon/Sony embedded previews are in the first 8MB
            data = f.read(8 * 1024 * 1024)
            idx = data.find(b'\xff\xd8')
            best_jpeg = None
            best_size = 0
            while idx != -1:
                end_idx = data.find(b'\xff\xd9', idx)
                if end_idx != -1:
                    size = end_idx - idx + 2
                    # We want the high-res preview (>100KB), skipping tiny 160x120 EXIF thumbnails
                    if size > best_size and size > 100000:
                        best_size = size
                        best_jpeg = data[idx:end_idx+2]
                idx = data.find(b'\xff\xd8', idx + 2)
            return best_jpeg
    except Exception:
        return None

def get_or_create_raw_preview(full_path, max_dim=360):
    """
    Serves high-speed JPEG previews and thumbnails for Canon .CR2, .CR3, .DNG RAW files.
    1. Uses embedded camera JPEG extraction (instant ~50ms).
    2. Resizes extracted JPEG for thumbnail (~30ms).
    3. Falls back to hardware sips conversion with uppercase symlink if needed.
    """
    cache_dir = THUMB_CACHE if max_dim <= 400 else PREVIEW_CACHE
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(RAW_SYMLINKS, exist_ok=True)

    h = hashlib.md5((full_path + f"_{max_dim}").encode('utf-8')).hexdigest()
    cache_path = os.path.join(cache_dir, f"{h}.jpg")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path

    # Check if high-res preview is already in PREVIEW_CACHE
    h_preview = hashlib.md5((full_path + "_1920").encode('utf-8')).hexdigest()
    preview_cache_path = os.path.join(PREVIEW_CACHE, f"{h_preview}.jpg")

    # Step 1: If we have the extracted preview JPEG cached or can extract it now
    if not (os.path.exists(preview_cache_path) and os.path.getsize(preview_cache_path) > 0):
        extracted_bytes = extract_raw_embedded_jpeg(full_path)
        if extracted_bytes:
            try:
                with open(preview_cache_path, 'wb') as pf:
                    pf.write(extracted_bytes)
            except Exception:
                pass

    # If we have the extracted preview JPEG
    if os.path.exists(preview_cache_path) and os.path.getsize(preview_cache_path) > 0:
        if max_dim > 400:
            # For lightbox: the extracted JPEG is already full-resolution crystal clear!
            return preview_cache_path
        else:
            # For thumbnail: resize the extracted JPEG (takes ~0.03s, 50x faster than debayering RAW!)
            try:
                subprocess.run(
                    ["sips", "-Z", str(max_dim), "-s", "format", "jpeg", "-s", "formatOptions", "70", preview_cache_path, "--out", cache_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=4.0
                )
                if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                    return cache_path
            except Exception:
                pass

    # Step 2: Fallback to sips with uppercase extension symlink
    ext = os.path.splitext(full_path)[1]
    symlink_path = os.path.join(RAW_SYMLINKS, f"{h}{ext.upper()}")
    if not os.path.exists(symlink_path):
        try:
            os.symlink(full_path, symlink_path)
        except Exception:
            symlink_path = full_path

    quality = "70" if max_dim <= 400 else "85"
    try:
        subprocess.run(
            ["sips", "-Z", str(max_dim), "-s", "format", "jpeg", "-s", "formatOptions", quality, symlink_path, "--out", cache_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8.0
        )
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return cache_path
    except Exception:
        pass

    return None

def get_video_thumb(video_path, cache_path):
    """Generates a lightweight 360px JPEG thumbnail for video files using macOS QuickLook."""
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path
    
    tmp_dir = "/tmp/cleaner_vthumbs"
    os.makedirs(tmp_dir, exist_ok=True)
    base = os.path.basename(video_path)
    try:
        subprocess.run(
            ["nice", "-n", "15", "qlmanage", "-t", "-s", "360", "-o", tmp_dir, video_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3.5
        )
        gen_file = os.path.join(tmp_dir, f"{base}.png")
        if os.path.exists(gen_file):
            subprocess.run(
                ["nice", "-n", "15", "sips", "-s", "format", "jpeg", "-s", "formatOptions", "65", gen_file, "--out", cache_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2.0
            )
            try:
                os.remove(gen_file)
            except Exception:
                pass
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                return cache_path
    except Exception:
        pass
    return None

def get_or_create_thumb(rel_path):
    full_path = os.path.abspath(os.path.join(VAULT_ROOT, rel_path))
    if not full_path.startswith(VAULT_ROOT) or not os.path.exists(full_path):
        return None

    # Step 1: Check cache FIRST without locking (instant 0ms response for cached thumbs)
    h = hashlib.md5(rel_path.encode('utf-8')).hexdigest()
    cache_path = os.path.join(THUMB_CACHE, f"{h}.jpg")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path

    ext = os.path.splitext(full_path)[1].lower()

    # Step 2: Concurrency-throttled thumbnail generation (Max 2 workers at once, nice priority)
    with THUMB_SEMAPHORE:
        # Double-check cache in case another thread finished it while waiting
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return cache_path

        # Video files: Generate quicklook thumbnail (NEVER stream the full video!)
        if ext in VIDEO_EXTS:
            return get_video_thumb(full_path, cache_path)

        # RAW files (.cr2, .cr3, .dng)
        if ext in RAW_EXTS:
            raw_thumb = get_or_create_raw_preview(full_path, max_dim=360)
            if raw_thumb:
                return raw_thumb
            return None

        # Standard images (.jpg, .png, .heic)
        try:
            os.makedirs(THUMB_CACHE, exist_ok=True)
            subprocess.run(
                ["nice", "-n", "15", "sips", "-Z", "360", "-s", "format", "jpeg", "-s", "formatOptions", "65", full_path, "--out", cache_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3.0
            )
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                return cache_path
        except Exception:
            pass

    return full_path if ext not in VIDEO_EXTS else None

class CleanerRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/" or path == "/index.html":
                self.serve_ui()
            elif path == "/api/albums":
                self.serve_albums()
            elif path == "/api/subfolders":
                self.serve_subfolders(parsed.query)
            elif path == "/api/destinations":
                self.serve_destinations()
            elif path == "/api/photos":
                self.serve_photos(parsed.query)
            elif path.startswith("/thumb/"):
                self.serve_thumb(urllib.parse.unquote(path[7:]))
            elif path.startswith("/media/"):
                self.serve_media(urllib.parse.unquote(path[7:]))
            else:
                self.send_error(404, "Not Found")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len) if content_len > 0 else b'{}'
            
            try:
                data = json.loads(post_body.decode('utf-8'))
            except Exception:
                data = {}

            if path == "/api/trash":
                self.handle_trash(data)
            elif path == "/api/move":
                self.handle_move(data)
            elif path == "/api/create_folder":
                self.handle_create_folder(data)
            elif path == "/api/restore":
                self.handle_restore(data)
            elif path == "/api/empty_trash":
                self.handle_empty_trash()
            else:
                self.send_error(404, "Not Found")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def serve_ui(self):
        if not os.path.exists(HTML_FILE_PATH):
            self.send_error(500, "cleaner_ui.html not found")
            return
        with open(HTML_FILE_PATH, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_albums(self):
        albums, trash_count = get_album_list()
        active = "2024"
        for a in albums:
            if a["id"].isdigit() and a["count"] > 0:
                active = a["id"]
                break
        
        payload = json.dumps({
            "albums": albums,
            "active_album": active,
            "trash_count": trash_count
        }).encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_subfolders(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        album = params.get('album', ['Trips'])[0]
        subfolders = get_subfolders_for_album(album)
        payload = json.dumps({"subfolders": subfolders}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_destinations(self):
        destinations = get_all_destination_folders()
        payload = json.dumps({"destinations": destinations}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_photos(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        album = params.get('album', ['2024'])[0]
        subfolder = params.get('subfolder', ['All'])[0]
        month = params.get('month', ['All'])[0]

        photos = scan_photos(album, subfolder=subfolder, month=month)
        payload = json.dumps({"photos": photos}).encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_thumb(self, rel_path):
        target_path = get_or_create_thumb(rel_path)
        if not target_path or not os.path.exists(target_path):
            self.send_error(404, "Thumb Not Found")
            return

        ext = os.path.splitext(target_path)[1].lower()
        if ext in VIDEO_EXTS:
            self.send_error(404, "Video Thumb Unavailable")
            return

        file_size = os.path.getsize(target_path)
        if ext in ('.jpg', '.jpeg'):
            content_type = 'image/jpeg'
        elif ext == '.png':
            content_type = 'image/png'
        else:
            content_type = mimetypes.guess_type(target_path)[0] or 'image/jpeg'

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(file_size))
        self.send_header('Cache-Control', 'public, max-age=604800')
        self.end_headers()

        with open(target_path, 'rb') as f:
            shutil.copyfileobj(f, self.wfile, length=64*1024)

    def serve_media(self, rel_path):
        full_path = os.path.abspath(os.path.join(VAULT_ROOT, rel_path))
        if not full_path.startswith(VAULT_ROOT) or not os.path.exists(full_path):
            self.send_error(404, "Media Not Found")
            return

        ext = os.path.splitext(full_path)[1].lower()

        # If it's a RAW camera photo (.cr2, .cr3, .dng), browsers cannot render raw sensor data!
        # Decode and serve a high-resolution 1920px JPEG preview generated via hardware!
        if ext in RAW_EXTS:
            raw_preview = get_or_create_raw_preview(full_path, max_dim=1920)
            if raw_preview and os.path.exists(raw_preview):
                file_size = os.path.getsize(raw_preview)
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(file_size))
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                with open(raw_preview, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile, length=256*1024)
                return

        file_size = os.path.getsize(full_path)
        mime_types = {
            '.heic': 'image/heic',
            '.heif': 'image/heif',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
            '.mov': 'video/quicktime',
            '.mp4': 'video/mp4',
            '.m4v': 'video/mp4'
        }
        content_type = mime_types.get(ext, mimetypes.guess_type(full_path)[0] or 'application/octet-stream')

        range_header = self.headers.get('Range', None)
        if range_header:
            try:
                ranges = range_header.replace('bytes=', '').split('-')
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if ranges[1] else file_size - 1
                end = min(end, file_size - 1)
                chunk_len = end - start + 1

                self.send_response(206)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(chunk_len))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()

                with open(full_path, 'rb') as f:
                    f.seek(start)
                    self.wfile.write(f.read(chunk_len))
                return
            except Exception:
                pass

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(file_size))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.end_headers()

        with open(full_path, 'rb') as f:
            shutil.copyfileobj(f, self.wfile, length=256*1024)

    def handle_trash(self, data):
        paths = data.get('paths', [])
        trashed_count = 0

        for rel_path in paths:
            src = os.path.abspath(os.path.join(VAULT_ROOT, rel_path))
            if not src.startswith(VAULT_ROOT) or not os.path.exists(src):
                continue
            
            dst = os.path.join(TRASH_ROOT, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)

            try:
                shutil.move(src, dst)
                UNDO_HISTORY.append((src, dst, "trash"))
                trashed_count += 1
            except Exception as e:
                print(f"Error moving {src} to trash: {e}")

        invalidate_album_cache()
        trash_count = count_media_in_dir(TRASH_ROOT)
        payload = json.dumps({"success": True, "trashed": trashed_count, "trash_count": trash_count}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def handle_move(self, data):
        paths = data.get('paths', [])
        target_folder = data.get('target_folder', '').strip().strip('/')
        if not target_folder:
            self.send_error(400, "target_folder required")
            return

        dst_dir = os.path.abspath(os.path.join(VAULT_ROOT, target_folder))
        if not dst_dir.startswith(VAULT_ROOT):
            self.send_error(400, "Invalid target folder")
            return

        os.makedirs(dst_dir, exist_ok=True)
        moved_count = 0

        for rel_path in paths:
            src = os.path.abspath(os.path.join(VAULT_ROOT, rel_path))
            if not src.startswith(VAULT_ROOT) or not os.path.exists(src):
                continue
            
            fname = os.path.basename(src)
            dst = os.path.join(dst_dir, fname)

            if src == dst:
                continue

            if os.path.exists(dst):
                base, ext = os.path.splitext(fname)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(dst_dir, f"{base}_{counter}{ext}")
                    counter += 1

            try:
                shutil.move(src, dst)
                UNDO_HISTORY.append((src, dst, "move"))
                moved_count += 1
            except Exception as e:
                print(f"Error moving {src} to {dst}: {e}")

        invalidate_album_cache()
        payload = json.dumps({
            "success": True,
            "moved_count": moved_count,
            "target_folder": target_folder
        }).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def handle_create_folder(self, data):
        folder_name = data.get('folder', '').strip().strip('/')
        if not folder_name:
            self.send_error(400, "Folder name is required")
            return

        dst_dir = os.path.abspath(os.path.join(VAULT_ROOT, folder_name))
        if not dst_dir.startswith(VAULT_ROOT):
            self.send_error(400, "Invalid folder path")
            return

        os.makedirs(dst_dir, exist_ok=True)
        invalidate_album_cache()

        payload = json.dumps({
            "success": True,
            "folder": folder_name,
            "message": f"Folder '{folder_name}' created successfully"
        }).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def handle_restore(self, data):
        if not UNDO_HISTORY:
            payload = json.dumps({"success": False, "message": "Nothing to undo"}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        orig_src, current_dst, action_type = UNDO_HISTORY.pop()
        restored = False

        if os.path.exists(current_dst):
            os.makedirs(os.path.dirname(orig_src), exist_ok=True)
            try:
                shutil.move(current_dst, orig_src)
                restored = True
            except Exception as e:
                print(f"Error restoring: {e}")

        invalidate_album_cache()
        trash_count = count_media_in_dir(TRASH_ROOT)
        rel_restored = os.path.relpath(orig_src, VAULT_ROOT)
        payload = json.dumps({
            "success": restored,
            "restored_path": rel_restored,
            "action_type": action_type,
            "trash_count": trash_count
        }).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def handle_empty_trash(self):
        if os.path.exists(TRASH_ROOT):
            try:
                shutil.rmtree(TRASH_ROOT)
                os.makedirs(TRASH_ROOT, exist_ok=True)
            except Exception as e:
                print(f"Error emptying trash: {e}")

        invalidate_album_cache()
        payload = json.dumps({"success": True, "trash_count": 0}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc_type, exc_val, _ = sys.exc_info()
        if exc_type in (BrokenPipeError, ConnectionResetError):
            return
        super().handle_error(request, client_address)

def main():
    port = 8888
    for p in range(8888, 8910):
        try:
            server = ThreadedHTTPServer(('localhost', p), CleanerRequestHandler)
            port = p
            break
        except OSError:
            continue

    url = f"http://localhost:{port}"
    print("\n" + "=" * 65)
    print(" 📸 MEMORIES VAULT CLEANER & ORGANIZER (iOS Photos Web App)")
    print("=" * 65)
    print(f"🚀 Running locally on: {url}")
    print(f"📂 Vault Location:     {VAULT_ROOT}")
    print(f"🗑️ Staged Trash:       {TRASH_ROOT}")
    print("=" * 65)
    print("\n💡 Press Ctrl + C in this terminal window whenever you want to stop the server.")
    print("Opening Safari now...\n")

    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping cleaner server. Happy organizing!")

if __name__ == '__main__':
    main()
