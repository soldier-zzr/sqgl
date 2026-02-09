const STORAGE_KEY = "community_orders_v3";
const SESSION_KEY = "community_user_v1";
const TOKEN_KEY = "community_token_v1";
const USE_REMOTE = window.location.protocol !== "file:";

const USERS = [
  { username: "admin", password: "123456", role: "admin", displayName: "管理员" },
  { username: "member1", password: "123456", role: "member", displayName: "成员1" },
  { username: "member2", password: "123456", role: "member", displayName: "成员2" },
];

const FEISHU_HEADERS = {
  phase: "转化期数",
  groupName: "组别",
  sourceChannel: "渠道来源",
  sellPlatform: "售卖平台",
  nickname: "微信昵称",
  phone: "手机号",
  finalPhone: "尾款电话",
  owner: "筛选人",
  conversionDate: "成交日期",
  finalPaymentStatus: "尾款情况",
  ipNo: "IP号",
  ipTime: "加ip时间",
  followUp: "三筛选/跟进",
  amount: "转化金额",
  product: "转化产品",
  orderTime: "订单时间",
};

const HEADER_ALIASES = {
  phase: ["转化期数"],
  groupName: ["组别"],
  sourceChannel: ["渠道来源"],
  sellPlatform: ["售卖平台"],
  nickname: ["微信昵称"],
  phone: ["手机号"],
  finalPhone: ["尾款电话"],
  owner: ["筛选人", "负责人（教练）", "负责人", "使用人", "尾款电话筛选人"],
  collector: ["追款人", "尾款电话筛选人"],
  conversionDate: ["成交日期"],
  finalPaymentStatus: ["尾款情况"],
  ipNo: ["IP号"],
  ipTime: ["加ip时间", "加IP时间"],
  followUp: ["三筛选/跟进", "筛选/跟进", "跟进标签"],
  amount: ["转化金额", "金额", "转化金额（元）"],
  product: ["转化产品", "产品"],
  orderTime: ["订单时间"],
  note: ["备注", "沟通记录"],
  unpaidReason: ["未付款原因"],
};

const state = {
  orders: [],
  editingId: null,
  currentUser: null,
  filters: {
    date: "",
    nickname: "",
    owner: "",
    status: "",
    onlyQipan: true,
  },
  pagination: {
    page: 1,
    pageSize: 50,
  },
  selectedIds: new Set(),
};

const els = {
  loginSection: document.getElementById("loginSection"),
  appSection: document.getElementById("appSection"),
  loginForm: document.getElementById("loginForm"),
  loginUsername: document.getElementById("loginUsername"),
  loginPassword: document.getElementById("loginPassword"),
  welcomeText: document.getElementById("welcomeText"),
  logoutBtn: document.getElementById("logoutBtn"),
  importFile: document.getElementById("importFile"),

  orderForm: document.getElementById("orderForm"),
  conversionDate: document.getElementById("conversionDate"),
  phase: document.getElementById("phase"),
  groupName: document.getElementById("groupName"),
  sourceChannel: document.getElementById("sourceChannel"),
  sellPlatform: document.getElementById("sellPlatform"),
  finalPaymentStatus: document.getElementById("finalPaymentStatus"),
  nickname: document.getElementById("nickname"),
  phone: document.getElementById("phone"),
  finalPhone: document.getElementById("finalPhone"),
  owner: document.getElementById("owner"),
  ipNo: document.getElementById("ipNo"),
  ipTime: document.getElementById("ipTime"),
  followUp: document.getElementById("followUp"),
  amount: document.getElementById("amount"),
  note: document.getElementById("note"),

  resetBtn: document.getElementById("resetBtn"),
  ordersTbody: document.getElementById("ordersTbody"),
  statsCards: document.getElementById("statsCards"),
  dailySummary: document.getElementById("dailySummary"),
  personSummary: document.getElementById("personSummary"),
  statusLogList: document.getElementById("statusLogList"),
  filterDate: document.getElementById("filterDate"),
  filterNickname: document.getElementById("filterNickname"),
  filterOwner: document.getElementById("filterOwner"),
  filterOnlyQipan: document.getElementById("filterOnlyQipan"),
  filterStatus: document.getElementById("filterStatus"),
  clearFilterBtn: document.getElementById("clearFilterBtn"),
  deleteSelectedBtn: document.getElementById("deleteSelectedBtn"),
  selectAllOnPage: document.getElementById("selectAllOnPage"),
  exportBtn: document.getElementById("exportBtn"),
  prevPageBtn: document.getElementById("prevPageBtn"),
  nextPageBtn: document.getElementById("nextPageBtn"),
  pageInfo: document.getElementById("pageInfo"),
};

async function init() {
  bindEvents();
  await restoreSession();
  setDefaultFormTime();
  render();
}

