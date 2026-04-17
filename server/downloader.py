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


def download(url: str, format_id: str, output_dir: str) -> str:
    task_id = str(uuid.uuid4())[:8]
    output_dir = os.path.expanduser(output_dir)
    _tasks[task_id] = {
        "status": "started",
        "progress": 0.0,
        "filename": None,
        "error": None,
    }

    thread = threading.Thread(
        target=_do_download,
        args=(task_id, url, format_id, output_dir),
        daemon=True,
    )
    thread.start()
    return task_id


def _do_download(task_id: str, url: str, format_id: str, output_dir: str):
    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            _tasks[task_id]["status"] = "downloading"
            _tasks[task_id]["progress"] = (downloaded / total * 100) if total else 0
            _tasks[task_id]["filename"] = d.get("filename")
        elif d["status"] == "finished":
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["progress"] = 100.0

    ydl_opts = {
        "format": format_id,
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "continuedl": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = str(e)


def get_task_status(task_id: str) -> dict:
    return _tasks.get(task_id, {"status": "not_found"})
