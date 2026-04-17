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
    const resp = await fetch(`${SERVER}/api/ping`, { signal: AbortSignal.timeout(2000) });
    return resp.ok;
  } catch { return false; }
}

async function getPageData(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const videoUrls = performance
          .getEntriesByType("resource")
          .map((e) => e.name)
          .filter((u) => /\.(m3u8|mp4)(\?|$)/i.test(u));
        document.querySelectorAll("video[src], source[src]").forEach((el) => {
          const s = el.src || el.getAttribute("src");
          if (s && /\.(m3u8|mp4)/i.test(s)) videoUrls.push(s);
        });
        return { html: document.documentElement.outerHTML, videoUrls: [...new Set(videoUrls)] };
      },
    });
    return results?.[0]?.result || { html: null, videoUrls: [] };
  } catch { return { html: null, videoUrls: [] }; }
}

async function getVideoInfo(url, tabId) {
  const { html, videoUrls } = await getPageData(tabId);
  const body = { url };
  if (html) body.html = html;
  if (videoUrls && videoUrls.length > 0) body.video_urls = videoUrls;
  const resp = await fetch(`${SERVER}/api/info`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: "未知错误" }));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }
  return resp.json();
}

async function cancelDownload(taskId) {
  try { await fetch(`${SERVER}/api/cancel?task_id=${taskId}`, { method: "POST" }); } catch {}
}

