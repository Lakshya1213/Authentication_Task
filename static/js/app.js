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
  // CRM Elements
  crmQuery: $("crm-query"),
  crmProviderSelect: $("crm-provider-select"),
  btnCrmSearch: $("btn-crm-search"),
  crmContactsList: $("crm-contacts-list"),
  crmAccountsList: $("crm-accounts-list"),
  crmDealsList: $("crm-deals-list"),
  tabBtnCrmSearch: $("tab-btn-crm-search"),
  tabBtnCrmProposals: $("tab-btn-crm-proposals"),
  sectionCrmSearch: $("section-crm-search"),
  sectionCrmProposals: $("section-crm-proposals"),
  crmProposalsList: $("crm-proposals-list"),
  btnRefreshProposals: $("btn-refresh-proposals"),
  
  // CRM Contact Detail Modal Elements
  modalCrmContactDetail: $("modal-crm-contact-detail"),
  crmContactName: $("crm-contact-name"),
  crmContactProviderBadge: $("crm-contact-provider-badge"),
  crmContactEmail: $("crm-contact-email"),
  crmContactPhone: $("crm-contact-phone"),
  crmContactOwner: $("crm-contact-owner"),
  crmContactAccount: $("crm-contact-account"),
  crmContactNoteText: $("crm-contact-note-text"),
  btnCrmContactNoteSubmit: $("btn-crm-contact-note-submit"),
  crmContactTaskTitle: $("crm-contact-task-title"),
  crmContactTaskDue: $("crm-contact-task-due"),
  btnCrmContactTaskSubmit: $("btn-crm-contact-task-submit"),
  crmContactHistory: $("crm-contact-history"),

  // CRM Account Detail Modal Elements
  modalCrmAccountDetail: $("modal-crm-account-detail"),
  crmAccountNameHeader: $("crm-account-name-header"),
  crmAccountProviderBadge: $("crm-account-provider-badge"),
  crmAccountIndustry: $("crm-account-industry"),
  crmAccountWebsite: $("crm-account-website"),
  crmAccountOwner: $("crm-account-owner"),
  crmAccountNoteText: $("crm-account-note-text"),
  btnCrmAccountNoteSubmit: $("btn-crm-account-note-submit"),
  crmAccountTaskTitle: $("crm-account-task-title"),
  crmAccountTaskDue: $("crm-account-task-due"),
  btnCrmAccountTaskSubmit: $("btn-crm-account-task-submit"),
  crmAccountHistory: $("crm-account-history"),

  // CRM Deal Detail Modal Elements
  modalCrmDealDetail: $("modal-crm-deal-detail"),
  crmDealNameHeader: $("crm-deal-name-header"),
  crmDealProviderBadge: $("crm-deal-provider-badge"),
  crmDealStage: $("crm-deal-stage"),
  crmDealAmount: $("crm-deal-amount"),
  crmDealCloseDate: $("crm-deal-close-date"),
  crmDealOwner: $("crm-deal-owner"),
  crmDealUpdateStage: $("crm-deal-update-stage"),
  crmDealUpdateAmount: $("crm-deal-update-amount"),
  crmDealUpdateReason: $("crm-deal-update-reason"),
  btnCrmDealProposeSubmit: $("btn-crm-deal-propose-submit"),
  crmDealNoteText: $("crm-deal-note-text"),
  btnCrmDealNoteSubmit: $("btn-crm-deal-note-submit"),
  crmDealTaskTitle: $("crm-deal-task-title"),
  crmDealTaskDue: $("crm-deal-task-due"),
  btnCrmDealTaskSubmit: $("btn-crm-deal-task-submit"),
  crmDealHistory: $("crm-deal-history"),
  
  // CRM Manual Creation Elements
  btnCrmOpenCreate: $("btn-crm-open-create"),
  modalCrmCreateRecord: $("modal-crm-create-record"),
  crmCreateProvider: $("crm-create-provider"),
  tabBtnCreateContact: $("tab-btn-create-contact"),
  tabBtnCreateCompany: $("tab-btn-create-company"),
  tabBtnCreateDeal: $("tab-btn-create-deal"),
  formCreateContact: $("form-create-contact"),
  formCreateCompany: $("form-create-company"),
  formCreateDeal: $("form-create-deal"),
  btnCrmCreateSubmit: $("btn-crm-create-submit"),
  crmCreateContactFirst: $("crm-create-contact-first"),
  crmCreateContactLast: $("crm-create-contact-last"),
  crmCreateContactEmail: $("crm-create-contact-email"),
  crmCreateContactPhone: $("crm-create-contact-phone"),
  crmCreateCompanyName: $("crm-create-company-name"),
  crmCreateCompanyIndustry: $("crm-create-company-industry"),
  crmCreateCompanyWebsite: $("crm-create-company-website"),
  crmCreateDealName: $("crm-create-deal-name"),
  crmCreateDealStage: $("crm-create-deal-stage"),
  crmCreateDealAmount: $("crm-create-deal-amount"),

  // Transcript Agent elements
  tabBtnCrmTranscript: $("tab-btn-crm-transcript"),
  sectionCrmTranscript: $("section-crm-transcript"),
  crmTranscriptDealId: $("crm-transcript-deal-id"),
  crmTranscriptProviderSelect: $("crm-transcript-provider-select"),
  crmTranscriptText: $("crm-transcript-text"),
  btnCrmTranscriptAnalyze: $("btn-crm-transcript-analyze"),
  crmTranscriptDiscoveredWrapper: $("crm-transcript-discovered-wrapper"),
  crmTranscriptDiscoveredProperties: $("crm-transcript-discovered-properties"),
  crmTranscriptDiscoveredTools: $("crm-transcript-discovered-tools"),
  crmTranscriptProposalsWrapper: $("crm-transcript-proposals-wrapper"),
  crmTranscriptProposalsTableBody: $("crm-transcript-proposals-table-body"),
  crmTranscriptSkippedWrapper: $("crm-transcript-skipped-wrapper"),
  crmTranscriptSkippedCount: $("crm-transcript-skipped-count"),
  crmTranscriptSkippedList: $("crm-transcript-skipped-list"),
  btnCrmTranscriptApply: $("btn-crm-transcript-apply"),
  crmTranscriptSummaryWrapper: $("crm-transcript-summary-wrapper"),
  crmTranscriptSummaryExecuted: $("crm-transcript-summary-executed"),
  crmTranscriptSummaryFailedContainer: $("crm-transcript-summary-failed-container"),
  crmTranscriptSummaryFailed: $("crm-transcript-summary-failed"),
};

