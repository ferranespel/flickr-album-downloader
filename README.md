# Flickr Album Downloader 📸

A robust Python script to download all your Flickr photos and videos in their original quality, with intelligent rate limiting and automatic resume capability.

## ✨ Features

- **Original Quality**: Prioritizes downloading photos in their original resolution
- **Video Support**: Downloads videos in the highest available quality
- **Smart Rate Limiting**: Adaptive delays to respect Flickr's API limits
- **Auto-Resume**: Continues from the last completed album if interrupted
- **Specific Album Mode**: Download only one specific album
- **Error Reporting**: Generates detailed JSON report of failed downloads
- **Progress Tracking**: Saves progress after each album completion
- **Exponential Backoff**: Automatically handles rate limit errors (429) with intelligent retry logic
- **Detailed Logging**: Comprehensive logs for monitoring and debugging

## 📋 Requirements

- Python 3.7+
- Flickr API credentials (API Key and Secret)

## 🚀 Installation

1. Clone this repository:
```bash
git clone https://github.com/ferranespel/flickr-album-downloader.git
cd flickr-downloader
```

2. Install required packages:
```bash
pip install flickrapi python-dotenv requests tqdm
```

3. Create a `.env` file in the project root:
```env
FLICKR_API_KEY=your_api_key_here
FLICKR_API_SECRET=your_api_secret_here
FLICKR_USER_ID=your_user_id_here
BASE_DIR=/path/to/download/folder
LOG_FILE=flickr_download.log
PROGRESS_FILE=progress.json
```

## 🔑 Getting Flickr API Credentials

