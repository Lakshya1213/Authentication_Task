/**
 * Google OAuth POC — frontend application
 * Uses session cookies (same-origin); all API calls include credentials.
 */

const $ = (id) => document.getElementById(id);

const views = {
  loading: $("view-loading"),
  login: $("view-login"),
  dashboard: $("view-dashboard"),
};

const els = {
  headerNav: $("header-nav"),
  headerUser: $("header-user"),
  alertSuccess: $("alert-success"),
  profileAvatar: $("profile-avatar"),
  profileAvatarFallback: $("profile-avatar-fallback"),
  profileName: $("profile-name"),
  profileEmail: $("profile-email"),
  profileId: $("profile-id"),
  connectedList: $("connected-list"),
  btnRefresh: $("btn-refresh"),
  btnDisconnect: $("btn-disconnect"),
  modalDisconnect: $("modal-disconnect"),
  modalCancel: $("modal-cancel"),
  modalConfirm: $("modal-confirm"),
  toastContainer: $("toast-container"),
};

/** @type {object|null} */
let currentUser = null;

function showView(name) {
  Object.entries(views).forEach(([key, el]) => {
    el.hidden = key !== name;
  });
}

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  els.toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function parseApiError(data) {
  if (typeof data === "string") return data;
  if (data?.message) return data.message;
  if (data?.detail?.message) return data.detail.message;
  if (typeof data?.detail === "string") return data.detail;
  return "Something went wrong";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    ...options,
  });

  let data = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await response.json();
  }

  if (!response.ok) {
    throw new Error(parseApiError(data));
  }

  return data;
}

function getInitials(name) {
  return (name || "?")
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function renderProfile(user) {
  currentUser = user;
  els.headerNav.hidden = false;
  els.headerUser.textContent = user.email;

  els.profileName.textContent = user.name;
  els.profileEmail.textContent = user.email;
  els.profileId.textContent = user.id;

  if (user.picture) {
    els.profileAvatar.src = user.picture;
    els.profileAvatar.alt = user.name;
    els.profileAvatar.hidden = false;
    els.profileAvatarFallback.hidden = true;
  } else {
    els.profileAvatar.hidden = true;
    els.profileAvatarFallback.hidden = false;
    els.profileAvatarFallback.textContent = getInitials(user.name);
  }
}

function renderConnectedApps(apps) {
  if (!apps.length) {
    els.connectedList.innerHTML =
      '<p class="muted empty-state">No connected apps found.</p>';
    return;
  }

  els.connectedList.innerHTML = apps
    .map(
      (app) => `
    <div class="connected-item">
      <div>
        <div class="connected-provider">
          <span class="provider-dot ${app.status === "connected" ? "" : "disconnected"}"></span>
          ${app.provider}
        </div>
        <div class="connected-meta">
          Scopes: ${app.scopes || "—"}<br />
          Connected: ${formatDate(app.connected_at)}
        </div>
      </div>
      <span class="badge badge-${app.status === "connected" ? "connected" : "disconnected"}">
        ${app.status}
      </span>
    </div>
  `
    )
    .join("");
}

async function loadConnectedApps() {
  els.btnRefresh.disabled = true;
  try {
    const apps = await api("/connected-apps");
    renderConnectedApps(apps);
  } catch (err) {
    els.connectedList.innerHTML = `<p class="muted empty-state">${err.message}</p>`;
  } finally {
    els.btnRefresh.disabled = false;
  }
}

async function loadDashboard() {
  try {
    const user = await api("/me");
    renderProfile(user);
    showView("dashboard");
    await loadConnectedApps();
  } catch {
    currentUser = null;
    els.headerNav.hidden = true;
    showView("login");
  }
}

async function disconnectGoogle() {
  els.btnDisconnect.disabled = true;
  els.modalConfirm.disabled = true;

  try {
    await api("/disconnect/google", { method: "POST" });
    els.modalDisconnect.close();
    showToast("Google account disconnected");
    currentUser = null;
    els.headerNav.hidden = true;
    showView("login");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    els.btnDisconnect.disabled = false;
    els.modalConfirm.disabled = false;
  }
}

function handleUrlParams() {
  const params = new URLSearchParams(window.location.search);

  if (params.get("login") === "success") {
    els.alertSuccess.hidden = false;
    els.alertSuccess.textContent = "Successfully signed in with Google!";
    showToast("Welcome back!");
  }

  const error = params.get("error");
  const message = params.get("message");
  if (error) {
    showToast(message || "Authentication failed", "error");
  }

  if (params.has("login") || params.has("error")) {
    window.history.replaceState({}, "", window.location.pathname);
  }
}

function bindEvents() {
  els.btnRefresh.addEventListener("click", loadConnectedApps);

  els.btnDisconnect.addEventListener("click", () => {
    els.modalDisconnect.showModal();
  });

  els.modalCancel.addEventListener("click", () => {
    els.modalDisconnect.close();
  });

  els.modalConfirm.addEventListener("click", disconnectGoogle);

  els.modalDisconnect.addEventListener("click", (e) => {
    if (e.target === els.modalDisconnect) {
      els.modalDisconnect.close();
    }
  });
}

async function init() {
  bindEvents();
  handleUrlParams();
  showView("loading");
  await loadDashboard();
}

init();