/** @type {object|null} */
let currentUser = null;
let providerToDisconnect = null;
let currentViewingMessageId = null;
let currentConfirmingDraftId = null;
let composeDataPendingSend = null;

const ALL_PROVIDERS = ["google", "microsoft", "linkedin", "zoom", "hubspot", "zoho", "salesforce"];

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
    
    const crmConnected = apps.some(a => ["hubspot", "zoho", "salesforce"].includes(a.provider.toLowerCase()) && a.status === "connected");
    if (crmConnected) {
      searchCRM();
      loadCRMProposals();
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

  // CRM Event Binds
  els.btnCrmSearch.addEventListener("click", searchCRM);
  els.crmQuery.addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchCRM();
  });

  els.tabBtnCrmSearch.addEventListener("click", () => {
    els.tabBtnCrmSearch.classList.add("active");
    els.tabBtnCrmProposals.classList.remove("active");
    els.tabBtnCrmTranscript.classList.remove("active");
    els.sectionCrmSearch.hidden = false;
    els.sectionCrmProposals.hidden = true;
    els.sectionCrmTranscript.hidden = true;
  });

  els.tabBtnCrmProposals.addEventListener("click", () => {
    els.tabBtnCrmProposals.classList.add("active");
    els.tabBtnCrmSearch.classList.remove("active");
    els.tabBtnCrmTranscript.classList.remove("active");
    els.sectionCrmProposals.hidden = false;
    els.sectionCrmSearch.hidden = true;
    els.sectionCrmTranscript.hidden = true;
    loadCRMProposals();
  });

  els.tabBtnCrmTranscript.addEventListener("click", () => {
    els.tabBtnCrmTranscript.classList.add("active");
    els.tabBtnCrmSearch.classList.remove("active");
    els.tabBtnCrmProposals.classList.remove("active");
    els.sectionCrmTranscript.hidden = false;
    els.sectionCrmSearch.hidden = true;
    els.sectionCrmProposals.hidden = true;
  });

  els.btnRefreshProposals.addEventListener("click", loadCRMProposals);

  // Notes and task submissions
  els.btnCrmContactNoteSubmit.addEventListener("click", addCRMNote);
  els.btnCrmAccountNoteSubmit.addEventListener("click", addCRMNote);
  els.btnCrmDealNoteSubmit.addEventListener("click", addCRMNote);

  els.btnCrmContactTaskSubmit.addEventListener("click", createCRMTask);
  els.btnCrmAccountTaskSubmit.addEventListener("click", createCRMTask);
  els.btnCrmDealTaskSubmit.addEventListener("click", createCRMTask);

  // Propose deal updates
  els.btnCrmDealProposeSubmit.addEventListener("click", proposeDealUpdate);

  // CRM Create Record Modal event bindings
  els.btnCrmOpenCreate.addEventListener("click", () => {
    // Sync default active tab and clear inputs
    els.tabBtnCreateContact.click();
    els.crmCreateContactFirst.value = "";
    els.crmCreateContactLast.value = "";
    els.crmCreateContactEmail.value = "";
    els.crmCreateContactPhone.value = "";
    els.crmCreateCompanyName.value = "";
    els.crmCreateCompanyIndustry.value = "";
    els.crmCreateCompanyWebsite.value = "";
    els.crmCreateDealName.value = "";
    els.crmCreateDealStage.selectedIndex = 0;
    els.crmCreateDealAmount.value = "";
    
    // Default destination provider value matching current search provider selection
    els.crmCreateProvider.value = els.crmProviderSelect.value || "hubspot";
    
    els.modalCrmCreateRecord.showModal();
  });

  els.tabBtnCreateContact.addEventListener("click", () => {
    currentCreateTab = "contact";
    els.tabBtnCreateContact.classList.add("active");
    els.tabBtnCreateCompany.classList.remove("active");
    els.tabBtnCreateDeal.classList.remove("active");
    els.formCreateContact.hidden = false;
    els.formCreateCompany.hidden = true;
    els.formCreateDeal.hidden = true;
  });

  els.tabBtnCreateCompany.addEventListener("click", () => {
    currentCreateTab = "company";
    els.tabBtnCreateCompany.classList.add("active");
    els.tabBtnCreateContact.classList.remove("active");
    els.tabBtnCreateDeal.classList.remove("active");
    els.formCreateCompany.hidden = false;
    els.formCreateContact.hidden = true;
    els.formCreateDeal.hidden = true;
  });

  els.tabBtnCreateDeal.addEventListener("click", () => {
    currentCreateTab = "deal";
    els.tabBtnCreateDeal.classList.add("active");
    els.tabBtnCreateContact.classList.remove("active");
    els.tabBtnCreateCompany.classList.remove("active");
    els.formCreateDeal.hidden = false;
    els.formCreateContact.hidden = true;
    els.formCreateCompany.hidden = true;
  });

  els.btnCrmCreateSubmit.addEventListener("click", submitCRMRecordCreation);

  // B2B Transcript Agent buttons
  els.btnCrmTranscriptAnalyze.addEventListener("click", runTranscriptAgentAnalysis);
  els.btnCrmTranscriptApply.addEventListener("click", applyApprovedTranscriptChanges);
}

