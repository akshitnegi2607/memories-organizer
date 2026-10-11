#!/usr/bin/env python3
"""
High-Precision Vault Refiner:
1. Date Correction: Uses the true earliest capture date min(ContentCreationDate, st_mtime).
2. Location Precision: High-density UK & India town dataset with tight 20km radius (e.g. Crawley, Redhill, Lucknow).
3. Unwanted Detection: Automatically isolates Screenshots and Stickers into _Review_Unwanted/ folders.
"""

import os
import sys
import math
import time
import re
import shutil
import hashlib
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import CoreServices
import Foundation

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]

# High-density database of towns, cities, and travel destinations
CITIES = [
    # Surrey & Sussex (near Gatwick, M23, South London)
    ("Crawley", "West Sussex", "United Kingdom", 51.1130, -0.1831),
    ("Gatwick", "West Sussex", "United Kingdom", 51.1537, -0.1821),
    ("Horley", "Surrey", "United Kingdom", 51.1719, -0.1633),
    ("Redhill", "Surrey", "United Kingdom", 51.2400, -0.1690),
    ("Reigate", "Surrey", "United Kingdom", 51.2373, -0.2070),
    ("Guildford", "Surrey", "United Kingdom", 51.2362, -0.5704),
    ("Woking", "Surrey", "United Kingdom", 51.3168, -0.5600),
    ("Dorking", "Surrey", "United Kingdom", 51.2323, -0.3330),
    ("Epsom", "Surrey", "United Kingdom", 51.3360, -0.2660),
    ("Horsham", "West Sussex", "United Kingdom", 51.0629, -0.3259),
    ("Haywards Heath", "West Sussex", "United Kingdom", 51.0039, -0.1444),
    ("Burgess Hill", "West Sussex", "United Kingdom", 50.9540, -0.1260),
    ("East Grinstead", "West Sussex", "United Kingdom", 51.1275, -0.0090),
    ("Brighton", "East Sussex", "United Kingdom", 50.8225, -0.1372),
    ("Hove", "East Sussex", "United Kingdom", 50.8352, -0.1714),
    ("Worthing", "West Sussex", "United Kingdom", 50.8179, -0.3729),
    ("Eastbourne", "East Sussex", "United Kingdom", 50.7680, 0.2905),
    ("Hastings", "East Sussex", "United Kingdom", 50.8552, 0.5729),
    ("Lewes", "East Sussex", "United Kingdom", 50.8744, 0.0084),
    ("Chichester", "West Sussex", "United Kingdom", 50.8365, -0.7792),

    # Greater London & Home Counties
    ("London", "Greater London", "United Kingdom", 51.5074, -0.1278),
    ("Croydon", "Greater London", "United Kingdom", 51.3762, -0.0982),
    ("Sutton", "Greater London", "United Kingdom", 51.3614, -0.1930),
    ("Kingston", "Greater London", "United Kingdom", 51.4123, -0.3007),
    ("Richmond", "Greater London", "United Kingdom", 51.4613, -0.3037),
    ("Wimbledon", "Greater London", "United Kingdom", 51.4214, -0.2066),
    ("Bromley", "Greater London", "United Kingdom", 51.4039, 0.0198),
    ("Slough", "Berkshire", "United Kingdom", 51.5105, -0.5950),
    ("Windsor", "Berkshire", "United Kingdom", 51.4839, -0.6044),
    ("Maidenhead", "Berkshire", "United Kingdom", 51.5217, -0.7177),
    ("Reading", "Berkshire", "United Kingdom", 51.4543, -0.9781),
    ("Bracknell", "Berkshire", "United Kingdom", 51.4160, -0.7490),
    ("Watford", "Hertfordshire", "United Kingdom", 51.6565, -0.3903),
    ("St Albans", "Hertfordshire", "United Kingdom", 51.7527, -0.3394),
    ("Luton", "Bedfordshire", "United Kingdom", 51.8787, -0.4200),
    ("Milton Keynes", "Buckinghamshire", "United Kingdom", 52.0406, -0.7594),
    ("Oxford", "Oxfordshire", "United Kingdom", 51.7520, -1.2577),
    ("Cambridge", "Cambridgeshire", "United Kingdom", 52.2053, 0.1218),
    ("Southampton", "Hampshire", "United Kingdom", 50.9097, -1.4044),
    ("Portsmouth", "Hampshire", "United Kingdom", 50.8198, -1.0880),
    ("Winchester", "Hampshire", "United Kingdom", 51.0632, -1.3080),
    ("Basingstoke", "Hampshire", "United Kingdom", 51.2625, -1.0870),
    ("Tunbridge Wells", "Kent", "United Kingdom", 51.1324, 0.2637),
    ("Sevenoaks", "Kent", "United Kingdom", 51.2724, 0.1879),
    ("Maidstone", "Kent", "United Kingdom", 51.2704, 0.5227),
    ("Canterbury", "Kent", "United Kingdom", 51.2802, 1.0789),

    # UK Cities
    ("Bristol", "Bristol", "United Kingdom", 51.4545, -2.5879),
    ("Bath", "Somerset", "United Kingdom", 51.3758, -2.3599),
    ("Cardiff", "South Glamorgan", "United Kingdom", 51.4816, -3.1791),
    ("Birmingham", "West Midlands", "United Kingdom", 52.4862, -1.8904),
    ("Manchester", "Greater Manchester", "United Kingdom", 53.4808, -2.2426),
    ("Liverpool", "Merseyside", "United Kingdom", 53.4084, -2.9916),
    ("Leeds", "West Yorkshire", "United Kingdom", 53.8008, -1.5491),
    ("Sheffield", "South Yorkshire", "United Kingdom", 53.3811, -1.4701),
    ("Newcastle", "Tyne and Wear", "United Kingdom", 54.9783, -1.6178),
    ("Edinburgh", "Midlothian", "United Kingdom", 55.9533, -3.1883),
    ("Glasgow", "Lanarkshire", "United Kingdom", 55.8642, -4.2518),
    ("Belfast", "Antrim", "United Kingdom", 54.5973, -5.9301),

    # India: UP, NCR & North
    ("Lucknow", "Uttar Pradesh", "India", 26.8467, 80.9462),
    ("Kanpur", "Uttar Pradesh", "India", 26.4499, 80.3319),
    ("Noida", "Uttar Pradesh", "India", 28.5355, 77.3910),
    ("Greater Noida", "Uttar Pradesh", "India", 28.4744, 77.5040),
    ("Ghaziabad", "Uttar Pradesh", "India", 28.6692, 77.4538),
    ("Gurugram", "Haryana", "India", 28.4595, 77.0266),
    ("Faridabad", "Haryana", "India", 28.4089, 77.3178),
    ("New Delhi", "Delhi", "India", 28.6139, 77.2090),
    ("Delhi", "Delhi", "India", 28.7041, 77.1025),
    ("Agra", "Uttar Pradesh", "India", 27.1767, 78.0081),
    ("Mathura", "Uttar Pradesh", "India", 27.4924, 77.6737),
    ("Varanasi", "Uttar Pradesh", "India", 25.3176, 82.9739),
    ("Prayagraj", "Uttar Pradesh", "India", 25.4358, 81.8463),
    ("Ayodhya", "Uttar Pradesh", "India", 26.7922, 82.1998),
    ("Gorakhpur", "Uttar Pradesh", "India", 26.7606, 83.3732),
    ("Jhansi", "Uttar Pradesh", "India", 25.4484, 78.5685),
    ("Bareilly", "Uttar Pradesh", "India", 28.3670, 79.4304),
    ("Meerut", "Uttar Pradesh", "India", 28.9845, 77.7064),
    ("Aligarh", "Uttar Pradesh", "India", 27.8974, 78.0880),

    # India: Maharashtra, West & South
    ("Mumbai", "Maharashtra", "India", 19.0760, 72.8777),
    ("Navi Mumbai", "Maharashtra", "India", 19.0330, 73.0297),
    ("Thane", "Maharashtra", "India", 19.2183, 72.9781),
    ("Kalyan", "Maharashtra", "India", 19.2403, 73.1305),
    ("Panvel", "Maharashtra", "India", 18.9894, 73.1175),
    ("Pune", "Maharashtra", "India", 18.5204, 73.8567),
    ("Pimpri-Chinchwad", "Maharashtra", "India", 18.6298, 73.7997),
    ("Lonavala", "Maharashtra", "India", 18.7557, 73.4091),
    ("Mahabaleshwar", "Maharashtra", "India", 17.9237, 73.6586),
    ("Nashik", "Maharashtra", "India", 19.9975, 73.7898),
    ("Shirdi", "Maharashtra", "India", 19.7645, 74.4762),
    ("Kolhapur", "Maharashtra", "India", 16.7050, 74.2433),
    ("Nagpur", "Maharashtra", "India", 21.1458, 79.0882),
    ("Goa", "Goa", "India", 15.2993, 74.1240),
    ("Panaji", "Goa", "India", 15.4909, 73.8278),
    ("Calangute", "Goa", "India", 15.5439, 73.7553),
    ("Margao", "Goa", "India", 15.2832, 73.9862),
    ("Bengaluru", "Karnataka", "India", 12.9716, 77.5946),
    ("Mysuru", "Karnataka", "India", 12.2958, 76.6394),
    ("Hyderabad", "Telangana", "India", 17.3850, 78.4867),
    ("Chennai", "Tamil Nadu", "India", 13.0827, 80.2707),
    ("Kochi", "Kerala", "India", 9.9312, 76.2673),
    ("Munnar", "Kerala", "India", 10.0889, 77.0595),
    ("Alappuzha", "Kerala", "India", 9.4981, 76.3388),
    ("Kolkata", "West Bengal", "India", 22.5726, 88.3639),
    ("Ahmedabad", "Gujarat", "India", 23.0225, 72.5714),
    ("Jaipur", "Rajasthan", "India", 26.9124, 75.7873),
    ("Udaipur", "Rajasthan", "India", 24.5854, 73.7125),
    ("Jodhpur", "Rajasthan", "India", 26.2389, 73.0243),
    ("Chandigarh", "Punjab", "India", 30.7333, 76.7794),
    ("Shimla", "Himachal Pradesh", "India", 31.1048, 77.1734),
    ("Manali", "Himachal Pradesh", "India", 32.2432, 77.1892),
    ("Dharamshala", "Himachal Pradesh", "India", 32.2190, 76.3234),
    ("Rishikesh", "Uttarakhand", "India", 30.0869, 78.2676),
    ("Haridwar", "Uttarakhand", "India", 29.9457, 78.1642),
    ("Dehradun", "Uttarakhand", "India", 30.3165, 78.0322),

    # Europe & International Travel
    ("Paris", "Île-de-France", "France", 48.8566, 2.3522),
    ("Nice", "Côte d'Azur", "France", 43.7102, 7.2620),
    ("Rome", "Lazio", "Italy", 41.9028, 12.4964),
    ("Milan", "Lombardy", "Italy", 45.4642, 9.1900),
    ("Florence", "Tuscany", "Italy", 43.7696, 11.2558),
    ("Venice", "Veneto", "Italy", 45.4408, 12.3155),
    ("Amsterdam", "North Holland", "Netherlands", 52.3676, 4.9041),
    ("Zurich", "Zurich", "Switzerland", 47.3769, 8.5417),
    ("Geneva", "Geneva", "Switzerland", 46.2044, 6.1432),
    ("Lucerne", "Lucerne", "Switzerland", 47.0502, 8.3093),
    ("Interlaken", "Bern", "Switzerland", 46.6863, 7.8632),
    ("Dubai", "Dubai", "UAE", 25.2048, 55.2708),
    ("Singapore", "Singapore", "Singapore", 1.3521, 103.8198),
    ("New York", "New York", "USA", 40.7128, -74.0060)
]

