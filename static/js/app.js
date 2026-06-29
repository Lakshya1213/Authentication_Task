/**
 * OAuth Connect POC — frontend application
 * Uses session cookies (same-origin); all API calls include credentials.
 */

window.onerror = function(message, source, lineno, colno, error) {
  alert("JS Error: " + message + " at line " + lineno + ":" + colno);
  return false;
};

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
  // Calendar elements
  calStart: $("cal-start"),
  calEnd: $("cal-end"),
  calQuery: $("cal-query"),
  btnCalFetch: $("btn-cal-fetch"),
  btnCalSearch: $("btn-cal-search"),
  eventsList: $("events-list"),
  modalEventDetail: $("modal-event-detail"),
  eventDetailTitle: $("event-detail-title"),
  eventDetailTime: $("event-detail-time"),
  eventDetailLocation: $("event-detail-location"),
  eventDetailDescription: $("event-detail-description"),
  eventDetailOrganizer: $("event-detail-organizer"),
  eventDetailAttendees: $("event-detail-attendees"),
  eventDetailLinkSection: $("event-detail-link-section"),
  eventDetailLink: $("event-detail-link"),
  btnEventDetailClose: $("btn-event-detail-close"),
  calChatInput: $("cal-chat-input"),
  btnChatSubmit: $("btn-chat-submit"),
  tabBtnView: $("tab-btn-view"),
  tabBtnCreate: $("tab-btn-create"),
  sectionCalView: $("section-cal-view"),
  sectionCalCreate: $("section-cal-create"),
  createTitle: $("create-title"),
  createStart: $("create-start"),
  createEnd: $("create-end"),
  createLocation: $("create-location"),
  createDescription: $("create-description"),
  btnCalCreateSubmit: $("btn-cal-create-submit"),
  // Mail elements
  mailQuery: $("mail-query"),
  mailLimit: $("mail-limit"),
  btnMailSearch: $("btn-mail-search"),
  mailList: $("mail-list"),
  mailCount: $("mail-count"),
  mailChatInput: $("mail-chat-input"),
  btnMailChatSubmit: $("btn-mail-chat-submit"),
  tabBtnMailView: $("tab-btn-mail-view"),
  tabBtnMailCreate: $("tab-btn-mail-create"),
  sectionMailView: $("section-mail-view"),
  sectionMailCreate: $("section-mail-create"),
  mailCreateTo: $("mail-create-to"),
  mailCreateCc: $("mail-create-cc"),
  mailCreateSubject: $("mail-create-subject"),
  mailCreateBody: $("mail-create-body"),
  btnMailDraftSubmit: $("btn-mail-draft-submit"),
  btnMailSendSubmit: $("btn-mail-send-submit"),
  modalMailDetail: $("modal-mail-detail"),
  mailDetailSubject: $("mail-detail-subject"),
  mailDetailFrom: $("mail-detail-from"),
  mailDetailTo: $("mail-detail-to"),
  mailDetailDate: $("mail-detail-date"),
  mailDetailBody: $("mail-detail-body"),
  mailReplyBody: $("mail-reply-body"),
  btnMailReplySubmit: $("btn-mail-reply-submit"),
  btnMailDetailClose: $("btn-mail-detail-close"),
  modalMailConfirm: $("modal-mail-confirm"),
  mailConfirmTo: $("mail-confirm-to"),
  mailConfirmSubject: $("mail-confirm-subject"),
  btnMailConfirmCancel: $("btn-mail-confirm-cancel"),
  btnMailConfirmSend: $("btn-mail-confirm-send"),
};

/** @type {object|null} */
let currentUser = null;
let providerToDisconnect = null;
let currentViewingMessageId = null;
let currentConfirmingDraftId = null;
let composeDataPendingSend = null;

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
    
    const googleConnected = apps.some(a => a.provider.toLowerCase() === "google" && a.status === "connected");
    if (googleConnected) {
      fetchEmails();
    }
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

async function fetchCalendarEvents() {
  const start = els.calStart.value ? new Date(els.calStart.value).toISOString() : "";
  const end = els.calEnd.value ? new Date(els.calEnd.value).toISOString() : "";
  const query = els.calQuery.value || "";

  els.btnCalFetch.disabled = true;
  els.eventsList.innerHTML = `<div class="spinner" style="margin: 2rem auto;"></div>`;

  try {
    let url = `/api/calendar/events?start_time=${encodeURIComponent(start)}&end_time=${encodeURIComponent(end)}`;
    if (query) {
      url = `/api/calendar/search?query=${encodeURIComponent(query)}&start_time=${encodeURIComponent(start)}&end_time=${encodeURIComponent(end)}`;
    }

    const events = await api(url);
    renderEvents(events);
  } catch (err) {
    els.eventsList.innerHTML = `<p class="muted empty-state" style="color: var(--danger);">${err.message}</p>`;
  } finally {
    els.btnCalFetch.disabled = false;
  }
}

