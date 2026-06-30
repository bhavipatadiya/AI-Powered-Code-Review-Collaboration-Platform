const API = "http://127.0.0.1:8000";

if (!document.getElementById("custom-modal-styles")) {
  const style = document.createElement("style");
  style.id = "custom-modal-styles";
  style.textContent = `
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes scaleUp { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  `;
  document.head.appendChild(style);
}

function showCustomModal({ title, message, buttons = [], onClose }) {
  const backdrop = document.createElement("div");
  backdrop.style.cssText = "position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px); display: flex; justify-content: center; align-items: center; z-index: 100000; animation: fadeIn 0.2s ease-out;";
  const container = document.createElement("div");
  container.style.cssText = "background: var(--color-surface, #fff); border: 1px solid var(--color-border, #e2e8f0); border-radius: var(--radius-md, 8px); padding: 24px; max-width: 400px; width: 90%; box-shadow: var(--shadow-lg, 0 10px 15px -3px rgba(0,0,0,0.1)); animation: scaleUp 0.2s ease-out;";
  const titleEl = document.createElement("h3");
  titleEl.style.cssText = "margin-top: 0; margin-bottom: 12px; font-size: 1.2rem; color: var(--color-text, #1e293b);";
  titleEl.textContent = title;
  container.appendChild(titleEl);
  const msgEl = document.createElement("p");
  msgEl.style.cssText = "font-size: 0.9rem; color: var(--color-muted, #64748b); line-height: 1.5; margin-bottom: 24px; white-space: pre-wrap;";
  msgEl.textContent = message;
  container.appendChild(msgEl);
  const btnContainer = document.createElement("div");
  btnContainer.style.cssText = "display: flex; justify-content: flex-end; gap: 12px;";
  buttons.forEach(btnSpec => {
    const btn = document.createElement("button");
    btn.textContent = btnSpec.text;
    if (btnSpec.type === "danger") {
      btn.style.cssText = "padding: 8px 16px; font-size: 0.85rem; border-radius: 4px; background: #e53e3e; color: white; border: none; cursor: pointer; font-weight: 500;";
    } else if (btnSpec.type === "primary") {
      btn.style.cssText = "padding: 8px 16px; font-size: 0.85rem; border-radius: 4px; background: var(--color-primary, #13c2c2); color: white; border: none; cursor: pointer; font-weight: 500;";
    } else {
      btn.style.cssText = "padding: 8px 16px; font-size: 0.85rem; border-radius: 4px; background: transparent; color: var(--color-text, #1e293b); border: 1px solid var(--color-border, #e2e8f0); cursor: pointer; font-weight: 500;";
    }
    btn.addEventListener("click", () => {
      document.body.removeChild(backdrop);
      if (btnSpec.onClick) btnSpec.onClick();
      if (onClose) onClose();
    });
    btnContainer.appendChild(btn);
  });
  container.appendChild(btnContainer);
  backdrop.appendChild(container);
  document.body.appendChild(backdrop);
}

function showCustomAlert(title, message, onOk) {
  showCustomModal({
    title,
    message,
    buttons: [
      { text: "OK", type: "primary", onClick: onOk }
    ]
  });
}

function showCustomConfirmDelete(title, message, onConfirm, onCancel) {
  showCustomModal({
    title,
    message,
    buttons: [
      { text: "Cancel", type: "ghost", onClick: onCancel },
      { text: "Delete", type: "danger", onClick: onConfirm }
    ]
  });
}

const token = localStorage.getItem("token");
if (!token) { window.location.href = "/login"; }

let currentUser = null;
try { currentUser = JSON.parse(localStorage.getItem("user")); } catch (_) {}

if (!currentUser || currentUser.role !== "admin") {
  showCustomAlert("Access Denied", "Access denied. Admins only.", () => {
    window.location.href = "/login";
  });
}

function authHeaders() {
  return { "Content-Type": "application/json", "Authorization": "Bearer " + token };
}

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(API + path, {
      ...options,
      headers: { ...authHeaders(), ...(options.headers || {}) }
    });
    if (res.status === 401 || res.status === 403) {
      showCustomAlert("Session Expired", "Session expired or access denied.", () => {
        window.location.href = "/login";
      });
      return null;
    }
    return res;
  } catch (err) {
    console.error("[apiFetch]", path, err);
    return null;
  }
}

document.getElementById("logout-btn").addEventListener("click", () => {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.location.href = "/login";
});

const adminProfileBtn = document.getElementById("admin-profile-btn");
if (adminProfileBtn) {
  adminProfileBtn.addEventListener("click", () => showTab("profile"));
}

