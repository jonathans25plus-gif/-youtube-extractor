@echo off
echo ============================================
echo YouTube Extractor - Build Script
echo ============================================
echo.

REM Check if FFmpeg is in bin folder
if not exist "bin\ffmpeg.exe" (
    echo [ERROR] FFmpeg not found in 'bin' folder!
    echo.
    echo Please download FFmpeg from:
    echo https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
    echo.
    echo Extract and copy ffmpeg.exe and ffprobe.exe to the 'bin' folder.
    echo.
    pause
    exit /b 1
)

echo [OK] FFmpeg found in bin folder
echo.
echo Starting PyInstaller build...
echo.

pyinstaller YouTubeExtractor.spec --clean --noconfirm

echo.
if exist "dist\YouTubeExtractor.exe" (
    echo ============================================
    echo [SUCCESS] Build complete!
    echo Executable: dist\YouTubeExtractor.exe
    echo ============================================
) else (
    echo [ERROR] Build failed!
)
echo.
pause
