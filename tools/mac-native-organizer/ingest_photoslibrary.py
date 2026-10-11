#!/usr/bin/env python3
"""
Ingest Apple Photos Library into Organized_Memories:
1. Connects to Photos.sqlite in Iphone-photo/Photos Library.photoslibrary.
2. Restores exact original filenames (IMG_XXXX.JPG), true capture dates, and GPS coordinates.
3. Automatically maps 2017-2019 family vacations (Mauritius, Thailand/Phuket/Bangkok, Nainital, India hometowns).
4. Deduplicates against Organized_Memories (staged to _Duplicates).
5. Cleans up Iphone-photo once completed.
"""

import os
import sys
import shutil
import hashlib
import csv
import argparse
import datetime
import math
import sqlite3
import re
from collections import defaultdict
from tqdm import tqdm

import CoreServices
import Foundation

VAULT_ROOT = "/Volumes/DIVAKSHSSD/Organized_Memories"
LIB_ROOT = "/Volumes/DIVAKSHSSD/Iphone-photo/Photos Library.photoslibrary"
DB_PATH = os.path.join(LIB_ROOT, "database", "Photos.sqlite")
ORIGINALS_DIR = os.path.join(LIB_ROOT, "originals")

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
    ("Watford", "Hertfordshire", "United Kingdom", 51.6565, -0.3903),
    ("Slough", "Berkshire", "United Kingdom", 51.5105, -0.5950),
    ("Windsor", "Berkshire", "United Kingdom", 51.4839, -0.6044),
    ("Maidenhead", "Berkshire", "United Kingdom", 51.5217, -0.7177),
    ("Bracknell", "Berkshire", "United Kingdom", 51.4160, -0.7490),
    ("Reading", "Berkshire", "United Kingdom", 51.4543, -0.9781),
    ("Luton", "Bedfordshire", "United Kingdom", 51.8787, -0.4200),
    ("Milton Keynes", "Buckinghamshire", "United Kingdom", 52.0406, -0.7594),
    ("Oxford", "Oxfordshire", "United Kingdom", 51.7520, -1.2577),
    ("Cambridge", "Cambridgeshire", "United Kingdom", 52.2053, 0.1218),
    ("Canterbury", "Kent", "United Kingdom", 51.2802, 1.0789),
    ("Maidstone", "Kent", "United Kingdom", 51.2704, 0.5227),
    ("Bath", "Somerset", "United Kingdom", 51.3758, -2.3599),
    ("Bristol", "Bristol", "United Kingdom", 51.4545, -2.5879),
    ("Southampton", "Hampshire", "United Kingdom", 50.9097, -1.4044),
    ("Portsmouth", "Hampshire", "United Kingdom", 50.8198, -1.0880),
    ("Winchester", "Hampshire", "United Kingdom", 51.0632, -1.3080),
    ("Basingstoke", "Hampshire", "United Kingdom", 51.2667, -1.0876),

    # UK Getaways & Scotland
    ("Edinburgh", "Scotland", "United Kingdom", 55.9533, -3.1883),
    ("Glasgow", "Scotland", "United Kingdom", 55.8642, -4.2518),
    ("Belfast", "Northern Ireland", "United Kingdom", 54.5973, -5.9301),
    ("Liverpool", "Merseyside", "United Kingdom", 53.4084, -2.9916),
    ("Cardiff", "Wales", "United Kingdom", 51.4816, -3.1791),

    # Thailand Vacations (2018)
    ("Bangkok", "Bangkok", "Thailand", 13.7563, 100.5018),
    ("Phuket", "Phuket", "Thailand", 7.8804, 98.3923),
    ("Patong", "Phuket", "Thailand", 7.8970, 98.2965),
    ("Chiang Mai", "Chiang Mai", "Thailand", 18.7883, 98.9853),
    ("Kanchanaburi", "Kanchanaburi", "Thailand", 14.0325, 99.5283),
    ("Pattaya", "Chonburi", "Thailand", 12.9276, 100.8771),
    ("Krabi", "Krabi", "Thailand", 8.0863, 98.9063),

    # Mauritius Vacations (2017)
    ("Port Louis", "Port Louis", "Mauritius", -20.1609, 57.5012),
    ("Grand Baie", "Rivière du Rempart", "Mauritius", -20.0108, 57.5804),
    ("Flic en Flac", "Black River", "Mauritius", -20.2730, 57.3639),
    ("Trou aux Biches", "Pamplemousses", "Mauritius", -20.0381, 57.5458),
    ("Le Morne", "Black River", "Mauritius", -20.4444, 57.3236),
    ("Belle Mare", "Flacq", "Mauritius", -20.1989, 57.7719),
    ("Mauritius", "Mauritius", "Mauritius", -20.2641, 57.8040),

    # India
    ("Lucknow", "Uttar Pradesh", "India", 26.8467, 80.9462),
    ("Kanpur", "Uttar Pradesh", "India", 26.4499, 80.3319),
    ("Varanasi", "Uttar Pradesh", "India", 25.3176, 82.9739),
    ("New Delhi", "Delhi", "India", 28.6139, 77.2090),
    ("Gurugram", "Haryana", "India", 28.4595, 77.0266),
    ("Noida", "Uttar Pradesh", "India", 28.5355, 77.3910),
    ("Ghaziabad", "Uttar Pradesh", "India", 28.6692, 77.4538),
    ("Bareilly", "Uttar Pradesh", "India", 28.3670, 79.4304),
    ("Meerut", "Uttar Pradesh", "India", 28.9845, 77.7064),
    ("Pune", "Maharashtra", "India", 18.5204, 73.8567),
    ("Pimpri-Chinchwad", "Maharashtra", "India", 18.6298, 73.7997),
    ("Mumbai", "Maharashtra", "India", 19.0760, 72.8777),
    ("Lonavala", "Maharashtra", "India", 18.7557, 73.4091),
    ("Khandala", "Maharashtra", "India", 18.7612, 73.3712),
    ("Goa", "Goa", "India", 15.2993, 74.1240),
    ("Calangute", "Goa", "India", 15.5439, 73.7553),
    ("Nainital", "Uttarakhand", "India", 29.3919, 79.4542),
    ("Bhimtal", "Uttarakhand", "India", 29.3500, 79.5667),
    ("Corbett", "Uttarakhand", "India", 29.5300, 78.7747),
    ("Dehradun", "Uttarakhand", "India", 30.3165, 78.0322),
    ("Mussoorie", "Uttarakhand", "India", 30.4598, 78.0644),
    ("Rishikesh", "Uttarakhand", "India", 30.0869, 78.2676),
    ("Haridwar", "Uttarakhand", "India", 29.9457, 78.1642),

    # UAE
    ("Dubai", "Dubai", "UAE", 25.2048, 55.2708),
    ("Abu Dhabi", "Abu Dhabi", "UAE", 24.4539, 54.3773),
]