let currentCRMEntity = null; // Store currently viewed CRM entity details

async function searchCRM() {
  const query = els.crmQuery.value.trim();
  const provider = els.crmProviderSelect.value;
  els.btnCrmSearch.disabled = true;

  try {
    const data = await api(`/crm/search?query=${encodeURIComponent(query)}&provider=${encodeURIComponent(provider)}`);
    
    // 1. Render Contacts
    if (data.contacts.length === 0) {
      els.crmContactsList.innerHTML = `<p class="muted empty-state" style="padding: 1rem 0; font-size: 0.85rem;">No contacts found.</p>`;
    } else {
      els.crmContactsList.innerHTML = data.contacts
        .map(c => `
          <div class="event-item crm-record-item" onclick="viewCRMRecord('contact', '${c.provider}', '${c.crm_object_id}')" style="cursor: pointer; margin-bottom: 0.5rem; padding: 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: rgba(255,255,255,0.01);">
            <div style="font-weight: 600; display:flex; justify-content:space-between;">
              <span>${escapeHtml(c.name)}</span>
              <span class="badge badge-success" style="font-size:0.65rem; padding: 0.15rem 0.35rem;">${c.provider}</span>
            </div>
            <div class="muted" style="font-size: 0.8rem; margin-top: 0.25rem;">
              ${escapeHtml(c.email)}<br/>
              ${escapeHtml(c.phone || 'No phone')}
            </div>
          </div>
        `).join("");
    }

    // 2. Render Companies/Accounts
    if (data.accounts.length === 0) {
      els.crmAccountsList.innerHTML = `<p class="muted empty-state" style="padding: 1rem 0; font-size: 0.85rem;">No accounts found.</p>`;
    } else {
      els.crmAccountsList.innerHTML = data.accounts
        .map(a => `
          <div class="event-item crm-record-item" onclick="viewCRMRecord('account', '${a.provider}', '${a.crm_object_id}')" style="cursor: pointer; margin-bottom: 0.5rem; padding: 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: rgba(255,255,255,0.01);">
            <div style="font-weight: 600; display:flex; justify-content:space-between;">
              <span>${escapeHtml(a.name)}</span>
              <span class="badge badge-success" style="font-size:0.65rem; padding: 0.15rem 0.35rem;">${a.provider}</span>
            </div>
            <div class="muted" style="font-size: 0.8rem; margin-top: 0.25rem;">
              Industry: ${escapeHtml(a.industry || '—')}<br/>
              Website: ${escapeHtml(a.website || '—')}
            </div>
          </div>
        `).join("");
    }

    // 3. Render Deals
    if (data.deals.length === 0) {
      els.crmDealsList.innerHTML = `<p class="muted empty-state" style="padding: 1rem 0; font-size: 0.85rem;">No deals found.</p>`;
    } else {
      els.crmDealsList.innerHTML = data.deals
        .map(d => `
          <div class="event-item crm-record-item" onclick="viewCRMRecord('deal', '${d.provider}', '${d.crm_object_id}')" style="cursor: pointer; margin-bottom: 0.5rem; padding: 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: rgba(255,255,255,0.01);">
            <div style="font-weight: 600; display:flex; justify-content:space-between;">
              <span>${escapeHtml(d.name)}</span>
              <span class="badge badge-success" style="font-size:0.65rem; padding: 0.15rem 0.35rem;">${d.provider}</span>
            </div>
            <div class="muted" style="font-size: 0.8rem; margin-top: 0.25rem; display: flex; justify-content: space-between;">
              <span>Stage: <strong style="color: #fdba74;">${escapeHtml(d.stage)}</strong></span>
              <strong>$${d.amount.toLocaleString()}</strong>
            </div>
          </div>
        `).join("");
    }

    showToast("CRM search completed successfully.");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    els.btnCrmSearch.disabled = false;
  }
}

