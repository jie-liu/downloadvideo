import yt_dlp
import uuid
import threading
import os

# task_id -> {"status": str, "progress": float, "filename": str|None, "error": str|None}
_tasks: dict = {}


def _human_size(size_bytes) -> str:
    if size_bytes is None:
        return "Unknown"
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.1f} GB"
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def get_info(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    for f in info.get("formats", []):
        filesize = f.get("filesize")
        filesize_approx = f.get("filesize_approx")
        effective_size = filesize or filesize_approx
        resolution = f.get("resolution") or (
            f"{f.get('width', '?')}x{f.get('height', '?')}"
            if f.get("width") else "audio only"
        )
        formats.append({
            "format_id": f.get("format_id"),
            "resolution": resolution,
            "ext": f.get("ext"),
            "filesize": filesize,
            "filesize_approx": filesize_approx,
            "display_size": _human_size(effective_size),
        })

    formats.sort(
        key=lambda x: (x["filesize"] or x["filesize_approx"] or -1),
        reverse=True,
    )

    return {
        "title": info.get("title", "Unknown"),
        "formats": formats,
    }
