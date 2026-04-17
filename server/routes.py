from flask import Blueprint, request, jsonify
from downloader import get_info, download, get_task_status
from config import DEFAULT_OUTPUT_DIR

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/ping")
def ping():
    return jsonify({"status": "ok"})


@bp.post("/info")
def info():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    html = data.get("html")
    video_urls = data.get("video_urls") or []
    try:
        result = get_info(url, html=html, video_urls=video_urls)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/download")
def start_download():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    format_id = data.get("format_id", "").strip()
    if not url or not format_id:
        return jsonify({"error": "url and format_id are required"}), 400
    direct_url = data.get("direct_url")
    referer = data.get("referer")
    title = data.get("title", "").strip() or None
    task_id = download(url, format_id, DEFAULT_OUTPUT_DIR, direct_url=direct_url, referer=referer, title=title)
    return jsonify({"task_id": task_id, "status": "started"})


@bp.post("/cancel")
def cancel():
    task_id = request.args.get("task_id", "")
    from downloader import cancel_download
    ok = cancel_download(task_id)
    return jsonify({"ok": ok})


@bp.post("/fix")
def fix_file():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "").strip()
    if not path:
        return jsonify({"ok": False, "error": "path is required"}), 400
    import os
    path = os.path.expanduser(path)
    from downloader import _is_ts_stream, _remux_ts_to_mp4
    if not os.path.exists(path):
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    if not _is_ts_stream(path):
        return jsonify({"ok": False, "error": "该文件不是损坏的 TS 流，无需修复"}), 400
    result = _remux_ts_to_mp4(path)
    if result == path and _is_ts_stream(path):
        return jsonify({"ok": False, "error": "修复失败（ffmpeg 不可用或转换出错）"})
    return jsonify({"ok": True, "path": result})


@bp.get("/scan")
def scan_broken():
    import os
    from downloader import _is_ts_stream, _human_size
    downloads = os.path.expanduser("~/Downloads")
    broken = []
    try:
        for fname in os.listdir(downloads):
            if not fname.lower().endswith(".mp4"):
                continue
            fpath = os.path.join(downloads, fname)
            if os.path.isfile(fpath) and _is_ts_stream(fpath):
                size = os.path.getsize(fpath)
                broken.append({
                    "name": fname,
                    "path": fpath,
                    "size": _human_size(size),
                })
    except Exception as e:
        return jsonify({"files": [], "error": str(e)})
    broken.sort(key=lambda x: x["name"])
    return jsonify({"files": broken})


@bp.get("/status")
def status():
    task_id = request.args.get("task_id", "")
    result = get_task_status(task_id)
    if result["status"] == "not_found":
        return jsonify(result), 404
    return jsonify(result)