async function viewCRMRecord(type, provider, objectId) {
  try {
    const data = await api(`/crm/detail?provider=${provider}&object_type=${type}&object_id=${objectId}`);
    currentCRMEntity = { type, provider, id: objectId };

    if (type === "contact") {
      els.crmContactName.textContent = data.name;
      els.crmContactProviderBadge.textContent = provider.toUpperCase();
      els.crmContactEmail.textContent = data.email || "—";
      els.crmContactPhone.textContent = data.phone || "—";
      els.crmContactOwner.textContent = data.owner?.name || "Unassigned";
      els.crmContactAccount.textContent = data.related_account?.name || "None";
      
      // Clear inputs
      els.crmContactNoteText.value = "";
      els.crmContactTaskTitle.value = "";
      els.crmContactTaskDue.value = "";

      renderCRMHistory(els.crmContactHistory, data.notes, data.tasks);
      els.modalCrmContactDetail.showModal();
    } 
    else if (type === "account") {
      els.crmAccountNameHeader.textContent = data.name;
      els.crmAccountProviderBadge.textContent = provider.toUpperCase();
      els.crmAccountIndustry.textContent = data.industry || "—";
      els.crmAccountWebsite.textContent = data.website || "—";
      els.crmAccountOwner.textContent = data.owner?.name || "Unassigned";

      // Clear inputs
      els.crmAccountNoteText.value = "";
      els.crmAccountTaskTitle.value = "";
      els.crmAccountTaskDue.value = "";

      renderCRMHistory(els.crmAccountHistory, data.notes, data.tasks);
      els.modalCrmAccountDetail.showModal();
    } 
    else if (type === "deal") {
      els.crmDealNameHeader.textContent = data.name;
      els.crmDealProviderBadge.textContent = provider.toUpperCase();
      els.crmDealStage.textContent = data.stage;
      els.crmDealAmount.textContent = `$${data.amount.toLocaleString()} ${data.currency || 'USD'}`;
      els.crmDealCloseDate.textContent = data.close_date || "—";
      els.crmDealOwner.textContent = data.owner?.name || "Unassigned";

      // Populate proposal fields
      els.crmDealUpdateStage.value = data.stage;
      els.crmDealUpdateAmount.value = data.amount;
      els.crmDealUpdateReason.value = "";

      // Clear note/task inputs
      els.crmDealNoteText.value = "";
      els.crmDealTaskTitle.value = "";
      els.crmDealTaskDue.value = "";

      renderCRMHistory(els.crmDealHistory, data.notes, data.tasks);
      els.modalCrmDealDetail.showModal();
    }
  } catch (err) {
    showToast(`Failed to load details: ${err.message}`, "error");
  }
}