async function apiRequest(path, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY) || "";
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function bindEvents() {
  els.loginForm.addEventListener("submit", handleLogin);
  els.logoutBtn.addEventListener("click", logout);
  els.orderForm.addEventListener("submit", onSubmit);
  els.resetBtn.addEventListener("click", resetForm);
  els.importFile.addEventListener("change", handleImportFile);

  els.filterDate.addEventListener("change", () => {
    state.filters.date = els.filterDate.value;
    state.pagination.page = 1;
    render();
  });

  els.filterNickname.addEventListener("input", () => {
    state.filters.nickname = els.filterNickname.value.trim();
    state.pagination.page = 1;
    render();
  });

  els.filterOwner.addEventListener("input", () => {
    state.filters.owner = els.filterOwner.value.trim();
    state.pagination.page = 1;
    render();
  });

  els.filterOnlyQipan.addEventListener("change", () => {
    state.filters.onlyQipan = els.filterOnlyQipan.checked;
    state.pagination.page = 1;
    render();
  });

  els.filterStatus.addEventListener("change", () => {
    state.filters.status = els.filterStatus.value;
    state.pagination.page = 1;
    render();
  });

  els.clearFilterBtn.addEventListener("click", () => {
    state.filters = { date: "", nickname: "", owner: "", status: "", onlyQipan: true };
    state.pagination.page = 1;
    els.filterDate.value = "";
    els.filterNickname.value = "";
    els.filterOwner.value = "";
    els.filterOnlyQipan.checked = true;
    els.filterStatus.value = "";
    render();
  });

  els.exportBtn.addEventListener("click", exportCsv);
  els.deleteSelectedBtn.addEventListener("click", deleteSelectedOrders);
  els.selectAllOnPage.addEventListener("change", toggleSelectAllOnPage);
  els.prevPageBtn.addEventListener("click", () => changePage(-1));
  els.nextPageBtn.addEventListener("click", () => changePage(1));
}

async function restoreSession() {
  if (USE_REMOTE) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    try {
      const data = await apiRequest("/api/me");
      state.currentUser = data.user;
      await loadOrders();
      toggleAuthView(true);
    } catch {
      localStorage.removeItem(TOKEN_KEY);
    }
    return;
  }

  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return;

  const user = USERS.find((item) => item.username === raw);
  if (!user) return;

  state.currentUser = user;
  await loadOrders();
  toggleAuthView(true);
}

async function handleLogin(event) {
  event.preventDefault();
  const username = els.loginUsername.value.trim();
  const password = els.loginPassword.value;
  try {
    if (USE_REMOTE) {
      const data = await apiRequest("/api/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem(TOKEN_KEY, data.token);
      state.currentUser = data.user;
      await loadOrders();
      toggleAuthView(true);
      render();
      return;
    }

    const user = USERS.find((item) => item.username === username && item.password === password);
    if (!user) {
      alert("账号或密码错误");
      return;
    }
    state.currentUser = user;
    localStorage.setItem(SESSION_KEY, user.username);
    await loadOrders();
    toggleAuthView(true);
    render();
  } catch {
    alert("登录失败，请检查服务是否已启动");
  }
}

function logout() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(TOKEN_KEY);
  state.currentUser = null;
  state.editingId = null;
  state.orders = [];
  state.selectedIds.clear();
  toggleAuthView(false);
}

function toggleAuthView(loggedIn) {
  els.loginSection.classList.toggle("hidden", loggedIn);
  els.appSection.classList.toggle("hidden", !loggedIn);

  if (loggedIn && state.currentUser) {
    els.welcomeText.textContent = `当前登录：${state.currentUser.displayName}（${state.currentUser.role === "admin" ? "管理员" : "成员"}）`;

    if (state.currentUser.role === "member") {
      els.owner.value = state.currentUser.displayName;
      els.owner.readOnly = true;
      els.filterOwner.value = state.currentUser.displayName;
      state.filters.owner = state.currentUser.displayName;
    } else {
      els.owner.readOnly = false;
    }
  }
}

