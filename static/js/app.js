/**
 * OAuth Connect POC — frontend application
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
  modalDisconnect: $("modal-disconnect"),
  modalCancel: $("modal-cancel"),
  modalConfirm: $("modal-confirm"),
  toastContainer: $("toast-container"),
};

/** @type {object|null} */
let currentUser = null;
let providerToDisconnect = null;

const ALL_PROVIDERS = ["google", "microsoft", "linkedin", "zoom"];

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
  els.connectedList.innerHTML = ALL_PROVIDERS
    .map((provider) => {
      const app = apps.find((a) => a.provider.toLowerCase() === provider);
      const isConnected = app && app.status === "connected";
      const providerDisplayName = provider.charAt(0).toUpperCase() + provider.slice(1);

      if (isConnected) {
        return `
          <div class="connected-item">
            <div>
              <div class="connected-provider">
                <span class="provider-dot"></span>
                ${providerDisplayName}
              </div>
              <div class="connected-meta">
                Scopes: ${app.scopes || "—"}<br />
                Connected: ${formatDate(app.connected_at)}
              </div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <span class="badge badge-connected">Connected</span>
              <button type="button" class="btn btn-secondary btn-sm" onclick="confirmDisconnect('${provider}')" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;">
                Disconnect
              </button>
            </div>
          </div>
        `;
      } else {
        const isFailed = app && (app.status === "expired" || app.status === "failed");
        const statusText = isFailed ? app.status : "Not Connected";
        return `
          <div class="connected-item" style="opacity: 0.85;">
            <div>
              <div class="connected-provider">
                <span class="provider-dot disconnected"></span>
                ${providerDisplayName}
              </div>
              <div class="connected-meta">
                Status: <span style="text-transform: capitalize; font-weight: 500;">${statusText}</span>
              </div>
            </div>
            <a href="/auth/${provider}/login" class="btn btn-secondary" style="padding: 0.3rem 0.75rem; font-size: 0.8rem; text-decoration: none;">
              ${isFailed ? "Reconnect" : "Connect"}
            </a>
          </div>
        `;
      }
    })
    .join("");
}

// Expose confirmDisconnect globally so inline button click handlers work (module scope workaround)
window.confirmDisconnect = function (provider) {
  providerToDisconnect = provider;
  const titleEl = $("modal-disconnect-title");
  if (titleEl) {
    titleEl.textContent = `Disconnect ${provider.charAt(0).toUpperCase() + provider.slice(1)}?`;
  }
  els.modalDisconnect.showModal();
};

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

async function disconnectProvider() {
  if (!providerToDisconnect) return;
  els.modalConfirm.disabled = true;

  try {
    await api(`/disconnect/${providerToDisconnect}`, { method: "POST" });
    els.modalDisconnect.close();
    showToast(`${providerToDisconnect.charAt(0).toUpperCase() + providerToDisconnect.slice(1)} account disconnected`);
    providerToDisconnect = null;
    await loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    els.modalConfirm.disabled = false;
  }
}

function handleUrlParams() {
  const params = new URLSearchParams(window.location.search);

  if (params.get("login") === "success") {
    els.alertSuccess.hidden = false;
    els.alertSuccess.textContent = "Successfully authenticated!";
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

  els.modalCancel.addEventListener("click", () => {
    els.modalDisconnect.close();
  });

  els.modalConfirm.addEventListener("click", disconnectProvider);

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