async function fetchCalendarEventsWithChat() {
  const query = els.calChatInput.value.trim ? els.calChatInput.value.trim() : els.calChatInput.value;
  if (!query) {
    showToast("Please enter a query first", "error");
    return;
  }

  els.btnChatSubmit.disabled = true;
  els.eventsList.innerHTML = `<div class="spinner" style="margin: 2rem auto;"></div>`;

  try {
    const data = await api(`/api/calendar/query?q=${encodeURIComponent(query)}`);
    
    if (data.action === "created") {
      showToast(data.message || "Event created successfully!", "success");
      renderEvents(data.events);
      els.calChatInput.value = "";
      return;
    }
    
    // Auto-update standard input fields in UI based on AI parsing
    if (data.start_time) {
      const startDate = new Date(data.start_time);
      els.calStart.value = formatLocalDateTime(startDate);
    }
    if (data.end_time) {
      const endDate = new Date(data.end_time);
      els.calEnd.value = formatLocalDateTime(endDate);
    }
    els.calQuery.value = data.search_query || "";
    
    renderEvents(data.events);
  } catch (err) {
    els.eventsList.innerHTML = `<p class="muted empty-state" style="color: var(--danger);">${err.message}</p>`;
  } finally {
    els.btnChatSubmit.disabled = false;
  }
}

