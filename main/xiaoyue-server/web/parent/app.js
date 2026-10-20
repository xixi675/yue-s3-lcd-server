const state = {
  token: sessionStorage.getItem("xiaoyueParentToken") || "",
  overview: null,
  loading: false,
};

const elements = {
  refreshButton: document.querySelector("#refreshButton"),
  authBanner: document.querySelector("#authBanner"),
  errorBanner: document.querySelector("#errorBanner"),
  authDialog: document.querySelector("#authDialog"),
  authForm: document.querySelector("#authForm"),
  tokenInput: document.querySelector("#tokenInput"),
  authError: document.querySelector("#authError"),
  metricServer: document.querySelector("#metricServer"),
  metricUptime: document.querySelector("#metricUptime"),
  metricDevices: document.querySelector("#metricDevices"),
  metricKnowledge: document.querySelector("#metricKnowledge"),
  metricCategories: document.querySelector("#metricCategories"),
  metricRules: document.querySelector("#metricRules"),
  metricRuleCategories: document.querySelector("#metricRuleCategories"),
  sidebarDot: document.querySelector("#sidebarDot"),
  sidebarStatus: document.querySelector("#sidebarStatus"),
  deviceBadge: document.querySelector("#deviceBadge"),
  deviceList: document.querySelector("#deviceList"),
  moduleList: document.querySelector("#moduleList"),
  ragBadge: document.querySelector("#ragBadge"),
  categoryList: document.querySelector("#categoryList"),
  knowledgeTitles: document.querySelector("#knowledgeTitles"),
  musicSummary: document.querySelector("#musicSummary"),
  musicList: document.querySelector("#musicList"),
  filterBadge: document.querySelector("#filterBadge"),
  filterForm: document.querySelector("#filterForm"),
  filterText: document.querySelector("#filterText"),
  filterResult: document.querySelector("#filterResult"),
  lastUpdated: document.querySelector("#lastUpdated"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDuration(seconds) {
  const value = Number(seconds || 0);
  if (value < 60) return `${value} 秒`;
  if (value < 3600) return `${Math.floor(value / 60)} 分钟`;
  if (value < 86400) {
    return `${Math.floor(value / 3600)} 小时 ${Math.floor((value % 3600) / 60)} 分钟`;
  }
  return `${Math.floor(value / 86400)} 天 ${Math.floor((value % 86400) / 3600)} 小时`;
}

function formatTime(timestamp) {
  if (!timestamp) return "--";
  return new Date(timestamp * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function showError(message) {
  elements.errorBanner.textContent = message;
  elements.errorBanner.hidden = false;
  elements.sidebarDot.classList.remove("online");
  elements.sidebarStatus.textContent = "连接异常";
}

function clearError() {
  elements.errorBanner.hidden = true;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    if (!elements.authDialog.open) elements.authDialog.showModal();
    elements.tokenInput.focus();
    throw new Error("unauthorized");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.message || `请求失败：${response.status}`);
  }
  return response.json();
}

function renderDevices(server) {
  elements.metricDevices.textContent = String(server.device_count);
  elements.deviceBadge.textContent = `${server.device_count} 台`;
  elements.sidebarDot.classList.add("online");
  elements.sidebarStatus.textContent = "服务在线";

  if (!server.devices.length) {
    elements.deviceList.innerHTML = '<div class="empty-state">当前没有设备连接</div>';
    return;
  }
  elements.deviceList.innerHTML = server.devices
    .map(
      (device) => `
        <div class="device-item">
          <div>
            <strong>${escapeHtml(device.device_id)}</strong>
            <small>${escapeHtml(device.peer)}</small>
          </div>
          <div class="device-meta">
            已连接 ${formatDuration(device.connected_seconds)}<br>
            自 ${formatTime(device.connected_at)}
          </div>
        </div>
      `,
    )
    .join("");
}

function renderModules(modules) {
  const modelLabel = modules.model
    ? `${modules.llm} · ${modules.model}`
    : modules.llm || "--";
  const rows = [
    ["大模型", modelLabel],
    ["语音识别", modules.asr || "--"],
    ["语音合成", modules.tts || "--"],
    ["意图模式", modules.intent || "--"],
  ];
  elements.moduleList.innerHTML = rows
    .map(
      ([label, value]) =>
        `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`,
    )
    .join("");
}

function renderKnowledge(rag) {
  elements.metricKnowledge.textContent = String(rag.items || 0);
  elements.metricCategories.textContent = `${rag.categories?.length || 0} 个分类`;
  elements.ragBadge.textContent = rag.enabled ? "RAG 已启用" : "RAG 未启用";
  elements.ragBadge.classList.toggle("badge-muted", !rag.enabled);

  const categories = rag.categories || [];
  elements.categoryList.innerHTML = categories.length
    ? categories
        .map(
          (category) =>
            `<span class="tag">${escapeHtml(category.name)} <b>${category.count}</b></span>`,
        )
        .join("")
    : '<span class="empty-inline">暂无分类</span>';

  const titles = rag.titles || [];
  elements.knowledgeTitles.innerHTML = titles.length
    ? titles
        .map(
          (title) =>
            `<div class="content-item" title="${escapeHtml(title)}"><span>${escapeHtml(title)}</span></div>`,
        )
        .join("")
    : '<span class="empty-inline">暂无内容</span>';
}

function renderMusic(music) {
  elements.musicSummary.textContent = `共 ${music.count} 首本地儿歌`;
  elements.musicList.innerHTML = music.items.length
    ? music.items
        .map(
          (title) =>
            `<div class="content-item" title="${escapeHtml(title)}"><span>${escapeHtml(title)}</span></div>`,
        )
        .join("")
    : '<span class="empty-inline">暂无儿歌</span>';
}

function renderSafety(safety) {
  elements.metricRules.textContent = String(safety.rules || 0);
  elements.metricRuleCategories.textContent = `${safety.categories || 0} 类内容`;
  elements.filterBadge.textContent = safety.enabled ? "过滤已启用" : "过滤已关闭";
  elements.filterBadge.classList.toggle("badge-muted", !safety.enabled);
}

function renderOverview(data) {
  state.overview = data;
  elements.metricServer.textContent = "在线";
  elements.metricUptime.textContent = `已运行 ${formatDuration(data.server.uptime_seconds)}`;
  elements.authBanner.hidden = data.auth.enabled;
  renderDevices(data.server);
  renderModules(data.modules);
  renderKnowledge(data.rag);
  renderMusic(data.music);
  renderSafety(data.safety);
  elements.lastUpdated.textContent = `更新于 ${new Date().toLocaleTimeString("zh-CN")}`;
}

async function loadOverview() {
  if (state.loading) return;
  state.loading = true;
  elements.refreshButton.disabled = true;
  clearError();
  try {
    const data = await api("/xiaoyue/parent/api/overview");
    renderOverview(data);
  } catch (error) {
    if (error.message !== "unauthorized") {
      showError(error.message || "无法读取家长端数据");
    }
  } finally {
    state.loading = false;
    elements.refreshButton.disabled = false;
  }
}

async function checkContent(event) {
  event.preventDefault();
  const text = elements.filterText.value.trim();
  if (!text) {
    elements.filterText.focus();
    return;
  }
  const button = elements.filterForm.querySelector("button[type='submit']");
  button.disabled = true;
  try {
    const result = await api("/xiaoyue/parent/api/check-content", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    elements.filterResult.hidden = false;
    elements.filterResult.className = `result-box ${result.blocked ? "blocked" : "allowed"}`;
    if (result.blocked) {
      elements.filterResult.innerHTML = `
        <strong>已拦截：${escapeHtml(result.category || "内容安全")}</strong>
        <span>${escapeHtml(result.text)}</span>
        <small>动作：${escapeHtml(result.action)}</small>
      `;
    } else {
      elements.filterResult.innerHTML = `
        <strong>未命中高风险规则</strong>
        <span>这段文字可以继续进入对话。</span>
      `;
    }
  } catch (error) {
    if (error.message !== "unauthorized") {
      elements.filterResult.hidden = false;
      elements.filterResult.className = "result-box blocked";
      elements.filterResult.innerHTML = `<strong>检测失败</strong><span>${escapeHtml(error.message)}</span>`;
    }
  } finally {
    button.disabled = false;
  }
}

elements.refreshButton.addEventListener("click", loadOverview);
elements.filterForm.addEventListener("submit", checkContent);

elements.authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const token = elements.tokenInput.value.trim();
  if (!token) return;
  state.token = token;
  sessionStorage.setItem("xiaoyueParentToken", token);
  elements.authError.hidden = true;
  elements.authDialog.close();
  loadOverview();
});

loadOverview();
setInterval(loadOverview, 30000);
