# Video Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Chrome 扩展 + 本地 Python Flask 服务，支持从 YouTube、yfsp.tv 等 1000+ 网站下载视频，格式列表按文件大小降序排列。

**Architecture:** Chrome 扩展 Popup 通过 HTTP 调用本地 Flask 服务（localhost:8765），服务调用 yt-dlp 解析视频信息和执行下载。扩展获取当前 Tab URL 发送给服务端，服务端返回格式列表，用户选择后触发下载，Popup 轮询进度直到完成。

**Tech Stack:** Python 3.9+, Flask, flask-cors, yt-dlp, Chrome Extension Manifest V3, Vanilla JS

---

## 文件结构

```
downloadvideo/
├── extension/
│   ├── manifest.json          # MV3 配置，权限声明
│   ├── popup.html             # 弹窗 HTML 结构
│   ├── popup.js               # 弹窗逻辑：调用 API、渲染列表、轮询进度
│   ├── popup.css              # 样式（暗色主题）
│   └── background.js          # Service Worker：检测服务状态
├── server/
│   ├── config.py              # 端口、下载目录常量
│   ├── downloader.py          # yt-dlp 封装：get_info / download / get_task_status
│   ├── routes.py              # Flask 路由：/api/ping /api/info /api/download /api/status
│   ├── server.py              # Flask 应用入口，CORS 配置
│   ├── requirements.txt       # 依赖声明
│   └── tests/
│       ├── test_downloader.py # get_info / download 单元测试（mock yt-dlp）
│       └── test_routes.py     # API 路由集成测试
└── docs/
    └── superpowers/
        ├── specs/2026-04-16-video-downloader-design.md
        └── plans/2026-04-16-video-downloader.md
```

---

## Task 1: 项目依赖与环境搭建

**Files:**
- Create: `server/requirements.txt`
- Create: `server/tests/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```
flask==3.0.3
flask-cors==4.0.1
yt-dlp>=2024.1.1
pytest==8.1.1
pytest-mock==3.14.0
```

- [ ] **Step 2: 安装依赖**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo/server
pip install -r requirements.txt
```

预期输出：`Successfully installed flask ... yt-dlp ... pytest ...`

- [ ] **Step 3: 验证 yt-dlp 可用**

```bash
yt-dlp --version
```

预期输出：`2024.x.x` 或更新版本

- [ ] **Step 4: 创建 tests 包**

```bash
mkdir -p /Users/jie.liu/Projects/github/downloadvideo/server/tests
touch /Users/jie.liu/Projects/github/downloadvideo/server/tests/__init__.py
```

- [ ] **Step 5: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add server/requirements.txt server/tests/__init__.py
git commit -m "chore: add server dependencies and test structure"
```

---

## Task 2: config.py — 配置常量

**Files:**
- Create: `server/config.py`
- Create: `server/tests/test_config.py`

- [ ] **Step 1: 写失败测试**

新建 `server/tests/test_config.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import PORT, DEFAULT_OUTPUT_DIR

def test_port_is_integer():
    assert isinstance(PORT, int)
    assert PORT == 8765

def test_default_output_dir_expands_home():
    assert DEFAULT_OUTPUT_DIR.startswith("/")
    assert "Downloads" in DEFAULT_OUTPUT_DIR
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo/server
python -m pytest tests/test_config.py -v
```

预期：`ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: 实现 config.py**

新建 `server/config.py`：

```python
import os

PORT = 8765
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Downloads")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_config.py -v
```

预期：`2 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add server/config.py server/tests/test_config.py
git commit -m "feat: add config module with port and output dir"
```

---

## Task 3: downloader.py — get_info()

**Files:**
- Create: `server/downloader.py`
- Create: `server/tests/test_downloader.py`

- [ ] **Step 1: 写失败测试**

