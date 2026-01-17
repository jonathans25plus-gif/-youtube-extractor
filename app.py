"""
YouTube Media Extractor - Advanced Web Application
Extracts audio/video from YouTube with queue, search, and modern features
Created by Jonathan Paul & Antigravity
"""

import os
import re
import json
import sys
import threading
import uuid
import shutil
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future
from flask import Flask, render_template, request, jsonify

import yt_dlp

# ============== SETUP FFMPEG PATH ==============
# This must be done before anything else tries to use ffmpeg
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    base_path = sys._MEIPASS
    bin_path = os.path.join(base_path, 'bin')
    # Add bin folder to PATH so shutil.which and yt-dlp can find ffmpeg
    if os.path.exists(bin_path):
        os.environ["PATH"] += os.pathsep + bin_path

# ============== APP VERSION & UPDATE CONFIG ==============
APP_VERSION = "1.0.2"
GITHUB_REPO = "jonathans25plus-gif/-youtube-extractor"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Try to import optional dependencies
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
    toaster = ToastNotifier()
except ImportError:
    TOAST_AVAILABLE = False

app = Flask(__name__)

# Configuration
DEFAULT_DOWNLOAD_FOLDER = str(Path.home() / "Downloads" / "YouTube Media")
HISTORY_FILE = Path(__file__).parent / "history.json"
MAX_PARALLEL_DOWNLOADS = 3

# Global state
download_queue = []  # List of pending downloads
active_downloads = {}  # task_id -> download info
download_history = []  # Completed downloads
cancel_flags = {}  # task_id -> bool (if True, cancel requested)
executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL_DOWNLOADS)

# Lock for thread-safe operations
queue_lock = threading.Lock()


# ============== HELPER FUNCTIONS ==============

def get_ffmpeg_path():
    """Get absolute path to ffmpeg binary"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    bin_path = os.path.join(base_path, 'bin')
    ffmpeg_exe = os.path.join(bin_path, 'ffmpeg.exe')
    
    if os.path.exists(ffmpeg_exe):
        return bin_path
    return None

def log_error(error_msg):
    """Log error to file"""
    try:
        log_file = os.path.join(DEFAULT_DOWNLOAD_FOLDER, 'errors.log')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {error_msg}\n")
    except:
        pass


def load_history():
    """Load download history from JSON file"""
    global download_history
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                download_history = json.load(f)
    except Exception:
        download_history = []


def save_history():
    """Save download history to JSON file"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(download_history[:100], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def send_notification(title, message):
    """Send Windows notification (safely isolated to prevent WNDPROC errors)"""
    if not TOAST_AVAILABLE:
        return
    
    def _safe_notify():
        try:
            # Create a new notifier instance for each notification
            # to avoid threading issues with PyWebView
            from win10toast import ToastNotifier
            notifier = ToastNotifier()
            notifier.show_toast(title, message, duration=5, threaded=False)
        except Exception:
            # Silently ignore notification errors
            pass
    
    # Run in a completely isolated daemon thread
    try:
        thread = threading.Thread(target=_safe_notify, daemon=True)
        thread.start()
    except Exception:
        pass


def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)


def detect_url_type(url):
    """Detect the type and platform of media URL"""
    url = url.strip().lower()
    
    # Platform detection
    platform_patterns = {
        'youtube': r'(?:youtube\.com|youtu\.be)',
        'tiktok': r'(?:tiktok\.com|vm\.tiktok\.com)',
        'soundcloud': r'soundcloud\.com',
        'vimeo': r'vimeo\.com',
        'dailymotion': r'(?:dailymotion\.com|dai\.ly)',
        'instagram': r'(?:instagram\.com|instagr\.am)',
        'twitter': r'(?:twitter\.com|x\.com)',
    }
    
    platform = 'unknown'
    for plat, pattern in platform_patterns.items():
        if re.search(pattern, url):
            platform = plat
            break
    
    # YouTube-specific patterns
    youtube_patterns = {
        'short': r'(?:youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        'video': r'(?:youtube\.com/watch\?v=|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        'playlist': r'youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
        'channel': r'youtube\.com/(?:c/|channel/|@)([a-zA-Z0-9_-]+)',
        'live': r'youtube\.com/live/([a-zA-Z0-9_-]{11})',
    }
    
    if platform == 'youtube':
        for url_type, pattern in youtube_patterns.items():
            match = re.search(pattern, url)
            if match:
                return {'type': url_type, 'id': match.group(1), 'platform': 'youtube'}
    
    # For other platforms, just return the platform
    return {'type': 'video', 'id': None, 'platform': platform}


def add_id3_tags(mp3_path, title, artist, thumbnail_url=None):
    """Add ID3 tags to MP3 file"""
    if not MUTAGEN_AVAILABLE:
        return
    
    try:
        try:
            audio = MP3(mp3_path, ID3=ID3)
        except ID3NoHeaderError:
            audio = MP3(mp3_path)
            audio.add_tags()
        
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(TALB(encoding=3, text="YouTube Download"))
        
        # Download and embed thumbnail
        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url, timeout=10)
                if response.status_code == 200:
                    audio.tags.add(APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,
                        desc='Cover',
                        data=response.content
                    ))
            except Exception:
                pass
        
        audio.save()
    except Exception:
        pass


