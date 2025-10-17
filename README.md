# Flickr Album Downloader 📸

A robust Python script to download all your Flickr photos and videos in their original quality, with intelligent rate limiting and automatic resume capability.

## ✨ Features

- **Original Quality**: Prioritizes downloading photos in their original resolution
- **Video Support**: Downloads videos in the highest available quality
- **Smart Rate Limiting**: Adaptive delays to respect Flickr's API limits
- **Auto-Resume**: Continues from the last completed album if interrupted
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

### Basic Usage

```bash
python3 flickr_downloader.py
```

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
└── flickr_download.log
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