async function onSubmit(event) {
  event.preventDefault();
  if (!ensureLogin()) return;

  const payload = collectFormData();
  if (!payload) return;

  try {
    if (state.editingId) {
      const current = state.orders.find((item) => item.id === state.editingId);
      if (current && !canEditOrder(current)) {
        alert("你没有权限编辑该订单");
        return;
      }

      let updatedOrder = null;
      state.orders = state.orders.map((order) => {
        if (order.id !== state.editingId) return order;
        const prevStatus = normalizeStatus(order.finalPaymentStatus);
        const nextStatus = normalizeStatus(payload.finalPaymentStatus);
        const nextLogs = normalizeStatusLogs(order);
        if (prevStatus !== nextStatus) {
          nextLogs.push(makeStatusLog(prevStatus, nextStatus));
        }
        updatedOrder = { ...order, ...payload, finalPaymentStatus: nextStatus, statusLogs: nextLogs };
        return updatedOrder;
      });
      if (USE_REMOTE && updatedOrder) {
        await apiRequest(`/api/orders/${encodeURIComponent(updatedOrder.id)}`, {
          method: "PUT",
          body: JSON.stringify({ order: updatedOrder }),
        });
      } else {
        persistOrders();
      }
      state.editingId = null;
    } else {
      const nextStatus = normalizeStatus(payload.finalPaymentStatus);
      const newOrder = {
        id: crypto.randomUUID(),
        createdBy: state.currentUser.username,
        ...payload,
        finalPaymentStatus: nextStatus,
        statusLogs: [makeStatusLog("新建", nextStatus)],
      };
      state.orders.unshift(newOrder);
      if (USE_REMOTE) {
        await apiRequest("/api/orders", {
          method: "POST",
          body: JSON.stringify({ order: newOrder }),
        });
      } else {
        persistOrders();
      }
    }

    resetForm();
    state.pagination.page = 1;
    render();
  } catch {
    alert("保存失败，请稍后重试");
    await loadOrders();
    render();
  }
}

function collectFormData() {
  const amount = Number(els.amount.value);
  if (Number.isNaN(amount) || amount < 0) {
    alert("请输入有效的金额");
    return null;
  }

  const owner = els.owner.value.trim() || (state.currentUser ? state.currentUser.displayName : "");
  if (!owner) {
    alert("请填写负责人");
    return null;
  }

  const amountMeta = deriveAmountMeta(els.sourceChannel.value.trim(), amount);

  return {
    conversionDate: els.conversionDate.value,
    phase: els.phase.value.trim(),
    groupName: els.groupName.value.trim(),
    sourceChannel: els.sourceChannel.value.trim(),
    sellPlatform: els.sellPlatform.value.trim(),
    finalPaymentStatus: els.finalPaymentStatus.value,
    nickname: els.nickname.value.trim(),
    phone: normalizePhone(els.phone.value.trim()),
    finalPhone: els.finalPhone.value.trim(),
    owner,
    ipNo: els.ipNo.value.trim(),
    ipTime: els.ipTime.value,
    followUp: els.followUp.value.trim(),
    amount,
    amountType: amountMeta.amountType,
    countedAmount: amountMeta.countedAmount,
    note: els.note.value.trim(),
  };
}

function ensureLogin() {
  if (state.currentUser) return true;
  alert("请先登录");
  return false;
}

function resetForm() {
  els.orderForm.reset();
  setDefaultFormTime();
  state.editingId = null;
  if (state.currentUser && state.currentUser.role === "member") {
    els.owner.value = state.currentUser.displayName;
  }
}

function setDefaultFormTime() {
  const now = new Date();
  const tzOffset = now.getTimezoneOffset() * 60000;
  const today = new Date(now - tzOffset).toISOString().slice(0, 10);

  if (!els.conversionDate.value) els.conversionDate.value = today;
}

async function loadOrders() {
  if (USE_REMOTE) {
    try {
      const data = await apiRequest("/api/orders");
      state.orders = (data.orders || []).map((order) => ({
        ...order,
        finalPaymentStatus: normalizeStatus(order.finalPaymentStatus),
        statusLogs: normalizeStatusLogs(order),
        phone: normalizePhone(String(order.phone || "")),
      }));
    } catch {
      state.orders = [];
    }
    return;
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    state.orders = raw ? JSON.parse(raw) : seedData();
    state.orders = state.orders.map((order) => ({
      ...order,
      finalPaymentStatus: normalizeStatus(order.finalPaymentStatus),
      statusLogs: normalizeStatusLogs(order),
      phone: normalizePhone(String(order.phone || "")),
    }));
    if (!raw) persistOrders();
  } catch (error) {
    state.orders = seedData();
    persistOrders();
  }
}

function persistOrders() {
  if (USE_REMOTE) return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.orders));
}

function getVisibleOrders() {
  const list = state.orders.filter((order) => {
    if (!state.currentUser) return false;
    if (state.currentUser.role === "admin") return true;
    return order.owner === state.currentUser.displayName;
  });

  return list.filter((order) => {
    const dateMatch = !state.filters.date || order.conversionDate === state.filters.date;
    const nameMatch = !state.filters.nickname || includesIgnoreCase(order.nickname, state.filters.nickname);
    const ownerMatch = !state.filters.owner || includesIgnoreCase(order.owner, state.filters.owner);
    const qipanMatch = !state.filters.onlyQipan || includesIgnoreCase(order.phase, "起盘营");
    const statusMatch = !state.filters.status || order.finalPaymentStatus === state.filters.status;
    return dateMatch && nameMatch && ownerMatch && qipanMatch && statusMatch;
  });
}