function renderCRMHistory(container, notes = [], tasks = []) {
  if (notes.length === 0 && tasks.length === 0) {
    container.innerHTML = `<p class="muted" style="margin:0;">No notes or tasks recorded on this sandbox record.</p>`;
    return;
  }

  const items = [];
  notes.forEach(n => {
    items.push({
      type: "note",
      text: n.text,
      date: new Date(n.created_at),
      html: `
        <div style="margin-bottom: 0.5rem; border-left: 2px solid #f97316; padding-left: 0.5rem;">
          <span style="font-weight:600; color:#fdba74;">Note</span>
          <span class="muted" style="font-size:0.75rem; float:right;">${formatDate(n.created_at)}</span>
          <p style="margin: 0.25rem 0 0 0;">${escapeHtml(n.text)}</p>
        </div>
      `
    });
  });

  tasks.forEach(t => {
    items.push({
      type: "task",
      date: new Date(t.created_at || Date.now()),
      html: `
        <div style="margin-bottom: 0.5rem; border-left: 2px solid #3b82f6; padding-left: 0.5rem;">
          <span style="font-weight:600; color:#60a5fa;">Task</span>
          <span class="muted" style="font-size:0.75rem; float:right;">Due: ${t.due_date || '—'}</span>
          <p style="margin: 0.25rem 0 0 0;">${escapeHtml(t.title)} (Owner: ${escapeHtml(t.owner)})</p>
        </div>
      `
    });
  });

  // Sort chronologically descending
  items.sort((a,b) => b.date - a.date);
  container.innerHTML = items.map(x => x.html).join("");
}

async function addCRMNote() {
  if (!currentCRMEntity) return;
  const textarea = currentCRMEntity.type === "contact" ? els.crmContactNoteText :
                   currentCRMEntity.type === "account" ? els.crmAccountNoteText : els.crmDealNoteText;
  
  const text = textarea.value.trim();
  if (!text) {
    showToast("Please enter some note text.", "error");
    return;
  }

  try {
    await api("/crm/write/note", {
      method: "POST",
      body: JSON.stringify({
        provider: currentCRMEntity.provider,
        entity_type: currentCRMEntity.type,
        entity_id: currentCRMEntity.id,
        note_text: text
      })
    });

    showToast("Note added successfully.");
    // Reload record detail
    await viewCRMRecord(currentCRMEntity.type, currentCRMEntity.provider, currentCRMEntity.id);
  } catch (err) {
    showToast(`Failed to add note: ${err.message}`, "error");
  }
}

async function createCRMTask() {
  if (!currentCRMEntity) return;
  const titleInput = currentCRMEntity.type === "contact" ? els.crmContactTaskTitle :
                     currentCRMEntity.type === "account" ? els.crmAccountTaskTitle : els.crmDealTaskTitle;
  const dueInput = currentCRMEntity.type === "contact" ? els.crmContactTaskDue :
                   currentCRMEntity.type === "account" ? els.crmAccountTaskDue : els.crmDealTaskDue;
  
  const title = titleInput.value.trim();
  const due = dueInput.value ? new Date(dueInput.value).toISOString() : null;

  if (!title) {
    showToast("Please enter a task description.", "error");
    return;
  }

  try {
    await api("/crm/write/task", {
      method: "POST",
      body: JSON.stringify({
        provider: currentCRMEntity.provider,
        entity_type: currentCRMEntity.type,
        entity_id: currentCRMEntity.id,
        task_title: title,
        due_date: due
      })
    });

    showToast("Follow-up task created successfully.");
    await viewCRMRecord(currentCRMEntity.type, currentCRMEntity.provider, currentCRMEntity.id);
  } catch (err) {
    showToast(`Failed to create task: ${err.message}`, "error");
  }
}