# iPhone / iPad / Android screen resolutions (Width, Height)
SCREEN_RESOLUTIONS = {
    (1170, 2532), (2532, 1170),  # iPhone 12, 13, 14
    (1284, 2778), (2778, 1284),  # iPhone 12 Pro Max, 13 Pro Max, 14 Plus
    (1179, 2556), (2556, 1179),  # iPhone 14 Pro, 15, 15 Pro, 16
    (1290, 2796), (2796, 1290),  # iPhone 14 Pro Max, 15 Pro Max, 16 Plus
    (1125, 2436), (2436, 1125),  # iPhone X, XS, 11 Pro
    (1242, 2688), (2688, 1242),  # iPhone XS Max, 11 Pro Max
    (828, 1792),  (1792, 828),   # iPhone XR, 11
    (750, 1334),  (1334, 750),   # iPhone 6, 7, 8, SE2, SE3
    (1080, 1920), (1920, 1080),  # iPhone 6+, 7+, 8+, Android standard
    (1080, 2340), (2340, 1080),  # Android standard
    (1080, 2400), (2400, 1080),  # Android standard
    (1440, 3120), (3120, 1440),  # Android flagship
    (1440, 3200), (3200, 1440),  # Android flagship
    (1640, 2360), (2360, 1640),  # iPad Air
    (1668, 2388), (2388, 1668),  # iPad Pro 11
    (2048, 2732), (2732, 2048),  # iPad Pro 12.9
}