async function submitManualEvent() {
  const title = els.createTitle.value.trim();
  const start = els.createStart.value;
  const end = els.createEnd.value;
  const location = els.createLocation.value.trim();
  const description = els.createDescription.value.trim();

  if (!title) {
    showToast("Title is required", "error");
    return;
  }
  if (!start || !end) {
    showToast("Start and End date times are required", "error");
    return;
  }

  els.btnCalCreateSubmit.disabled = true;

  try {
    const payload = {
      title,
      start_time: new Date(start).toISOString(),
      end_time: new Date(end).toISOString(),
      location: location || null,
      description: description || null
    };

    const newEvent = await api("/api/calendar/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    showToast("Event created successfully!", "success");
    
    // Reset Form
    els.createTitle.value = "";
    els.createStart.value = "";
    els.createEnd.value = "";
    els.createLocation.value = "";
    els.createDescription.value = "";

    // Toggle back to View Tab
    els.tabBtnView.click();

    // Re-fetch calendar list
    els.calStart.value = formatLocalDateTime(new Date(newEvent.start_time));
    els.calEnd.value = formatLocalDateTime(new Date(newEvent.end_time));
    fetchCalendarEvents();

  } catch (err) {
    showToast(err.message || "Failed to create event", "error");
  } finally {
    els.btnCalCreateSubmit.disabled = false;
  }
}

async function fetchEmails() {
  const query = els.mailQuery.value || "";
  const limit = els.mailLimit.value || 10;

  els.btnMailSearch.disabled = true;
  els.mailList.innerHTML = `<div class="spinner" style="margin: 2rem auto;"></div>`;

  try {
    const url = `/api/mail/search?query=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}&provider=gmail`;
    const emails = await api(url);
    renderEmails(emails);
  } catch (err) {
    els.mailList.innerHTML = `<p class="muted empty-state" style="color: var(--danger);">${err.message}</p>`;
  } finally {
    els.btnMailSearch.disabled = false;
  }
}

async function fetchEmailsWithChat() {
  const query = els.mailChatInput.value.trim ? els.mailChatInput.value.trim() : els.mailChatInput.value;
  if (!query) {
    showToast("Please enter a query first", "error");
    return;
  }

  els.btnMailChatSubmit.disabled = true;
  els.mailList.innerHTML = `<div class="spinner" style="margin: 2rem auto;"></div>`;

  try {
    const data = await api(`/api/mail/query?q=${encodeURIComponent(query)}`);
    
    if (data.action === "search") {
      els.mailQuery.value = data.query || "";
      renderEmails(data.emails);
      return;
    }

    if (data.action === "draft_created") {
      showToast(data.message || "Email draft created successfully!", "success");
      els.mailChatInput.value = "";
      fetchEmails();
      return;
    }

    if (data.action === "confirmation_required") {
      showToast("Confirmation Required to send this email.", "warning");
      currentConfirmingDraftId = data.draft_id;
      
      els.mailConfirmTo.textContent = data.details.to;
      els.mailConfirmSubject.textContent = data.details.subject;
      els.modalMailConfirm.showModal();
      
      els.mailChatInput.value = "";
      fetchEmails();
      return;
    }
  } catch (err) {
    els.mailList.innerHTML = `<p class="muted empty-state" style="color: var(--danger);">${err.message}</p>`;
  } finally {
    els.btnMailChatSubmit.disabled = false;
  }
}

function renderEmails(emails) {
  const countEl = els.mailCount;
  if (countEl) {
    if (emails && emails.length > 0) {
      countEl.textContent = `${emails.length} email${emails.length === 1 ? '' : 's'}`;
      countEl.style.display = "inline-block";
    } else {
      countEl.style.display = "none";
    }
  }

  if (!emails || emails.length === 0) {
    els.mailList.innerHTML = `
      <div class="empty-state-container">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="empty-state-icon">
          <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="currentColor"/>
        </svg>
        <p class="muted empty-state-text">No emails found.</p>
      </div>
    `;
    return;
  }

  els.mailList.innerHTML = emails
    .map((mail) => {
      const dateStr = new Date(mail.received_at).toLocaleString();
      const subject = mail.subject || "(No Subject)";
      const fromName = mail.from ? (mail.from.name || mail.from.email) : "Unknown";
      const attachmentIcon = mail.has_attachments 
        ? `<span class="badge badge-secondary" style="font-size: 0.7rem; padding: 0.1rem 0.3rem; margin-left: 0.5rem; display: inline-flex; align-items: center; gap: 0.1rem;">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:10px; height:10px;"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
             Attachment
           </span>`
        : "";
        
      return `
        <div class="event-item">
          <div class="event-info" style="max-width: 75%;">
            <div class="event-title" style="display: flex; align-items: center; font-weight: 500;">
              ${escapeHtml(subject)}
              ${attachmentIcon}
            </div>
            <div class="event-time">From: ${escapeHtml(fromName)} | ${dateStr}</div>
            <p class="muted" style="margin: 0.25rem 0 0 0; font-size: 0.8rem; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
              ${escapeHtml(mail.snippet || "")}
            </p>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" onclick="viewMailDetails('${mail.message_id}')" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;">
            Read Mail
          </button>
        </div>
      `;
    })
    .join("");
}

window.viewMailDetails = async function(messageId) {
  try {
    const mail = await api(`/api/mail/read?message_id=${messageId}&provider=gmail`);
    showMailDetailsModal(mail);
  } catch (err) {
    showToast(err.message, "error");
  }
};

function showMailDetailsModal(mail) {
  currentViewingMessageId = mail.message_id;
  
  els.mailDetailSubject.textContent = mail.subject || "(No Subject)";
  els.mailDetailFrom.textContent = mail.from ? `${mail.from.name || ""} <${mail.from.email}>` : "—";
  
  const toList = mail.to || [];
  els.mailDetailTo.textContent = toList.map(t => `${t.name || ""} <${t.email}>`).join(", ") || "—";
  
  els.mailDetailDate.textContent = new Date(mail.received_at).toLocaleString();
  els.mailDetailBody.textContent = mail.body_text || "—";
  
  els.mailReplyBody.value = "";
  els.modalMailDetail.showModal();
}

async function submitMailReply() {
  const body = els.mailReplyBody.value.trim();
  if (!body) {
    showToast("Reply content cannot be empty", "error");
    return;
  }

  els.btnMailReplySubmit.disabled = true;

  try {
    const payload = {
      message_id: currentViewingMessageId,
      body,
      provider: "gmail"
    };

    const res = await api("/api/mail/reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.status === "blocked") {
      showToast(res.message || "Sending blocked due to safety policy", "error");
    } else {
      showToast("Reply draft saved successfully!", "success");
      els.mailReplyBody.value = "";
      els.modalMailDetail.close();
      fetchEmails();
    }
  } catch (err) {
    showToast(err.message || "Failed to create reply draft", "error");
  } finally {
    els.btnMailReplySubmit.disabled = false;
  }
}

async function submitMailDraft() {
  const to = els.mailCreateTo.value.trim();
  const cc = els.mailCreateCc.value.trim();
  const subject = els.mailCreateSubject.value.trim();
  const body = els.mailCreateBody.value.trim();

  if (!to) {
    showToast("Recipient is required", "error");
    return;
  }

  els.btnMailDraftSubmit.disabled = true;

  try {
    const payload = {
      to,
      cc: cc || null,
      subject: subject || "(No Subject)",
      body: body || "",
      provider: "gmail"
    };

    await api("/api/mail/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    showToast("Email draft saved successfully!", "success");
    resetMailComposeForm();
    els.tabBtnMailView.click();
    fetchEmails();
  } catch (err) {
    showToast(err.message || "Failed to save draft", "error");
  } finally {
    els.btnMailDraftSubmit.disabled = false;
  }
}

function resetMailComposeForm() {
  els.mailCreateTo.value = "";
  els.mailCreateCc.value = "";
  els.mailCreateSubject.value = "";
  els.mailCreateBody.value = "";
  composeDataPendingSend = null;
  currentConfirmingDraftId = null;
}

function initiateMailSend() {
  const to = els.mailCreateTo.value.trim();
  const cc = els.mailCreateCc.value.trim();
  const subject = els.mailCreateSubject.value.trim();
  const body = els.mailCreateBody.value.trim();

  if (!to) {
    showToast("Recipient is required", "error");
    return;
  }

  composeDataPendingSend = {
    to,
    cc: cc || null,
    subject: subject || "(No Subject)",
    body: body || "",
    provider: "gmail",
    confirmation_required: false
  };

  els.mailConfirmTo.textContent = to + (cc ? ` (CC: ${cc})` : "");
  els.mailConfirmSubject.textContent = subject || "(No Subject)";
  els.modalMailConfirm.showModal();
}

async function confirmAndSendMail() {
  els.btnMailConfirmSend.disabled = true;

  try {
    let res;
    if (currentConfirmingDraftId) {
      res = await api("/api/mail/send-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          draft_id: currentConfirmingDraftId,
          provider: "gmail"
        })
      });
    } else if (composeDataPendingSend) {
      res = await api("/api/mail/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(composeDataPendingSend)
      });
    }

    if (res && res.status === "blocked") {
      showToast(res.message || "Sending blocked due to safety policy", "error");
    } else {
      showToast(res.message || "Email sent successfully!", "success");
      resetMailComposeForm();
      els.modalMailConfirm.close();
      els.tabBtnMailView.click();
      fetchEmails();
    }
  } catch (err) {
    showToast(err.message || "Failed to send email", "error");
  } finally {
    els.btnMailConfirmSend.disabled = false;
    currentConfirmingDraftId = null;
    composeDataPendingSend = null;
  }
}