const navItems = document.querySelectorAll(".nav-item[data-tab]");
const sections = document.querySelectorAll(".admin-section");

let isSortDesc = true;
let currentTab = "overview";

const sortToggleBtn = document.getElementById("sort-toggle-btn");
if (sortToggleBtn) {
  sortToggleBtn.addEventListener("click", () => {
    isSortDesc = !isSortDesc;
    sortToggleBtn.textContent = isSortDesc ? "Sort: DESC" : "Sort: ASC";
    showTab(currentTab);
  });
}

function showTab(name) {
  sections.forEach(s => s.classList.remove("active"));
  navItems.forEach(n => n.classList.remove("active"));

  const sec = document.getElementById("tab-" + name);
  if (sec) sec.classList.add("active");

  const nav = document.querySelector(`.nav-item[data-tab="${name}"]`);
  if (nav) nav.classList.add("active");

  currentTab = name;

  const loaders = {
    overview: loadOverview,
    users:    loadUsers,
    projects: loadProjects,
    files:    loadFiles,
    reviews:  loadReviews,
    chats:    loadChats,
    activity: loadActivity,
    logins:   loadLogins,
    logs:     loadAdminLogs,
    profile:  loadProfile,
  };
  if (loaders[name]) loaders[name]();
}
   
navItems.forEach(item => {
  item.addEventListener("click", e => {
    e.preventDefault();
    showTab(item.dataset.tab);
  });
});

async function loadProfile() {
  const res = await apiFetch('/auth/profile');
  if (res && res.ok) {
    const data = await res.json();
    const uEl = document.getElementById('prof-username');
    const eEl = document.getElementById('prof-email');
    if(uEl) uEl.value = data.username;
    if(eEl) eEl.value = data.email;
  }
}

function showAlert(e, msg, type) { if (e) { e.textContent = msg; e.className = "form-alert alert-" + type; e.style.display = "block"; } }

const profileForm = document.getElementById('profile-form');
if (profileForm) {
  profileForm.addEventListener('submit', async e => {
    e.preventDefault();
    const res = await apiFetch('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify({
        username: document.getElementById('prof-username').value.trim(),
        email: document.getElementById('prof-email').value.trim()
      })
    });
    const alertEl = document.getElementById('prof-alert');
    if (res && res.ok) {
      showAlert(alertEl, 'Profile updated successfully!', 'success');
      const data = await res.json();
      if (currentUser) {
        currentUser.username = data.username;
        currentUser.email = data.email;
        localStorage.setItem('user', JSON.stringify(currentUser));
        const adminProfileSpan = document.querySelector("#admin-profile-btn .user-name");
        if (adminProfileSpan) adminProfileSpan.textContent = data.username;
        const adminProfileAvatar = document.querySelector("#admin-profile-btn .user-avatar");
        if (adminProfileAvatar) adminProfileAvatar.textContent = data.username.charAt(0).toUpperCase();
      }
    } else {
      const err = await res.json();
      showAlert(alertEl, err.detail || 'Update failed', 'danger');
    }
  });
}

const passwordForm = document.getElementById('password-form');
if (passwordForm) {
  passwordForm.addEventListener('submit', async e => {
    e.preventDefault();
    const res = await apiFetch('/auth/profile/password', {
      method: 'PUT',
      body: JSON.stringify({
        old_password: document.getElementById('prof-old-pwd').value,
        new_password: document.getElementById('prof-new-pwd').value
      })
    });
    const alertEl = document.getElementById('pwd-alert');
    if (res && res.ok) {
      showAlert(alertEl, 'Password changed successfully!', 'success');
      e.target.reset();
    } else {
      const err = await res.json();
      showAlert(alertEl, err.detail || 'Password change failed', 'danger');
    }
  });
}

const profDeleteBtn = document.getElementById('prof-delete-btn');
if (profDeleteBtn) {
  profDeleteBtn.addEventListener('click', () => {
    showCustomConfirmDelete(
      'Delete Account',
      'Are you absolutely sure you want to delete your account? This action cannot be undone.',
      async () => {
        const res = await apiFetch('/auth/profile', { method: 'DELETE' });
        if (res && res.ok) {
          showCustomAlert('Account Deleted', 'Account deleted. You will be logged out.', () => {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
          });
        } else {
          showCustomAlert('Error', 'Failed to delete account');
        }
      }
    );
  });
}

showTab("overview");

