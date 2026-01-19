# Release Notes - YouTube Extractor v1.0.5

## 🗓️ Release Date: January 19, 2026

---

## 🐛 Bug Fixes

### 1. Playlist Display Limit Removed
- **Problem**: Playlists were limited to showing only 50 videos
- **Solution**: Removed the arbitrary 50-video limit. Now all videos in a playlist are displayed regardless of size
- **Impact**: Users can now see and download entire playlists with hundreds of videos

### 2. Improved Download Reliability
- **Problem**: Some videos were failing with "Could not fetch video info (invalid URL?)" errors
- **Solution**: 
  - Added retry logic (3 attempts) for video info extraction
  - Enhanced yt-dlp options for better compatibility:
    - Increased retries from 3 to 5 for downloads
    - Added geo-bypass support (US)
    - Added age-restriction bypass
    - Added browser cookie support (Chrome) for restricted content
    - Increased socket timeout to 30 seconds
    - Optimized HTTP chunk size for better performance
- **Impact**: Significantly fewer download failures, especially for:
  - Age-restricted videos
  - Region-locked content
  - Videos that require authentication

---

## 📋 Technical Changes

| File | Changes |
|------|---------|
| `app.py` | Removed `[:50]` limit on playlist videos (line 292) |
| `app.py` | Added playlist extraction options: `playliststart`, `playlistend`, `ignoreerrors` |
| `app.py` | Added retry loop with 3 attempts for video info extraction |
| `app.py` | Enhanced yt-dlp options: `geo_bypass`, `age_limit`, `cookiesfrombrowser`, `socket_timeout` |

---

## 🔄 Upgrade Instructions

1. Download the new `YouTubeExtractor.exe` from the releases page
2. Replace your existing executable
3. Restart the application

The application should also prompt you to update automatically if you have the previous version running.

---

## ⚠️ Notes

- The browser cookie support uses Chrome cookies by default (if Chrome is installed)
- For maximum compatibility with restricted videos, ensure you're logged into YouTube in Chrome
