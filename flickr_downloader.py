import os
import flickrapi
import logging
import json
from tqdm import tqdm
from dotenv import load_dotenv
import requests
from datetime import datetime
import time
import random

# ---------------- LOAD ENVIRONMENT VARIABLES ----------------
load_dotenv()

API_KEY = os.getenv("FLICKR_API_KEY")
API_SECRET = os.getenv("FLICKR_API_SECRET")
USER_ID = os.getenv("FLICKR_USER_ID")

BASE_DIR = os.getenv("BASE_DIR")
LOG_FILE = os.path.join(BASE_DIR, os.getenv("LOG_FILE"))
PROGRESS_FILE = os.path.join(BASE_DIR, os.getenv("PROGRESS_FILE"))
ERRORS_FILE = os.path.join(BASE_DIR, "download_errors.json")

# Specific album mode (optional - leave empty to download all albums)
SPECIFIC_ALBUM = os.getenv("SPECIFIC_ALBUM", "")  # e.g., "Julio 2013"

# Rate limiting configuration
DELAY_BETWEEN_DOWNLOADS = 0.8  # seconds between downloads (more aggressive)
DELAY_AFTER_429 = 60  # seconds to wait if we receive 429 (more conservative)
MAX_RETRIES_429 = 5  # maximum attempts for 429 errors
ADAPTIVE_DELAY = True  # If True, increases delay after multiple 429s

# Global counter for adaptive adjustment
rate_limit_count = 0

# Error tracking
download_errors = {
    "failed_photos": [],
    "failed_videos": [],
    "no_url_videos": []
}

os.makedirs(BASE_DIR, exist_ok=True)

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename=LOG_FILE,
    filemode='w',
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
)

def log(msg):
    print(msg)
    logging.info(msg)

# ---------------- PROGRESS TRACKING ----------------
progress = {"last_album": None}
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE) as f:
        try:
            progress.update(json.load(f))
        except Exception:
            pass

def save_progress(last_album):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({"last_album": last_album}, f, indent=2)
    log(f"💾 Progress updated: {last_album}")

def save_errors():
    """Save error report to JSON file"""
    with open(ERRORS_FILE, 'w') as f:
        json.dump(download_errors, f, indent=2)
    
    # Print summary
    total_errors = (len(download_errors['failed_photos']) + 
                   len(download_errors['failed_videos']) + 
                   len(download_errors['no_url_videos']))
    
    if total_errors > 0:
        log(f"\n📊 ERROR SUMMARY:")
        log(f"  ❌ Failed photos: {len(download_errors['failed_photos'])}")
        log(f"  ❌ Failed videos (404): {len(download_errors['failed_videos'])}")
        log(f"  ⚠️  Videos without URL: {len(download_errors['no_url_videos'])}")
        log(f"  📄 Full report saved to: {ERRORS_FILE}")
    else:
        log(f"✅ No errors! All files downloaded successfully.")

# ---------------- AUTHENTICATION ----------------
flickr = flickrapi.FlickrAPI(API_KEY, API_SECRET, format='parsed-json')
flickr.authenticate_via_browser(perms='read')
log("🔑 Authentication completed.")

# ---------------- GET ALBUMS ----------------
albums = flickr.photosets.getList(user_id=USER_ID)['photosets']['photoset']
log(f"📚 Total albums: {len(albums)}")
for i, a in enumerate(albums):
    readable_date = datetime.fromtimestamp(int(a['date_create'])).strftime('%d/%m/%Y')
    log(f"{i+1}: {a['title']['_content']} (ID: {a['id']}, Date: {readable_date})")

