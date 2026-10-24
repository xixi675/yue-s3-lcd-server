const state = {
  token: sessionStorage.getItem("xiaoyueParentToken") || "",
  overview: null,
  loading: false,
  conversationTab: "current",
  selectedConversationId: null,
  conversationsLoading: false,
};

const elements = {
  refreshButton: document.querySelector("#refreshButton"),
  authBanner: document.querySelector("#authBanner"),
  errorBanner: document.querySelector("#errorBanner"),
  authDialog: document.querySelector("#authDialog"),
  authForm: document.querySelector("#authForm"),
  tokenInput: document.querySelector("#tokenInput"),
  authError: document.querySelector("#authError"),
  overviewTitle: document.querySelector("#overviewTitle"),
  overviewDescription: document.querySelector("#overviewDescription"),
  metricServer: document.querySelector("#metricServer"),
  metricUptime: document.querySelector("#metricUptime"),
  metricDevices: document.querySelector("#metricDevices"),
  metricModel: document.querySelector("#metricModel"),
  metricModelName: document.querySelector("#metricModelName"),
  sidebarDot: document.querySelector("#sidebarDot"),
  sidebarStatus: document.querySelector("#sidebarStatus"),
  deviceBadge: document.querySelector("#deviceBadge"),
  deviceList: document.querySelector("#deviceList"),
  conversationTitle: document.querySelector("#conversationTitle"),
  conversationBadge: document.querySelector("#conversationBadge"),
  conversationLayout: document.querySelector("#conversationLayout"),
  conversationHistoryPane: document.querySelector("#conversationHistoryPane"),
  conversationList: document.querySelector("#conversationList"),
  conversationMeta: document.querySelector("#conversationMeta"),
  conversationMessages: document.querySelector("#conversationMessages"),
  conversationTabs: document.querySelectorAll("[data-conversation-tab]"),
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
  const onlineCount = Number(server.device_count || 0);
  const knownCount = Number(server.known_device_count || 0);
  elements.overviewTitle.textContent =
    onlineCount > 0
      ? `小月在线，${onlineCount} 台设备正在连接`
      : knownCount > 0
        ? "小月在线，设备暂时离线"
        : "小月在线，等待设备联网";
  elements.overviewDescription.textContent =
    onlineCount > 0
      ? `后端已运行 ${formatDuration(server.uptime_seconds)}，当前设备连接正常，可以继续语音对话。`
      : knownCount > 0
        ? `后端已运行 ${formatDuration(server.uptime_seconds)}，设备目前处于待机或离线状态。`
        : `后端已运行 ${formatDuration(server.uptime_seconds)}。设备联网后，对话记录和内容安全状态会显示在这里。`;

  elements.metricDevices.textContent = String(server.device_count);
  elements.deviceBadge.textContent =
    server.device_count > 0
      ? `${server.device_count} 台在线`
      : server.known_device_count > 0
        ? `${server.known_device_count} 台已记录`
        : "暂无设备";
  elements.sidebarDot.classList.add("online");
  elements.sidebarStatus.textContent = "服务在线";

  if (!server.devices.length) {
    elements.deviceList.innerHTML =
      '<div class="empty-state">暂无设备记录，设备联网后会显示在这里</div>';
    return;
  }
  elements.deviceList.innerHTML = server.devices
    .map((device) => {
      const statusLabel =
        device.status === "online"
          ? "在线"
          : device.status === "idle"
            ? "待机"
            : "离线";
      const statusClass = device.online ? "" : " badge-muted";
      const meta = device.online
        ? `本次连接 ${formatDuration(device.connected_seconds)}<br>最近在线 ${formatTime(device.last_seen)}`
        : `最近在线 ${formatTime(device.last_seen)}<br>${formatDuration(device.last_seen_seconds)}前`;
      return `
        <div class="device-item">
          <div>
            <strong>${escapeHtml(device.device_id)}</strong>
            <small>${escapeHtml(device.peer)}</small>
          </div>
          <div class="device-meta">
            <span class="badge${statusClass}">${statusLabel}</span><br>
            ${meta}
          </div>
        </div>
      `;
    })
    .join("");
}