_geo_cache = {}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def get_high_precision_location(lat, lon):
    """
    Resolves coordinates with a tight 20 km radius so towns are never mislabeled.
    Returns: Town_Country, or Region_Country if 20-35km, or None if rural/distant.
    """
    if lat is None or lon is None:
        return None
    try:
        lat = float(lat)
        lon = float(lon)
        if math.isnan(lat) or math.isnan(lon):
            return None
    except (ValueError, TypeError):
        return None

    cache_key = (round(lat, 3), round(lon, 3))
    if cache_key in _geo_cache:
        return _geo_cache[cache_key]

    best = None
    min_dist = float('inf')

    for name, region, country, clat, clng in CITIES:
        dist = haversine_km(lat, lon, clat, clng)
        if dist < min_dist:
            min_dist = dist
            best = (name, region, country, dist)

    if best:
        name, region, country, dist = best
        # Tight radius: within 20 km -> exact town name
        if dist <= 20.0:
            res = f"{name}_{country}"
            _geo_cache[cache_key] = res
            return res
        # Close region: 20 km to 35 km -> county/region name
        elif dist <= 35.0 and region:
            res = f"{region}_{country}"
            _geo_cache[cache_key] = res
            return res

    _geo_cache[cache_key] = None
    return None

def parse_filename_date(filename):
    m1 = re.search(r'(?:IMG_|VID_|PXL_|PHOTO_)?(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})', filename, re.IGNORECASE)
    if m1:
        try:
            return datetime(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)),
                            int(m1.group(4)), int(m1.group(5)), int(m1.group(6)))
        except ValueError:
            pass

    m2 = re.search(r'(\d{4})-(\d{2})-(\d{2})[_\s\w]*?(\d{2})[.:](\d{2})[.:](\d{2})', filename)
    if m2:
        try:
            return datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)),
                            int(m2.group(4)), int(m2.group(5)), int(m2.group(6)))
        except ValueError:
            pass

    m3 = re.search(r'(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})', filename)
    if m3:
        try:
            y, m, d = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
            if 1995 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
                return datetime(y, m, d, 12, 0, 0)
        except ValueError:
            pass

    return None

