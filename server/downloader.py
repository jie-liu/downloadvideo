import yt_dlp
import uuid
import threading
import os
import requests

# task_id -> {"status": str, "progress": float, "filename": str|None, "error": str|None}
_tasks: dict = {}


def _is_yfsp_url(url: str) -> bool:
    return "yfsp.tv" in url or "miolive.tv" in url


def _get_yfsp_info(url: str) -> dict:
    """yfsp.tv 自定义提取器"""
    import re

    # 从 URL 提取视频 ID
    match = re.search(r'[?&]v=([^&\s]+)', url)
    if not match:
        raise ValueError(f"无法从 URL 提取视频 ID: {url}")
    video_id = match.group(1)

    # 尝试从页面获取标题
    title = video_id  # 默认用 video_id 作为标题
    try:
        page_resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=10,
        )
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', page_resp.text, re.IGNORECASE)
        if title_match:
            raw_title = title_match.group(1).strip()
            # 过滤掉纯站名
            if raw_title and raw_title != "爱壹帆国际版-海量高清视频免费在线观看":
                title = raw_title
    except Exception:
        pass  # 获取标题失败时使用 video_id

    # 调用 MasterPlayList API 获取 m3u8
    api_url = f"https://upload.yfsp.tv/api/video/MasterPlayList?id={video_id}"
    resp = requests.get(
        api_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.yfsp.tv/",
        },
        timeout=15,
    )
    resp.raise_for_status()

    m3u8_content = resp.text

    # 解析 m3u8：找到所有 stream info 和对应的 URL
    formats = []
    lines = m3u8_content.strip().splitlines()
    i = 0
    stream_index = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            # 提取 BANDWIDTH 和 NAME
            bandwidth_match = re.search(r'BANDWIDTH=(\d+)', line)
            name_match = re.search(r'NAME="([^"]+)"', line)
            bandwidth = int(bandwidth_match.group(1)) if bandwidth_match else 0
            stream_name = name_match.group(1) if name_match else str(stream_index + 1)

            # 下一行是 URL
            if i + 1 < len(lines):
                stream_url = lines[i + 1].strip()
                if stream_url and not stream_url.startswith("#"):
                    formats.append({
                        "format_id": f"yfsp_{stream_index}",
                        "resolution": stream_name,
                        "ext": "mp4",
                        "filesize": None,
                        "filesize_approx": bandwidth * 10 if bandwidth > 1 else None,
                        "display_size": _human_size(bandwidth * 10 if bandwidth > 1 else None),
                        "_direct_url": stream_url,
                    })
                    stream_index += 1
                    i += 2
                    continue
        i += 1

    # 如果没有解析到 STREAM-INF，回退：把整个 m3u8 URL 当作一个格式
    if not formats:
        formats.append({
            "format_id": "yfsp_0",
            "resolution": "unknown",
            "ext": "mp4",
            "filesize": None,
            "filesize_approx": None,
            "display_size": "Unknown",
            "_direct_url": api_url,
        })

    # 按 filesize_approx 降序排列（bandwidth 大的在前）
    formats.sort(key=lambda x: (x["filesize_approx"] or -1), reverse=True)

    return {"title": title, "formats": formats}


def _get_generic_page_info(url: str, html: str = None) -> dict:
    """通用页面提取器：当 yt-dlp 不支持时，扫描页面源码找 m3u8/mp4 链接。
    html 由扩展直接传入时（Cloudflare 保护页面），跳过 HTTP 抓取。"""
    import re

    if html:
        content = html
    else:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=15,
        )
        resp.raise_for_status()
        content = resp.text

    # 提取标题
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else url

    # 收集视频 URL：先找直接出现的 m3u8/mp4 URL（含 \/ 转义形式）
    video_urls = []
    for u in re.findall(r'https?:(?:\\?/){2}[^\s\'"<>]+\.m3u8[^\s\'"<>]*', content):
        video_urls.append(u.replace('\\/', '/'))

    # 找 JSON 字段中的 url（如 player_aaaa={"url":"..."}，值可能含 \/ 转义）
    for raw in re.findall(r'"url"\s*:\s*"([^"]+)"', content):
        clean = raw.replace('\\/', '/')
        if not clean.startswith('http'):
            clean = 'https:' + clean
        if '.m3u8' in clean or '.mp4' in clean:
            video_urls.append(clean)

    # 去重保序
    seen = set()
    unique_urls = []
    for u in video_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    if not unique_urls:
        raise ValueError("页面中未找到视频链接，该网站可能不受支持")

    # 对每个视频 URL 用 yt-dlp 获取格式信息
    formats = []
    for i, video_url in enumerate(unique_urls):
        try:
            ydl_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
            for f in info.get("formats", []):
                filesize = f.get("filesize")
                filesize_approx = f.get("filesize_approx")
                resolution = f.get("resolution") or (
                    f"{f.get('width')}x{f.get('height')}" if f.get("width") else "unknown"
                )
                formats.append({
                    "format_id": f.get("format_id", f"generic_{i}"),
                    "resolution": resolution,
                    "ext": f.get("ext", "mp4"),
                    "filesize": filesize,
                    "filesize_approx": filesize_approx,
                    "display_size": _human_size(filesize or filesize_approx),
                    "_direct_url": video_url,
                })
        except Exception:
            formats.append({
                "format_id": f"generic_{i}",
                "resolution": "unknown",
                "ext": "mp4",
                "filesize": None,
                "filesize_approx": None,
                "display_size": "Unknown",
                "_direct_url": video_url,
            })

    formats.sort(key=lambda x: (x["filesize"] or x["filesize_approx"] or -1), reverse=True)
    return {"title": title, "formats": formats}


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


def get_info(url: str, html: str = None) -> dict:
    # yfsp.tv 使用自定义提取器
    if _is_yfsp_url(url):
        return _get_yfsp_info(url)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        err = str(e).lower()
        if "unsupported url" in err or "no video formats" in err:
            return _get_generic_page_info(url, html=html)
        raise

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


def download(url: str, format_id: str, output_dir: str, direct_url: str = None) -> str:
    task_id = str(uuid.uuid4())[:8]
    output_dir = os.path.expanduser(output_dir)
    _tasks[task_id] = {
        "status": "started",
        "progress": 0.0,
        "filename": None,
        "error": None,
        "_direct_url": direct_url,  # yfsp.tv 等用到
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
        # 不在 finished 里设置 done，等后处理钩子
        elif d["status"] == "finished":
            _tasks[task_id]["progress"] = 99.0  # 接近完成，等后处理

    def postprocessor_hook(d):
        if d["status"] == "finished":
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["progress"] = 100.0
            if d.get("info_dict", {}).get("filepath"):
                _tasks[task_id]["filename"] = d["info_dict"]["filepath"]

    direct_url = _tasks[task_id].get("_direct_url")
    actual_url = direct_url if direct_url else url

    ydl_opts = {
        "format": "best" if direct_url else format_id,
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "continuedl": True,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([actual_url])
        # 如果 postprocessor_hook 没有触发（纯流媒体无后处理），确保设为 done
        if _tasks[task_id]["status"] not in ("done", "error"):
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["progress"] = 100.0
    except Exception as e:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = str(e)


def get_task_status(task_id: str) -> dict:
    task = _tasks.get(task_id)
    if task is None:
        return {"status": "not_found"}
    # 过滤内部字段，不暴露给客户端
    return {k: v for k, v in task.items() if not k.startswith("_")}
