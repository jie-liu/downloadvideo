# Video Downloader

Chrome 扩展 + 本地 Python Flask 服务，支持 YouTube、yfsp.tv 及 1000+ 视频网站一键下载。

## 快速开始

```bash
# 1. 安装依赖
cd server
pip3 install -r requirements.txt

# 2. 启动本地服务
python3 server.py
# 输出：Video Downloader Server running at http://localhost:8765

# 3. 加载 Chrome 扩展
# Chrome → 扩展程序 → 开发者模式 → 加载已解压的扩展程序 → 选择 extension/ 目录
```

## 功能

- 自动识别页面视频，列出所有可用格式（按画质从高到低）
- 最高画质标注 "最高画质" 徽章，音频选项单独显示在末尾
- 下载进度实时显示，支持 ✕ 按钮取消
- 下载文件名使用视频页面标题，保存到 `~/Downloads`
- 绕过 Cloudflare 保护（扩展直接从浏览器 DOM 抓取视频 URL）

## 已测试网站

| 网站 | 测试链接 | 提取方式 |
|------|---------|---------|
| yfsp.tv | `https://www.yfsp.tv/watch?v=0xItNu7p1YRzB5fikyH6fF` | 自定义提取器（MasterPlayList API）|
| taiav.com | `https://taiav.com/cn/movie/675a8ad56dede10b592ef178` | 自定义提取器（/api/getmovie）|
| 91md.me | `https://91md.me/index.php/vod/play/id/33300/sid/1/nid/1.html` | 通用 HTML 扫描（m3u8 提取）|
| avple.tv | `https://avple.tv/video/163516315180610` | 扩展传 HTML 绕过 Cloudflare |
| YouTube | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` | yt-dlp 原生支持 |

## 架构

```
extension/          Chrome 扩展（Manifest V3）
├── popup.html/js/css   弹窗 UI
├── background.js       Service Worker
└── manifest.json

server/             本地 Flask 服务（localhost:8765）
├── server.py           Flask 入口
├── routes.py           API 路由（/api/info /api/download /api/status /api/cancel）
├── downloader.py       提取器管道（yt-dlp → yfsp → taiav → 通用扫描）
└── requirements.txt
```

## API

| 端点 | 说明 |
|------|------|
| `GET /api/ping` | 检测服务是否在线 |
| `POST /api/info` | 获取视频格式列表 |
| `POST /api/download` | 启动后台下载，返回 task_id |
| `GET /api/status?task_id=` | 查询下载进度 |
| `POST /api/cancel?task_id=` | 取消下载 |