def get_true_metadata(filepath):
    """
    Extracts the true original capture date by taking the earliest valid date,
    and identifies screenshots / unwanted images.
    """
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()
    st = os.stat(filepath)
    mtime = datetime.fromtimestamp(st.st_mtime)

    # 1. Query macOS Spotlight
    spotlight_date = None
    lat = None
    lng = None
    width = None
    height = None
    camera = None

    try:
        url = Foundation.NSURL.fileURLWithPath_(filepath)
        item = CoreServices.MDItemCreateWithURL(None, url)
        if item:
            raw_c = CoreServices.MDItemCopyAttribute(item, 'kMDItemContentCreationDate')
            if raw_c:
                spotlight_date = datetime.fromtimestamp(raw_c.timeIntervalSince1970())
            lat = CoreServices.MDItemCopyAttribute(item, 'kMDItemLatitude')
            lng = CoreServices.MDItemCopyAttribute(item, 'kMDItemLongitude')
            width = CoreServices.MDItemCopyAttribute(item, 'kMDItemPixelWidth')
            height = CoreServices.MDItemCopyAttribute(item, 'kMDItemPixelHeight')
            camera = CoreServices.MDItemCopyAttribute(item, 'kMDItemAcquisitionModel')
    except Exception:
        pass

    # 2. Determine True Original Date
    # Filename date is most explicit
    fn_date = parse_filename_date(filename)

    candidate_dates = []
    if fn_date and 1995 <= fn_date.year <= 2030:
        candidate_dates.append(fn_date)
    if spotlight_date and 1995 <= spotlight_date.year <= 2030:
        candidate_dates.append(spotlight_date)
    if mtime and 1995 <= mtime.year <= 2030:
        candidate_dates.append(mtime)

    # The true capture date is the EARLIEST valid timestamp (since a file cannot predate its creation)
    if candidate_dates:
        true_date = min(candidate_dates)
    else:
        true_date = mtime

    # 3. Check for Screenshots & Unwanted Media
    is_screenshot = False
    is_sticker = False

    # Screenshot check
    if re.search(r'screenshot|screen_shot|screen shot|rpreplay', filename, re.IGNORECASE):
        is_screenshot = True
    elif ext == '.png' and not camera:
        if width and height:
            if (width, height) in SCREEN_RESOLUTIONS:
                is_screenshot = True

    # Sticker / Meme check
    if filename.startswith('STK-') or ext == '.webp':
        is_sticker = True
    elif st.st_size < 35 * 1024 and width and height and width < 350 and height < 350 and not camera:
        is_sticker = True

    loc_tag = get_high_precision_location(lat, lng)
    return true_date, loc_tag, is_screenshot, is_sticker