# ---------------- HELPER FUNCTIONS ----------------
def download_file(url, path, retries=3):
    """Downloads file with adaptive rate limiting handling"""
    global rate_limit_count
    backoff_time = DELAY_AFTER_429
    
    for attempt in range(retries):
        try:
            r = requests.get(url, stream=True, timeout=60)
            
            # If we receive 429, wait and retry
            if r.status_code == 429:
                rate_limit_count += 1
                wait_time = backoff_time * (1.5 ** min(rate_limit_count, 3))
                log(f"⏸️  Rate limit #{rate_limit_count}. Waiting {wait_time:.0f}s...")
                time.sleep(wait_time)
                backoff_time *= 2
                continue
            
            # If download was successful, reset counter
            if r.status_code == 200:
                rate_limit_count = max(0, rate_limit_count - 1)
            
            r.raise_for_status()
            
            with open(path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    if chunk:
                        f.write(chunk)
            
            size = os.path.getsize(path)
            if size > 0:
                return True
            else:
                log(f"⚠️ File 0 bytes (attempt {attempt+1}/{retries}): {path}")
                if os.path.exists(path):
                    os.remove(path)
        except requests.exceptions.HTTPError as e:
            if '429' in str(e):
                rate_limit_count += 1
                wait_time = backoff_time * (1.5 ** min(rate_limit_count, 3))
                log(f"⏸️  Rate limit #{rate_limit_count} on attempt {attempt+1}. Waiting {wait_time:.0f}s...")
                time.sleep(wait_time)
                backoff_time *= 2
            else:
                log(f"❌ HTTP error downloading (attempt {attempt+1}/{retries}): {e}")
        except Exception as e:
            log(f"❌ Error downloading {path} (attempt {attempt+1}/{retries}): {e}")
            if os.path.exists(path):
                os.remove(path)
        
        if attempt < retries - 1:
            time.sleep(2)
    
    return False

def download_photo_with_fallback(photo_id, album_dir, album_title):
    """Attempts to download photo ALWAYS prioritizing Original size"""
    try:
        sizes = flickr.photos.getSizes(photo_id=photo_id)['sizes']['size']
    except Exception as e:
        log(f"❌ Error getting sizes for {photo_id}: {e}")
        download_errors['failed_photos'].append({
            "album": album_title,
            "photo_id": photo_id,
            "error": str(e)
        })
        return False
    
    priority_order = ['Original', 'Large 2048', 'Large 1600', 'Large', 'Medium 800', 'Medium']
    
    for priority_index, label in enumerate(priority_order):
        matching_size = None
        for s in sizes:
            if s['label'] == label and s.get('source'):
                matching_size = s
                break
        
        if not matching_size:
            if label == 'Original':
                log(f"⚠️ Original size NOT available for {photo_id}")
            continue
        
        url = matching_size['source']
        ext = url.split('?')[0].split('.')[-1]
        filename = f"{photo_id}_{label.replace(' ', '_')}.{ext}"
        filepath = os.path.join(album_dir, filename)
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            log(f"✓ Already exists: {filename}")
            return True
        
        current_delay = DELAY_BETWEEN_DOWNLOADS
        if ADAPTIVE_DELAY and rate_limit_count > 0:
            current_delay *= (1 + rate_limit_count * 0.5)
        
        time.sleep(current_delay + random.uniform(0, 0.5))
        
        max_retries = MAX_RETRIES_429 * 2 if label == 'Original' else MAX_RETRIES_429
        
        log(f"🔄 Attempting to download {photo_id} as {label}... ({max_retries} max attempts)")
        ok = download_file(url, filepath, retries=max_retries)
        
        if ok:
            size = os.path.getsize(filepath)
            log(f"⬇️ Photo downloaded: {filename} ({size} bytes)")
            return True
        else:
            if label == 'Original':
                log(f"⚠️ ⚠️ ⚠️ FAILED to download ORIGINAL for {photo_id} after {max_retries} attempts")
                log(f"      → Falling back to smaller sizes...")
            else:
                log(f"⚠️ Failed to download {label}, trying next size...")
    
    log(f"❌ ❌ ❌ FAILED to download photo {photo_id} in ALL available sizes")
    
    available_sizes = [s['label'] for s in sizes]
    log(f"ℹ️ Available sizes for {photo_id}: {', '.join(available_sizes)}")
    
    download_errors['failed_photos'].append({
        "album": album_title,
        "photo_id": photo_id,
        "available_sizes": available_sizes
    })
    
    return False

def download_video(photo_id, album_dir, album_title):
    """Downloads video from Flickr"""
    try:
        sizes = flickr.photos.getSizes(photo_id=photo_id)['sizes']['size']
        
        video_url = None
        video_label = None
        
        video_priority = ['Video Original', 'Site MP4', 'Mobile MP4', 'HD MP4', '720p', '1080p']
        
        for priority_label in video_priority:
            for s in sizes:
                if priority_label.lower() in s['label'].lower():
                    video_url = s.get('source')
                    video_label = s['label']
                    if video_url:
                        break
            if video_url:
                break
        
        if not video_url:
            for s in sizes:
                label_lower = s['label'].lower()
                if 'video' in label_lower or 'mp4' in label_lower:
                    video_url = s.get('source')
                    video_label = s['label']
                    if video_url:
                        break
        
        if not video_url:
            log(f"❌ No video URL found for {photo_id}")
            log(f"ℹ️ Available sizes: {', '.join([s['label'] for s in sizes])}")
            download_errors['no_url_videos'].append({
                "album": album_title,
                "photo_id": photo_id,
                "available_sizes": [s['label'] for s in sizes]
            })
            return False
        
        ext = video_url.split('?')[0].split('.')[-1]
        if not ext or len(ext) > 4:
            ext = 'mp4'
        
        filename = f"{photo_id}_video_{video_label.replace(' ', '_')}.{ext}"
        filepath = os.path.join(album_dir, filename)
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            log(f"✓ Already exists: {filename}")
            return True
        
        current_delay = DELAY_BETWEEN_DOWNLOADS
        if ADAPTIVE_DELAY and rate_limit_count > 0:
            current_delay *= (1 + rate_limit_count * 0.5)
        
        time.sleep(current_delay + random.uniform(0, 0.5))
        
        log(f"🔄 Attempting to download video {photo_id} as {video_label}...")
        ok = download_file(video_url, filepath, retries=MAX_RETRIES_429 * 2)
        
        if ok:
            size = os.path.getsize(filepath)
            log(f"⬇️ Video downloaded: {filename} ({size} bytes)")
            return True
        else:
            log(f"❌ Failed to download video: {photo_id}")
            download_errors['failed_videos'].append({
                "album": album_title,
                "photo_id": photo_id,
                "url": video_url,
                "label": video_label
            })
            return False
            
    except Exception as e:
        log(f"❌ Error downloading video {photo_id}: {e}")
        download_errors['failed_videos'].append({
            "album": album_title,
            "photo_id": photo_id,
            "error": str(e)
        })
        return False

# ---------------- DOWNLOAD ----------------
skip = True if (progress.get("last_album") and not SPECIFIC_ALBUM) else False

log(f"⏱️  Configuration: {DELAY_BETWEEN_DOWNLOADS}s between downloads, {DELAY_AFTER_429}s after 429")

if SPECIFIC_ALBUM:
    log(f"🎯 SPECIFIC ALBUM MODE: Will only download '{SPECIFIC_ALBUM}'")

for album in albums:
    album_title = album['title']['_content']
    album_id = album['id']
    album_dir = os.path.join(BASE_DIR, album_title)
    os.makedirs(album_dir, exist_ok=True)

    # If specific album mode, skip all others
    if SPECIFIC_ALBUM and album_title != SPECIFIC_ALBUM:
        continue

    if skip:
        if album_title == progress["last_album"]:
            skip = False
        log(f"⏩ Skipping completed album: {album_title}")
        continue

    log(f"📁 Processing album: {album_title}")

    page = 1
    per_page = 500
    while True:
        response = flickr.photosets.getPhotos(photoset_id=album_id, user_id=USER_ID, page=page, per_page=per_page)
        items = response['photoset']['photo']
        if not items:
            break

        for item in tqdm(items, desc=f"Downloading: {album_title}", unit="file"):
            photo_id = item['id']
            
            try:
                media_type = flickr.photos.getInfo(photo_id=photo_id)['photo']['media']
            except Exception as e:
                log(f"❌ Error getting info for {photo_id}: {e}")
                continue

            if media_type == 'photo':
                download_photo_with_fallback(photo_id, album_dir, album_title)
            elif media_type == 'video':
                download_video(photo_id, album_dir, album_title)
            else:
                log(f"❌ Unsupported media type: {media_type} ({photo_id})")

        if page >= response['photoset']['pages']:
            break
        page += 1

    save_progress(album_title)
    log(f"✅ Album completed: {album_title}")
    
    # If specific album mode, exit after completing it
    if SPECIFIC_ALBUM:
        break

# Save error report at the end
save_errors()

log("🏁 Download completed from last album.")