function renderEvents(events) {
  const countEl = document.getElementById("events-count");
  if (countEl) {
    if (events && events.length > 0) {
      countEl.textContent = `${events.length} event${events.length === 1 ? '' : 's'}`;
      countEl.style.display = "inline-block";
    } else {
      countEl.style.display = "none";
    }
  }

  if (!events || events.length === 0) {
    els.eventsList.innerHTML = `
      <div class="empty-state-container">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="empty-state-icon">
          <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2zm-7 5h5v2h-5v-2z" fill="currentColor"/>
        </svg>
        <p class="muted empty-state-text">No events found in this date range.</p>
      </div>
    `;
    return;
  }

  els.eventsList.innerHTML = events
    .map((event) => {
      const startStr = new Date(event.start_time).toLocaleString();
      return `
        <div class="event-item">
          <div class="event-info">
            <div class="event-title">${escapeHtml(event.title)}</div>
            <div class="event-time">${startStr}</div>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" onclick="viewEventDetails('${event.event_id}')" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;">
            View Details
          </button>
        </div>
      `;
    })
    .join("");
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

window.viewEventDetails = async function(eventId) {
  try {
    const event = await api(`/api/calendar/events/${eventId}`);
    showEventDetailsModal(event);
  } catch (err) {
    showToast(err.message, "error");
  }
};

function showEventDetailsModal(event) {
  els.eventDetailTitle.eventDetailTitle = event.title || "(No Title)";
  document.getElementById("event-detail-title").textContent = event.title || "(No Title)";
  
  const start = new Date(event.start_time).toLocaleString();
  const end = new Date(event.end_time).toLocaleString();
  els.eventDetailTime.textContent = `${start} - ${end}`;
  
  els.eventDetailLocation.textContent = event.location || "—";
  els.eventDetailDescription.textContent = event.description || "—";
  els.eventDetailOrganizer.textContent = event.organizer 
    ? `${event.organizer.name || ""} (${event.organizer.email || ""})`
    : "—";

  if (event.attendees && event.attendees.length > 0) {
    els.eventDetailAttendees.innerHTML = event.attendees
      .map(att => `
        <div class="attendee-item">
          <span>${escapeHtml(att.name || att.email)}</span>
          <span class="badge-status ${att.status || 'needsAction'}">${att.status || 'needsAction'}</span>
        </div>
      `)
      .join("");
  } else {
    els.eventDetailAttendees.innerHTML = `<p class="muted" style="margin: 0; font-size: 0.85rem;">No attendees.</p>`;
  }

  if (event.meeting_link) {
    els.eventDetailLink.href = event.meeting_link;
    els.eventDetailLinkSection.hidden = false;
  } else {
    els.eventDetailLinkSection.hidden = true;
  }

  els.modalEventDetail.showModal();
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

  // Calendar event binds
  els.btnCalFetch.addEventListener("click", fetchCalendarEvents);
  els.btnCalSearch.addEventListener("click", fetchCalendarEvents);
  els.btnChatSubmit.addEventListener("click", fetchCalendarEventsWithChat);
  els.calChatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      fetchCalendarEventsWithChat();
    }
  });

  // Tab switching binds
  els.tabBtnView.addEventListener("click", () => {
    els.tabBtnView.classList.add("active");
    els.tabBtnCreate.classList.remove("active");
    els.sectionCalView.hidden = false;
    els.sectionCalCreate.hidden = true;
  });

  els.tabBtnCreate.addEventListener("click", () => {
    els.tabBtnCreate.classList.add("active");
    els.tabBtnView.classList.remove("active");
    els.sectionCalCreate.hidden = false;
    els.sectionCalView.hidden = true;
    
    // Pre-populate creation times
    const now = new Date();
    const oneHourLater = new Date(now.getTime() + 60 * 60 * 1000);
    els.createStart.value = formatLocalDateTime(now);
    els.createEnd.value = formatLocalDateTime(oneHourLater);
  });

  els.btnCalCreateSubmit.addEventListener("click", submitManualEvent);
  els.btnEventDetailClose.addEventListener("click", () => els.modalEventDetail.close());
  els.modalEventDetail.addEventListener("click", (e) => {
    if (e.target === els.modalEventDetail) {
      els.modalEventDetail.close();
    }
  });

  // Mail event binds
  els.btnMailSearch.addEventListener("click", fetchEmails);
  els.btnMailChatSubmit.addEventListener("click", fetchEmailsWithChat);
  els.mailChatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      fetchEmailsWithChat();
    }
  });

  // Mail tab switching binds
  els.tabBtnMailView.addEventListener("click", () => {
    els.tabBtnMailView.classList.add("active");
    els.tabBtnMailCreate.classList.remove("active");
    els.sectionMailView.hidden = false;
    els.sectionMailCreate.hidden = true;
  });

  els.tabBtnMailCreate.addEventListener("click", () => {
    els.tabBtnMailCreate.classList.add("active");
    els.tabBtnMailView.classList.remove("active");
    els.sectionMailCreate.hidden = false;
    els.sectionMailView.hidden = true;
  });

  els.btnMailDraftSubmit.addEventListener("click", submitMailDraft);
  els.btnMailSendSubmit.addEventListener("click", initiateMailSend);
  els.btnMailReplySubmit.addEventListener("click", submitMailReply);
  
  els.btnMailDetailClose.addEventListener("click", () => els.modalMailDetail.close());
  els.modalMailDetail.addEventListener("click", (e) => {
    if (e.target === els.modalMailDetail) {
      els.modalMailDetail.close();
    }
  });

  els.btnMailConfirmCancel.addEventListener("click", () => {
    els.modalMailConfirm.close();
    currentConfirmingDraftId = null;
    composeDataPendingSend = null;
  });
  
  els.btnMailConfirmSend.addEventListener("click", confirmAndSendMail);
  
  els.modalMailConfirm.addEventListener("click", (e) => {
    if (e.target === els.modalMailConfirm) {
      els.modalMailConfirm.close();
      currentConfirmingDraftId = null;
      composeDataPendingSend = null;
    }
  });
}

function formatLocalDateTime(date) {
  const tzoffset = date.getTimezoneOffset() * 60000;
  const localISOTime = (new Date(date - tzoffset)).toISOString().slice(0, 16);
  return localISOTime;
}

async function init() {
  bindEvents();
  handleUrlParams();
  showView("loading");

  // Set default start/end dates
  const now = new Date();
  els.calStart.value = formatLocalDateTime(now);
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  els.calEnd.value = formatLocalDateTime(tomorrow);

  await loadDashboard();
}

init();