新建 `server/tests/test_downloader.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from downloader import get_info

MOCK_INFO = {
    "title": "Test Video",
    "formats": [
        {"format_id": "137", "resolution": "1920x1080", "ext": "mp4",
         "filesize": 500_000_000, "filesize_approx": None, "width": 1920, "height": 1080},
        {"format_id": "22", "resolution": "1280x720", "ext": "mp4",
         "filesize": 200_000_000, "filesize_approx": None, "width": 1280, "height": 720},
        {"format_id": "18", "resolution": "640x360", "ext": "mp4",
         "filesize": None, "filesize_approx": 50_000_000, "width": 640, "height": 360},
        {"format_id": "audio", "resolution": "audio only", "ext": "m4a",
         "filesize": None, "filesize_approx": None, "width": None, "height": None},
    ]
}

def test_get_info_returns_title_and_formats(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = MOCK_INFO
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    result = get_info("https://example.com/video")

    assert result["title"] == "Test Video"
    assert len(result["formats"]) == 4

def test_get_info_formats_sorted_by_size_desc(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = MOCK_INFO
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    result = get_info("https://example.com/video")
    formats = result["formats"]

    # 第一个应该是最大的（500MB）
    assert formats[0]["format_id"] == "137"
    # 第二个是 200MB
    assert formats[1]["format_id"] == "22"
    # filesize_approx 排在有 filesize 的后面
    assert formats[2]["format_id"] == "18"
    # 两者都为 None 的排末尾
    assert formats[3]["format_id"] == "audio"

def test_get_info_display_size_human_readable(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = MOCK_INFO
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    result = get_info("https://example.com/video")
    # 500MB 格式应有可读大小
    assert "MB" in result["formats"][0]["display_size"] or "GB" in result["formats"][0]["display_size"]
    # 无大小的应显示 Unknown
    assert result["formats"][3]["display_size"] == "Unknown"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo/server
python -m pytest tests/test_downloader.py -v
```

预期：`ModuleNotFoundError: No module named 'downloader'`

- [ ] **Step 3: 实现 downloader.py 的 get_info()**

新建 `server/downloader.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_downloader.py -v
```

预期：`3 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add server/downloader.py server/tests/test_downloader.py
git commit -m "feat: add get_info with yt-dlp, sorted by filesize desc"
```

---

## Task 4: downloader.py — download() 与 task 追踪

**Files:**
- Modify: `server/downloader.py`
- Modify: `server/tests/test_downloader.py`

- [ ] **Step 1: 追加失败测试到 test_downloader.py**

在 `server/tests/test_downloader.py` 末尾追加：

```python
from downloader import download, get_task_status

def test_download_returns_task_id(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.download = MagicMock(return_value=None)
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    task_id = download("https://example.com/video", "137", "/tmp")
    assert isinstance(task_id, str)
    assert len(task_id) > 0

def test_get_task_status_returns_started(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.download = MagicMock(return_value=None)
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    task_id = download("https://example.com/video", "22", "/tmp")
    status = get_task_status(task_id)
    assert status["status"] in ("started", "downloading", "done")

def test_get_task_status_unknown_task():
    status = get_task_status("nonexistent-task-id")
    assert status["status"] == "not_found"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_downloader.py::test_download_returns_task_id -v
```

预期：`ImportError: cannot import name 'download'`

- [ ] **Step 3: 在 downloader.py 末尾追加 download() 和 get_task_status()**

在 `server/downloader.py` 末尾追加：

```python
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
```

- [ ] **Step 4: 运行全部测试确认通过**

```bash
python -m pytest tests/test_downloader.py -v
```

预期：`6 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add server/downloader.py server/tests/test_downloader.py
git commit -m "feat: add download() with background thread and task tracking"
```

---

## Task 5: routes.py — 所有 API 端点

**Files:**
- Create: `server/routes.py`
- Create: `server/tests/test_routes.py`

- [ ] **Step 1: 写失败测试**

