# 🎉 YouTube Extractor v1.0.6 — Instagram & Multi-Platform Fix

## 🐛 Bug Fixes

- **Fix crash on Instagram Reels download** — `argument of type 'NoneType' is not iterable` error is now fixed
- **Fix NoneType errors** across all download functions (`get_video_info`, `get_available_formats`, `download_media`)
- **Fix Chrome cookie loading crash** — the app no longer crashes when Chrome is open; cookies are loaded gracefully when available

## ✨ Improvements

- **Better Instagram support** — added proper User-Agent and Instagram-specific extractor options
- **Twitter/X support improved** — added platform-specific options for better extraction
- **Multi-platform URL handling** — playlist URLs now use the correct platform URL instead of hardcoded YouTube URLs
- **Requires yt-dlp 2026.7+** for full Instagram Reels compatibility

## ⚠️ Important

- For best results with Instagram private content, close Chrome before downloading so the app can read your cookies
- Public Instagram Reels work without any authentication
- Make sure to update yt-dlp: `pip install --upgrade yt-dlp`