function render() {
  if (!state.currentUser) return;
  const list = getVisibleOrders();
  const paged = paginate(list);
  renderTable(paged);
  renderPagination(list.length);
  renderStats(list);
  renderDailySummary(list);
  renderPersonSummary(list);
  renderStatusLogs(list);
}

function renderTable(list) {
  if (!list.length) {
    els.ordersTbody.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>';
    return;
  }

  els.ordersTbody.innerHTML = list
    .map((order) => {
      const badgeClass =
        order.finalPaymentStatus === "已支付"
          ? "badge-paid"
          : order.finalPaymentStatus === "追款中"
            ? "badge-follow"
            : "badge-pending";

      return `
      <tr>
        <td><input class="row-check" type="checkbox" data-id="${order.id}" ${state.selectedIds.has(order.id) ? "checked" : ""} /></td>
        <td>${order.conversionDate || "-"}</td>
        <td><span class="badge ${badgeClass}">${escapeHtml(order.finalPaymentStatus || "-")}</span></td>
        <td>${escapeHtml(order.nickname || "-")}</td>
        <td>${escapeHtml(order.owner || "-")}</td>
        <td>${escapeHtml(getAmountType(order))}</td>
        <td>${formatCurrency(getCountedAmount(order))}</td>
        <td>${escapeHtml(formatPhoneDisplay(order.phone))}</td>
        <td>
          <span class="action-link" data-action="edit" data-id="${order.id}">编辑</span>
          <span class="action-link" data-action="delete" data-id="${order.id}">删除</span>
        </td>
      </tr>`;
    })
    .join("");

  els.ordersTbody.querySelectorAll(".action-link").forEach((node) => {
    node.addEventListener("click", onTableAction);
  });
  els.ordersTbody.querySelectorAll(".row-check").forEach((node) => {
    node.addEventListener("change", onRowCheckChange);
  });
  updatePageSelectionState(list);
}

async function onTableAction(event) {
  const action = event.target.dataset.action;
  const id = event.target.dataset.id;
  const order = state.orders.find((item) => item.id === id);
  if (!order) return;

  if (!canEditOrder(order)) {
    alert("你没有权限操作该订单");
    return;
  }

  if (action === "delete") {
    if (!confirm("确认删除这条订单吗？")) return;
    try {
      if (USE_REMOTE) {
        await apiRequest(`/api/orders/${encodeURIComponent(id)}`, { method: "DELETE" });
      }
      state.orders = state.orders.filter((item) => item.id !== id);
      state.selectedIds.delete(id);
      persistOrders();
      render();
    } catch {
      alert("删除失败，请稍后重试");
      await loadOrders();
      render();
    }
    return;
  }

  state.editingId = id;
  els.conversionDate.value = order.conversionDate || "";
  els.phase.value = order.phase || "";
  els.groupName.value = order.groupName || "";
  els.sourceChannel.value = order.sourceChannel || "";
  els.sellPlatform.value = order.sellPlatform || "";
  els.finalPaymentStatus.value = normalizeStatus(order.finalPaymentStatus || "待支付");
  els.nickname.value = order.nickname || "";
  els.phone.value = normalizePhone(String(order.phone || ""));
  els.finalPhone.value = order.finalPhone || "";
  els.owner.value = order.owner || "";
  els.ipNo.value = order.ipNo || "";
  els.ipTime.value = order.ipTime || "";
  els.followUp.value = order.followUp || "";
  els.amount.value = order.amount || 0;
  els.note.value = order.note || "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function canEditOrder(order) {
  if (!state.currentUser) return false;
  if (state.currentUser.role === "admin") return true;
  return order.owner === state.currentUser.displayName;
}

function renderStats(list) {
  const today = toLocalDateString(new Date());
  const month = today.slice(0, 7);

  const todayAmount = sumCountedAmount(list.filter((item) => item.conversionDate === today));
  const monthAmount = sumCountedAmount(list.filter((item) => (item.conversionDate || "").startsWith(month)));
  const paidRate = calcPaidRate(list);

  const cards = [
    { title: "筛选后订单数", value: `${list.length} 单` },
    { title: "今日转化金额", value: formatCurrency(todayAmount) },
    { title: "本月转化金额", value: formatCurrency(monthAmount) },
    { title: "尾款支付率", value: `${paidRate}%` },
  ];

  els.statsCards.innerHTML = cards
    .map(
      (card) => `
      <article class="stat-card">
        <div class="stat-title">${card.title}</div>
        <div class="stat-value">${card.value}</div>
      </article>`
    )
    .join("");
}