新建 `server/tests/test_routes.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch
from server import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_ping(client):
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}

def test_info_missing_url(client):
    resp = client.post("/api/info", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()

def test_info_calls_get_info(client):
    fake_result = {"title": "Test", "formats": []}
    with patch("routes.get_info", return_value=fake_result) as mock_fn:
        resp = client.post("/api/info", json={"url": "https://example.com"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Test"
    mock_fn.assert_called_once_with("https://example.com")

def test_info_get_info_error(client):
    with patch("routes.get_info", side_effect=Exception("Unsupported URL")):
        resp = client.post("/api/info", json={"url": "https://example.com"})
    assert resp.status_code == 500
    assert "error" in resp.get_json()

def test_download_missing_params(client):
    resp = client.post("/api/download", json={"url": "https://example.com"})
    assert resp.status_code == 400

def test_download_starts_task(client):
    with patch("routes.download", return_value="abc123") as mock_dl:
        resp = client.post("/api/download", json={
            "url": "https://example.com",
            "format_id": "137",
            "output_dir": "~/Downloads",
        })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["task_id"] == "abc123"
    assert data["status"] == "started"

def test_status_unknown_task(client):
    with patch("routes.get_task_status", return_value={"status": "not_found"}):
        resp = client.get("/api/status?task_id=xyz")
    assert resp.status_code == 404

def test_status_known_task(client):
    fake_status = {"status": "downloading", "progress": 42.0, "filename": "video.mp4", "error": None}
    with patch("routes.get_task_status", return_value=fake_status):
        resp = client.get("/api/status?task_id=abc123")
    assert resp.status_code == 200
    assert resp.get_json()["progress"] == 42.0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_routes.py -v
```

预期：`ImportError: cannot import name 'create_app' from 'server'`

- [ ] **Step 3: 创建 routes.py**

新建 `server/routes.py`：

```python
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
```

- [ ] **Step 4: 创建 server.py（含 create_app）**

新建 `server/server.py`：

```python
from flask import Flask
from flask_cors import CORS
from routes import bp
from config import PORT


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(bp)
    return app


if __name__ == "__main__":
    app = create_app()
    print(f"Video Downloader Server running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    app.run(host="0.0.0.0", port=PORT, debug=False)
```

- [ ] **Step 5: 运行全部测试确认通过**

```bash
python -m pytest tests/ -v
```

预期：`全部 passed`（test_config + test_downloader + test_routes）

- [ ] **Step 6: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add server/routes.py server/server.py server/tests/test_routes.py
git commit -m "feat: add Flask routes and server entry point"
```

---

## Task 6: 验证 yt-dlp 对 yfsp.tv 的支持

**Files:** 无新文件，命令行验证

- [ ] **Step 1: 启动本地服务**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo/server
python server.py
```

预期：`Video Downloader Server running at http://localhost:8765`（保持运行，开新终端继续）

- [ ] **Step 2: 检查 yt-dlp 是否支持 yfsp.tv**

```bash
yt-dlp --list-extractors 2>/dev/null | grep -i "yfsp\|miolive\|yifan\|anybound"
```

- [ ] **Step 3: 用 yt-dlp 直接测试 yfsp.tv 链接**

```bash
yt-dlp --dump-json "https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF" 2>&1 | head -50
```

- [ ] **Step 4: 根据结果决定后续**

  - **如果成功输出 JSON**：继续 Task 7（扩展开发），yfsp.tv 无需特殊处理
  - **如果报 "Unsupported URL"**：执行 Task 6b（自定义提取器）后再继续 Task 7
  - **如果报认证/Cookie 错误**：执行 Task 6c（Cookie 传递）后再继续 Task 7

---

## Task 6b: yfsp.tv 自定义提取器（仅当 Task 6 Step 3 失败时执行）

**Files:**
- Modify: `server/downloader.py`

- [ ] **Step 1: 分析 yfsp.tv API**

```bash
# 提取视频 ID
VIDEO_ID="0xItNu7p1YRzB5fikyH6fF"

# 尝试调用 MasterPlayList API（需要浏览器 Cookie）
curl -s \
  -H "Referer: https://www.yfsp.tv/" \
  -H "Origin: https://www.yfsp.tv" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  "https://api.miolive.tv/api/video/MasterPlayList?id=${VIDEO_ID}" | head -200
```

- [ ] **Step 2: 尝试带 Chrome Cookie 的 yt-dlp**

```bash
yt-dlp --cookies-from-browser chrome \
  --dump-json "https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF" 2>&1 | head -50
```

