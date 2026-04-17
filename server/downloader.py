import yt_dlp
import uuid
import threading
import os
import requests

# task_id -> {"status": str, "progress": float, "filename": str|None, "error": str|None}
_tasks: dict = {}


def _is_yfsp_url(url: str) -> bool:
    return "yfsp.tv" in url or "miolive.tv" in url


def _is_taiav_url(url: str) -> bool:
    return any(h in url for h in ("taiav.com", "bangerspis.xyz", "rapidtai.com", "m1fuping.lol", "taimadou.com"))


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


def _get_taiav_info(url: str) -> dict:
    """taiav.com 自定义提取器：调用 /api/getmovie 获取 m3u8"""
    import re

    # 提取视频 ID
    match = re.search(r'/movie/([a-f0-9]+)', url)
    if not match:
        raise ValueError(f"无法从 URL 提取视频 ID: {url}")
    video_id = match.group(1)
    base_url = "https://taiav.com"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": url,
    }

    # 获取页面标题
    title = video_id
    try:
        page_resp = requests.get(url, headers=headers, timeout=10)
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', page_resp.text, re.IGNORECASE)
        if title_match:
            raw = title_match.group(1).strip()
            # 去掉末尾的站名后缀
            raw = re.sub(r'\s*[-|]\s*Taiav\.com.*$', '', raw, flags=re.IGNORECASE).strip()
            if raw:
                title = raw
    except Exception:
        pass

    # 按清晰度顺序尝试（高→低），拿到第一个可用的
    formats = []
    for hd in ["1280", "720", "480"]:
        try:
            resp = requests.get(
                f"{base_url}/api/getmovie?type={hd}&id={video_id}",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("m3u8"):
                continue
            m3u8_url = base_url + data["m3u8"]
            resolution_map = {"1280": "1280x720 (HD)", "720": "720x480", "480": "480x270"}
            formats.append({
                "format_id": f"taiav_{hd}",
                "resolution": resolution_map.get(hd, hd),
                "ext": "mp4",
                "filesize": None,
                "filesize_approx": int(hd) * 100000,  # 粗略估计用于排序
                "display_size": "Unknown",
                "_direct_url": m3u8_url,
                "_referer": url,
            })
        except Exception:
            continue

    if not formats:
        raise ValueError("无法获取 taiav.com 视频链接，可能需要登录或视频不存在")

    return {"title": title, "formats": formats}


def _get_generic_page_info(url: str, html: str = None, video_urls: list = None) -> dict:
    """通用页面提取器：当 yt-dlp 不支持时，扫描页面源码找 m3u8/mp4 链接。
    html 由扩展直接传入时（Cloudflare 保护页面），跳过 HTTP 抓取。
    video_urls 由扩展从 performance.getEntriesByType 获取，优先使用。"""
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

    # 收集视频 URL：优先用扩展传来的（包含动态加载的资源）
    collected = list(video_urls or [])

    # 再从 HTML 源码找（处理 \/ 转义形式）
    for u in re.findall(r'https?:(?:\\?/){2}[^\s\'"<>]+\.m3u8[^\s\'"<>]*', content):
        collected.append(u.replace('\\/', '/'))

    # 找 JSON 字段中的 url
    for raw in re.findall(r'"url"\s*:\s*"([^"]+)"', content):
        clean = raw.replace('\\/', '/')
        if not clean.startswith('http'):
            clean = 'https:' + clean
        if '.m3u8' in clean or '.mp4' in clean:
            collected.append(clean)

    # 去重保序
    seen = set()
    unique_urls = []
    for u in collected:
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


def _parse_ytdlp_formats(info: dict) -> list:
    """将 yt-dlp info dict 转换为统一 format 列表，视频按大小降序，音频追加末尾。"""
    video_formats = []
    audio_formats = []

    for f in info.get("formats", []):
        filesize = f.get("filesize")
        filesize_approx = f.get("filesize_approx")
        effective_size = filesize or filesize_approx
        has_video = f.get("width") or f.get("height") or (
            f.get("vcodec") and f.get("vcodec") != "none"
        )
        has_audio = f.get("acodec") and f.get("acodec") != "none"

        if not has_video and has_audio:
            # 纯音频格式
            abr = f.get("abr")
            audio_formats.append({
                "format_id": f.get("format_id"),
                "resolution": f"Audio {int(abr)}kbps" if abr else "Audio only",
                "ext": f.get("ext"),
                "filesize": filesize,
                "filesize_approx": filesize_approx,
                "display_size": _human_size(effective_size),
                "is_audio": True,
            })
        elif has_video:
            resolution = f.get("resolution") or (
                f"{f.get('width')}x{f.get('height')}" if f.get("width") else "unknown"
            )
            video_formats.append({
                "format_id": f.get("format_id"),
                "resolution": resolution,
                "ext": f.get("ext"),
                "filesize": filesize,
                "filesize_approx": filesize_approx,
                "display_size": _human_size(effective_size),
            })

    # 视频按大小降序，音频按码率降序
    video_formats.sort(key=lambda x: (x["filesize"] or x["filesize_approx"] or -1), reverse=True)
    audio_formats.sort(key=lambda x: (x["filesize"] or x["filesize_approx"] or -1), reverse=True)
    return video_formats + audio_formats


def get_info(url: str, html: str = None, video_urls: list = None) -> dict:
    """提取视频信息，按顺序尝试各提取器直到成功。"""
    last_error = None

    # 1. yt-dlp（支持 YouTube 等 1000+ 网站）
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", "Unknown"),
            "formats": _parse_ytdlp_formats(info),
        }
    except Exception as e:
        last_error = e

    # 2. yfsp 风格（?v=<id> + MasterPlayList API）
    try:
        return _get_yfsp_info(url)
    except Exception:
        pass

    # 3. taiav 风格（/movie/<hex-id> + /api/getmovie）
    try:
        return _get_taiav_info(url)
    except Exception:
        pass

    # 4. 通用 HTML 扫描（含扩展传来的 HTML / video_urls）
    return _get_generic_page_info(url, html=html, video_urls=video_urls)


