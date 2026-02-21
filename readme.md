# 🦁 Lion YT Downloader

**Lion YT Downloader** is a high-performance, open-source desktop application designed to streamline the process of downloading video and audio from YouTube and hundreds of other platforms. 

Built with **Python 3.13** and **PyQt6**, it offers a polished dark-themed interface with advanced features for professional workflows.

---

## ✨ Key Features

- **🚀 Smart Drag & Drop:** Drag video thumbnails or URLs directly from your browser into the app.
- **🔄 Auto-Format Conversion:** All video downloads are automatically converted to `.mp4` using FFmpeg for universal compatibility.
- **🎭 Quality Selection:** 
  - **Ultra Quality:** 4K/8K (Best available).
  - **High Definition:** Forced 1080p or 720p.
  - **Audio Only:** Pure MP3 (192kbps).
- **🖼️ Async Thumbnails:** High-resolution thumbnails are rendered in the sidebar as you download, without freezing the UI.
- **🧠 Duplicate Detection:** Automatically detects if a video is already in your output folder (Orange color code) to save time and bandwidth.
- **🎨 Visual Status Coding:**
  - 🟢 **Green:** Downloaded successfully.
  - 🟡 **Yellow:** File already exists (skipped).
  - 🔴 **Red:** Error or invalid link.

---

## 🛠 Installation & Setup

### For Developers (Running from source)
If you want to run the code manually, install the required dependencies:
pip install PyQt6 yt-dlp pyqtdarktheme

### FFmpeg Requirement (Essential)

To merge high-quality video/audio and convert files to MP4, you must have FFmpeg:

    Download the binaries (ffmpeg.exe and ffprobe.exe) from Gyan.dev.

    Place both .exe files in the same folder as main.py (or next to the final LionYTDownloader.exe).

### 📦 Building the Executable (.exe)

I have included a dedicated build script for Windows users:
1. Ensure `icon.ico`, `ffmpeg.exe`, and `ffprobe.exe` are in the project root folder.
2. Double-click `build_app.bat`.
3. Enter the version number when prompted.
4. The script will generate a ready-to-distribute `.zip` file containing the App and the required FFmpeg binaries.

## 🤝 Custom Software & Freelance Services

This tool was created to demonstrate how automation can drastically speed up a creative workflow.

Do you need a custom tool for your business?
I specialize in building:

    Custom Desktop Applications (Windows/Mac/Linux).

    Workflow Automation & Web Scraping scripts.

    Data Processing tools and internal management software.

If you want to speed up your work with software tailored specifically to your needs, let's talk!

📩 Contact me for inquiries: ewejose@gmail.com
📄 License

This project is open-source under the MIT License. You are free to use, modify, and distribute it as you wish.

Created with ❤️ by Ewe.