- [ ] **Step 3: 如果带 Cookie 成功，在 downloader.py 的 get_info() 中加入 Cookie 选项**

在 `server/downloader.py` 的 `get_info()` 函数，将 `ydl_opts` 修改为：

```python
def get_info(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "cookiesfrombrowser": ("chrome",),  # 从 Chrome 读取 Cookie
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # ... 其余代码不变
```

同样在 `_do_download()` 的 `ydl_opts` 中加入 `"cookiesfrombrowser": ("chrome",)`。

- [ ] **Step 4: 再次测试**

```bash
curl -s -X POST http://localhost:8765/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF"}' | python3 -m json.tool
```

预期：返回包含 `title` 和 `formats` 的 JSON

- [ ] **Step 5: Commit（如有改动）**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add server/downloader.py
git commit -m "fix: add cookiesfrombrowser for yfsp.tv support"
```

---

## Task 7: Chrome 扩展 — manifest.json & background.js

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/background.js`

- [ ] **Step 1: 创建 manifest.json**

新建 `extension/manifest.json`：

```json
{
  "manifest_version": 3,
  "name": "Video Downloader",
  "version": "1.0.0",
  "description": "Download videos from YouTube, yfsp.tv and 1000+ sites",
  "permissions": [
    "activeTab",
    "storage"
  ],
  "host_permissions": [
    "http://localhost:8765/*"
  ],
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "background": {
    "service_worker": "background.js"
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

- [ ] **Step 2: 创建图标目录和占位图标**

```bash
mkdir -p /Users/jie.liu/Projects/github/downloadvideo/extension/icons
# 用 Python 生成简单的 PNG 占位图标
python3 -c "
import struct, zlib

def make_png(size, color=(30, 144, 255)):
    def chunk(name, data):
        c = zlib.crc32(name + data) & 0xffffffff
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    raw = b''.join(b'\x00' + bytes(color) * size for _ in range(size))
    idat = zlib.compress(raw)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

import os
base = '/Users/jie.liu/Projects/github/downloadvideo/extension/icons'
for s in [16, 48, 128]:
    with open(f'{base}/icon{s}.png', 'wb') as f:
        f.write(make_png(s))
print('Icons created')
"
```

- [ ] **Step 3: 创建 background.js**

新建 `extension/background.js`：

```javascript
const SERVER_URL = "http://localhost:8765";

// 检测服务是否在线
async function checkServer() {
  try {
    const resp = await fetch(`${SERVER_URL}/api/ping`, { signal: AbortSignal.timeout(2000) });
    return resp.ok;
  } catch {
    return false;
  }
}

// 监听来自 popup 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "CHECK_SERVER") {
    checkServer().then((online) => sendResponse({ online }));
    return true; // 保持异步响应
  }
});
```

- [ ] **Step 4: 在 Chrome 中加载扩展验证**

```
1. 打开 Chrome → 地址栏输入 chrome://extensions/
2. 开启右上角"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择 /Users/jie.liu/Projects/github/downloadvideo/extension/ 目录
5. 确认扩展出现在列表中，无报错
```

- [ ] **Step 5: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add extension/
git commit -m "feat: add Chrome extension manifest and background service worker"
```

---

## Task 8: Chrome 扩展 — popup.html & popup.css

**Files:**
- Create: `extension/popup.html`
- Create: `extension/popup.css`

- [ ] **Step 1: 创建 popup.html**

