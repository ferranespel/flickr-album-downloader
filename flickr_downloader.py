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
                wait_time = backoff_time * (1.5 ** min(rate_limit_count, 3))  # Increases with multiple 429s
                log(f"⏸️  Rate limit #{rate_limit_count}. Waiting {wait_time:.0f}s...")
                time.sleep(wait_time)
                backoff_time *= 2  # Exponential backoff
                continue
            
            # If download was successful, reset counter
            if r.status_code == 200:
                rate_limit_count = max(0, rate_limit_count - 1)  # Gradually decrease
            
            r.raise_for_status()  # Raises exception for other HTTP errors
            
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
            # Small wait between normal attempts
            time.sleep(2)
    
    return False

def download_photo_with_fallback(photo_id, album_dir):
    """Attempts to download photo ALWAYS prioritizing Original size"""
    try:
        sizes = flickr.photos.getSizes(photo_id=photo_id)['sizes']['size']
    except Exception as e:
        log(f"❌ Error getting sizes for {photo_id}: {e}")
        return False
    
    # Priority: Original > Large 2048 > Large 1600 > Large > Medium 800 > Medium
    priority_order = ['Original', 'Large 2048', 'Large 1600', 'Large', 'Medium 800', 'Medium']
    
    for priority_index, label in enumerate(priority_order):
        # Search for size in available sizes list
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
        
        # If already exists with content, consider it successful
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            log(f"✓ Already exists: {filename}")
            return True
        
        # DELAY BEFORE each download attempt (adaptive)
        current_delay = DELAY_BETWEEN_DOWNLOADS
        if ADAPTIVE_DELAY and rate_limit_count > 0:
            current_delay *= (1 + rate_limit_count * 0.5)  # Increases delay if problems occur
        
        time.sleep(current_delay + random.uniform(0, 0.5))
        
        # For Original, try with more persistence
        max_retries = MAX_RETRIES_429 * 2 if label == 'Original' else MAX_RETRIES_429
        
        # Attempt download
        log(f"🔄 Attempting to download {photo_id} as {label}... ({max_retries} max attempts)")
        ok = download_file(url, filepath, retries=max_retries)
        
        if ok:
            size = os.path.getsize(filepath)
            log(f"⬇️ Photo downloaded: {filename} ({size} bytes)")
            return True
        else:
            # Only fallback if NOT Original OR if Original is not available
            if label == 'Original':
                log(f"⚠️ ⚠️ ⚠️ FAILED to download ORIGINAL for {photo_id} after {max_retries} attempts")
                log(f"      → Falling back to smaller sizes...")
            else:
                log(f"⚠️ Failed to download {label}, trying next size...")
            # Continue with next size in priority list
    
    # If we reach here, all sizes failed
    log(f"❌ ❌ ❌ FAILED to download photo {photo_id} in ALL available sizes")
    
    # Save log of available sizes for debugging
    available_sizes = [s['label'] for s in sizes]
    log(f"ℹ️ Available sizes for {photo_id}: {', '.join(available_sizes)}")
    
    return False

def download_video(photo_id, album_dir):
    """Downloads video from Flickr"""
    try:
        sizes = flickr.photos.getSizes(photo_id=photo_id)['sizes']['size']
        
        # Search for video size - prioritize HD/Original
        video_url = None
        video_label = None
        
        # Priority order for videos
        video_priority = ['Video Original', 'Site MP4', 'Mobile MP4', 'HD MP4', '720p', '1080p']
        
        # First search by specific labels
        for priority_label in video_priority:
            for s in sizes:
                if priority_label.lower() in s['label'].lower():
                    video_url = s.get('source')
                    video_label = s['label']
                    if video_url:
                        break
            if video_url:
                break
        
        # If not found, search for anything with "video" or "mp4"
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
            return False
        
        ext = video_url.split('?')[0].split('.')[-1]
        if not ext or len(ext) > 4:  # Validate extension
            ext = 'mp4'
        
        filename = f"{photo_id}_video_{video_label.replace(' ', '_')}.{ext}"
        filepath = os.path.join(album_dir, filename)
        
        # If already exists with content, consider it successful
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            log(f"✓ Already exists: {filename}")
            return True
        
        # DELAY before downloading video (adaptive)
        current_delay = DELAY_BETWEEN_DOWNLOADS
        if ADAPTIVE_DELAY and rate_limit_count > 0:
            current_delay *= (1 + rate_limit_count * 0.5)
        
        time.sleep(current_delay + random.uniform(0, 0.5))
        
        log(f"🔄 Attempting to download video {photo_id} as {video_label}...")
        ok = download_file(video_url, filepath, retries=MAX_RETRIES_429 * 2)  # More attempts for videos
        
        if ok:
            size = os.path.getsize(filepath)
            log(f"⬇️ Video downloaded: {filename} ({size} bytes)")
            return True
        else:
            log(f"❌ Failed to download video: {photo_id}")
            return False
            
    except Exception as e:
        log(f"❌ Error downloading video {photo_id}: {e}")
        return False

# ---------------- DOWNLOAD ----------------
skip = True if progress.get("last_album") else False

log(f"⏱️  Configuration: {DELAY_BETWEEN_DOWNLOADS}s between downloads, {DELAY_AFTER_429}s after 429")

for album in albums:
    album_title = album['title']['_content']
    album_id = album['id']
    album_dir = os.path.join(BASE_DIR, album_title)
    os.makedirs(album_dir, exist_ok=True)

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
                download_photo_with_fallback(photo_id, album_dir)
            elif media_type == 'video':
                download_video(photo_id, album_dir)
            else:
                log(f"❌ Unsupported media type: {media_type} ({photo_id})")

        if page >= response['photoset']['pages']:
            break
        page += 1

    save_progress(album_title)
    log(f"✅ Album completed: {album_title}")

log("🏁 Download completed from last album.")