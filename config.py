"""Constantes y builders de opciones para yt-dlp."""

from __future__ import annotations

QUALITY_OPTIONS: list[tuple[str, str]] = [
    ("best", "Video (Mejor calidad)"),
    ("8k", "Video (8K)"),
    ("4k", "Video (4K / 2160p)"),
    ("2k", "Video (2K / 1440p)"),
    ("1080", "Video (1080p)"),
    ("720", "Video (720p)"),
    ("480", "Video (480p)"),
    ("360", "Video (360p)"),
    ("audio", "Audio (MP3)"),
]

QUALITY_HEIGHTS: dict[str, int] = {
    "8k": 4320,
    "4k": 2160,
    "2k": 1440,
    "1080": 1080,
    "720": 720,
    "480": 480,
    "360": 360,
}

CODEC_OPTIONS: list[tuple[str, str]] = [
    ("original", "Original (sin recodificar)"),
    ("h264", "MP4 + H.264"),
    ("h265", "MKV + H.265"),
    ("prores", "MKV + ProRes"),
]

AUDIO_BITRATE_OPTIONS: list[tuple[str, str]] = [
    ("128", "128 kbps"),
    ("192", "192 kbps (recomendado)"),
    ("256", "256 kbps"),
    ("320", "320 kbps"),
]

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".avi")
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav", ".flac", ".aac", ".opus")

CONCURRENT_FRAGMENTS = 8
YTDLP_RETRIES = 10
FRAGMENT_RETRIES = 10
SOCKET_TIMEOUT = 30

PARALLEL_DOWNLOAD_OPTIONS: list[tuple[int, str]] = [
    (1, "1 (secuencial)"),
    (2, "2 en paralelo"),
    (3, "3 en paralelo"),
]
DEFAULT_PARALLEL_DOWNLOADS = 2

POSTPROCESSOR_LABELS: dict[str, str] = {
    "FFmpegExtractAudio": "Extrayendo y codificando audio",
    "FFmpegVideoConvertor": "Recodificando video",
    "FFmpegVideoRemuxer": "Remuxing de contenedor",
    "FFmpegMerger": "Uniendo pistas de video y audio",
    "FFmpegSubtitlesConvertor": "Convirtiendo subtítulos",
    "ModifyChapters": "Procesando capítulos",
    "EmbedThumbnail": "Insertando miniatura",
    "SponsorBlock": "Procesando segmentos SponsorBlock",
    "MoveFiles": "Organizando archivos",
}

ENCODE_CODECS = frozenset({"prores", "h265", "h264"})


def build_video_format(format_type: str, codec_type: str) -> str:
    """Construye la cadena de formato de yt-dlp según calidad y códec."""
    height = QUALITY_HEIGHTS.get(format_type)

    if codec_type == "original":
        if height:
            return (
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"best[height<={height}]/best"
            )
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"

    if height:
        return (
            f"bestvideo[height<={height}]+bestaudio/"
            f"best[height<={height}]/best"
        )
    return "bestvideo+bestaudio/best"


def get_codec_ffmpeg_args(codec_type: str) -> tuple[list[str], str]:
    """Devuelve argumentos FFmpeg y extensión destino para recodificación."""
    if codec_type == "prores":
        return (
            ["-c:v", "prores_ks", "-profile:v", "1", "-pix_fmt", "yuv422p10le", "-c:a", "copy"],
            "mkv",
        )
    if codec_type == "h265":
        return (
            ["-c:v", "libx265", "-crf", "26", "-preset", "fast", "-c:a", "copy"],
            "mkv",
        )
    if codec_type == "h264":
        return (
            ["-c:v", "libx264", "-crf", "23", "-preset", "fast", "-c:a", "copy"],
            "mp4",
        )
    return [], "mp4"


def extensions_for_format(format_type: str) -> tuple[str, ...]:
    """Extensiones válidas según el tipo de descarga."""
    return AUDIO_EXTENSIONS if format_type == "audio" else VIDEO_EXTENSIONS