function renderConversationMessages(conversation) {
  if (!conversation || !conversation.messages.length) {
    elements.conversationMessages.innerHTML =
      '<div class="empty-state">暂无对话内容，唤醒小月并开始聊天后会显示在这里</div>';
    return;
  }

  elements.conversationMessages.innerHTML = conversation.messages
    .map((message) => {
      const isUser = message.role === "user";
      return `
        <article class="message-row ${isUser ? "message-user" : "message-assistant"}">
          <div class="message-heading">
            <strong>${isUser ? "孩子" : "小月"}</strong>
            <time>${formatTime(message.created_at)}</time>
          </div>
          <p>${escapeHtml(message.content)}</p>
        </article>
      `;
    })
    .join("");

  if (conversation.active) {
    elements.conversationMessages.scrollTop =
      elements.conversationMessages.scrollHeight;
  }
}

function renderConversationList(sessions, selectedId) {
  if (!sessions.length) {
    elements.conversationList.innerHTML =
      '<div class="empty-state compact">暂无历史对话</div>';
    return;
  }
  elements.conversationList.innerHTML = sessions
    .map(
      (session) => `
        <button
          class="conversation-session${session.id === selectedId ? " active" : ""}"
          type="button"
          data-session-id="${escapeHtml(session.id)}"
        >
          <span class="conversation-session-top">
            <strong>${formatTime(session.started_at)}</strong>
            <small>${session.active ? "进行中" : `${session.message_count} 条`}</small>
          </span>
          <span class="conversation-session-preview">${escapeHtml(session.preview || "暂无文字内容")}</span>
          <small>${escapeHtml(session.device_id || "未知设备")}</small>
        </button>
      `,
    )
    .join("");
}

function renderConversations(data) {
  const isHistory = state.conversationTab === "history";
  const conversation = isHistory
    ? data.selected || data.current
    : data.current;
  const selectedId = conversation?.id || null;

  elements.conversationTitle.textContent = "对话记录";
  elements.conversationLayout.classList.toggle("show-history", isHistory);
  elements.conversationHistoryPane.hidden = !isHistory;

  if (isHistory) {
    renderConversationList(data.sessions || [], selectedId);
  }

  if (!conversation) {
    elements.conversationBadge.textContent = "暂无记录";
    elements.conversationBadge.classList.add("badge-muted");
    elements.conversationMeta.textContent = "还没有可查看的对话";
    renderConversationMessages(null);
    return;
  }

  elements.conversationBadge.textContent = conversation.active
    ? "进行中"
    : "最近一次";
  elements.conversationBadge.classList.toggle(
    "badge-muted",
    !conversation.active,
  );
  elements.conversationMeta.innerHTML = `
    <span>${escapeHtml(conversation.device_id || "未知设备")}</span>
    <span>${formatTime(conversation.started_at)}</span>
    <span>${conversation.messages.length} 条消息</span>
  `;
  renderConversationMessages(conversation);
}

async function loadConversations() {
  if (state.conversationsLoading) return;
  state.conversationsLoading = true;
  try {
    const query =
      state.conversationTab === "history" && state.selectedConversationId
        ? `?session_id=${encodeURIComponent(state.selectedConversationId)}`
        : "";
    const data = await api(`/xiaoyue/parent/api/conversations${query}`);
    renderConversations(data);
  } catch (error) {
    if (error.message !== "unauthorized") {
      elements.conversationBadge.textContent = "读取失败";
      elements.conversationBadge.classList.add("badge-muted");
      elements.conversationMeta.textContent = error.message || "无法读取对话记录";
    }
  } finally {
    state.conversationsLoading = false;
  }
}

function renderModules(modules) {
  elements.metricModel.textContent = modules.llm || "未配置";
  elements.metricModelName.textContent = modules.model || "未指定模型";
}

function renderKnowledge(rag) {
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

async function refreshDashboard() {
  await Promise.allSettled([loadOverview(), loadConversations()]);
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

elements.refreshButton.addEventListener("click", refreshDashboard);
elements.filterForm.addEventListener("submit", checkContent);

elements.conversationTabs.forEach((button) => {
  button.addEventListener("click", () => {
    state.conversationTab = button.dataset.conversationTab;
    if (state.conversationTab === "current") {
      state.selectedConversationId = null;
    }
    elements.conversationTabs.forEach((tab) => {
      const active = tab === button;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    loadConversations();
  });
});

elements.conversationList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-session-id]");
  if (!button) return;
  state.selectedConversationId = button.dataset.sessionId;
  loadConversations();
});

elements.authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const token = elements.tokenInput.value.trim();
  if (!token) return;
  state.token = token;
  sessionStorage.setItem("xiaoyueParentToken", token);
  elements.authError.hidden = true;
  elements.authDialog.close();
  refreshDashboard();
});

refreshDashboard();
setInterval(loadOverview, 30000);
setInterval(() => {
  if (!document.hidden) loadConversations();
}, 8000);