_geo_cache = {}

def get_high_precision_location(lat, lng):
    if lat is None or lng is None:
        return None
    if lat == -180.0 or lng == -180.0:
        return None
    cache_key = (round(lat, 3), round(lng, 3))
    if cache_key in _geo_cache:
        return _geo_cache[cache_key]

    R = 6371.0
    for name, region, country, clat, clng in CITIES:
        dlat = math.radians(clat - lat)
        dlng = math.radians(clng - lng)
        a = (math.sin(dlat / 2)**2 +
             math.cos(math.radians(lat)) * math.cos(math.radians(clat)) *
             math.sin(dlng / 2)**2)
        dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        if dist <= 25.0:
            res = (name, country)
            _geo_cache[cache_key] = res
            return res

    _geo_cache[cache_key] = None
    return None

def fast_chunk_hash(filepath, filesize):
    CHUNK = 65536
    try:
        if filesize == 0:
            return None
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
        return h.hexdigest()
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Ingest Apple Photos Library into Organized_Memories")
    parser.add_argument("-e", "--execute", action="store_true", help="Perform actual file moves (dry run by default)")
    args = parser.parse_args()
    execute = args.execute

    print("\n" + "=" * 65)
    print(" 🍎 INGESTING APPLE PHOTOS LIBRARY (2017–2019 RECOVERY)")
    print(f" Mode: {'ACTIVE EXECUTION' if execute else 'DRY RUN PREVIEW'}")
    print("=" * 65 + "\n")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        return

    # Step 1: Query Photos.sqlite
    print("🔍 Reading metadata from Photos.sqlite...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    COCOA_EPOCH = datetime.datetime(2001, 1, 1, 0, 0, 0)

    query = '''
    SELECT 
        a.ZFILENAME,
        att.ZORIGINALFILENAME,
        a.ZDATECREATED,
        a.ZLATITUDE,
        a.ZLONGITUDE
    FROM ZASSET a
    LEFT JOIN ZADDITIONALASSETATTRIBUTES att ON a.ZADDITIONALATTRIBUTES = att.Z_PK
    WHERE a.ZFILENAME IS NOT NULL;
    '''
    c.execute(query)
    rows = c.fetchall()
    print(f"Found {len(rows):,} mapped media records in Apple database.")

    sqlite_meta = {}
    for r in rows:
        zfilename, orig_name, cocoa_date, lat, lon = r
        dt = None
        if cocoa_date:
            dt = COCOA_EPOCH + datetime.timedelta(seconds=cocoa_date)
        sqlite_meta[zfilename] = {
            'orig_name': orig_name,
            'date': dt,
            'lat': lat if (lat and lat != -180.0) else None,
            'lon': lon if (lon and lon != -180.0) else None
        }

    # Step 2: Index current Organized_Memories for instant deduplication
    print("\n🔍 Indexing current vault files for deduplication...")
    vault_size_index = defaultdict(list)
    for root, dirs, files in os.walk(VAULT_ROOT):
        if '_Duplicates' in root:
            continue
        rel = os.path.relpath(root, VAULT_ROOT)
        for f in files:
            if not f.startswith('.'):
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    vault_size_index[sz].append(fp)
                except Exception:
                    pass

    print(f"Indexed vault sizes across {len(vault_size_index):,} unique size buckets.")

    # Step 3: Scan originals folder
    print("\n📁 Scanning originals/ directory...")
    originals_files = []
    for root, _, files in os.walk(ORIGINALS_DIR):
        for f in files:
            if not f.startswith('.'):
                ext = os.path.splitext(f)[1].upper()
                if ext != '.AAE': # Skip XML sidecars
                    fp = os.path.join(root, f)
                    originals_files.append((fp, f, ext))

    print(f"Found {len(originals_files):,} master media files in originals/.")

    # Step 4: Plan moves
    planned_moves = [] # (src, dest, is_duplicate, master_for_audit)
    duplicates_count = 0
    unique_count = 0
    screenshots_count = 0

    audit_csv_path = os.path.join(VAULT_ROOT, "duplicates_audit.csv")
    existing_duplicates = []
    if os.path.exists(audit_csv_path):
        try:
            with open(audit_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 3:
                        existing_duplicates.append(row)
        except Exception:
            pass

    for fp, zfilename, ext in tqdm(originals_files, desc="Processing Photos"):
        try:
            sz = os.path.getsize(fp)
        except Exception:
            continue

        meta = sqlite_meta.get(zfilename, {})
        dt = meta.get('date')
        if not dt:
            # Fallback to mtime
            dt = datetime.datetime.fromtimestamp(os.stat(fp).st_mtime)

        orig_name = meta.get('orig_name')
        if not orig_name:
            orig_name = zfilename # fallback to uuid

        # Check for screenshot
        is_screenshot = False
        if ext == '.PNG' or 'screenshot' in orig_name.lower():
            is_screenshot = True

        lat, lon = meta.get('lat'), meta.get('lon')
        geo = get_high_precision_location(lat, lon) if (lat and lon) else None

        # Determine target folder
        yr = str(dt.year)
        mo_str = dt.strftime('%Y-%m_%B')
        t_prefix = dt.strftime('%Y-%m-%d_%H-%M-%S')

        # Clean filename
        clean_name = f"{t_prefix}_{orig_name.lower()}"

        if is_screenshot:
            dest_dir = os.path.join(VAULT_ROOT, "_Review_Unwanted", "Screenshots", yr, mo_str)
            screenshots_count += 1
        elif geo:
            city, country = geo
            if country == 'Thailand':
                dest_dir = os.path.join(VAULT_ROOT, "Trips", "International", "Thailand", city)
            elif country == 'Mauritius':
                dest_dir = os.path.join(VAULT_ROOT, "Trips", "International", "Mauritius")
            elif country == 'India':
                if city in ['Lucknow', 'Pune', 'Varanasi', 'Goa', 'Lonavala', 'Kanpur', 'Bareilly']:
                    dest_dir = os.path.join(VAULT_ROOT, "India", city)
                elif city in ['Nainital', 'Bhimtal', 'Corbett', 'Mussoorie', 'Dehradun']:
                    dest_dir = os.path.join(VAULT_ROOT, "India", "Uttarakhand")
                elif city in ['New Delhi', 'Gurugram', 'Noida', 'Ghaziabad', 'Meerut']:
                    dest_dir = os.path.join(VAULT_ROOT, "India", "Delhi NCR")
                else:
                    dest_dir = os.path.join(VAULT_ROOT, "India", city)
            elif country == 'UAE':
                dest_dir = os.path.join(VAULT_ROOT, "Trips", "International", "Dubai")
            else:
                # UK or Home Base
                folder_loc = f"{mo_str}_{city}_{country}"
                dest_dir = os.path.join(VAULT_ROOT, yr, folder_loc)
        else:
            # Untagged
            dest_dir = os.path.join(VAULT_ROOT, yr, mo_str)

        dest_path = os.path.join(dest_dir, clean_name)

        # Check for duplicate against vault
        candidates = vault_size_index.get(sz, [])
        is_dup = False
        master_match = None
        if candidates:
            src_hash = fast_chunk_hash(fp, sz)
            for cand_fp in candidates:
                cand_hash = fast_chunk_hash(cand_fp, sz)
                if src_hash and cand_hash and src_hash == cand_hash:
                    is_dup = True
                    master_match = cand_fp
                    break

        if is_dup:
            dup_dest = os.path.join(VAULT_ROOT, "_Duplicates", "Iphone-photo", yr, clean_name)
            planned_moves.append((fp, dup_dest, True, master_match))
            duplicates_count += 1
        else:
            planned_moves.append((fp, dest_path, False, None))
            vault_size_index[sz].append(dest_path)
            unique_count += 1

    print("\n" + "=" * 65)
    print(" 📊 INGESTION MANIFEST SUMMARY")
    print("=" * 65)
    print(f"Total Photos Processed:     {len(planned_moves):,}")
    print(f"Unique Memories Recovered:  {unique_count:,}")
    print(f"Screenshots Isolated:       {screenshots_count:,}")
    print(f"Duplicates Staged:          {duplicates_count:,}")
    print("=" * 65 + "\n")

    if not execute:
        print("💡 This was a DRY RUN PREVIEW. No files were moved.")
        print("Run with -e / --execute to perform actual recovery.")
        return

    # Step 5: Execute moves
    print("🚀 Moving recovered memories into vault...")
    new_audit_rows = []
    for src, dest, is_dup, master_path in tqdm(planned_moves, desc="Moving files"):
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        final_dest = dest
        if os.path.exists(final_dest):
            base, ext = os.path.splitext(dest)
            counter = 1
            while os.path.exists(final_dest):
                final_dest = f"{base}_{counter}{ext}"
                counter += 1
        try:
            shutil.move(src, final_dest)
            if is_dup and master_path:
                sz_mb = f"{os.path.getsize(final_dest) / (1024*1024):.2f}"
                new_audit_rows.append([master_path, final_dest, sz_mb])
        except Exception as e:
            print(f"Error moving {src}: {e}")

    # Step 6: Update duplicates_audit.csv
    print("\n📝 Updating duplicates_audit.csv...")
    all_audit_rows = existing_duplicates + new_audit_rows
    with open(audit_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Master Photo in Vault", "Duplicate Photo in _Duplicates", "Size (MB)"])
        for r in all_audit_rows:
            writer.writerow(r)

    print(f"Saved {len(all_audit_rows)} total rows in {audit_csv_path}")

    # Step 7: Clean up Iphone-photo
    print("\n🧹 Cleaning up Iphone-photo package...")
    try:
        shutil.rmtree("/Volumes/DIVAKSHSSD/Iphone-photo")
        print("Removed /Volumes/DIVAKSHSSD/Iphone-photo successfully.")
    except Exception as e:
        print(f"Notice: Could not auto-delete Iphone-photo: {e}")

    print("\n🎉 APPLE PHOTOS LIBRARY RECOVERY COMPLETED SUCCESSFULLY!")

if __name__ == '__main__':
    main()