def format_duration(seconds):
    """Format duration in seconds to mm:ss or hh:mm:ss"""
    if not seconds:
        return "Unknown"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_size(bytes_size):
    """Format bytes to human readable size"""
    if not bytes_size:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def get_video_info(url):
    """Get video/playlist information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
    }
    
    # Explicitly set ffmpeg location
    ffmpeg_loc = get_ffmpeg_path()
    if ffmpeg_loc:
        ydl_opts['ffmpeg_location'] = ffmpeg_loc
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                # It's a playlist
                videos = []
                for entry in info.get('entries', []):
                    if entry:
                        video_id = entry.get('id', '')
                        videos.append({
                            'id': video_id,
                            'title': entry.get('title', 'Unknown'),
                            'duration': entry.get('duration', 0),
                            'thumbnail': entry.get('thumbnail', ''),
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                        })
                return {
                    'type': 'playlist',
                    'title': info.get('title', 'Playlist'),
                    'count': len(videos),
                    'videos': videos[:50],
                    'uploader': info.get('uploader', 'Unknown'),
                }
            else:
                # Single video
                return {
                    'type': 'video',
                    'id': info.get('id', ''),
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'formats': get_available_formats(info),
                    'url': info.get('webpage_url') or info.get('url', ''),
                }
    except Exception as e:
        log_error(f"Error getting video info: {str(e)}")
        return {'error': str(e)}


def get_available_formats(info):
    """Extract available formats from video info"""
    formats = []
    seen_qualities = set()
    
    for f in info.get('formats', []):
        if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
            height = f.get('height', 0)
            if height and height not in seen_qualities:
                seen_qualities.add(height)
                formats.append({
                    'quality': f'{height}p',
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext', 'mp4'),
                    'filesize': f.get('filesize', 0),
                })
    
    formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
    return formats[:6]


def search_media(query, platform='youtube', max_results=50):
    """Search for videos/tracks using yt-dlp library with thread isolation"""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
    
    def _do_search():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
        }
        
        # Explicitly set ffmpeg location
        ffmpeg_loc = get_ffmpeg_path()
        if ffmpeg_loc:
            ydl_opts['ffmpeg_location'] = ffmpeg_loc
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Build search query based on platform
            if platform == 'soundcloud':
                search_query = f'scsearch{max_results}:{query}'
            elif platform == 'dailymotion':
                search_query = f'dmsearch{max_results}:{query}'
            else:  # Default to YouTube
                search_query = f'ytsearch{max_results}:{query}'
            
            results = ydl.extract_info(search_query, download=False)
            
            if not results:
                return []
            
            videos = []
            entries = results.get('entries', [])
            
            for entry in entries:
                if entry:
                    video_id = entry.get('id', '')
                    title = entry.get('title', '')
                    
                    if video_id and title:
                        # Build URL based on platform
                        if platform == 'soundcloud':
                            url = entry.get('webpage_url') or entry.get('url', '')
                            thumbnail = entry.get('thumbnail', '')
                        else:
                            url = f"https://www.youtube.com/watch?v={video_id}"
                            thumbnail = entry.get('thumbnail') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                        
                        videos.append({
                            'id': video_id,
                            'title': title,
                            'duration': entry.get('duration', 0),
                            'duration_formatted': format_duration(entry.get('duration', 0)),
                            'thumbnail': thumbnail,
                            'uploader': entry.get('uploader') or entry.get('channel') or 'Unknown',
                            'url': url,
                            'platform': platform,
                        })
            return videos
    
    try:
        # Execute in isolated thread to avoid Flask context issues
        with ThreadPoolExecutor(max_workers=1) as search_executor:
            future = search_executor.submit(_do_search)
            videos = future.result(timeout=120)
            return {'results': videos, 'total': len(videos)}
    except FuturesTimeoutError:
        return {'error': 'Search timeout', 'results': [], 'total': 0}
    except Exception as e:
        log_error(f"Search error: {str(e)}")
        return {'error': str(e), 'results': [], 'total': 0}


# Keep old function name for compatibility
def search_youtube(query, max_results=50):
    return search_media(query, 'youtube', max_results)


def update_queue_item_status(task_id, status):
    """Update the status of a queue item by its task_id"""
    with queue_lock:
        for item in download_queue:
            if item.get('task_id') == task_id:
                item['status'] = status
                break


def download_media(task_id, url, output_folder, format_type='audio', quality='best', normalize_volume=False):
    """Download media from YouTube URL"""
    global active_downloads, download_history
    
    if cancel_flags.get(task_id):
        active_downloads[task_id]['status'] = 'cancelled'
        update_queue_item_status(task_id, 'cancelled')
        return
    
    os.makedirs(output_folder, exist_ok=True)
    
    def progress_hook(d):
        if cancel_flags.get(task_id):
            raise Exception("Download cancelled by user")
        
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            percent = (downloaded / total * 100) if total > 0 else 0
            
            active_downloads[task_id].update({
                'status': 'downloading',
                'percent': round(percent, 1),
                'speed': format_size(d.get('speed', 0)) + '/s' if d.get('speed') else '',
                'eta': d.get('eta', 0),
                'downloaded': format_size(downloaded),
                'total': format_size(total),
                'current_title': d.get('info_dict', {}).get('title', 'Unknown'),
            })
            
        elif d['status'] == 'finished':
            active_downloads[task_id]['status'] = 'processing'
            active_downloads[task_id]['percent'] = 100
    
    # Configure yt-dlp options
    if format_type == 'audio':
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': quality if quality in ['mp3', 'm4a', 'flac', 'wav'] else 'mp3',
            'preferredquality': '0',
        }]
        
        # Add volume normalization if requested
        if normalize_volume:
            postprocessors.append({
                'key': 'FFmpegMetadata',
            })
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': postprocessors,
            'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),
        }
        
        # Add FFmpeg postprocessor args for volume normalization
        if normalize_volume:
            ydl_opts['postprocessor_args'] = {
                'ffmpeg': ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
            }
    else:
        # Video download
        format_str = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]' if quality != 'best' else 'bestvideo+bestaudio/best'
        ydl_opts = {
            'format': format_str,
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),
        }
    
    # Explicitly set ffmpeg location
    ffmpeg_loc = get_ffmpeg_path()
    if ffmpeg_loc:
        ydl_opts['ffmpeg_location'] = ffmpeg_loc
    
    ydl_opts.update({
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'continuedl': True,  # Resume downloads
        'retries': 3,
        'fragment_retries': 3,
    })
    
    active_downloads[task_id] = {
        'status': 'starting',
        'percent': 0,
        'files': [],
        'errors': [],
        'completed': 0,
        'total': 1,
        'format_type': format_type,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Check for cancellation before starting download
            if cancel_flags.get(task_id):
                active_downloads[task_id]['status'] = 'cancelled'
                update_queue_item_status(task_id, 'cancelled')
                return

            # Extract info first
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                raise Exception("Could not fetch video info (invalid URL?)")

            if 'entries' in info:
                total = len([e for e in info.get('entries', []) if e])
                active_downloads[task_id]['total'] = total
            
            result = ydl.extract_info(url, download=True)
            
            if cancel_flags.get(task_id):
                active_downloads[task_id]['status'] = 'cancelled'
                update_queue_item_status(task_id, 'cancelled')
                return
            
            # Process results
            entries = result.get('entries', [result]) if 'entries' in result else [result]
            
            for entry in entries:
                if entry:
                    filename = ydl.prepare_filename(entry)
                    
                    if format_type == 'audio':
                        ext = quality if quality in ['mp3', 'm4a', 'flac', 'wav'] else 'mp3'
                        final_filename = os.path.splitext(filename)[0] + f'.{ext}'
                    else:
                        final_filename = os.path.splitext(filename)[0] + '.mp4'
                    
                    if os.path.exists(final_filename):
                        # Add ID3 tags for audio
                        if format_type == 'audio' and final_filename.endswith('.mp3'):
                            add_id3_tags(
                                final_filename,
                                entry.get('title', 'Unknown'),
                                entry.get('uploader', 'Unknown'),
                                entry.get('thumbnail')
                            )
                        
                        file_info = {
                            'title': entry.get('title', 'Unknown'),
                            'path': final_filename,
                            'duration': entry.get('duration', 0),
                            'size': os.path.getsize(final_filename),
                        }
                        active_downloads[task_id]['files'].append(file_info)
                        
                        # Add to history
                        history_entry = {
                            'title': entry.get('title', 'Unknown'),
                            'path': final_filename,
                            'duration': format_duration(entry.get('duration', 0)),
                            'date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                            'type': format_type,
                            'size': format_size(os.path.getsize(final_filename)),
                        }
                        with queue_lock:
                            download_history.insert(0, history_entry)
                            download_history[:] = download_history[:100]
                        save_history()
                    
                    active_downloads[task_id]['completed'] += 1
        
        active_downloads[task_id]['status'] = 'completed'
        update_queue_item_status(task_id, 'completed')
        
        # Send notification
        file_count = len(active_downloads[task_id]['files'])
        send_notification(
            "Téléchargement terminé ✓",
            f"{file_count} fichier(s) téléchargé(s)"
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        log_error(f"Download error for {url}: {error_details}")
        
        if 'cancelled' in str(e).lower():
            active_downloads[task_id]['status'] = 'cancelled'
            update_queue_item_status(task_id, 'cancelled')
        else:
            active_downloads[task_id]['status'] = 'error'
            active_downloads[task_id]['error'] = str(e)
            update_queue_item_status(task_id, 'error')


# Flask Routes

@app.route('/')
def index():
    return render_template('index.html', default_folder=DEFAULT_DOWNLOAD_FOLDER)


@app.route('/api/info', methods=['POST'])
def get_info():
    """Get video/playlist information"""
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Detect URL type
    url_info = detect_url_type(url)
    
    info = get_video_info(url)
    
    if 'error' in info:
        return jsonify(info), 400
    
    # Format durations
    if info.get('type') == 'video':
        info['duration_formatted'] = format_duration(info.get('duration', 0))
        info['url_type'] = url_info['type']
    elif info.get('type') == 'playlist':
        for video in info.get('videos', []):
            video['duration_formatted'] = format_duration(video.get('duration', 0))
    
    return jsonify(info)


@app.route('/api/search', methods=['GET'])
def search():
    """Search media with pagination support"""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', '1')
    platform = request.args.get('platform', 'youtube').strip()
    
    try:
        page = max(1, int(page))
    except ValueError:
        page = 1
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Results per page
    per_page = 10
    
    try:
        results = search_media(query, platform)
        all_results = results.get('results', [])
        total = len(all_results)
        
        # Calculate pagination
        total_pages = (total + per_page - 1) // per_page  # Ceiling division
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_results = all_results[start_idx:end_idx]
        
        return jsonify({
            'results': paginated_results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'results': [], 'total': 0})


@app.route('/api/download', methods=['POST'])
def start_download():
    """Start downloading media"""
    data = request.json
    url = data.get('url', '').strip()
    output_folder = data.get('folder', DEFAULT_DOWNLOAD_FOLDER).strip()
    format_type = data.get('format', 'audio')  # 'audio' or 'video'
    quality = data.get('quality', 'mp3')  # For audio: mp3, m4a, flac, wav / For video: 720, 1080, etc.
    normalize_volume = data.get('normalize', False)  # Volume normalization
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    task_id = str(uuid.uuid4())
    cancel_flags[task_id] = False
    
    # Submit download task to thread pool
    executor.submit(download_media, task_id, url, output_folder, format_type, quality, normalize_volume)
    
    return jsonify({'task_id': task_id, 'status': 'started'})


@app.route('/api/queue/add', methods=['POST'])
def add_to_queue():
    """Add item to download queue"""
    data = request.json
    
    queue_item = {
        'id': str(uuid.uuid4()),
        'url': data.get('url', '').strip(),
        'title': data.get('title', 'Unknown'),
        'thumbnail': data.get('thumbnail', ''),
        'format': data.get('format', 'audio'),
        'quality': data.get('quality', 'mp3'),
        'normalize': data.get('normalize', False),
        'status': 'pending',
        'added_at': datetime.now().isoformat(),
    }
    
    with queue_lock:
        download_queue.append(queue_item)
    
    return jsonify({'success': True, 'item': queue_item})


@app.route('/api/queue', methods=['GET'])
def get_queue():
    """Get download queue"""
    return jsonify({'queue': download_queue})


@app.route('/api/queue/<item_id>', methods=['DELETE'])
def remove_from_queue(item_id):
    """Remove item from queue"""
    with queue_lock:
        download_queue[:] = [item for item in download_queue if item['id'] != item_id]
    return jsonify({'success': True})


@app.route('/api/queue/start', methods=['POST'])
def start_queue():
    """Start processing the download queue"""
    results = []
    
    with queue_lock:
        pending_items = [item for item in download_queue if item['status'] == 'pending']
    
    for item in pending_items:
        task_id = str(uuid.uuid4())
        cancel_flags[task_id] = False
        
        item['status'] = 'downloading'
        item['task_id'] = task_id
        
        executor.submit(
            download_media, 
            task_id, 
            item['url'], 
            DEFAULT_DOWNLOAD_FOLDER,
            item['format'],
            item['quality'],
            item.get('normalize', False)
        )
        
        results.append({'item_id': item['id'], 'task_id': task_id})
    
    return jsonify({'started': results})


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """Get download progress"""
    if task_id not in active_downloads:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify(active_downloads[task_id])


@app.route('/api/cancel/<task_id>', methods=['POST'])
def cancel_download(task_id):
    """Cancel a download"""
    cancel_flags[task_id] = True
    return jsonify({'success': True, 'message': 'Cancel requested'})


@app.route('/api/history')
def get_history():
    """Get download history"""
    return jsonify(download_history)


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    """Clear download history"""
    global download_history
    download_history = []
    save_history()
    return jsonify({'success': True})


@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    """Open folder in file explorer"""
    data = request.json
    folder = data.get('folder', DEFAULT_DOWNLOAD_FOLDER)
    
    if os.path.exists(folder):
        os.startfile(folder)
        return jsonify({'success': True})
    
    return jsonify({'error': 'Folder does not exist'}), 400


@app.route('/api/check-ffmpeg')
def check_ffmpeg():
    """Check if FFmpeg is installed"""
    ffmpeg_path = shutil.which('ffmpeg')
    return jsonify({
        'installed': ffmpeg_path is not None,
        'path': ffmpeg_path,
        'mutagen': MUTAGEN_AVAILABLE,
        'notifications': TOAST_AVAILABLE,
    })


@app.route('/api/preview-audio', methods=['POST'])
def preview_audio():
    """Get audio stream URL for preview playback"""
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'skip_download': True,
        }
        
        # Explicitly set ffmpeg location
        ffmpeg_loc = get_ffmpeg_path()
        if ffmpeg_loc:
            ydl_opts['ffmpeg_location'] = ffmpeg_loc
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info:
                # Get the best audio format URL
                audio_url = None
                
                # Try to get direct audio URL from formats
                for fmt in info.get('formats', []):
                    if fmt.get('acodec') != 'none' and fmt.get('url'):
                        audio_url = fmt.get('url')
                        break
                
                if not audio_url:
                    audio_url = info.get('url')
                
                return jsonify({
                    'success': True,
                    'audio_url': audio_url,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                })
            
        return jsonify({'error': 'Could not extract audio URL'}), 400
        
    except Exception as e:
        log_error(f"Audio preview error: {str(e)}")
        return jsonify({'error': str(e)}), 400


# ============== AUTO-UPDATE SYSTEM ==============

@app.route('/api/version')
def get_version():
    """Get current app version"""
    return jsonify({
        'version': APP_VERSION,
        'app_name': 'YouTube Extractor',
        'author': 'Jonathan Paul & Antigravity'
    })


@app.route('/api/check-update')
def check_update():
    """Check if a new version is available on GitHub"""
    try:
        response = requests.get(GITHUB_API_URL, timeout=10)
        
        if response.status_code == 200:
            release_data = response.json()
            latest_version = release_data.get('tag_name', '').lstrip('v')
            
            # Find the exe download URL
            download_url = None
            for asset in release_data.get('assets', []):
                if asset.get('name', '').endswith('.exe'):
                    download_url = asset.get('browser_download_url')
                    break
            
            # Compare versions
            current_parts = [int(x) for x in APP_VERSION.split('.')]
            latest_parts = [int(x) for x in latest_version.split('.') if x.isdigit()]
            
            # Pad with zeros if needed
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(latest_parts) < 3:
                latest_parts.append(0)
            
            update_available = latest_parts > current_parts
            
            return jsonify({
                'update_available': update_available,
                'current_version': APP_VERSION,
                'latest_version': latest_version,
                'download_url': download_url,
                'release_notes': release_data.get('body', ''),
                'release_name': release_data.get('name', '')
            })
        else:
            return jsonify({
                'update_available': False,
                'current_version': APP_VERSION,
                'error': 'Could not check for updates'
            })
            
    except Exception as e:
        return jsonify({
            'update_available': False,
            'current_version': APP_VERSION,
            'error': str(e)
        })


@app.route('/api/download-update', methods=['POST'])
def download_update():
    """Download and install the latest update"""
    try:
        data = request.json or {}
        download_url = data.get('download_url')
        
        if not download_url:
            # Get the download URL from GitHub
            response = requests.get(GITHUB_API_URL, timeout=10)
            if response.status_code == 200:
                release_data = response.json()
                target_asset = None
                for asset in release_data.get('assets', []):
                    # Prioritize the raw executable
                    if asset.get('name', '').lower() == 'youtubeextractor.exe':
                        target_asset = asset
                        break
                    # Fallback to any exe if not found (but risky if setup is present)
                    if asset.get('name', '').endswith('.exe') and 'setup' not in asset.get('name', '').lower():
                        target_asset = asset
                
                if target_asset:
                    download_url = target_asset.get('browser_download_url')
        
        if not download_url:
            return jsonify({'success': False, 'error': 'No download URL found'}), 400
        
        # Download the new exe
        response = requests.get(download_url, stream=True, timeout=300)
        
        if response.status_code == 200:
            # Get the current exe path
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
                update_dir = os.path.dirname(current_exe)
            else:
                # Running as script - save to current directory
                update_dir = os.path.dirname(os.path.abspath(__file__))
                current_exe = None
            
            # Use TEMP directory for downloading (avoids permission issues)
            import tempfile
            temp_dir = tempfile.gettempdir()
            new_exe_path = os.path.join(temp_dir, 'YouTubeExtractor_new.exe')
            
            # Save the new exe to temp
            with open(new_exe_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Create a PowerShell script that requests elevation to replace the exe
            if current_exe:
                # Use PowerShell with -Verb RunAs for elevation
                ps_content = f'''
$ErrorActionPreference = "Stop"
Start-Sleep -Seconds 2
Remove-Item -Path "{current_exe}" -Force
Move-Item -Path "{new_exe_path}" -Destination "{current_exe}" -Force
Start-Process -FilePath "{current_exe}"
'''
                ps_path = os.path.join(temp_dir, 'update_script.ps1')
                with open(ps_path, 'w', encoding='utf-8') as f:
                    f.write(ps_content)
                
                # Create a batch that launches PowerShell with admin rights
                batch_content = f'''@echo off
powershell -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"{ps_path}\"' -Verb RunAs"
'''
                batch_path = os.path.join(temp_dir, 'update.bat')
                with open(batch_path, 'w') as f:
                    f.write(batch_content)
                
                return jsonify({
                    'success': True,
                    'message': 'Update downloaded. Click "Install & Restart" to complete.',
                    'batch_path': batch_path,
                    'restart_required': True
                })
            else:
                return jsonify({
                    'success': True,
                    'message': f'Update downloaded to {new_exe_path}',
                    'restart_required': False
                })
        else:
            return jsonify({'success': False, 'error': 'Failed to download update'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/install-update', methods=['POST'])
def install_update():
    """Execute the update batch script and close the app"""
    try:
        data = request.json or {}
        batch_path = data.get('batch_path')
        
        if batch_path and os.path.exists(batch_path):
            # Start the batch file and exit
            subprocess.Popen(batch_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Schedule shutdown
            def shutdown():
                import time
                time.sleep(0.5)
                os._exit(0)
            
            threading.Thread(target=shutdown, daemon=True).start()
            
            return jsonify({'success': True, 'message': 'Installing update...'})
        else:
            return jsonify({'success': False, 'error': 'Update batch file not found'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎵 YouTube Media Extractor - Advanced Edition")
    print("="*60)
    print(f"\n📂 Default download folder: {DEFAULT_DOWNLOAD_FOLDER}")
    print(f"📜 History file: {HISTORY_FILE}")
    print(f"🔧 ID3 Tags: {'✓ Enabled' if MUTAGEN_AVAILABLE else '✗ Disabled (install mutagen)'}")
    print(f"🔔 Notifications: {'✓ Enabled' if TOAST_AVAILABLE else '✗ Disabled (install win10toast)'}")
    print("\n🌐 Open your browser at: http://localhost:5000")
    print("\n   Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Create default download folder
    os.makedirs(DEFAULT_DOWNLOAD_FOLDER, exist_ok=True)
    
    # Load history
    load_history()
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False, threaded=False)
