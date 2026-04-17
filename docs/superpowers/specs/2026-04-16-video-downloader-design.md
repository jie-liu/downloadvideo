# Video Downloader — 设计文档

**日期**：2026-04-16  
**版本**：v1.0  
**状态**：已批准，待实现

---

## 1. 项目概述

开发一款视频下载工具，支持 YouTube、yfsp.tv 及 yt-dlp 兼容的 1000+ 视频网站。产品形态为 **Chrome 扩展 + 本地 Python Flask 服务**（方案 B），方案 C（增加网页版 + 降级请求拦截）已记录，视后续需求决定是否切换。

### 目标
- 用户在视频页面点击插件图标，看到可下载的格式列表（按文件大小降序排列）
- 一键下载到本地 `~/Downloads` 目录
- 支持 YouTube（依赖 yt-dlp）和 yfsp.tv（HLS m3u8，依赖 yt-dlp）

### 不在范围内（v1）
- 批量下载 / 播放列表
- 内置视频播放器
- 浏览器内预览
- 网页版 UI（方案 C 后备）
- 自动更新机制

---

## 2. 技术方案

**采用方案 B：Chrome 扩展 + 本地 Python Flask 服务**

备选方案 C（Chrome 扩展 + 本地服务 + Web UI + 降级拦截）已记录，若方案 B 无法满足需求可切换。

### 核心技术栈
- **Chrome 扩展**：Manifest V3，Vanilla JS（无框架，保持轻量）
- **本地服务**：Python 3.9+，Flask，yt-dlp
- **通信**：HTTP REST，localhost:8765，CORS 放通扩展 origin

---

## 3. 架构

```
┌─────────────────────────────┐      HTTP/localhost:8765
│   Chrome Extension          │ ◄──────────────────────────┐
│  - popup.html/js/css        │                            │
│  - background.js            │                            │
│  - manifest.json            │                            │
└─────────────────────────────┘                            │
                                                           │
┌─────────────────────────────────────────────────────────┐│
│   本地 Python Flask 服务 (localhost:8765)                ││
│  server.py → routes.py → downloader.py                  ││
│  yt-dlp 核心引擎                                         ││
└─────────────────────────────────────────────────────────┘│
                                     └─────────────────────┘
```

### 目录结构

```
downloadvideo/
├── extension/
│   ├── manifest.json          # MV3，权限声明
│   ├── popup.html             # 插件弹窗 UI
│   ├── popup.js               # 弹窗逻辑：调用 API、渲染列表、触发下载
│   ├── popup.css              # 样式（暗色主题）
│   └── background.js          # Service Worker：检测本地服务状态
├── server/
│   ├── server.py              # Flask 主入口，CORS 配置
│   ├── routes.py              # API 路由注册
│   ├── downloader.py          # yt-dlp 封装：get_info / download
│   ├── config.py              # 端口、下载目录等配置
│   └── requirements.txt       # flask, flask-cors, yt-dlp
└── docs/
    └── superpowers/specs/
        └── 2026-04-16-video-downloader-design.md
```

---

## 4. API 设计

### POST /api/info
**请求**
```json
{ "url": "https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF" }
```
**响应**（格式列表按 filesize 降序排列）
```json
{
  "title": "视频标题",
  "formats": [
    {
      "format_id": "137+140",
      "resolution": "1920x1080",
      "ext": "mp4",
      "filesize": 524288000,
      "filesize_approx": null,
      "display_size": "500 MB"
    }
  ]
}
```
- filesize 为 null 时用 filesize_approx 替代；两者均为 null 则排到列表末尾

### POST /api/download
**请求**
```json
{
  "url": "https://...",
  "format_id": "137+140",
  "output_dir": "~/Downloads"
}
```
**响应**
```json
{ "task_id": "abc123", "status": "started" }
```

### GET /api/status?task_id=abc123
**响应**
```json
{
  "task_id": "abc123",
  "status": "downloading",   // started | downloading | done | error
  "progress": 45.2,          // 百分比
  "filename": "视频标题.mp4",
  "error": null
}
```

### GET /api/ping
**响应**：`{"status": "ok"}` — 扩展用于检测服务是否在线

---

## 5. Chrome 扩展行为

### manifest.json 关键配置
```json
{
  "manifest_version": 3,
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["http://localhost:8765/*"]
}
```

### Popup 交互流程
1. 打开 → 显示"加载中…"，同时 ping 本地服务
2. 服务未启动 → 显示红色提示"请先启动本地服务"及启动命令
3. 服务在线 → 获取当前 activeTab URL → 调用 `/api/info`
4. 返回格式列表 → 渲染（每行：分辨率 | 格式 | 大小 | 下载按钮）
5. 点击下载 → 调用 `/api/download` → 轮询 `/api/status`（每 2 秒）
6. 完成 → 显示"已保存到 ~/Downloads/xxx.mp4"；失败 → 显示错误信息

---

## 6. downloader.py 核心逻辑

```python
# get_info：获取格式列表，按大小降序
ydl_opts = {"quiet": True, "no_warnings": True}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)

formats = []
for f in info.get("formats", []):
    size = f.get("filesize") or f.get("filesize_approx")
    formats.append({...})

# 按 filesize 降序，None 排末尾
formats.sort(key=lambda x: x["filesize"] or -1, reverse=True)

# download：后台线程执行，更新 task 状态
ydl_opts = {
    "format": format_id,
    "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
    "continue": True,          # 断点续传
    "progress_hooks": [hook],  # 更新进度
}
```

---

## 7. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 本地服务未启动 | Popup 显示启动命令 `python server/server.py` |
| yt-dlp 未安装 | 服务启动时检测，返回 `{"error": "yt-dlp not found", "install": "pip install yt-dlp"}` |
| 网站不支持 | 透传 yt-dlp 错误信息给 Popup |
| filesize 为 null | 用 filesize_approx 替代，仍排序；两者均 null 排末尾 |
| 下载中断 | `--continue` 参数支持断点续传 |
| CORS 问题 | flask-cors 放通所有 localhost 来源 |

---

## 8. 测试用例

| 测试场景 | 链接 | 预期结果 |
|---------|------|---------|
| yfsp.tv 基础下载 | `https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF` | 解析成功，显示格式列表，最大文件排首位，可正常下载 |
| YouTube 下载 | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` | 解析成功，显示多种画质，下载到 ~/Downloads |
| 服务未启动 | 任意 URL | Popup 显示红色提示和启动命令 |
| 不支持的网站 | `https://example.com` | Popup 显示友好错误提示 |
| filesize 为空 | 部分网站 | 有 filesize_approx 的仍排序，全为 null 排末尾 |

---

## 9. 备选方案记录

### 方案 C（已记录，备用）

在方案 B 基础上增加：
- **降级模式**：本地服务未启动时，扩展用 `chrome.webRequest` 拦截页面网络请求，捕获 m3u8/mp4 URL，以只读方式展示可下载链接
- **Web UI**：本地服务同时提供网页版（`localhost:8765`），支持粘贴链接直接下载，无需安装扩展
- 触发条件：方案 B 用户反馈安装门槛过高，或需要在无 Chrome 环境使用

---

## 10. 启动说明（开发者）

```bash
# 1. 安装依赖
cd server
pip install -r requirements.txt

# 2. 启动本地服务
python server.py
# 输出：Running on http://localhost:8765

# 3. 加载扩展
# Chrome → 扩展程序 → 开发者模式 → 加载已解压的扩展程序 → 选择 extension/ 目录
```
