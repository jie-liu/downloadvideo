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


@bp.get("/status")
def status():
    task_id = request.args.get("task_id", "")
    result = get_task_status(task_id)
    if result["status"] == "not_found":
        return jsonify(result), 404
    return jsonify(result)