def _is_ts_stream(filepath: str) -> bool:
    """检查文件是否为 MPEG-TS 流（首字节为 0x47 同步字节）。"""
    try:
        with open(filepath, "rb") as f:
            return f.read(1) == b"\x47"
    except Exception:
        return False


def _find_ffmpeg() -> str:
    """找 ffmpeg 可执行文件路径。"""
    import shutil
    # 优先找系统 PATH 里的
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 常见手动安装位置
    for candidate in [
        os.path.expanduser("~/bin/ffmpeg"),
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def _remux_ts_to_mp4(src: str) -> str:
    """用 ffmpeg 把 TS 流 remux 成标准 MP4，成功返回新路径（保持原文件名），失败返回原路径。"""
    import subprocess, tempfile
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return src  # ffmpeg 不可用，保留原文件
    base, _ = os.path.splitext(src)
    # 先写到临时文件，成功后再替换原文件
    tmp = base + "._tmp_remux.mp4"
    try:
        result = subprocess.run(
            [ffmpeg, "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", tmp],
            capture_output=True,
            timeout=600,
        )
        # 检查输出文件是否是合法 MP4（有 ftyp box），不完全依赖退出码
        # 某些静态编译的 ffmpeg 转换成功但仍返回非零退出码
        output_valid = os.path.exists(tmp) and not _is_ts_stream(tmp)
        if output_valid:
            os.remove(src)       # 删掉原始 TS 文件
            os.rename(tmp, src)  # 用标准 MP4 替换，保持文件名
            return src
    except subprocess.TimeoutExpired:
        pass
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
    return src  # 失败，返回原文件


def _sanitize_filename(name: str) -> str:
    """移除文件名中不合法的字符。"""
    import re
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name.strip()[:200] or "video"


def cancel_download(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if not task:
        return False
    task["_cancelled"] = True
    task["status"] = "cancelled"
    # 尝试关闭 yt-dlp 底层请求会话以中断下载
    ydl = task.get("_ydl")
    if ydl:
        try:
            ydl.close()
        except Exception:
            pass
    return True


def download(url: str, format_id: str, output_dir: str, direct_url: str = None, referer: str = None, title: str = None) -> str:
    task_id = str(uuid.uuid4())[:8]
    output_dir = os.path.expanduser(output_dir)
    _tasks[task_id] = {
        "status": "started",
        "progress": 0.0,
        "filename": None,
        "error": None,
        "_direct_url": direct_url,
        "_referer": referer,
        "_title": title,
        "_cancelled": False,
        "_ydl": None,
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
    referer = _tasks[task_id].get("_referer")
    title = _tasks[task_id].get("_title")
    actual_url = direct_url if direct_url else url

    # 构建输出文件名：优先用已知标题，否则让 yt-dlp 自己提取
    if title:
        outtmpl = os.path.join(output_dir, f"{_sanitize_filename(title)}.%(ext)s")
    else:
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")

    ydl_opts = {
        "format": "best" if direct_url else format_id,
        "outtmpl": outtmpl,
        "continuedl": True,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "quiet": True,
        "no_warnings": True,
    }
    if referer:
        ydl_opts["http_headers"] = {"Referer": referer}

    ydl = yt_dlp.YoutubeDL(ydl_opts)
    _tasks[task_id]["_ydl"] = ydl
    try:
        ydl.download([actual_url])
        # postprocessor_hook 未触发时（纯流媒体无后处理）确保设为 done
        if _tasks[task_id]["status"] not in ("done", "error", "cancelled"):
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["progress"] = 100.0

        # 检查输出文件是否为 TS 流，若是则用 ffmpeg remux 成真正的 MP4
        filepath = _tasks[task_id].get("filename")
        if filepath and os.path.exists(filepath) and _is_ts_stream(filepath):
            _tasks[task_id]["status"] = "remuxing"
            fixed = _remux_ts_to_mp4(filepath)
            _tasks[task_id]["filename"] = fixed
        _tasks[task_id]["status"] = "done"
        _tasks[task_id]["progress"] = 100.0
    except Exception as e:
        if _tasks[task_id].get("_cancelled"):
            _tasks[task_id]["status"] = "cancelled"
        else:
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = str(e)
    finally:
        try:
            ydl.__exit__(None, None, None)
        except Exception:
            pass
        _tasks[task_id]["_ydl"] = None


def get_task_status(task_id: str) -> dict:
    task = _tasks.get(task_id)
    if task is None:
        return {"status": "not_found"}
    result = {k: v for k, v in task.items() if not k.startswith("_")}
    # 若下载完成，检查文件是否仍为 TS 流（remux 未成功时提示前端显示修复按钮）
    if result.get("status") == "done" and result.get("filename"):
        result["is_ts"] = _is_ts_stream(result["filename"])
    return result