function renderPagination(total) {
  const { pageSize } = state.pagination;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (state.pagination.page > totalPages) {
    state.pagination.page = totalPages;
  }

  els.pageInfo.textContent = `第 ${state.pagination.page} / ${totalPages} 页（共 ${total} 条）`;
  els.prevPageBtn.disabled = state.pagination.page <= 1;
  els.nextPageBtn.disabled = state.pagination.page >= totalPages;
  els.deleteSelectedBtn.disabled = state.selectedIds.size === 0;
}

function paginate(list) {
  const { page, pageSize } = state.pagination;
  const start = (page - 1) * pageSize;
  return list.slice(start, start + pageSize);
}

function changePage(offset) {
  const visibleTotal = getVisibleOrders().length;
  const totalPages = Math.max(1, Math.ceil(visibleTotal / state.pagination.pageSize));
  const next = Math.min(totalPages, Math.max(1, state.pagination.page + offset));
  if (next === state.pagination.page) return;
  state.pagination.page = next;
  render();
}

function onRowCheckChange(event) {
  const id = event.target.dataset.id;
  if (!id) return;
  if (event.target.checked) {
    state.selectedIds.add(id);
  } else {
    state.selectedIds.delete(id);
  }
  updatePageSelectionState(paginate(getVisibleOrders()));
  els.deleteSelectedBtn.disabled = state.selectedIds.size === 0;
}

function toggleSelectAllOnPage() {
  const pageList = paginate(getVisibleOrders());
  for (const order of pageList) {
    if (els.selectAllOnPage.checked) {
      state.selectedIds.add(order.id);
    } else {
      state.selectedIds.delete(order.id);
    }
  }
  render();
}

function updatePageSelectionState(pageList) {
  if (!pageList.length) {
    els.selectAllOnPage.checked = false;
    els.selectAllOnPage.indeterminate = false;
    return;
  }
  const selectedCount = pageList.filter((item) => state.selectedIds.has(item.id)).length;
  els.selectAllOnPage.checked = selectedCount === pageList.length;
  els.selectAllOnPage.indeterminate = selectedCount > 0 && selectedCount < pageList.length;
}

async function deleteSelectedOrders() {
  const ids = Array.from(state.selectedIds);
  if (!ids.length) return;
  if (!confirm(`确认删除选中的 ${ids.length} 条记录吗？`)) return;

  try {
    if (USE_REMOTE) {
      for (const id of ids) {
        await apiRequest(`/api/orders/${encodeURIComponent(id)}`, { method: "DELETE" });
      }
    }
    state.orders = state.orders.filter((item) => !state.selectedIds.has(item.id));
    state.selectedIds.clear();
    persistOrders();
    render();
  } catch {
    alert("批量删除失败，请稍后重试");
    await loadOrders();
    state.selectedIds.clear();
    render();
  }
}

function renderDailySummary(list) {
  const grouped = groupBy(list, "conversionDate");
  const rows = Object.entries(grouped)
    .filter(([date]) => Boolean(date))
    .map(([date, items]) => ({ date, total: sumCountedAmount(items), count: items.length }))
    .sort((a, b) => b.date.localeCompare(a.date));

  if (!rows.length) {
    els.dailySummary.innerHTML = '<li class="empty">暂无数据</li>';
    return;
  }

  els.dailySummary.innerHTML = rows
    .map(
      (row) => `
      <li class="summary-item">
        <span>${row.date}（${row.count} 单）</span>
        <strong>${formatCurrency(row.total)}</strong>
      </li>`
    )
    .join("");
}

function renderPersonSummary(list) {
  const grouped = groupBy(list, "owner");
  const rows = Object.entries(grouped)
    .map(([name, items]) => ({
      name,
      total: sumCountedAmount(items),
      count: items.length,
      paidRate: calcPaidRate(items),
    }))
    .sort((a, b) => b.total - a.total);

  if (!rows.length) {
    els.personSummary.innerHTML = '<li class="empty">暂无数据</li>';
    return;
  }

  els.personSummary.innerHTML = rows
    .map(
      (row) => `
      <li class="summary-item">
        <span>${escapeHtml(row.name)}（${row.count} 单，尾款支付率 ${row.paidRate}%）</span>
        <strong>${formatCurrency(row.total)}</strong>
      </li>`
    )
    .join("");
}