async function proposeDealUpdate() {
  if (!currentCRMEntity || currentCRMEntity.type !== "deal") return;
  
  const stage = els.crmDealUpdateStage.value;
  const amount = parseFloat(els.crmDealUpdateAmount.value);
  const reason = els.crmDealUpdateReason.value.trim();

  if (isNaN(amount) || amount < 0) {
    showToast("Please enter a valid amount.", "error");
    return;
  }

  try {
    const res = await api("/crm/propose-deal-update", {
      method: "POST",
      body: JSON.stringify({
        provider: currentCRMEntity.provider,
        deal_id: currentCRMEntity.id,
        proposed_changes: { stage, amount },
        reason: reason || "Standard update proposal"
      })
    });

    showToast("Stage update proposal created successfully. Approvals can be managed on the proposals tab.");
    els.modalCrmDealDetail.close();
    loadCRMProposals();
  } catch (err) {
    showToast(`Failed to propose update: ${err.message}`, "error");
  }
}

async function loadCRMProposals() {
  try {
    const proposals = await api("/crm/proposals");
    if (proposals.length === 0) {
      els.crmProposalsList.innerHTML = `<p class="muted empty-state" style="padding: 2rem; text-align: center;">No proposals created yet.</p>`;
      return;
    }

    els.crmProposalsList.innerHTML = proposals
      .map(p => {
        const changesText = Object.entries(p.proposed_changes)
          .map(([k, v]) => `${k.toUpperCase()}: <strong>${escapeHtml(v.toString())}</strong>`)
          .join(", ");
        
        let actionsHtml = "";
        if (p.status === "pending") {
          actionsHtml = `
            <div style="margin-top: 0.5rem; display: flex; gap: 0.5rem;">
              <button class="btn btn-primary-gradient btn-sm" onclick="approveProposal(${p.id})">Approve & Write</button>
              <button class="btn btn-secondary btn-sm" onclick="rejectProposal(${p.id})">Reject</button>
            </div>
          `;
        }

        const statusClass = p.status === "approved" ? "badge-success" : p.status === "rejected" ? "badge-danger" : "badge-connected";

        return `
          <div class="event-item" style="margin-bottom: 0.75rem; padding: 1rem; border: 1px solid var(--border); border-radius: 8px; background: rgba(255,255,255,0.01);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-weight:600; font-size:1.05rem;">Deal Proposal (ID: ${p.deal_id})</span>
              <span class="badge ${statusClass}">${p.status.toUpperCase()}</span>
            </div>
            <div class="muted" style="font-size:0.85rem; margin-top: 0.5rem;">
              Provider: <strong style="text-transform: capitalize;">${p.provider}</strong><br/>
              Changes: ${changesText}<br/>
              Reason: <em>"${escapeHtml(p.reason || 'None')}"</em><br/>
              Proposed At: ${formatDate(p.created_at)}
            </div>
            ${actionsHtml}
          </div>
        `;
      }).join("");
  } catch (err) {
    showToast(`Failed to load proposals: ${err.message}`, "error");
  }
}

async function approveProposal(id) {
  try {
    await api(`/crm/proposals/${id}/approve`, { method: "POST" });
    showToast("Proposal approved and executed to CRM successfully!");
    loadCRMProposals();
    searchCRM(); // Refresh search results
  } catch (err) {
    showToast(`Failed to approve proposal: ${err.message}`, "error");
  }
}

async function rejectProposal(id) {
  try {
    await api(`/crm/proposals/${id}/reject`, { method: "POST" });
    showToast("Proposal rejected.");
    loadCRMProposals();
  } catch (err) {
    showToast(`Failed to reject proposal: ${err.message}`, "error");
  }
}

let currentCreateTab = "contact";