新建 `extension/popup.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Video Downloader</title>
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <div class="container">
    <header>
      <h1>Video Downloader</h1>
    </header>

    <!-- 状态提示区域 -->
    <div id="status-bar" class="status-bar hidden"></div>

    <!-- 服务未启动提示 -->
    <div id="server-offline" class="offline-notice hidden">
      <p>本地服务未启动，请在终端运行：</p>
      <code>cd server && python server.py</code>
    </div>

    <!-- 加载中 -->
    <div id="loading" class="loading">
      <div class="spinner"></div>
      <p>正在分析视频...</p>
    </div>

    <!-- 视频信息 -->
    <div id="video-info" class="hidden">
      <p id="video-title" class="video-title"></p>
      <div id="formats-list" class="formats-list"></div>
    </div>

    <!-- 下载进度 -->
    <div id="download-progress" class="hidden">
      <p id="progress-text">下载中...</p>
      <div class="progress-bar">
        <div id="progress-fill" class="progress-fill" style="width: 0%"></div>
      </div>
      <p id="progress-percent">0%</p>
    </div>

    <!-- 下载完成 -->
    <div id="download-done" class="hidden">
      <p class="success-msg">✓ 下载完成</p>
      <p id="saved-path" class="saved-path"></p>
      <button id="btn-back" class="btn-secondary">返回</button>
    </div>
  </div>
  <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 2: 创建 popup.css**

新建 `extension/popup.css`：

```css
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  width: 380px;
  min-height: 150px;
  background: #1a1a2e;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 13px;
}

.container { padding: 12px; }

header h1 {
  font-size: 15px;
  font-weight: 600;
  color: #4fc3f7;
  margin-bottom: 10px;
}