function renderStatusLogs(list) {
  const logs = list
    .flatMap((order) =>
      normalizeStatusLogs(order).map((log) => ({
        ...log,
        nickname: order.nickname || "-",
        owner: order.owner || "-",
      }))
    )
    .sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")))
    .slice(0, 50);

  if (!logs.length) {
    els.statusLogList.innerHTML = '<li class="empty">暂无状态变更</li>';
    return;
  }

  els.statusLogList.innerHTML = logs
    .map(
      (log) => `
      <li class="summary-item">
        <span>${escapeHtml(log.nickname)} / ${escapeHtml(log.owner)} / ${escapeHtml(log.from || "-")} -> ${escapeHtml(log.to || "-")}</span>
        <strong>${escapeHtml(formatDateTime(log.at))} · ${escapeHtml(log.by || "-")}</strong>
      </li>`
    )
    .join("");
}

function exportCsv() {
  if (!state.orders.length) {
    alert("暂无订单可导出");
    return;
  }

  const headers = [
    FEISHU_HEADERS.conversionDate,
    FEISHU_HEADERS.phase,
    FEISHU_HEADERS.groupName,
    FEISHU_HEADERS.sourceChannel,
    FEISHU_HEADERS.sellPlatform,
    FEISHU_HEADERS.nickname,
    FEISHU_HEADERS.phone,
    FEISHU_HEADERS.finalPhone,
    FEISHU_HEADERS.finalPaymentStatus,
    FEISHU_HEADERS.owner,
    FEISHU_HEADERS.ipNo,
    FEISHU_HEADERS.ipTime,
    FEISHU_HEADERS.followUp,
    FEISHU_HEADERS.amount,
    "金额类型",
    "计入金额",
    "备注",
  ];

  const visible = getVisibleOrders();
  const rows = visible.map((order) => [
    order.conversionDate || "",
    order.phase || "",
    order.groupName || "",
    order.sourceChannel || "",
    order.sellPlatform || "",
    order.nickname || "",
    order.phone || "",
    order.finalPhone || "",
    order.finalPaymentStatus || "",
    order.owner || "",
    order.ipNo || "",
    order.ipTime || "",
    order.followUp || "",
    order.amount || 0,
    getAmountType(order),
    getCountedAmount(order),
    order.note || "",
  ]);

  const csv = [headers, ...rows]
    .map((line) => line.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");

  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `社群转化订单_${toLocalDateString(new Date())}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function handleImportFile(event) {
  if (!ensureLogin()) return;

  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const text = normalizeCsvText(String(reader.result || ""));
      const rows = parseCsv(text);
      if (rows.length < 2) {
        alert("CSV 内容为空");
        return;
      }

      const header = rows[0].map((item) => normalizeHeader(item));
      const imported = rows
        .slice(1)
        .filter((line) => line.some((item) => item.trim() !== ""))
        .map((line) => mapRowToOrder(header, line))
        .filter(Boolean);

      if (!imported.length) {
        alert("未识别到可导入数据，请检查表头");
        return;
      }

      const existingKeys = new Set(state.orders.map((item) => buildDedupKey(item)));
      const preview = buildImportPreview(imported, existingKeys);
      const shouldContinue = confirm(buildPreviewMessage(preview));
      if (!shouldContinue) {
        return;
      }

      let added = 0;
      for (const order of preview.addable) {
        state.orders.unshift(order);
        existingKeys.add(buildDedupKey(order));
        if (USE_REMOTE) {
          await apiRequest("/api/orders", {
            method: "POST",
            body: JSON.stringify({ order }),
          });
        }
        added += 1;
      }

      persistOrders();
      state.pagination.page = 1;
      if (USE_REMOTE) {
        await loadOrders();
      }
      render();
      alert(
        `导入完成：新增 ${added} 条，跳过重复 ${preview.duplicate.length} 条，无权限 ${preview.noPermission.length} 条，非起盘营 ${preview.nonQipan.length} 条`
      );
    } catch (error) {
      alert("导入失败，请确认是飞书导出的 CSV 文件");
    } finally {
      event.target.value = "";
    }
  };

  reader.readAsText(file, "utf-8");
}

function canImportOrder(order) {
  if (!state.currentUser) return false;
  if (state.currentUser.role === "admin") return true;
  return order.owner === state.currentUser.displayName;
}

function mapRowToOrder(header, row) {
  const getByAliases = (aliases) => getValueByAliases(header, row, aliases);

  const amountRaw = getByAliases(HEADER_ALIASES.amount);
  const amount = parseAmount(amountRaw);
  const sourceChannel = getByAliases(HEADER_ALIASES.sourceChannel).trim();
  const amountMeta = deriveAmountMeta(sourceChannel, amount);
  const orderTime = normalizeDateTime(getByAliases(HEADER_ALIASES.orderTime));
  const conversionDate = normalizeDate(getByAliases(HEADER_ALIASES.conversionDate));

  const fallbackOwner = state.currentUser ? state.currentUser.displayName : "";
  const owner = (getByAliases(HEADER_ALIASES.owner) || fallbackOwner).trim();

  if (!owner) return null;
  if (!conversionDate) return null;

  return {
    id: crypto.randomUUID(),
    createdBy: state.currentUser ? state.currentUser.username : "",
    orderTime: orderTime || `${conversionDate}T00:00`,
    conversionDate,
    phase: getByAliases(HEADER_ALIASES.phase).trim(),
    groupName: getByAliases(HEADER_ALIASES.groupName).trim(),
    product: getByAliases(HEADER_ALIASES.product).trim(),
    sourceChannel,
    sellPlatform: getByAliases(HEADER_ALIASES.sellPlatform).trim(),
    finalPaymentStatus: normalizeStatus(getByAliases(HEADER_ALIASES.finalPaymentStatus)),
    nickname: getByAliases(HEADER_ALIASES.nickname).trim(),
    phone: normalizePhone(getByAliases(HEADER_ALIASES.phone).trim()),
    finalPhone: getByAliases(HEADER_ALIASES.finalPhone).trim(),
    owner,
    ipNo: getByAliases(HEADER_ALIASES.ipNo).trim(),
    ipTime: normalizeDateTime(getByAliases(HEADER_ALIASES.ipTime)),
    followUp: getByAliases(HEADER_ALIASES.followUp).trim(),
    amount,
    amountType: amountMeta.amountType,
    countedAmount: amountMeta.countedAmount,
    note: getByAliases(HEADER_ALIASES.note).trim(),
    statusLogs: [],
  };
}

function normalizeStatus(raw) {
  const text = (raw || "").trim();
  if (text === "已支付" || text === "已付") return "已支付";
  if (text === "已退款" || text === "退款") return "已退款";
  if (text === "无效线索" || text === "保留占位" || text === "全退占") return "无效线索";
  if (text === "已追代付" || text === "已催付" || text === "追款中" || text === "待追" || text === "一直联系不上") {
    return "追款中";
  }
  return "待支付";
}

function getValueByAliases(header, row, aliases) {
  for (const name of aliases) {
    const idx = header.indexOf(normalizeHeader(name));
    if (idx === -1) continue;
    const value = (row[idx] || "").trim();
    if (value !== "") return value;
  }
  return "";
}

function buildDedupKey(order) {
  const date = String(order.conversionDate || "").trim();
  const name = String(order.nickname || "").trim().toLowerCase();
  const phone = normalizePhone(String(order.phone || ""));
  return `${date}__${name}__${phone}`;
}

function normalizePhone(phone) {
  const raw = phone.replaceAll(" ", "").replaceAll("-", "");
  const sci = Number(raw);
  if (Number.isFinite(sci) && /e\+?/i.test(raw)) {
    return String(Math.trunc(sci)).replace(/\D/g, "");
  }
  return raw.replace(/\D/g, "");
}

function formatPhoneDisplay(phone) {
  const n = normalizePhone(String(phone || ""));
  return n || "-";
}

function buildImportPreview(imported, existingKeys) {
  const addable = [];
  const duplicate = [];
  const noPermission = [];
  const nonQipan = [];
  const inBatch = new Set();

  for (const order of imported) {
    if (!includesIgnoreCase(order.phase, "起盘营")) {
      nonQipan.push(order);
      continue;
    }

    if (!canImportOrder(order)) {
      noPermission.push(order);
      continue;
    }

    const key = buildDedupKey(order);
    if (existingKeys.has(key) || inBatch.has(key)) {
      duplicate.push(order);
      continue;
    }

    inBatch.add(key);
    addable.push(order);
  }

  return { addable, duplicate, noPermission, nonQipan };
}

function makeStatusLog(from, to) {
  return {
    from,
    to,
    by: getCurrentOperatorName(),
    at: new Date().toISOString(),
  };
}

function normalizeStatusLogs(order) {
  if (!Array.isArray(order.statusLogs)) return [];
  return order.statusLogs
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      from: String(item.from || ""),
      to: String(item.to || ""),
      by: String(item.by || ""),
      at: String(item.at || ""),
    }));
}

function getCurrentOperatorName() {
  return state.currentUser ? state.currentUser.displayName : "系统";
}

function buildPreviewMessage(preview) {
  const lines = [
    "导入前预览：",
    `可新增：${preview.addable.length} 条`,
    `重复跳过：${preview.duplicate.length} 条`,
    `无权限跳过：${preview.noPermission.length} 条`,
    `非起盘营跳过：${preview.nonQipan.length} 条`,
  ];

  const dupSample = preview.duplicate
    .slice(0, 5)
    .map((item) => `${item.conversionDate || "-"} / ${item.nickname || "-"} / ${item.phone || "-"}`);
  if (dupSample.length > 0) {
    lines.push("", "重复示例（前5条）：", ...dupSample);
  }

  lines.push("", "点击“确定”开始导入，点击“取消”终止。");
  return lines.join("\n");
}

function parseAmount(raw) {
  const n = Number(String(raw || "").replaceAll(",", "").trim());
  return Number.isFinite(n) ? n : 0;
}

function normalizeCsvText(text) {
  if (text.charCodeAt(0) === 0xfeff) {
    return text.slice(1);
  }
  return text;
}

function normalizeHeader(header) {
  return String(header || "").replaceAll("\uFEFF", "").trim();
}

function normalizeDate(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  const date = new Date(text.replaceAll("/", "-"));
  if (Number.isNaN(date.getTime())) return "";
  return toLocalDateString(date);
}

function normalizeDateTime(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  const date = new Date(text.replaceAll("/", "-"));
  if (Number.isNaN(date.getTime())) return "";
  return toLocalDateTimeString(date);
}

function toLocalDateString(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function toLocalDateTimeString(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d}T${hh}:${mm}`;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];

    if (ch === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (!inQuotes && ch === ",") {
      row.push(cell);
      cell = "";
      continue;
    }

    if (!inQuotes && (ch === "\n" || ch === "\r")) {
      if (ch === "\r" && next === "\n") {
        i += 1;
      }
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      continue;
    }

    cell += ch;
  }

  row.push(cell);
  rows.push(row);
  return rows;
}