async function submitCRMRecordCreation() {
  const provider = els.crmCreateProvider.value;
  els.btnCrmCreateSubmit.disabled = true;

  try {
    if (currentCreateTab === "contact") {
      const first = els.crmCreateContactFirst.value.trim();
      const last = els.crmCreateContactLast.value.trim();
      const email = els.crmCreateContactEmail.value.trim();
      const phone = els.crmCreateContactPhone.value.trim();

      if (!first || !last || !email) {
        showToast("First Name, Last Name, and Email are required.", "error");
        els.btnCrmCreateSubmit.disabled = false;
        return;
      }

      await api("/crm/write/contact", {
        method: "POST",
        body: JSON.stringify({
          provider,
          first_name: first,
          last_name: last,
          email,
          phone: phone || null
        })
      });
      showToast("Contact created successfully!");
    } 
    else if (currentCreateTab === "company") {
      const name = els.crmCreateCompanyName.value.trim();
      const industry = els.crmCreateCompanyIndustry.value.trim();
      const website = els.crmCreateCompanyWebsite.value.trim();

      if (!name) {
        showToast("Company Name is required.", "error");
        els.btnCrmCreateSubmit.disabled = false;
        return;
      }

      await api("/crm/write/company", {
        method: "POST",
        body: JSON.stringify({
          provider,
          name,
          industry: industry || null,
          website: website || null
        })
      });
      showToast("Company created successfully!");
    } 
    else if (currentCreateTab === "deal") {
      const name = els.crmCreateDealName.value.trim();
      const stage = els.crmCreateDealStage.value;
      const amount = parseFloat(els.crmCreateDealAmount.value);

      if (!name || isNaN(amount) || amount < 0) {
        showToast("Deal Name and a valid positive Amount are required.", "error");
        els.btnCrmCreateSubmit.disabled = false;
        return;
      }

      await api("/crm/write/deal", {
        method: "POST",
        body: JSON.stringify({
          provider,
          name,
          stage,
          amount
        })
      });
      showToast("Deal created successfully!");
    }

    els.modalCrmCreateRecord.close();
    // Auto-refresh CRM search results
    await searchCRM();
  } catch (err) {
    showToast(`Creation failed: ${err.message}`, "error");
  } finally {
    els.btnCrmCreateSubmit.disabled = false;
  }
}

let currentTranscriptProposals = []; // In-memory cache of proposed updates

async function runTranscriptAgentAnalysis() {
  const dealId = els.crmTranscriptDealId.value.trim();
  const provider = els.crmTranscriptProviderSelect.value;
  const transcript = els.crmTranscriptText.value.trim();

  if (!dealId || !transcript) {
    showToast("Please enter a Deal ID and paste a sales call transcript.", "error");
    return;
  }

  els.btnCrmTranscriptAnalyze.disabled = true;
  els.btnCrmTranscriptAnalyze.textContent = "Analyzing Transcript...";
  
  // Hide previous wrappers
  els.crmTranscriptDiscoveredWrapper.hidden = true;
  els.crmTranscriptProposalsWrapper.hidden = true;
  els.crmTranscriptSummaryWrapper.hidden = true;

  try {
    const data = await api("/hubspot-transcript-agent/run", {
      method: "POST",
      body: JSON.stringify({ deal_id: dealId, transcript, provider })
    });

    // 1. Render Discovered Tools and Properties
    els.crmTranscriptDiscoveredProperties.innerHTML = "";
    els.crmTranscriptDiscoveredTools.innerHTML = "";

    const dealProps = data.discovered_properties.deals || [];
    dealProps.slice(0, 15).forEach(p => {
      els.crmTranscriptDiscoveredProperties.innerHTML += `<span class="badge badge-success" style="font-size:0.7rem; margin-right:0.25rem; margin-bottom:0.25rem;">${escapeHtml(p.label)} (${escapeHtml(p.name)})</span>`;
    });
    if (dealProps.length > 15) {
      els.crmTranscriptDiscoveredProperties.innerHTML += `<span class="badge badge-secondary" style="font-size:0.7rem;">+${dealProps.length - 15} more</span>`;
    }

    const tools = data.discovered_tools || [];
    tools.forEach(t => {
      els.crmTranscriptDiscoveredTools.innerHTML += `<span class="badge badge-primary" style="font-size:0.7rem; margin-right:0.25rem; margin-bottom:0.25rem;">${escapeHtml(t.name)}</span>`;
    });

    els.crmTranscriptDiscoveredWrapper.hidden = false;

    // 2. Render Proposed Changes
    currentTranscriptProposals = data.proposed_changes || [];
    if (currentTranscriptProposals.length === 0) {
      els.crmTranscriptProposalsTableBody.innerHTML = `<tr><td colspan="8" class="muted" style="text-align:center; padding:1.5rem;">No updates proposed from this transcript.</td></tr>`;
    } else {
      els.crmTranscriptProposalsTableBody.innerHTML = currentTranscriptProposals.map((c, idx) => `
        <tr style="border-bottom:1px solid var(--border);">
          <td style="padding: 0.75rem;"><span class="badge badge-primary" style="font-size: 0.75rem;">${escapeHtml(c.action_type)}</span></td>
          <td style="padding: 0.75rem; text-transform: capitalize;">${escapeHtml(c.object_type)}</td>
          <td style="padding: 0.75rem; font-family: monospace;">${escapeHtml(c.property_name || "create_activity")}</td>
          <td style="padding: 0.75rem; color: var(--text-muted); max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(String(c.current_value || "Empty"))}</td>
          <td style="padding: 0.75rem; font-weight: 600; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(String(c.proposed_value || c.tool_payload.task_title || "Create Record"))}</td>
          <td style="padding: 0.75rem; max-width: 150px; font-size: 0.8rem; line-height: 1.3;">${escapeHtml(c.reason)}</td>
          <td style="padding: 0.75rem; max-width: 150px; font-style: italic; color: #fbbf24; font-size: 0.8rem; line-height: 1.3;">"${escapeHtml(c.evidence_text)}"</td>
          <td style="padding: 0.75rem; text-align: center;">
            <input type="checkbox" id="chk-transcript-prop-${idx}" checked style="width: 16px; height: 16px; cursor: pointer;" />
          </td>
        </tr>
      `).join('');
    }
    
    // 3. Render Skipped Candidates
    const skipped = data.skipped_candidates || [];
    els.crmTranscriptSkippedCount.textContent = skipped.length;
    if (skipped.length === 0) {
      els.crmTranscriptSkippedWrapper.hidden = true;
    } else {
      els.crmTranscriptSkippedList.innerHTML = skipped.map(s => `
        <li style="margin-bottom:0.25rem;">
          <strong style="color: var(--text-muted);">${escapeHtml(s.candidate.property_label || s.candidate.title || "Record")}</strong>: 
          ${escapeHtml(s.reason)}
        </li>
      `).join('');
      els.crmTranscriptSkippedWrapper.hidden = false;
    }

    els.crmTranscriptProposalsWrapper.hidden = false;
    showToast("Transcript analyzed successfully!");
  } catch (err) {
    showToast(`Analysis failed: ${err.message}`, "error");
  } finally {
    els.btnCrmTranscriptAnalyze.disabled = false;
    els.btnCrmTranscriptAnalyze.textContent = "Analyze Transcript";
  }
}