1. Go to [Flickr App Garden](https://www.flickr.com/services/apps/create/)
2. Click "Request an API Key"
3. Choose "Apply for a Non-Commercial Key" (or Commercial if applicable)
4. Fill in the application form
5. Copy your API Key and Secret to the `.env` file

To find your User ID:
- Visit your Flickr profile
- Use [idGettr](https://www.webfx.com/tools/idgettr/) or similar service
- Or check the URL of your photostream: `flickr.com/photos/YOUR_USER_ID`

## 💻 Usage

### Basic Usage (Download All Albums)

```bash
python3 flickr_downloader.py
```

### Download a Specific Album

Add to your `.env` file:
```env
SPECIFIC_ALBUM=Julio 2013
```

Or set it temporarily:
```bash
SPECIFIC_ALBUM="Julio 2013" python3 flickr_downloader.py
```

This is useful for:
- Re-downloading albums with errors
- Testing the script with a small album
- Updating a specific album without processing all

### Prevent System Sleep (macOS)

To ensure uninterrupted downloads on macOS:

```bash
caffeinate -dims python3 flickr_downloader.py
```

Flags explanation:
- `-d`: Prevent display from sleeping
- `-i`: Prevent system idle sleep
- `-m`: Prevent disk from sleeping
- `-s`: Prevent system sleep (even when laptop lid is closed)

### Resume After Interruption

The script automatically resumes from the last completed album. No special commands needed - just run the script again!

## ⚙️ Configuration

You can adjust the rate limiting settings in the script:

```python
DELAY_BETWEEN_DOWNLOADS = 0.8  # Seconds between downloads
DELAY_AFTER_429 = 60           # Seconds to wait after rate limit error
MAX_RETRIES_429 = 5            # Maximum retry attempts for rate limits
ADAPTIVE_DELAY = True          # Enable adaptive delay adjustment
```

### Recommended Settings

- **Fast (with good internet)**: `DELAY_BETWEEN_DOWNLOADS = 0.5`
- **Balanced (recommended)**: `DELAY_BETWEEN_DOWNLOADS = 0.8` (default)
- **Conservative**: `DELAY_BETWEEN_DOWNLOADS = 1.5`
- **Ultra-safe**: `DELAY_BETWEEN_DOWNLOADS = 3.0`

## 📊 What to Expect

For ~14,000 photos/videos across 123 albums:
- **Estimated time**: 10-13 hours (with default settings)
- **Original size priority**: Script tries 10 times for original quality
- **Fallback sizes**: Large 2048 → Large 1600 → Large → Medium 800 → Medium

## 🗂️ Output Structure

```
BASE_DIR/
├── Album Name 1/
│   ├── photo_id_Original.jpg
│   ├── photo_id_Original.png
│   └── photo_id_video_Video_Original.mp4
├── Album Name 2/
│   └── ...
├── progress.json
├── download_errors.json    # Generated if there are errors
└── flickr_download.log
```

### Error Report (download_errors.json)

After completion, check `download_errors.json` for details about failed downloads:

```json
{
  "failed_photos": [
    {
      "album": "Julio 2013",
      "photo_id": "123456789",
      "available_sizes": ["Large", "Medium"]
    }
  ],
  "failed_videos": [
    {
      "album": "Junio 2014",
      "photo_id": "987654321",
      "url": "https://...",
      "label": "Site MP4"
    }
  ],
  "no_url_videos": [
    {
      "album": "Noviembre 2012",
      "photo_id": "555555555",
      "available_sizes": ["Square", "Medium", "Original"]
    }
  ]
}
```

## 🔍 Monitoring Progress

### Check Progress File
```bash
cat progress.json
```

### Monitor Log in Real-Time
```bash
tail -f flickr_download.log
```

### Search for Failed Original Downloads
```bash
grep "FAILED to download ORIGINAL" flickr_download.log
```

## 🔄 Handling Download Errors

After a complete download run, the script generates a detailed error report that helps you identify and retry failed downloads.

### Understanding the Error Report

The script creates `download_errors.json` with three categories of errors:

#### 1. **Failed Photos** (`failed_photos`)
Photos that couldn't be downloaded in any available size.
```json
{
  "album": "Julio 2013",
  "photo_id": "123456789",
  "available_sizes": ["Large", "Medium"]
}
```
**Reason**: Usually connectivity issues or corrupted files on Flickr's servers.

#### 2. **Failed Videos** (`failed_videos`)
Videos that returned 404 errors (URL not found).
```json
{
  "album": "Junio 2014",
  "photo_id": "14727162752",
  "url": "https://live.staticflickr.com/video/...",
  "label": "Site MP4"
}
```
**Reason**: Video URLs have expired or Flickr no longer hosts these videos. Common with older videos (2012-2014).

#### 3. **Videos Without URL** (`no_url_videos`)
Videos where Flickr's API doesn't provide a download URL.
```json
{
  "album": "Noviembre 2012",
  "photo_id": "9294494487",
  "available_sizes": ["Square", "Medium", "Original"]
}
```
**Reason**: Very old videos (typically pre-2013) where Flickr's API structure has changed.

### Viewing the Error Report

```bash
# View the complete error report
cat download_errors.json

# Count errors by type
cat download_errors.json | grep -c "failed_photos"
cat download_errors.json | grep -c "failed_videos"
cat download_errors.json | grep -c "no_url_videos"

# Pretty print with Python
python3 -m json.tool download_errors.json
```

### Retrying Failed Albums

Use the **Specific Album Mode** to retry albums with errors:

#### Step 1: Identify problematic albums
```bash
# Check which albums had errors
cat download_errors.json | grep '"album"' | sort -u
```

#### Step 2: Set the album in `.env`
```env
SPECIFIC_ALBUM=Junio 2014
```

#### Step 3: Run the downloader
```bash
python3 flickr_downloader.py
```

#### Step 4: Repeat for other albums
Update `SPECIFIC_ALBUM` in `.env` and run again for each album with errors.

### Batch Retry Script

If you have many albums with errors, create a simple retry script:

```bash
#!/bin/bash
# retry_albums.sh

albums=(
    "Junio 2014"
    "Febrero 2014"
    "Diciembre 2013"
    "Noviembre 2012"
)

for album in "${albums[@]}"; do
    echo "Retrying album: $album"
    SPECIFIC_ALBUM="$album" python3 flickr_downloader.py
    sleep 10  # Wait between albums
done
```

```bash
chmod +x retry_albums.sh
./retry_albums.sh
```

### When Videos Can't Be Downloaded

Some videos (especially from 2012-2014) may be permanently unavailable:

**Options:**
1. **Accept the loss**: These videos may no longer exist on Flickr
2. **Check Flickr directly**: Log into Flickr and try downloading manually
3. **Contact Flickr Support**: Report missing videos if they should be available

**Note**: The script has already tried multiple times with exponential backoff, so if a video failed, it's likely a permanent issue on Flickr's side.

## 🛠️ Troubleshooting

### Rate Limiting (429 Errors)

If you encounter too many rate limit errors:
1. Stop the script
2. Wait 15-30 minutes
3. Increase `DELAY_BETWEEN_DOWNLOADS` to 1.5 or 2.0
4. Restart the script

### Authentication Issues

If authentication fails:
1. Check your API credentials in `.env`
2. Ensure your API key is active in Flickr App Garden
3. Try regenerating your API secret

### Empty Files (0 bytes)

The script automatically:
- Deletes 0-byte files
- Retries the download
- Falls back to smaller sizes if needed

### Videos Not Found (404 Errors)

Some old videos may return 404 errors because:
- The video URL has expired
- Flickr no longer hosts the video
- The video was deleted

**Solution**: Check `download_errors.json` to see which videos failed and try re-uploading them to Flickr or accept the loss.

### Videos Without Download URL

Very old videos (pre-2013) may not have a downloadable URL in Flickr's API. These will be logged in `download_errors.json` under `no_url_videos`.

### Re-download Failed Items

To retry failed albums:

1. Check `download_errors.json` to see which albums had errors
2. Set `SPECIFIC_ALBUM` in `.env` to that album name
3. Run the script again

```bash
# In .env
SPECIFIC_ALBUM=Julio 2013
```

```bash
python3 flickr_downloader.py
```

## 📝 Notes

- **First run**: Browser window will open for Flickr authentication
- **Progress**: Saved after each completed album
- **Interruption**: Safe to stop and resume anytime
- **Duplicates**: Script checks for existing files and skips them

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## ⚠️ Disclaimer

This tool is for personal use to backup your own Flickr content. Please respect Flickr's Terms of Service and API usage guidelines.

## 🙏 Acknowledgments

- Built with [FlickrAPI](https://stuvel.eu/flickrapi) Python library
- Progress bars by [tqdm](https://github.com/tqdm/tqdm)

---

**Star ⭐ this repository if you find it helpful!**