function seedData() {
  const day1 = toLocalDateString(new Date(Date.now() - 24 * 3600 * 1000));
  const day2 = toLocalDateString(new Date(Date.now() - 48 * 3600 * 1000));

  return [
    {
      id: crypto.randomUUID(),
      createdBy: "admin",
      orderTime: `${day1}T10:30`,
      conversionDate: day1,
      phase: "第3期",
      groupName: "A组",
      product: "私教营",
      sourceChannel: "社群转介绍",
      sellPlatform: "微信",
      finalPaymentStatus: "待支付",
      nickname: "小雨",
      phone: "13800001111",
      finalPhone: "",
      owner: "成员1",
      ipNo: "IP-102",
      ipTime: `${day1}T09:05`,
      followUp: "今日二次跟进",
      amount: 1999,
      note: "已确认付款意向",
    },
    {
      id: crypto.randomUUID(),
      createdBy: "admin",
      orderTime: `${day2}T14:15`,
      conversionDate: day2,
      phase: "第3期",
      groupName: "B组",
      product: "会员课",
      sourceChannel: "短视频引流",
      sellPlatform: "微信",
      finalPaymentStatus: "已支付",
      nickname: "阿杰",
      phone: "13900002222",
      finalPhone: "",
      owner: "成员2",
      ipNo: "IP-085",
      ipTime: `${day2}T10:00`,
      followUp: "已完结",
      amount: 999,
      note: "全款到账",
    },
  ];
}