async function applyApprovedTranscriptChanges() {
  const provider = els.crmTranscriptProviderSelect.value;
  const approved = [];
  
  currentTranscriptProposals.forEach((c, idx) => {
    const chk = document.getElementById(`chk-transcript-prop-${idx}`);
    if (chk && chk.checked) {
      approved.push(c);
    }
  });

  if (approved.length === 0) {
    showToast("Please approve at least one change before applying.", "error");
    return;
  }

  els.btnCrmTranscriptApply.disabled = true;
  els.btnCrmTranscriptApply.textContent = "Applying Updates...";

  try {
    const res = await api("/hubspot-transcript-agent/apply", {
      method: "POST",
      body: JSON.stringify({ approved_changes: approved, provider })
    });

    // Render Executed Summary
    els.crmTranscriptSummaryExecuted.innerHTML = res.executed.map(e => `
      <li style="margin-bottom:0.25rem;">${escapeHtml(e)}</li>
    `).join('');
    if (res.executed.length === 0) {
      els.crmTranscriptSummaryExecuted.innerHTML = `<li>No changes were applied.</li>`;
    }

    // Render Failed Summary
    if (res.failed && res.failed.length > 0) {
      els.crmTranscriptSummaryFailed.innerHTML = res.failed.map(f => `
        <li style="margin-bottom:0.25rem;">${escapeHtml(f)}</li>
      `).join('');
      els.crmTranscriptSummaryFailedContainer.hidden = false;
    } else {
      els.crmTranscriptSummaryFailedContainer.hidden = true;
    }

    els.crmTranscriptSummaryWrapper.hidden = false;
    els.crmTranscriptProposalsWrapper.hidden = true;
    
    showToast("CRM updates completed!");
  } catch (err) {
    showToast(`Application failed: ${err.message}`, "error");
  } finally {
    els.btnCrmTranscriptApply.disabled = false;
    els.btnCrmTranscriptApply.textContent = "Apply Approved Updates";
  }
}

// Make globally accessible
window.approveProposal = approveProposal;
window.rejectProposal = rejectProposal;
window.viewCRMRecord = viewCRMRecord;

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
