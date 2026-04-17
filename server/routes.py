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
    try:
        result = get_info(url)
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
    output_dir = data.get("output_dir", DEFAULT_OUTPUT_DIR)
    task_id = download(url, format_id, output_dir)
    return jsonify({"task_id": task_id, "status": "started"})


@bp.get("/status")
def status():
    task_id = request.args.get("task_id", "")
    result = get_task_status(task_id)
    if result["status"] == "not_found":
        return jsonify(result), 404
    return jsonify(result)