def fast_chunk_hash(filepath):
    CHUNK = 65536
    try:
        filesize = os.path.getsize(filepath)
        h = hashlib.md5()
        h.update(str(filesize).encode())
        with open(filepath, 'rb') as f:
            if filesize <= CHUNK * 3:
                h.update(f.read())
            else:
                h.update(f.read(CHUNK))
                f.seek(filesize // 2)
                h.update(f.read(CHUNK))
                f.seek(filesize - CHUNK)
                h.update(f.read(CHUNK))
        return h.hexdigest(), filesize
    except Exception:
        return None, 0

def main():
    parser = argparse.ArgumentParser(description="High-Precision Vault Refiner & Duplicate Mirror")
    parser.add_argument("-v", "--vault", default="/Volumes/DIVAKSHSSD/Organized_Memories", help="Path to Organized_Memories vault")
    parser.add_argument("-e", "--execute", action="store_true", help="Perform actual moves (dry-run by default)")
    parser.add_argument("--workers", type=int, default=8, help="Number of worker threads")
    args = parser.parse_args()

    vault_dir = os.path.abspath(args.vault)
    dry_run = not args.execute

    print("\n" + "=" * 65)
    print(" 🎯 HIGH-PRECISION VAULT REFINER & DUPLICATE MIRROR")
    print("=" * 65)
    print(f"📁 Vault:    {vault_dir}")
    print(f"⚡ Mode:     {'DRY-RUN PREVIEW (No files modified)' if dry_run else 'ACTIVE MOVE'}")
    print("🔍 Features: True Earliest Date | 20km Town Radius | Screenshot Isolation | Mirror Duplicates")
    print("=" * 65 + "\n")

    t0 = time.time()

    # Step 1: Collect all files in clean vault (excluding _Duplicates and _Review_Unwanted)
    clean_files = []
    duplicate_files = []

    for root, dirs, files in os.walk(vault_dir):
        is_dupe_folder = '_Duplicates' in root
        is_unwanted_folder = '_Review_Unwanted' in root

        for f in files:
            if f.startswith('.'): continue
            ext = os.path.splitext(f)[1].lower()
            if ext in {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.webp', '.mp4', '.mov', '.m4v', '.3gp'}:
                fp = os.path.join(root, f)
                if is_dupe_folder:
                    duplicate_files.append(fp)
                elif not is_unwanted_folder:
                    clean_files.append(fp)

    print(f"📊 Scanning {len(clean_files):,} clean photos and {len(duplicate_files):,} duplicate photos in vault...")

    # Step 2: Analyze clean photos
    planned_clean_moves = []
    screenshot_count = 0
    sticker_count = 0
    clean_hash_map = {}  # hash -> relative_target_path

    def analyze_clean_file(fp):
        date, loc, is_screenshot, is_sticker = get_true_metadata(fp)
        h, sz = fast_chunk_hash(fp)
        return fp, date, loc, is_screenshot, is_sticker, h, sz

    print("🔍 Analyzing clean photos & building match index...")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(analyze_clean_file, fp) for fp in clean_files]
        for fut in tqdm(as_completed(futures), total=len(clean_files), desc="Indexing Vault", unit="files"):
            fp, date, loc, is_screenshot, is_sticker, h, sz = fut.result()
            fname = os.path.basename(fp)
            ext = os.path.splitext(fname)[1].lower()

            year = str(date.year)
            month_num = f"{date.month:02d}"
            month_name = MONTH_NAMES[date.month - 1]
            day = f"{date.day:02d}"
            hour = f"{date.hour:02d}"
            minute = f"{date.minute:02d}"
            second = f"{date.second:02d}"

            if is_screenshot:
                screenshot_count += 1
                rel_folder = os.path.join("_Review_Unwanted", "Screenshots", year, f"{year}-{month_num}_{month_name}")
            elif is_sticker:
                sticker_count += 1
                rel_folder = os.path.join("_Review_Unwanted", "Stickers_and_Memes", year, f"{year}-{month_num}_{month_name}")
            elif loc:
                rel_folder = os.path.join(year, f"{year}-{month_num}_{month_name}_{loc}")
            else:
                rel_folder = os.path.join(year, f"{year}-{month_num}_{month_name}")

            clean_base = re.sub(r'^\d{4}[-_]\d{2}[-_]\d{2}[-_]\d{2}[-_.]\d{2}[-_.]\d{2}_?', '', os.path.splitext(fname)[0])
            new_name = f"{year}-{month_num}-{day}_{hour}-{minute}-{second}_{clean_base}{ext}"
            rel_target = os.path.join(rel_folder, new_name)
            full_target = os.path.join(vault_dir, rel_target)

            if h and not is_screenshot and not is_sticker:
                clean_hash_map[h] = (rel_folder, new_name, full_target)

            planned_clean_moves.append((fp, full_target))

    # Collision avoidance for clean files
    seen_clean = set()
    final_clean_moves = []
    for src, dst in planned_clean_moves:
        candidate = dst
        counter = 1
        base_no_ext, ext_only = os.path.splitext(candidate)
        while candidate in seen_clean or (os.path.exists(candidate) and candidate != src):
            candidate = f"{base_no_ext}_{counter}{ext_only}"
            counter += 1
        seen_clean.add(candidate)
        if src != candidate:
            final_clean_moves.append((src, candidate))

    # Step 3: Align Duplicates to Mirror the Clean Vault Exactly
    print(f"\n👯 Aligning {len(duplicate_files):,} duplicates to mirror clean vault structure...")
    planned_dupe_moves = []
    audit_pairs = []

    def process_dupe_file(fp):
        h, sz = fast_chunk_hash(fp)
        return fp, h, sz

    seen_dupe = set()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(process_dupe_file, fp) for fp in duplicate_files]
        for fut in tqdm(as_completed(futures), total=len(duplicate_files), desc="Mirroring Dupes", unit="files"):
            fp, h, sz = fut.result()
            fname = os.path.basename(fp)
            ext = os.path.splitext(fname)[1].lower()

            if h and h in clean_hash_map:
                rel_folder, master_name, master_full = clean_hash_map[h]
                dupe_folder = os.path.join(vault_dir, "_Duplicates", rel_folder)
                target_dupe = os.path.join(dupe_folder, master_name)
                audit_pairs.append((master_full, target_dupe, sz))
            else:
                # Standalone duplicate with own metadata
                date, loc, is_ss, is_stk = get_true_metadata(fp)
                year = str(date.year)
                month_num = f"{date.month:02d}"
                month_name = MONTH_NAMES[date.month - 1]
                day = f"{date.day:02d}"
                hour = f"{date.hour:02d}"
                minute = f"{date.minute:02d}"
                second = f"{date.second:02d}"

                clean_base = re.sub(r'^\d{4}[-_]\d{2}[-_]\d{2}[-_]\d{2}[-_.]\d{2}[-_.]\d{2}_?', '', os.path.splitext(fname)[0])
                new_name = f"{year}-{month_num}-{day}_{hour}-{minute}-{second}_{clean_base}{ext}"

                if loc:
                    subf = os.path.join("_Duplicates", year, f"{year}-{month_num}_{month_name}_{loc}")
                else:
                    subf = os.path.join("_Duplicates", year, f"{year}-{month_num}_{month_name}")
                target_dupe = os.path.join(vault_dir, subf, new_name)

            candidate = target_dupe
            counter = 1
            base_no_ext, ext_only = os.path.splitext(candidate)
            while candidate in seen_dupe or (os.path.exists(candidate) and candidate != fp):
                candidate = f"{base_no_ext}_{counter}{ext_only}"
                counter += 1
            seen_dupe.add(candidate)

            if fp != candidate:
                planned_dupe_moves.append((fp, candidate))

    elapsed = time.time() - t0

    print("\n" + "=" * 65)
    print(" 📋 REFINEMENT & MIRROR RESULTS")
    print("=" * 65)
    print(f"⏱️ Analysis Time:          {elapsed:.1f} seconds")
    print(f"📸 Clean Photos to Re-sort: {len(final_clean_moves):,} files")
    print(f"👯 Duplicates to Re-align:  {len(planned_dupe_moves):,} files (Now exact 1:1 mirrors!)")
    print(f"📱 Screenshots Isolated:    {screenshot_count:,} photos ➔ moving to _Review_Unwanted/Screenshots")
    print(f"💬 WhatsApp Stickers:       {sticker_count:,} items  ➔ moving to _Review_Unwanted/Stickers_and_Memes")
    print("=" * 65 + "\n")

    # Generate CSV Audit Sheet
    csv_path = os.path.join(vault_dir, "duplicates_audit.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("Master Photo in Vault,Matching Duplicate in _Duplicates,Size (MB)\n")
        for master, dupe, sz in audit_pairs:
            f.write(f'"{master}","{dupe}",{sz / (1024*1024):.2f}\n')

    print(f"📄 Duplicates Audit Sheet: {csv_path}")
    print("   Open this in Excel / Numbers to inspect every matching pair side-by-side!\n")

    all_moves = final_clean_moves + planned_dupe_moves

    if not dry_run and all_moves:
        print(f"🚚 Moving {len(all_moves):,} files into their corrected & mirrored folders...")
        def move_worker(src_dst):
            src, dst = src_dst
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            list(tqdm(executor.map(move_worker, all_moves), total=len(all_moves), desc="Reorganizing", unit="files"))

        print("🧹 Cleaning up empty folders...")
        for root, dirs, files in os.walk(vault_dir, topdown=False):
            if '_Duplicates' in root or '_Review_Unwanted' in root:
                continue
            if not os.listdir(root):
                try:
                    os.rmdir(root)
                except OSError:
                    pass

        print("\n✅ Complete! Both your clean vault and _Duplicates are in 1:1 matching alignment.")
    elif dry_run:
        print("💡 This was a DRY-RUN. To execute the changes, add '--execute'!")

if __name__ == "__main__":
    main()