async function loadOverview() {

  console.log("Loading overview...");

  const res = await apiFetch("/admin-api/overview");

  console.log("Response:", res);

  if (!res || !res.ok) {
    console.log("Overview API failed");
    return;
  }

  const d = await res.json();

  console.log("Overview Data:", d);

  setText("a-users", d.users_count ?? 0);
  setText("a-projects", d.projects_count ?? 0);
  setText("a-files", d.files_count ?? 0);
  setText("a-reviews", d.reviews_count ?? 0);
  setText("a-chats", d.chats_count ?? 0);
  setText("a-commits", d.activities_count ?? 0);
}

async function loadUsers() {
  const tbody = document.getElementById("users-tbody");
  tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Loading…</td></tr>`;

  const res = await apiFetch("/admin-api/users");
  if (!res || !res.ok) return;
  let users = await res.json();
  
  users.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);

  tbody.innerHTML = "";
  if (!users.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No users found.</td></tr>`;
    return;
  }

  users.forEach((u, i) => {
    const displayId = isSortDesc ? users.length - i : i + 1;
    const tr = document.createElement("tr");
    const statusPill = u.role === "admin"
      ? `<span class="status-pill status-admin">Admin</span>`
      : u.is_active
        ? `<span class="status-pill status-active">Active</span>`
        : `<span class="status-pill status-disabled">Disabled</span>`;

    const actions = u.role === "admin"
      ? `<span style="color:var(--color-muted); font-size:.78rem;">—</span>`
      : `<button class="btn-table-action btn-delete"
          onclick="deleteUser(${u.id}, '${escHtml(u.username)}')">Delete</button>`;

    tr.innerHTML = `
      <td>${displayId}</td>
      <td><strong>${escHtml(u.username)}</strong></td>
      <td>${escHtml(u.email)}</td>
      <td>${escHtml(u.role)}</td>
      <td>${statusPill}</td>
      <td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</td>
      <td>${actions}</td>`;
    tbody.appendChild(tr);
  });
}

async function deleteUser(userId, username) {
  showCustomConfirmDelete(
    'Delete User',
    `Permanently delete user "${username}" and ALL their data?\n\nThis will remove:\n• All projects\n• All uploaded files\n• All reviews\n• All notifications\n• All chat messages\n• Activity logs\n\nThis CANNOT be undone.`,
    async () => {
      const res = await apiFetch(`/admin-api/users/${userId}`, { method: "DELETE" });
      if (!res || !res.ok) {
        const err = await res?.json().catch(() => ({}));
        showCustomAlert('Error', "Failed to delete user: " + (err.detail || "Unknown error"));
        return;
      }
      loadUsers();
      loadOverview();
    }
  );
}

