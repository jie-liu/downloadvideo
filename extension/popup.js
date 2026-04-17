const SERVER = "http://localhost:8765";
const POLL_INTERVAL = 2000;

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

async function startDownload(url, formatId, directUrl) {
  const body = {
    url,
    format_id: formatId,
    output_dir: "~/Downloads",
  };
  // yfsp.tv 等自定义提取器：传递直接的 m3u8 URL
  if (directUrl) {
    body.direct_url = directUrl;
  }
  const resp = await fetch(`${SERVER}/api/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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
    show("video-info");
    return;
  }

  formats.forEach((fmt) => {
    const item = document.createElement("div");
    item.className = "format-item";
    // 把 _direct_url 存在 data 属性上（如果有）
    item.dataset.formatId = fmt.format_id;
    item.dataset.directUrl = fmt._direct_url || "";
    item.innerHTML = `
      <div class="format-meta">
        <div class="format-resolution">${fmt.resolution}</div>
        <div class="format-detail">${(fmt.ext || "").toUpperCase()} · ${fmt.display_size}</div>
      </div>
      <button class="btn-download">下载</button>
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

  let failCount = 0;
  const MAX_FAILS = 3;

  const timer = setInterval(async () => {
    try {
      const status = await pollStatus(taskId);
      failCount = 0; // 成功后重置

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
      failCount++;
      if (failCount >= MAX_FAILS) {
        clearInterval(timer);
        showError("无法获取下载状态（网络连接问题）");
      }
    }
  }, POLL_INTERVAL);
}

async function main() {
  const online = await pingServer();
  if (!online) {
    hide("loading");
    show("server-offline");
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url;

  if (!url || url.startsWith("chrome://") || url.startsWith("chrome-extension://")) {
    hide("loading");
    showError("当前页面不支持下载");
    return;
  }

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

  $("formats-list").addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-download");
    if (!btn) return;

    document.querySelectorAll(".btn-download").forEach((b) => (b.disabled = true));

    const item = btn.closest(".format-item");
    const formatId = item.dataset.formatId;
    const directUrl = item.dataset.directUrl || null;

    try {
      const { task_id } = await startDownload(url, formatId, directUrl);
      startProgressPolling(task_id);
    } catch (err) {
      document.querySelectorAll(".btn-download").forEach((b) => (b.disabled = false));
      showError(`启动下载失败：${err.message}`);
    }
  });

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