function sumAmount(list) {
  return list.reduce((sum, item) => sum + Number(item.amount || 0), 0);
}

function sumCountedAmount(list) {
  return list.reduce((sum, item) => sum + getCountedAmount(item), 0);
}

function calcPaidRate(list) {
  if (!list.length) return 0;
  const paid = list.filter((item) => item.finalPaymentStatus === "已支付").length;
  return Math.round((paid / list.length) * 100);
}

function groupBy(list, key) {
  return list.reduce((acc, item) => {
    const val = item[key] || "未命名";
    if (!acc[val]) acc[val] = [];
    acc[val].push(item);
    return acc;
  }, {});
}

function includesIgnoreCase(value, keyword) {
  return String(value || "").toLowerCase().includes(String(keyword || "").toLowerCase());
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}`;
}

function formatCurrency(value) {
  return `¥${Number(value || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getCountedAmount(order) {
  if (typeof order.countedAmount === "number" && Number.isFinite(order.countedAmount)) {
    return order.countedAmount;
  }
  return deriveAmountMeta(order.sourceChannel || "", order.amount || 0).countedAmount;
}

function getAmountType(order) {
  const type = order.amountType || deriveAmountMeta(order.sourceChannel || "", order.amount || 0).amountType;
  return type.includes("不计入") ? "" : type;
}

function deriveAmountMeta(sourceChannel, rawAmount) {
  const text = String(sourceChannel || "").trim();
  if (text.includes("占位")) {
    return { amountType: "占位卡(不计入)", countedAmount: 0 };
  }
  if (text.includes("全款")) {
    return { amountType: "全款(计入)", countedAmount: 6980 };
  }
  const amount = Number(rawAmount || 0);
  if (amount > 0) {
    return { amountType: "其他(不计入)", countedAmount: 0 };
  }
  return { amountType: "其他(不计入)", countedAmount: 0 };
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

init();