async function loadProjects() {
  const tbody = document.getElementById("projects-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading…</td></tr>`;
  const res = await apiFetch("/admin-api/projects");
  if (!res || !res.ok) return;
  let projects = await res.json();
  projects.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);
  tbody.innerHTML = "";
  if (!projects.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No projects.</td></tr>`; return; }
  projects.forEach(p => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.id}</td>
      <td><strong>${escHtml(p.name)}</strong></td>
      <td>${escHtml(p.description || "—")}</td>
      <td>${p.owner_id}</td>
      <td>${p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}</td>
      <td><button class="btn-table-action btn-delete" onclick="deleteProject(${p.id})">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

async function loadFiles() {
  const tbody = document.getElementById("files-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading…</td></tr>`;
  const res = await apiFetch("/admin-api/files");
  if (!res || !res.ok) return;
  let files = await res.json();
  files.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);
  tbody.innerHTML = "";
  if (!files.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No files.</td></tr>`; return; }
  files.forEach(f => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${f.id}</td>
      <td>${escHtml(f.filename)}</td>
      <td>${escHtml(f.file_type)}</td>
      <td>${f.project_id}</td>
      <td>${f.uploaded_at ? new Date(f.uploaded_at).toLocaleDateString() : "—"}</td>
      <td><button class="btn-table-action btn-delete" onclick="deleteFile(${f.id})">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

async function loadReviews() {
  const tbody = document.getElementById("reviews-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading…</td></tr>`;
  const res = await apiFetch("/admin-api/reviews");
  if (!res || !res.ok) return;
  let reviews = await res.json();
  reviews.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);
  tbody.innerHTML = "";
  if (!reviews.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No reviews.</td></tr>`; return; }
  reviews.forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.project_id}</td>
      <td>${r.file_id}</td>
      <td style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escHtml(r.issues || "—")}</td>
      <td>${r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}</td>
      <td><button class="btn-table-action btn-delete" onclick="deleteReview(${r.id})">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

async function loadChats() {
  const tbody = document.getElementById("chats-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading…</td></tr>`;
  const res = await apiFetch("/admin-api/chats");
  if (!res || !res.ok) return;
  let chats = await res.json();
  chats.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);
  tbody.innerHTML = "";
  if (!chats.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No messages.</td></tr>`; return; }
  chats.forEach(c => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${c.id}</td>
      <td>${c.project_id}</td>
      <td>${escHtml(c.username || "User #" + c.sender_id)}</td>
      <td>${escHtml(c.message)}</td>
      <td>${c.created_at ? new Date(c.created_at).toLocaleString() : "—"}</td>
      <td><button class="btn-table-action btn-delete" onclick="deleteChat(${c.id})">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

async function loadActivity() {
  const tbody = document.getElementById("activity-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading…</td></tr>`;
  const res = await apiFetch("/admin-api/activity");
  if (!res || !res.ok) return;
  let activities = await res.json();
  activities.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);
  tbody.innerHTML = "";
  if (!activities.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No activity.</td></tr>`; return; }
  activities.forEach(a => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${a.id}</td>
      <td>${escHtml(a.action)}</td>
      <td>${a.project_id ?? "—"}</td>
      <td>${a.user_id ?? "—"}</td>
      <td>${a.timestamp ? new Date(a.timestamp).toLocaleString() : "—"}</td>
      <td><button class="btn-table-action btn-delete" onclick="deleteActivity(${a.id})">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

async function loadLogins() {
  const tbody = document.getElementById("logins-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading…</td></tr>`;
  const res = await apiFetch("/admin-api/login-history");
  if (!res || !res.ok) return;
  let logs = await res.json();
  logs.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);
  tbody.innerHTML = "";
  if (!logs.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No login records.</td></tr>`; return; }
  logs.forEach(l => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${l.id}</td>
      <td>${l.user_id}</td>
      <td>${escHtml(l.ip_address || "—")}</td>
      <td style="max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escHtml(l.user_agent || "—")}</td>
      <td>${l.created_at ? new Date(l.created_at).toLocaleString() : "—"}</td>
      <td><button class="btn-table-action btn-delete" onclick="deleteLogin(${l.id})">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

async function loadAdminLogs() {
  const tbody = document.getElementById("logs-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading…</td></tr>`;
  const res = await apiFetch("/admin-api/logs");
  if (!res || !res.ok) return;
  let logs = await res.json();
  logs.sort((a, b) => isSortDesc ? b.id - a.id : a.id - b.id);
  tbody.innerHTML = "";
  if (!logs.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No admin actions yet.</td></tr>`; return; }
  logs.forEach(l => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${l.id}</td>
      <td>${escHtml(l.action)}</td>
      <td>${l.target_id ?? "—"}</td>
      <td>${escHtml(l.detail || "—")}</td>
      <td>${l.created_at ? new Date(l.created_at).toLocaleString() : "—"}</td>
      <td><button class="btn-table-action btn-delete" onclick="deleteLog(${l.id})">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

async function performDelete(url, loadFn, name) {
  showCustomConfirmDelete("Delete Confirmation", `Permanently delete this ${name}? This cannot be undone.`, async () => {
    const res = await apiFetch(url, { method: "DELETE" });
    if (!res || !res.ok) {
      const err = await res?.json().catch(() => ({}));
      showCustomAlert("Error", `Failed to delete ${name}: ` + (err.detail || "Unknown error"));
      return;
    }
    loadFn();
    loadOverview();
  });
}

async function deleteProject(id) { await performDelete(`/admin-api/projects/${id}`, loadProjects, "project"); }
async function deleteFile(id) { await performDelete(`/admin-api/files/${id}`, loadFiles, "file"); }
async function deleteReview(id) { await performDelete(`/admin-api/reviews/${id}`, loadReviews, "review"); }
async function deleteChat(id) { await performDelete(`/admin-api/chats/${id}`, loadChats, "chat message"); }
async function deleteActivity(id) { await performDelete(`/admin-api/activity/${id}`, loadActivity, "activity record"); }
async function deleteLogin(id) { await performDelete(`/admin-api/login-history/${id}`, loadLogins, "login record"); }
async function deleteLog(id) { await performDelete(`/admin-api/logs/${id}`, loadAdminLogs, "admin log"); }

function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

showTab("overview");

if (currentUser && currentUser.username) { const adminProfileSpan = document.querySelector('#admin-profile-btn .user-name'); if (adminProfileSpan) adminProfileSpan.textContent = currentUser.username; const adminProfileAvatar = document.querySelector('#admin-profile-btn .user-avatar'); if (adminProfileAvatar) adminProfileAvatar.textContent = currentUser.username.charAt(0).toUpperCase(); }