.status-bar {
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 8px;
  font-size: 12px;
}
.status-bar.error { background: #4a1515; color: #ff6b6b; }
.status-bar.info  { background: #1a3a4a; color: #4fc3f7; }

.offline-notice {
  background: #3a2000;
  border: 1px solid #ff8c00;
  border-radius: 6px;
  padding: 10px;
  color: #ffa500;
}
.offline-notice code {
  display: block;
  margin-top: 6px;
  background: #1a1a1a;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: #90ee90;
  user-select: all;
}

.loading { text-align: center; padding: 20px; color: #aaa; }
.spinner {
  width: 28px; height: 28px;
  border: 3px solid #333;
  border-top-color: #4fc3f7;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 8px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.video-title {
  font-size: 12px;
  color: #aaa;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.formats-list { display: flex; flex-direction: column; gap: 4px; }

.format-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #16213e;
  border: 1px solid #0f3460;
  border-radius: 6px;
  padding: 8px 10px;
  gap: 8px;
}

.format-meta { flex: 1; }
.format-resolution { font-weight: 600; color: #e0e0e0; }
.format-detail { font-size: 11px; color: #888; margin-top: 2px; }

.btn-download {
  background: #4fc3f7;
  color: #0a0a1a;
  border: none;
  border-radius: 5px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}
.btn-download:hover { background: #81d4fa; }
.btn-download:disabled { background: #555; color: #888; cursor: default; }

.progress-bar {
  background: #333;
  border-radius: 4px;
  height: 8px;
  margin: 8px 0 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #4fc3f7;
  transition: width 0.3s ease;
}
#progress-percent { color: #aaa; font-size: 12px; }

.success-msg { color: #90ee90; font-size: 15px; margin-bottom: 6px; }
.saved-path { color: #aaa; font-size: 11px; word-break: break-all; margin-bottom: 10px; }

.btn-secondary {
  background: #16213e;
  color: #4fc3f7;
  border: 1px solid #4fc3f7;
  border-radius: 5px;
  padding: 5px 14px;
  font-size: 12px;
  cursor: pointer;
}
.btn-secondary:hover { background: #0f3460; }

.hidden { display: none !important; }
```

- [ ] **Step 3: 在 Chrome 中手动验证 UI 渲染**

```
1. 重新加载扩展（chrome://extensions/ → 刷新）
2. 点击插件图标
3. 确认显示暗色主题弹窗，出现"正在分析视频..."加载状态
```

- [ ] **Step 4: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add extension/popup.html extension/popup.css
git commit -m "feat: add popup UI with dark theme"
```

---

## Task 9: Chrome 扩展 — popup.js（完整交互逻辑）

**Files:**
- Create: `extension/popup.js`

- [ ] **Step 1: 创建 popup.js**

新建 `extension/popup.js`：

```javascript
const SERVER = "http://localhost:8765";
const POLL_INTERVAL = 2000;

// DOM 元素
const $ = (id) => document.getElementById(id);
const show = (id) => $(id).classList.remove("hidden");
const hide = (id) => $(id).classList.add("hidden");

function showError(msg) {
  const bar = $("status-bar");
  bar.textContent = msg;
  bar.className = "status-bar error";
  show("status-bar");
}

function showInfo(msg) {
  const bar = $("status-bar");
  bar.textContent = msg;
  bar.className = "status-bar info";
  show("status-bar");
}

async function pingServer() {
  try {
    const resp = await fetch(`${SERVER}/api/ping`, {
      signal: AbortSignal.timeout(2000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

async function getVideoInfo(url) {
  const resp = await fetch(`${SERVER}/api/info`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: "未知错误" }));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }
  return resp.json();
}

async function startDownload(url, formatId) {
  const resp = await fetch(`${SERVER}/api/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, format_id: formatId, output_dir: "~/Downloads" }),
  });
  if (!resp.ok) throw new Error("启动下载失败");
  return resp.json();
}

async function pollStatus(taskId) {
  const resp = await fetch(`${SERVER}/api/status?task_id=${taskId}`);
  return resp.json();
}

function renderFormats(title, formats) {
  hide("loading");
  $("video-title").textContent = title;

  const list = $("formats-list");
  list.innerHTML = "";

  if (formats.length === 0) {
    list.innerHTML = '<p style="color:#888;padding:8px">未找到可下载的格式</p>';
  }

  formats.forEach((fmt) => {
    const item = document.createElement("div");
    item.className = "format-item";
    item.innerHTML = `
      <div class="format-meta">
        <div class="format-resolution">${fmt.resolution}</div>
        <div class="format-detail">${fmt.ext.toUpperCase()} · ${fmt.display_size}</div>
      </div>
      <button class="btn-download" data-format-id="${fmt.format_id}">下载</button>
    `;
    list.appendChild(item);
  });

  show("video-info");
}

function startProgressPolling(taskId) {
  hide("video-info");
  hide("status-bar");
  show("download-progress");
  $("progress-text").textContent = "下载中...";

  const timer = setInterval(async () => {
    try {
      const status = await pollStatus(taskId);

      if (status.status === "downloading" || status.status === "started") {
        const pct = Math.round(status.progress || 0);
        $("progress-fill").style.width = `${pct}%`;
        $("progress-percent").textContent = `${pct}%`;
      } else if (status.status === "done") {
        clearInterval(timer);
        hide("download-progress");
        const filename = status.filename
          ? status.filename.split("/").pop()
          : "视频文件";
        $("saved-path").textContent = `~/Downloads/${filename}`;
        show("download-done");
      } else if (status.status === "error") {
        clearInterval(timer);
        hide("download-progress");
        showError(`下载失败：${status.error}`);
        show("video-info");
      }
    } catch {
      clearInterval(timer);
      showError("无法获取下载状态");
    }
  }, POLL_INTERVAL);
}

// 主流程
async function main() {
  // 检查服务是否在线
  const online = await pingServer();
  if (!online) {
    hide("loading");
    show("server-offline");
    return;
  }

  // 获取当前 Tab URL
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url;

  if (!url || url.startsWith("chrome://") || url.startsWith("chrome-extension://")) {
    hide("loading");
    showError("当前页面不支持下载");
    return;
  }

  // 获取视频信息
  try {
    showInfo(`正在解析: ${new URL(url).hostname}`);
    const { title, formats } = await getVideoInfo(url);
    hide("status-bar");
    renderFormats(title, formats);
  } catch (err) {
    hide("loading");
    showError(`解析失败：${err.message}`);
    return;
  }

  // 监听下载按钮点击
  $("formats-list").addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-download");
    if (!btn) return;

    // 禁用所有按钮防止重复点击
    document.querySelectorAll(".btn-download").forEach((b) => (b.disabled = true));

    const formatId = btn.dataset.formatId;
    try {
      const { task_id } = await startDownload(url, formatId);
      startProgressPolling(task_id);
    } catch (err) {
      document.querySelectorAll(".btn-download").forEach((b) => (b.disabled = false));
      showError(`启动下载失败：${err.message}`);
    }
  });

  // 返回按钮
  $("btn-back").addEventListener("click", () => {
    hide("download-done");
    document.querySelectorAll(".btn-download").forEach((b) => (b.disabled = false));
    show("video-info");
  });
}

main().catch((err) => {
  hide("loading");
  showError(`错误：${err.message}`);
});
```

- [ ] **Step 2: 在 Chrome 中手动验证扩展流程**

```
1. 重新加载扩展
2. 打开 https://www.youtube.com/watch?v=dQw4w9WgXcQ
3. 确保本地服务已启动：cd server && python server.py
4. 点击插件图标
5. 验证：显示"正在解析..."→ 出现格式列表，最大尺寸排首位
6. 点击第一个"下载"按钮
7. 验证：出现进度条，进度更新，最终显示"✓ 下载完成"
```

- [ ] **Step 3: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add extension/popup.js
git commit -m "feat: add popup interaction logic with download and progress polling"
```

---

## Task 10: 端到端测试 — yfsp.tv 与 YouTube

**Files:** 无新文件

- [ ] **Step 1: 启动服务**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo/server
python server.py
```

- [ ] **Step 2: 测试 yfsp.tv 链接（API 层）**

```bash
curl -s -X POST http://localhost:8765/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF"}' \
  | python3 -m json.tool
```

预期：返回包含 `title`、`formats` 数组的 JSON，formats 按 filesize 降序排列

- [ ] **Step 3: 下载 yfsp.tv 视频（API 层）**

```bash
# 用上一步返回的第一个 format_id
FORMAT_ID=$(curl -s -X POST http://localhost:8765/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF"}' \
  | python3 -c "import sys,json; data=json.load(sys.stdin); print(data['formats'][0]['format_id'])")

curl -s -X POST http://localhost:8765/api/download \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF\", \"format_id\": \"${FORMAT_ID}\", \"output_dir\": \"~/Downloads\"}" \
  | python3 -m json.tool
```

- [ ] **Step 4: 轮询下载状态直到完成**

```bash
TASK_ID=<上一步返回的 task_id>
while true; do
  STATUS=$(curl -s "http://localhost:8765/api/status?task_id=${TASK_ID}" | python3 -m json.tool)
  echo "$STATUS"
  echo "$STATUS" | grep -q '"done"' && break
  echo "$STATUS" | grep -q '"error"' && break
  sleep 2
done
```

预期：最终状态变为 `done`，`~/Downloads` 目录中出现下载的视频文件

- [ ] **Step 5: 测试 YouTube 链接**

```bash
curl -s -X POST http://localhost:8765/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' \
  | python3 -m json.tool
```

预期：返回多种画质格式，1080p/720p 排在前面

- [ ] **Step 6: 通过扩展测试完整流程**

```
1. 打开 https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF
2. 点击插件图标
3. 验证格式列表出现，最大尺寸排首位
4. 点击下载，验证进度条正常更新
5. 验证下载完成提示和文件路径
```

- [ ] **Step 7: 运行全部单元测试**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo/server
python -m pytest tests/ -v
```

预期：全部 passed

- [ ] **Step 8: Commit**

```bash
cd /Users/jie.liu/Projects/github/downloadvideo
git add -A
git commit -m "test: end-to-end validation for yfsp.tv and YouTube"
```

---

## Self-Review

**Spec 覆盖检查：**
- ✅ YouTube 下载（yt-dlp，Task 10）
- ✅ yfsp.tv 下载（Task 6 + 6b + 10）
- ✅ 格式按文件大小降序（Task 3）
- ✅ filesize/filesize_approx 均为 null 排末尾（Task 3 test）
- ✅ 本地服务未启动提示（popup.js + popup.html）
- ✅ 下载进度轮询（Task 9）
- ✅ 断点续传（downloader.py `continuedl: True`）
- ✅ 方案 C 记录在设计文档中（不在实现范围内）

**类型一致性：**
- `get_info` / `download` / `get_task_status` 在 downloader.py 定义，routes.py 正确导入 ✅
- `task_id` 在所有地方均为 8 位 UUID 字符串 ✅
- API 响应字段 `format_id`、`display_size`、`filesize` 在 downloader.py 和 popup.js 中保持一致 ✅