async function startDownload(url, formatId, directUrl, referer, title) {
  const body = { url, format_id: formatId, output_dir: "~/Downloads" };
  if (directUrl) body.direct_url = directUrl;
  if (referer) body.referer = referer;
  if (title) body.title = title;
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

// ─── 修复面板 ────────────────────────────────────────────────
function showRepairPanel() {
  hide("loading"); hide("video-info"); hide("download-done");
  hide("download-progress"); hide("fix-progress"); hide("status-bar");
  hide("broken-list"); $("broken-list").innerHTML = "";
  $("scan-hint").textContent = "找出格式损坏的 MP4";
  show("repair-panel");
}

function hideRepairPanel() {
  hide("repair-panel"); hide("fix-progress");
}

async function scanBrokenFiles() {
  $("scan-hint").textContent = "扫描中...";
  try {
    const resp = await fetch(`${SERVER}/api/scan`);
    const { files } = await resp.json();
    const list = $("broken-list");
    list.innerHTML = "";
    if (!files || files.length === 0) {
      $("scan-hint").textContent = "~/Downloads 中未发现损坏文件 ✓";
      return;
    }
    $("scan-hint").textContent = `发现 ${files.length} 个损坏文件`;
    files.forEach((f) => {
      const item = document.createElement("div");
      item.className = "broken-item";
      item.innerHTML = `
        <span class="broken-item-name" title="${f.path}">${f.name}</span>
        <span class="broken-item-size">${f.size}</span>
        <button class="btn-fix-small" data-path="${f.path}">修复</button>
      `;
      list.appendChild(item);
    });
    show("broken-list");
  } catch {
    $("scan-hint").textContent = "扫描失败";
  }
}

async function fixFile(path) {
  hide("repair-panel");
  show("fix-progress");
  $("fix-result").className = "fix-result hidden";
  $("fix-result").textContent = "";
  $("fix-progress-fill").style.width = "50%";

  try {
    const resp = await fetch(`${SERVER}/api/fix`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const data = await resp.json();
    $("fix-progress-fill").style.width = "100%";
    $("fix-progress-fill").style.animation = "none";
    const res = $("fix-result");
    if (data.ok) {
      res.textContent = `✓ 修复完成：${data.path.split("/").pop()}`;
      res.className = "fix-result success";
    } else {
      res.textContent = `✗ 修复失败：${data.error || "未知错误"}`;
      res.className = "fix-result error";
    }
    show("fix-result");
  } catch (e) {
    $("fix-result").textContent = `✗ 请求失败：${e.message}`;
    $("fix-result").className = "fix-result error";
    show("fix-result");
  }
}

// ─── 格式渲染 ────────────────────────────────────────────────
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
  formats.forEach((fmt, idx) => {
    const item = document.createElement("div");
    item.className = "format-item" + (fmt.is_audio ? " format-audio" : "");
    item.dataset.formatId = fmt.format_id;
    item.dataset.directUrl = fmt._direct_url || "";
    item.dataset.referer = fmt._referer || "";
    const badge = idx === 0 && !fmt.is_audio
      ? '<span class="badge-best">最高画质</span>'
      : (fmt.is_audio ? '<span class="badge-audio">仅音频</span>' : "");
    item.innerHTML = `
      <div class="format-meta">
        <div class="format-resolution">${fmt.resolution}${badge}</div>
        <div class="format-detail">${(fmt.ext || "").toUpperCase()} · ${fmt.display_size}</div>
      </div>
      <button class="btn-download">下载</button>
    `;
    list.appendChild(item);
  });
  show("video-info");
}

// ─── 下载进度轮询 ────────────────────────────────────────────
function startProgressPolling(taskId, savedPathRef) {
  hide("video-info"); hide("status-bar");
  show("download-progress");
  $("progress-text").textContent = "下载中...";
  $("progress-fill").style.width = "0%";
  $("progress-percent").textContent = "0%";

  let failCount = 0;
  const MAX_FAILS = 3;

  const stop = (restoreFormats = false) => {
    clearInterval(timer);
    hide("download-progress");
    if (restoreFormats) {
      document.querySelectorAll(".btn-download").forEach((b) => (b.disabled = false));
      show("video-info");
    }
  };

  $("btn-cancel").onclick = async () => {
    await cancelDownload(taskId);
    stop(true);
    showInfo("下载已取消");
  };

  const timer = setInterval(async () => {
    try {
      const status = await pollStatus(taskId);
      failCount = 0;

      if (status.status === "remuxing") {
        $("progress-text").textContent = "转换格式中...";
        $("progress-fill").style.width = "99%";
        $("progress-percent").textContent = "99%";
      } else if (status.status === "downloading" || status.status === "started") {
        $("progress-text").textContent = "下载中...";
        const pct = Math.round(status.progress || 0);
        $("progress-fill").style.width = `${pct}%`;
        $("progress-percent").textContent = `${pct}%`;
      } else if (status.status === "done") {
        stop();
        const filepath = status.filename || "";
        const filename = filepath.split("/").pop() || "视频文件";
        $("saved-path").textContent = `~/Downloads/${filename}`;
        // 若文件仍是 TS（remux 失败），显示修复按钮
        if (status.is_ts) {
          $("btn-fix-downloaded").dataset.path = filepath;
          show("btn-fix-downloaded");
        } else {
          hide("btn-fix-downloaded");
        }
        show("download-done");
      } else if (status.status === "cancelled") {
        stop(true); showInfo("下载已取消");
      } else if (status.status === "error") {
        stop(true); showError(`下载失败：${status.error}`);
      }
    } catch {
      if (++failCount >= MAX_FAILS) {
        stop(true); showError("无法获取下载状态（网络连接问题）");
      }
    }
  }, POLL_INTERVAL);
}

// ─── main ────────────────────────────────────────────────────
async function main() {
  // 🔧 修复面板 tab 按钮
  $("btn-repair-tab").addEventListener("click", () => {
    if (!$("repair-panel").classList.contains("hidden")) {
      hideRepairPanel();
      show("loading"); // 回到初始化状态（main 已跑完会显示 video-info）
      show("video-info"); hide("loading");
    } else {
      showRepairPanel();
    }
  });

  $("btn-repair-back").addEventListener("click", () => {
    hideRepairPanel();
    show("video-info");
  });

  $("btn-scan").addEventListener("click", scanBrokenFiles);

  $("broken-list").addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-fix-small");
    if (btn) fixFile(btn.dataset.path);
  });

  $("btn-fix-manual").addEventListener("click", () => {
    const path = $("repair-path-input").value.trim();
    if (path) fixFile(path);
  });

  $("btn-fix-downloaded").addEventListener("click", () => {
    const path = $("btn-fix-downloaded").dataset.path;
    if (path) fixFile(path);
  });

  const online = await pingServer();
  if (!online) { hide("loading"); show("server-offline"); return; }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url;

  if (!url || url.startsWith("chrome://") || url.startsWith("chrome-extension://")) {
    hide("loading"); showError("当前页面不支持下载"); return;
  }

  try {
    showInfo(`正在解析: ${new URL(url).hostname}`);
    const { title, formats } = await getVideoInfo(url, tab.id);
    hide("status-bar");
    renderFormats(title, formats);
  } catch (err) {
    hide("loading"); showError(`解析失败：${err.message}`); return;
  }

  $("formats-list").addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-download");
    if (!btn) return;
    document.querySelectorAll(".btn-download").forEach((b) => (b.disabled = true));
    const item = btn.closest(".format-item");
    const formatId = item.dataset.formatId;
    const directUrl = item.dataset.directUrl || null;
    const referer = item.dataset.referer || null;
    const title = $("video-title").textContent || null;
    try {
      const { task_id } = await startDownload(url, formatId, directUrl, referer, title);
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

main().catch((err) => { hide("loading"); showError(`错误：${err.message}`); });
