const API   = "http://127.0.0.1:8000";
const token = localStorage.getItem("token");
if (!token) { 
  window.location.href = "/login"; 
}

let currentUser = null;
try { currentUser = JSON.parse(localStorage.getItem("user")); } catch (_) {}

async function api(path, opts = {}) {
  try {
    const res = await fetch(API + path, {
      ...opts,
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
        ...(opts.headers || {})
      }
    });
    if (res.status === 401) {
      localStorage.clear();
      window.location.href = "/login";
      return null;
    }
    return res;
  } catch (e) {
    console.error("Network error:", path, e);
    return null;
  }
}

function esc(s) {
  if (s == null) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function el(id) { return document.getElementById(id); }
function setText(id, v) { const e = el(id); if (e) e.textContent = v; }
function showAlert(e, msg, type) { if (e) { e.textContent = msg; e.className = "form-alert alert-" + type; e.style.display = "block"; } }
function hideAlert(e) { if (e) { e.style.display = "none"; e.textContent = ""; } }

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
  msgEl.style.cssText = "font-size: 0.9rem; color: var(--color-muted, #64748b); line-height: 1.5; margin-bottom: 24px;";
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

function showCustomConfirm(title, message, onConfirm, onCancel) {
  showCustomModal({
    title,
    message,
    buttons: [
      { text: "Cancel", type: "ghost", onClick: onCancel },
      { text: "Continue", type: "danger", onClick: onConfirm }
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

function initUser() {
  if (!currentUser) return;
  setText("user-name",    currentUser.username || "User");
  setText("user-avatar",  (currentUser.username || "U")[0].toUpperCase());
  setText("welcome-title", "Welcome back, " + currentUser.username + "!");
  setText("welcome-sub",   "Logged in as " + (currentUser.role || "user"));
  if (currentUser.role === "admin") {
    const lnk = el("admin-nav-link");
    if (lnk) lnk.style.display = "inline-flex";
  }
}

function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    showCustomAlert("Logged Out", "Logged out successfully", () => {
      window.location.href = "/login";
    });
}

const sidebar     = el("sidebar");
const mainContent = document.querySelector(".main-content");

el("sidebar-toggle").addEventListener("click", () => {
  if (window.innerWidth <= 700) {
    sidebar.classList.toggle("open");
  } else {
    sidebar.classList.toggle("collapsed");
    mainContent.classList.toggle("expanded");
  }
});

let socket = null;
let chatProjectId = null;

function initSocket() {
  if (typeof io === "undefined") return;
  socket = io(API, { 
    transports: ["websocket", "polling"],
    auth: { token: token } 
  });

  socket.on("connect", () => {
    if (currentUser?.user_id) socket.emit("join_user_room", { user_id: currentUser.user_id });
    if (activeProjectId) socket.emit("join_project", {
      project_id: activeProjectId,
      username:   currentUser?.username,
      user_id:    currentUser?.user_id
    });
  });

  socket.on("notification", d => {
    if (!notifs.find(n => n.msg === (d.message || "New notification"))) {
      addNotif(d.message || "New notification");
    }
  });

  socket.on("activity_update", d => {
    const collabPid = document.getElementById("collab-page-project-select")?.value;
    if (collabPid && String(d.project_id) === String(collabPid)) {
      loadActivity(collabPid);
    }
    if (String(d.project_id) === String(activeProjectId)) {
      loadActivity(activeProjectId);
    }
  });

  socket.on("comment_added", d => {
    const collabPid = document.getElementById("collab-page-project-select")?.value;
    if (collabPid && String(d.project_id) === String(collabPid)) {
      loadGlobalComments(collabPid);
    }
    if (typeof loadFileComments === 'function' && window.currentFileId && String(d.file_id) === String(window.currentFileId)) {
      loadFileComments(d.file_id);
    }
  });

  socket.on("force_logout", d => {
    showCustomAlert("System Alert", d.message || "Your session has been invalidated.", () => {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    });
  });

  socket.on("chat_message", d => {
    if (String(d.project_id) === String(chatProjectId)) addChatBubble(d);
    if (currentUser && d.sender_id !== currentUser.user_id) {
       addNotif(`New message from ${d.username || "User"} in project`);
    }
  });

  socket.on("typing", d => {
    if (String(d.project_id) !== String(chatProjectId)) return;
    const typingEl = el("chat-typing-indicator");
    if (!typingEl) return;
    if (d.typing) {
      typingEl.textContent = `${esc(d.username)} is typing…`;
      typingEl.style.display = "block";
    } else {
      typingEl.style.display = "none";
      typingEl.textContent = "";
    }
  });

  socket.on("user_joined", d => {
    if (String(d.project_id) !== String(chatProjectId)) return;
    const box = el("chat-messages");
    if (box) {
      const key = `join-${d.username}`;
      if (!box.querySelector(`[data-event="${key}"]`)) {
        const div = document.createElement("div");
        div.className = "chat-system-msg";
        div.dataset.event = key;
        div.textContent = `${d.username} joined the room`;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
        setTimeout(() => div.remove(), 8000);
      }
    }
  });

  socket.on("user_left", d => {
    if (String(d.project_id) !== String(chatProjectId)) return;
    const box = el("chat-messages");
    if (box) {
      const key = `leave-${d.username}`;
      if (!box.querySelector(`[data-event="${key}"]`)) {
        const div = document.createElement("div");
        div.className = "chat-system-msg";
        div.dataset.event = key;
        div.textContent = `${d.username} left the room`;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
        setTimeout(() => div.remove(), 8000);
      }
    }
  });
}

let notifs = [];

function addNotif(msg) {
  notifs.unshift({ msg, time: new Date().toLocaleTimeString(), read: false });
  renderNotifs();
}

function renderNotifs() {
  const list  = el("notif-list");
  const badge = el("notif-badge");
  const unread = notifs.filter(n => !n.read).length;
  if (badge) { badge.textContent = unread > 9 ? "9+" : unread; badge.style.display = unread ? "flex" : "none"; }
  if (!list) return;
  list.innerHTML = "";
  if (!notifs.length) { list.innerHTML = "<p class='notif-empty'>No new notifications</p>"; return; }
  notifs.slice(0, 15).forEach(n => {
    const d = document.createElement("div");
    d.className = "notif-row" + (n.read ? " read" : "");
    d.innerHTML = `<div class="notif-dot"></div><div><div class="notif-msg">${esc(n.msg)}</div><div class="notif-time">${n.time}</div></div>`;
    list.appendChild(d);
  });
}

el("notif-bell-btn").addEventListener("click", e => {
  e.stopPropagation();
  const panel = el("notif-dropdown");
  const open  = panel.style.display !== "none";
  panel.style.display = open ? "none" : "block";
  if (!open) { notifs.forEach(n => n.read = true); renderNotifs(); }
});

el("notif-clear-btn").addEventListener("click", () => { notifs = []; renderNotifs(); });

document.addEventListener("click", e => {
  const wrap = el("notif-wrap");
  if (wrap && !wrap.contains(e.target)) {
    const p = el("notif-dropdown");
    if (p) p.style.display = "none";
  }
});

const navItems = document.querySelectorAll(".nav-item");
const sections = document.querySelectorAll(".section");

function showSection(name) {
  sections.forEach(s => s.classList.remove("active"));
  navItems.forEach(n => n.classList.remove("active"));
  document.querySelectorAll(".sidebar-project-link").forEach(l => l.classList.remove("active"));

  const sec = el("section-" + name);
  if (sec) sec.classList.add("active");
  const nav = document.querySelector(`.nav-item[data-section="${name}"]`);
  if (nav) nav.classList.add("active");

  if (name === "dashboard")      loadOverview();
  if (name === "projects")       loadProjects();
  if (name === "reviews")        loadReviewProjectSelect();
  if (name === "collaboration")  loadCollaborationPage();
  if (name === "chats")          { fillProjectSelects(); }
  if (name === "version")        loadVersionProjectSelect();
  if (name === "analytics")      loadAnalytics();
  if (name === "profile")        loadProfile();
}

const userProfileBtn = el("user-profile-btn");
if (userProfileBtn) {
  userProfileBtn.addEventListener("click", () => showSection("profile"));
}

navItems.forEach(item => {
  item.addEventListener("click", e => {
    e.preventDefault();
    showSection(item.dataset.section);
    if (window.innerWidth <= 700) sidebar.classList.remove("open");
  });
});

async function loadOverview() {
  loadInvitations();
  const res = await api("/dashboard-api/overview");
  if (!res || !res.ok) return;
  const d = await res.json();
  setText("stat-users",    d.total_users                      ?? "0");
  setText("stat-projects", d.projects                         ?? "0");
  setText("stat-files",    d.files                            ?? "0");
  setText("stat-reviews",  d.review_summary?.total_reviews    ?? "0");
  setText("stat-commits",  d.commits                          ?? "0");
  setText("stat-chats",    d.chat_messages                    ?? "0");
  setText("stat-loc",      d.lines_of_code                    ?? "0");
  
  const ownerSection = el("owner-dashboard-projects");
  const tbody = el("owner-projects-tbody");
  
  if (d.owned_projects_details && d.owned_projects_details.length > 0) {
    if (ownerSection) ownerSection.style.display = "block";
    if (tbody) {
      tbody.innerHTML = "";
      d.owned_projects_details.forEach(p => {
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid var(--color-border)";
        
        let dateStr = "";
        if (p.created_at) {
          dateStr = new Date(p.created_at).toLocaleDateString();
        }
        
        tr.innerHTML = `
          <td style="padding: 12px 16px; font-size: 0.9rem; font-weight: 500;">${esc(p.name)}</td>
          <td style="padding: 12px 16px; font-size: 0.85rem; color: var(--color-muted);">${dateStr}</td>
          <td style="padding: 12px 16px; font-size: 0.85rem; color: var(--color-muted);">${p.files_count}</td>
          <td style="padding: 12px 16px; font-size: 0.85rem; color: var(--color-muted);">${p.reviews_count}</td>
          <td style="padding: 12px 16px; font-size: 0.85rem; color: var(--color-muted);">${p.collaborators_count}</td>
          <td style="padding: 12px 16px; font-size: 0.85rem; color: var(--color-muted);">${esc(p.latest_activity)}</td>
        `;
        tbody.appendChild(tr);
      });
    }
  } else {
    if (ownerSection) ownerSection.style.display = "none";
  }
}

async function loadInvitations() {
  const res = await api("/collab-api/invitations");
  if (!res || !res.ok) return;
  const invites = await res.json();
  const container = el("invitations-container");
  const list = el("invitations-list");
  if (!container || !list) return;
  
  if (!invites.length) {
    container.style.display = "none";
    return;
  }
  
  container.style.display = "block";
  list.innerHTML = "";
  invites.forEach(inv => {
    const d = document.createElement("div");
    d.style.cssText = "display:flex; justify-content:space-between; align-items:center; background:var(--color-bg); padding:12px; border:1px solid var(--color-border); border-radius:var(--radius-sm);";
    d.innerHTML = `
      <div>
        <strong>${esc(inv.project_name)}</strong>
        <div style="font-size:0.85rem; color:var(--color-muted);">Invited by Project Owner</div>
      </div>
      <div style="display:flex; gap:8px;">
        <button class="btn-primary btn-sm accept-btn">Accept</button>
        <button class="btn-danger btn-sm reject-btn">Reject</button>
      </div>
    `;
    d.querySelector(".accept-btn").addEventListener("click", async () => {
      const r = await api("/collab-api/invitations/" + inv.id + "/accept", { method: "POST" });
      if (r && r.ok) {
        showCustomAlert("Success", "Invitation accepted!");
        loadOverview();
        loadProjects();
      } else {
        showCustomAlert("Error", "Failed to accept");
      }
    });
    d.querySelector(".reject-btn").addEventListener("click", async () => {
      const r = await api("/collab-api/invitations/" + inv.id + "/reject", { method: "POST" });
      if (r && r.ok) {
        showCustomAlert("Success", "Invitation rejected.");
        loadOverview();
      } else {
        showCustomAlert("Error", "Failed to reject");
      }
    });
    list.appendChild(d);
  });
}

let projectList = [];
let _projectsCache = { owned: [], invited: [] };
let activeProjectId = null;

async function fetchProjects() {
  const res = await api("/projects/my-projects");
  if (!res || !res.ok) return { owned: [], invited: [] };
  return await res.json();
}

async function loadProjects() {
  const ownedEl = el("project-list-owned");
  const invitedEl = el("project-list-invited");
  
  if (ownedEl) ownedEl.innerHTML = "<div class='empty-state'>Loading…</div>";
  if (invitedEl) invitedEl.innerHTML = "<div class='empty-state'>Loading…</div>";

  const projects = await fetchProjects();
  _projectsCache = projects;
  projectList = (projects.owned || []).concat(projects.invited || []);
  
  fillProjectSelects(projects);
  buildSidebarLinks();

  if (ownedEl) {
    ownedEl.innerHTML = "";
    if (projects.owned?.length) {
      projects.owned.forEach(p => ownedEl.appendChild(makeProjectCard(p, false)));
    } else {
      ownedEl.innerHTML = "<div class='empty-state'>No owned projects.</div>";
    }
  }
  
  if (invitedEl) {
    invitedEl.innerHTML = "";
    if (projects.invited?.length) {
      projects.invited.forEach(p => invitedEl.appendChild(makeProjectCard(p, true)));
    } else {
      invitedEl.innerHTML = "<div class='empty-state'>No invited projects.</div>";
    }
  }
}

document.querySelectorAll(".ws-tab-btn[data-projtab]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ws-tab-btn[data-projtab]").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    
    document.querySelectorAll(".proj-panel").forEach(p => p.style.display = "none");
    const target = document.getElementById("projects-" + btn.dataset.projtab + "-panel");
    if (target) {
      target.style.display = "block";
    }
  });
});

document.querySelectorAll(".ws-tab-btn[data-wstab]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ws-tab-btn[data-wstab]").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    
    document.querySelectorAll(".ws-panel").forEach(p => p.classList.remove("active"));
    const target = document.getElementById("wsp-" + btn.dataset.wstab);
    if (target) {
      target.classList.add("active");
    }
  });
});

function makeProjectCard(p, isInvited) {
  const card = document.createElement("div");
  card.className = "project-card";
  const date = p.created_at ? new Date(p.created_at).toLocaleDateString() : "";
  card.innerHTML = `
    <div class="project-card-header">
      <h4>${esc(p.name)}</h4>
      <div class="kebab-menu">
        <button class="kebab-btn">&#8942;</button>
        <div class="kebab-dropdown">
          <button class="kebab-option" data-act="open">Open</button>
          ${!isInvited ? '<button class="kebab-option danger" data-act="delete">Delete</button>' : ''}
        </div>
      </div>
    </div>
    <p>${esc(p.description || "No description.")}</p>
    ${isInvited ? `<div style="margin-top:6px; font-size:0.75rem; color:var(--color-muted);">Owner: ${esc(p.owner_name)} &middot; Role: ${esc(p.role)}</div>` : ""}
    ${date ? `<div class="project-date">Created ${date}</div>` : ""}
    <button class="btn-open-project">Open Project &rarr;</button>`;

  const kebabBtn  = card.querySelector(".kebab-btn");
  const kebabDrop = card.querySelector(".kebab-dropdown");
  kebabBtn.addEventListener("click", e => { e.stopPropagation(); closeKebabs(); kebabDrop.classList.toggle("open"); });
  card.querySelectorAll("[data-act='open']").forEach(b => b.addEventListener("click", e => { e.stopPropagation(); closeKebabs(); openWorkspace(p); }));
  
  if (!isInvited) {
    card.querySelector("[data-act='delete']").addEventListener("click", e => { e.stopPropagation(); closeKebabs(); confirmDelete(p); });
  }
  
  card.querySelector(".btn-open-project").addEventListener("click", () => openWorkspace(p));
  return card;
}

function closeKebabs() { document.querySelectorAll(".kebab-dropdown.open").forEach(d => d.classList.remove("open")); }
document.addEventListener("click", closeKebabs);

function buildSidebarLinks() {
  const c = el("sidebar-project-links");
  if (!c) return;
  c.innerHTML = "";
  projectList.forEach(p => {
    const a = document.createElement("a");
    a.href = "#";
    a.className = "sidebar-project-link";
    a.textContent = p.name;
    a.dataset.projectId = p.id;
    a.addEventListener("click", e => { e.preventDefault(); openWorkspace(p); });
    c.appendChild(a);
  });
}

function fillProjectSelects(projectsObj) {

  if (!projectsObj || typeof projectsObj !== "object" || Array.isArray(projectsObj)) {
    projectsObj = _projectsCache;
  }

  const allProjects = [...(projectsObj.owned || []), ...(projectsObj.invited || [])];

  ["review-project-select","chat-project-select","version-project-select","collab-page-project-select","analytics-project-select"].forEach(id => {
    const sel = el(id);
    if (!sel) return;
    const cur = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    allProjects.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name + " (ID:" + p.id + ")";
      sel.appendChild(opt);
    });
    if (cur) sel.value = cur;
  });

  fillReviewHistoryFilter();
}

const chatBtn = el("btn-open-chat-room");
if (chatBtn) {
  chatBtn.addEventListener("click", () => {
    const pId = el("chat-project-select").value;
    if (!pId) { showCustomAlert("Chat", "Please select a project first."); return; }
    window.location.href = `/project/${pId}/chat`;
  });
}

const createModal = el("create-project-modal");
const projForm    = el("project-form");
const projAlert   = el("proj-alert");

el("open-create-modal-btn").addEventListener("click", () => { projForm.reset(); hideAlert(projAlert); createModal.style.display = "flex"; });
el("modal-close-btn").addEventListener("click",  () => createModal.style.display = "none");
el("modal-cancel-btn").addEventListener("click", () => createModal.style.display = "none");
createModal.addEventListener("click", e => { if (e.target === createModal) createModal.style.display = "none"; });

projForm.addEventListener("submit", async e => {
  e.preventDefault();
  hideAlert(projAlert);
  const name = el("proj-name").value.trim();
  const desc = el("proj-desc").value.trim();
  const github_token = "";
  if (!name) { showAlert(projAlert, "Project name is required.", "error"); return; }
  const res = await api("/projects/create", { method: "POST", body: JSON.stringify({ name, description: desc, github_token }) });
  if (!res || !res.ok) { const err = await res?.json(); showAlert(projAlert, err?.detail || "Failed.", "error"); return; }
  showAlert(projAlert, "Project created!", "success");
  setTimeout(() => { createModal.style.display = "none"; loadProjects(); }, 800);
});

const deleteModal = el("delete-confirm-modal");
let pendingDel = null;

function confirmDelete(p) { pendingDel = p; setText("delete-project-name", p.name); deleteModal.style.display = "flex"; }
function closeDeleteModal() { deleteModal.style.display = "none"; pendingDel = null; }

el("delete-modal-close-btn").addEventListener("click", closeDeleteModal);
el("cancel-delete-btn").addEventListener("click",      closeDeleteModal);
deleteModal.addEventListener("click", e => { if (e.target === deleteModal) closeDeleteModal(); });

el("confirm-delete-btn").addEventListener("click", async () => {
  if (!pendingDel) return;
  const p = pendingDel; closeDeleteModal();
  const res = await api("/projects/" + p.id, { method: "DELETE" });
  if (!res || !res.ok) { showCustomAlert("Error", "Failed to delete project."); return; }
  loadProjects();
});
 
function openWorkspace(p) {
  activeProjectId = p.id;
                          
  document.querySelectorAll(".sidebar-project-link").forEach(l =>
    l.classList.toggle("active", parseInt(l.dataset.projectId) === p.id)
  );
  navItems.forEach(n => n.classList.remove("active"));
  sections.forEach(s => s.classList.remove("active"));
  
  const ws = el("section-workspace");
  if (ws) ws.classList.add("active");

  setText("workspace-project-name", p.name);
  setText("workspace-project-desc", p.description || "");
  
  const ghBtn = document.getElementById("workspace-github-btn");
  if (ghBtn) {
    ghBtn.style.display = "inline-block";
    ghBtn.onclick = () => {
      if (p.github_repo_url) {
        window.open("https://github.com/" + p.github_repo_url, "_blank");
      } else {
        showCustomAlert("GitHub", "This project is not connected to a GitHub repository.");
      }
    };
  }

  loadFiles(p.id);
  loadActivity(p.id);
  repoFolders = [];
  loadRepoBrowser();

  if (socket?.connected) {
    socket.emit("join_project", {
      project_id: p.id,
      username:   currentUser?.username,
      user_id:    currentUser?.user_id
    });
  }
}

el("back-to-projects-btn").addEventListener("click", () => showSection("projects"));

function switchTab(name) {

}

async function loadFiles(projectId) {
  const listEl = el("workspace-files-list");
  listEl.innerHTML = "<div class='empty-state'>Loading…</div>";
  const res = await api("/projects/" + projectId + "/files");
  if (!res || !res.ok) { listEl.innerHTML = "<div class='empty-state'>Failed to load.</div>"; return; }
  const files = await res.json();
  listEl.innerHTML = "";
  if (!files.length) { listEl.innerHTML = "<div class='empty-state'>No files yet.</div>"; return; }
  files.forEach(f => {
    const row = document.createElement("div");
    row.className = "ws-file-item";
    row.innerHTML = `<div><div class="ws-file-name">${esc(f.filename)}</div><div class="ws-file-meta">${esc(f.file_type)} · ID: ${f.id} · Folder: ${esc(f.folder || "/")}</div></div>`;
    listEl.appendChild(row);
  });
}

el("upload-form").addEventListener("submit", async e => {
  e.preventDefault();
  if (!activeProjectId) return;
  const fileInput = el("code-file");
  const alertEl   = el("upload-alert");
  const file = fileInput.files[0];
  if (!file) { showAlert(alertEl, "Choose a file first.", "error"); return; }
  hideAlert(alertEl);
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API}/projects/upload/${activeProjectId}`, {
    method: "POST",
    headers: { "Authorization": "Bearer " + token },
    body: fd
  });
  if (!res) { showAlert(alertEl, "Server unreachable.", "error"); return; }
  const data = await res.json();
  if (!res.ok) { showAlert(alertEl, data.detail || "Upload failed.", "error"); return; }
  let successMsg = (data.filename || "File") + " uploaded.";
  if (data.pinecone_stored) {
    successMsg += ` Vector stored successfully (${data.vector_count} chunks).`;
  }
  showAlert(alertEl, successMsg, "success");
  fileInput.value = "";
  loadFiles(activeProjectId);
  loadActivity(activeProjectId);
});

async function loadActivity(projectId) {
  const listEl = el("project-updates-list");
  const collabListEl = el("workspace-activity-list");
  
  if (listEl) listEl.innerHTML = "<div class='empty-state'>Loading…</div>";
  if (collabListEl) collabListEl.innerHTML = "<div class='empty-state'>Loading…</div>";
  
  const res = await api("/projects/" + projectId + "/activities");
  if (!res || !res.ok) {
    if (listEl) listEl.innerHTML = "<div class='empty-state'>Failed to load.</div>";
    if (collabListEl) collabListEl.innerHTML = "<div class='empty-state'>Failed to load.</div>";
    return;
  }
  
  const items = await res.json();
  if (listEl) listEl.innerHTML = "";
  if (collabListEl) collabListEl.innerHTML = "";
  
  if (!items.length) {
    if (listEl) listEl.innerHTML = "<div class='empty-state'>No activity yet.</div>";
    if (collabListEl) collabListEl.innerHTML = "<div class='empty-state'>No activity yet.</div>";
    return;
  }
  
  [...items].reverse().forEach(a => {
    const t = a.timestamp ? new Date(a.timestamp).toLocaleString() : "";
    const html = `<div class="timeline-icon">&#128196;</div><div class="timeline-content"><div class="timeline-action">${esc(a.action)}</div><div class="timeline-time">${esc(a.username || a.user_id)} &middot; ${t}</div></div>`;
    
    if (listEl) {
      const d1 = document.createElement("div");
      d1.className = "timeline-item";
      d1.innerHTML = html;
      listEl.appendChild(d1);
    }
    
    if (collabListEl) {
      const d2 = document.createElement("div");
      d2.className = "timeline-item";
      d2.innerHTML = html;
      collabListEl.appendChild(d2);
    }
  });
}

let repoCurrentPath = "/";
let repoFolders     = [];

let _fileViewerScrollY = 0;  

el("repo-upload-btn").addEventListener("click", () => {
  el("repo-upload-form-wrap").style.display = "block";
  el("repo-folder-form-wrap").style.display = "none";
});
el("repo-upload-cancel").addEventListener("click", () => {
  el("repo-upload-form-wrap").style.display = "none";
});

el("repo-new-folder-btn").addEventListener("click", () => {
  el("repo-folder-form-wrap").style.display = "block";
  el("repo-upload-form-wrap").style.display = "none";
});
el("repo-folder-cancel").addEventListener("click", () => {
  el("repo-folder-form-wrap").style.display = "none";
});

el("repo-root-btn").addEventListener("click", () => {
  repoCurrentPath = "/";
  loadRepoBrowser();
});

el("repo-upload-form").addEventListener("submit", async e => {
  e.preventDefault();
  if (!activeProjectId) return;
  const alertEl = el("repo-upload-alert");
  const fileInput = el("repo-file-input");
  const folder    = el("repo-upload-folder").value || "/";
  const file      = fileInput.files[0];
  if (!file) { showAlert(alertEl, "Choose a file.", "error"); return; }
  hideAlert(alertEl);
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API}/projects/upload/${activeProjectId}?folder=${encodeURIComponent(folder)}`, {
    method: "POST",
    headers: { "Authorization": "Bearer " + token },
    body: fd
  });
  if (!res) { showAlert(alertEl, "Server unreachable.", "error"); return; }
  const data = await res.json();
  if (!res.ok) { showAlert(alertEl, data.detail || "Upload failed.", "error"); return; }
  let successMsg = (data.filename || "File") + " uploaded.";
  if (data.pinecone_stored) {
    successMsg += ` Vector stored successfully (${data.vector_count} chunks).`;
  }
  showAlert(alertEl, successMsg, "success");
  fileInput.value = "";
  el("repo-upload-form-wrap").style.display = "none";
  repoCurrentPath = folder;
  await loadRepoBrowser();
  loadFiles(activeProjectId);
});

el("repo-folder-form").addEventListener("submit", async e => {
  e.preventDefault();
  if (!activeProjectId) return;
  const alertEl = el("repo-folder-alert");
  const name    = el("repo-folder-name").value.trim();
  const parent  = el("repo-folder-parent").value || "/";
  if (!name) { showAlert(alertEl, "Enter a folder name.", "error"); return; }
  hideAlert(alertEl);
  const res = await api("/projects/" + activeProjectId + "/folders", {
    method: "POST",
    body: JSON.stringify({ name, parent })
  });
  if (!res || !res.ok) { showAlert(alertEl, "Failed to create folder.", "error"); return; }
  showAlert(alertEl, "Folder '" + name + "' created.", "success");
  el("repo-folder-name").value = "";
  el("repo-folder-form-wrap").style.display = "none";
  await loadRepoFolders();
  loadRepoBrowser();
});

async function loadRepoFolders() {
  if (!activeProjectId) return;
  const res = await api("/projects/" + activeProjectId + "/folders");
  if (!res || !res.ok) return;
  repoFolders = await res.json();
  refreshFolderDropdowns();
}

function refreshFolderDropdowns() {
  ["repo-upload-folder", "repo-folder-parent"].forEach(id => {
    const sel = el(id);
    if (!sel) return;
    sel.innerHTML = "<option value='/'>/ root</option>";
    repoFolders.forEach(f => {
      const path = f.parent === "/" ? "/" + f.name : f.parent + "/" + f.name;
      const opt  = document.createElement("option");
      opt.value = path;
      opt.textContent = path;
      sel.appendChild(opt);
    });
  });
}

async function openFileViewer(fileId) {
  _fileViewerScrollY = window.scrollY;
  const browser = el("repo-browser-wrap");
  const viewer  = el("repo-file-viewer");
  if (browser) browser.style.display = "none";
  if (!viewer) return;
  viewer.style.display = "block";
  viewer.innerHTML = `<div class='empty-state'>Loading file…</div>`;

  const res = await api("/projects/files/" + fileId + "/content");
  if (!res || !res.ok) {
    viewer.innerHTML = "<div class='empty-state'>Could not load file.</div>";
    return;
  }
  const f = await res.json();

  const langMap = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".java": "java", ".cpp": "cpp", ".c": "c",
    ".html": "html", ".css": "css", ".json": "json", ".txt": "plaintext",
    ".cs": "csharp"
  };
  const lang = langMap[f.file_type] || "plaintext";
  const date = f.uploaded_at ? new Date(f.uploaded_at).toLocaleString() : "Unknown";

  viewer.innerHTML = `
    <div class="file-viewer-header">
      <button class="btn-back" id="file-viewer-back-btn">&#8592; Back to Files</button>
      <div class="file-viewer-meta">
        <span class="fv-name">&#128196; ${esc(f.filename)}</span>
        <span class="fv-badge">${esc(f.file_type)}</span>
        <span class="fv-info" id="fv-line-count">${f.lines} lines &middot; Uploaded ${date}</span>
      </div>
      <div style="margin-left:auto; display:flex; gap:8px; align-items:center;">
        <span id="fv-save-status" style="font-size:.75rem; color:var(--color-muted);"></span>
        <button class="btn-primary btn-sm" id="fv-save-btn" style="width:auto;">&#128190; Save Changes</button>
      </div>
    </div>

    <div class="file-viewer-body">
      <textarea id="fv-editor" class="fv-editor" spellcheck="false">${esc(f.content)}</textarea>
    </div>

    <div class="fv-comments-section">
      <div class="fv-comments-header">&#128172; Collaborative Comments</div>
      <div id="fv-comments-list" class="fv-comments-list">
        <div class="empty-state">Loading comments…</div>
      </div>
      <form id="fv-comment-form" class="fv-comment-form">
        <input type="text" id="fv-comment-input" placeholder="Add a comment on this file…" autocomplete="off" />
        <button type="submit" class="btn-primary btn-sm" style="width:auto;">Post</button>
      </form>
    </div>`;

  window.currentFileId = fileId;

  const saveBtn    = el("fv-save-btn");
  const saveStatus = el("fv-save-status");

  saveBtn.addEventListener("click", async () => {
    const content = el("fv-editor").value;
    const isChanged = (f.content !== content);
    
    saveStatus.textContent = "Saving…";
    saveStatus.style.color = "var(--color-muted)";

    const r = await api("/projects/files/" + fileId + "/content", {
      method: "PUT",
      body:   JSON.stringify({ content })
    });

    if (r && r.ok) {
      const d = await r.json();
      f.content = content; 

      saveStatus.textContent = "Saved ✓";
      saveStatus.style.color = "var(--color-muted)";
      setText("fv-line-count", d.lines + " lines");

      const cfId = el("commit-file-id");
      if (cfId) cfId.value = fileId;

      setTimeout(() => { saveStatus.textContent = ""; }, 3000);

      if (activeProjectId) loadActivity(activeProjectId);

      if (isChanged) {
        showSection("reviews");
        const sel = el("review-project-select");
        if (sel) sel.value = activeProjectId;
        
        const fViewer = el("repo-file-viewer");
        if (fViewer) fViewer.style.display = "none";
        window.currentFileId = null;
        const pBrowser = el("repo-browser-wrap");
        if (pBrowser) pBrowser.style.display = "block";
        
        runReview(fileId, f.filename, f.file_path, content);
      }

    } else {
      saveStatus.textContent = "Save failed ✗";
      saveStatus.style.color = "var(--color-danger)";
    }
  });

  el("file-viewer-back-btn").addEventListener("click", () => {
    viewer.style.display = "none";
    window.currentFileId = null;
    if (browser) browser.style.display = "block";
    window.scrollTo(0, _fileViewerScrollY);
  });

  loadFileComments(fileId, f.project_id);

  el("fv-comment-form").addEventListener("submit", async e => {
    e.preventDefault();
    const txt = el("fv-comment-input").value.trim();
    if (!txt) return;
    el("fv-comment-input").value = "";
    const r = await api("/collaboration/comment", {
      method: "POST",
      body:   JSON.stringify({ project_id: f.project_id, file_id: fileId, comment: txt })
    });
    if (r && r.ok) loadFileComments(fileId, f.project_id);
  });
}

async function loadFileComments(fileId, projectId) {
  const listEl = el("fv-comments-list");
  if (!listEl) return;
  const res = await api("/collaboration/comments/" + fileId);
  if (!res || !res.ok) { listEl.innerHTML = "<div class='empty-state'>Failed to load comments.</div>"; return; }
  const comments = await res.json();
  listEl.innerHTML = "";
  if (!comments.length) {
    listEl.innerHTML = "<div class='empty-state'>No comments yet. Be the first to comment.</div>";
    return;
  }
  comments.forEach(c => {
    const d   = document.createElement("div");
    d.className = "fv-comment-item";
    const ts  = c.timestamp ? new Date(c.timestamp).toLocaleString() : "";
    const isMe = currentUser && c.user_id === currentUser.user_id;
    d.innerHTML = `
      <div class="fv-comment-meta">
        <span class="fv-comment-user ${isMe ? "fv-comment-me" : ""}">${esc(c.username)}</span>
        <span class="fv-comment-time">${ts}</span>
      </div>
      <div class="fv-comment-body">${esc(c.comment)}</div>`;
    listEl.appendChild(d);
  });
}

async function loadRepoBrowser() {
  if (!activeProjectId) return;
  await loadRepoFolders();

  const viewer  = el("repo-file-viewer");
  const browser = el("repo-browser-wrap");
  if (viewer) viewer.style.display = "none";
  if (browser) browser.style.display = "block";

  setText("repo-current-path", repoCurrentPath);

  const folderDiv = el("repo-folder-list");
  const fileDiv   = el("repo-file-list");
  const emptyEl   = el("repo-empty");
  if (folderDiv) folderDiv.innerHTML = "";
  if (fileDiv)   fileDiv.innerHTML   = "";

  const subFolders = repoFolders.filter(f => f.parent === repoCurrentPath);

  const res   = await api("/projects/" + activeProjectId + "/files?folder=" + encodeURIComponent(repoCurrentPath));
  const files = (res && res.ok) ? await res.json() : [];

  if (emptyEl) emptyEl.style.display = (subFolders.length === 0 && files.length === 0) ? "block" : "none";

  subFolders.forEach(f => {
    const folderPath = repoCurrentPath === "/" ? "/" + f.name : repoCurrentPath + "/" + f.name;
    const row = document.createElement("div");
    row.className = "repo-item folder";
    row.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; flex:1;">
        <span>&#128193;</span>
        <div>
          <div class="repo-item-name">${esc(f.name)}</div>
        </div>
      </div>
      <div class="repo-item-actions">
        <button class="repo-act-btn repo-act-del" title="Delete folder">&#128465;</button>
      </div>`;
    row.querySelector(".repo-item-name").addEventListener("click", () => {
      repoCurrentPath = folderPath;
      loadRepoBrowser();
    });
    row.querySelector(".repo-act-del").addEventListener("click", async () => {
      showCustomConfirmDelete("Delete Folder", 'Delete folder "' + f.name + '"?', async () => {
        const r = await api("/projects/folders/" + f.id, { method: "DELETE" });
        if (r && r.ok) loadRepoBrowser();
        else showCustomAlert("Error", "Delete failed.");
      });
    });
    if (folderDiv) folderDiv.appendChild(row);
  });

  files.forEach(f => {
    const row = document.createElement("div");
    row.className = "repo-item";
    row.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; flex:1;">
        <span>&#128196;</span>
        <div>
          <div class="repo-item-name repo-file-link" title="Click to view file">${esc(f.filename)}</div>
          <div class="repo-item-meta">${esc(f.file_type)} &middot; ID: ${f.id}</div>
        </div>
      </div>
      <div class="repo-item-actions">
        <button class="repo-act-btn" title="View">&#128065;</button>
        <button class="repo-act-btn" title="Rename">&#9998;</button>
        <button class="repo-act-btn" title="Move">&#8645;</button>
        <button class="repo-act-btn repo-act-del" title="Delete">&#128465;</button>
      </div>`;

    row.querySelector(".repo-file-link").addEventListener("click", () => openFileViewer(f.id));
    const btns = row.querySelectorAll(".repo-act-btn");

    btns[0].addEventListener("click", () => openFileViewer(f.id));

    btns[1].addEventListener("click", async () => {
      const newName = prompt("Rename to:", f.filename);
      if (!newName || newName === f.filename) return;
      const r = await api("/projects/files/" + f.id + "/rename", {
        method: "PATCH",
        body: JSON.stringify({ new_filename: newName })
      });
      if (r && r.ok) { loadRepoBrowser(); loadFiles(activeProjectId); }
      else showCustomAlert("Error", "Rename failed.");
    });

    btns[2].addEventListener("click", async () => {
      const options = ["/ (root)", ...repoFolders.map(fo => fo.parent === "/" ? "/" + fo.name : fo.parent + "/" + fo.name)];
      const target  = prompt("Move to folder:\n" + options.join("\n"), repoCurrentPath);
      if (!target) return;
      const folder = target === "/ (root)" ? "/" : target;
      const r = await api("/projects/files/" + f.id + "/move", {
        method: "PATCH",
        body: JSON.stringify({ new_folder: folder })
      });
      if (r && r.ok) loadRepoBrowser();
      else showCustomAlert("Error", "Move failed.");
    });

    btns[3].addEventListener("click", () => {
      showCustomConfirm("Delete File", 'Delete "' + f.filename + '"?', async () => {
        const r = await api("/projects/files/" + f.id, { method: "DELETE" });
        if (r && r.ok) { loadRepoBrowser(); loadFiles(activeProjectId); }
        else showCustomAlert("Error", "Delete failed.");
      });
    });

    if (fileDiv) fileDiv.appendChild(row);
  });
}

async function loadReviewProjectSelect() {
  if (!projectList.length) {
    const projects = await fetchProjects();
    _projectsCache = projects;
    projectList = (projects.owned || []).concat(projects.invited || []);
  }
  fillProjectSelects();
}

el("load-files-btn").addEventListener("click", async () => {
  const projectId = el("review-project-select").value;
  if (!projectId) return;

  el("review-result").style.display       = "none";
  el("review-history-card").style.display = "none";
  el("review-files-list").style.display   = "none";
  el("review-files-items").innerHTML      = "<div class='empty-state'>Loading…</div>";

  const res = await api("/projects/" + projectId + "/files");
  if (!res || !res.ok) return;
  const files = await res.json();

  el("review-files-list").style.display = "block";
  el("review-files-items").innerHTML = "";

  if (!files.length) {
    el("review-files-items").innerHTML = "<div class='empty-state'>No files in this project.</div>";
    return;
  }

  files.forEach(f => {

    const row = document.createElement("div");
    row.className = "file-item";
    row.innerHTML = `<div><div class="file-item-name">${esc(f.filename)}</div><div class="file-item-meta">${esc(f.file_type)} · ID: ${f.id}</div></div><button class="btn-primary btn-sm" data-file-id="${f.id}">Review</button>`;
    row.querySelector("button").addEventListener("click", () => runReview(f.id));
    el("review-files-items").appendChild(row);
  });

  loadReviewHistory(projectId);

  const autoRes = await api("/review/auto/" + projectId);
  if (autoRes && autoRes.ok) {
    const autoData = await autoRes.json();
    if (autoData.type === "automatic") {
      el("review-result").style.display = "block";
      showReviewResult(autoData.review, autoData.file_id);
      return; 
    }
  }
});

async function runReview(fileId, filename = null, filePath = null, changedContent = null) {
  el("review-result").style.display = "block";
  setText("review-summary-text", "Running review...");
  const badge = el("review-complexity-badge");
  if (badge) badge.textContent = "";

  ["rs-issues-list","rs-opt-list","rs-imp-list","rs-doc-list"].forEach(id => {
    const e = el(id);
    if (e) e.innerHTML = "";
  });

  let res;
  if (changedContent !== null) {
    res = await api("/review/file/" + fileId, {
      method: "POST",
      body: JSON.stringify({
        file_id: fileId,
        filename: filename,
        file_path: filePath,
        changed_content: changedContent
      })
    });
  } else {
    res = await api("/review/file/" + fileId, { method: "POST" });
  }

  if (!res) {
    setText("review-summary-text", "Server not reachable.");
    return;
  }

  if (res.status === 503) {
    setText("review-summary-text", "AI Review Service Unavailable");
    return;
  }

  if (!res.ok) {
    const errorText = await res.text();
    console.error(errorText);
    setText("review-summary-text", "Review failed.");
    return;
  }

  const data = await res.json();
  showReviewResult(data, fileId);
}

function showReviewResult(data, targetFileId) {
  const ai = data.ai_review || {};

  const isOpenAI = ai._source === "openai";
  const sourceLabel = isOpenAI ? "&#10024; Reviewed by OpenAI GPT-4o-mini" : "&#128295; Reviewed by Ollama";
  const sourceCls   = "source-ai";

  const sumEl = el("review-summary-text");
  if (sumEl) {
    sumEl.innerHTML = `
      <span class="source-banner ${sourceCls}">${sourceLabel}</span>
    `;
  }

  let fileName = data.filename || data.file_name || "main.py"; 
  if (!data.filename && !data.file_name && targetFileId) {
    const fileItem = document.querySelector(`.file-item button[data-file-id="${targetFileId}"]`);
    if (fileItem) fileName = fileItem.parentElement.querySelector(".file-item-name").textContent;
  }
  
  const cleanStr = (str, fallback) => {
    if (!str || ["none", "null", "undefined", "unknown", ""].includes(String(str).toLowerCase().trim())) return fallback;
    return str;
  };
  
  const rcFilename = el("rc-filename");
  if (rcFilename) {
    const filePath = data.filepath || data.file_path || "";
    rcFilename.innerHTML = `${esc(fileName)}<br/><span style="font-size: 0.9rem; color: var(--color-muted); font-weight: normal;">Path: ${esc(filePath)}</span>`;
  }
  setText("rc-issue", cleanStr(ai.code_issue, "No specific issue identified."));
  setText("rc-explanation", cleanStr(ai.explanation, "No explanation provided."));
  setText("rc-fix", cleanStr(ai.suggested_fix, "No fix suggested."));
  setText("rc-opt", cleanStr(ai.optimization, "No optimization required."));
  
  const genDocEl = el("rc-doc");
  if (genDocEl) {
    genDocEl.textContent = ai.generated_documentation_comments || "No documentation generated.";
  }

  const pid = el("review-project-select").value;
  if (pid) loadReviewHistory(pid);
}

function fillList(id, items, emptyText) {
  const listEl = el(id);
  if (!listEl) return;
  listEl.innerHTML = "";
  if (!items || !items.length) {
    listEl.innerHTML = `<li class="empty-item">${emptyText}</li>`;
    return;
  }
  items.forEach(t => {
    const li = document.createElement("li");
    li.textContent = t;
    listEl.appendChild(li);
  });
}

async function loadReviewHistory(projectId) {
  const histCard = el("review-history-card");
  if (histCard) histCard.style.display = "block";
  const list = el("review-history-list");
  if (!list) return;
  list.innerHTML = "<div class='empty-state'>Loading…</div>";
  const res = await api("/review/history/" + projectId);
  if (!res || !res.ok) { list.innerHTML = "<div class='empty-state'>Failed to load review history.</div>"; return; }
  const reviews = await res.json();
  list.innerHTML = "";
  if (!reviews.length) { list.innerHTML = "<div class='empty-state'>No past reviews.</div>"; return; }
  reviews.forEach(r => {
    const d = document.createElement("div");
    d.className = "review-history-item";
    const date  = r.created_at ? new Date(r.created_at).toLocaleString() : "";
    const score = r.score ?? "—";
    const scoreCls = score >= 80 ? "score-good" : score >= 50 ? "score-medium" : "score-low";
    const comp  = r.complexity || "unknown";
    d.innerHTML = `
      <div class="rhi-header">
        <span class="rhi-file">&#128196; ${esc(r.filename || "main.py")}</span>
        <span class="rhi-score ${scoreCls}">${score}/100</span>
        <span class="rhi-time">${date}</span>
      </div>
      <div class="rhi-summary"><strong>Summary:</strong><br/>${esc(["none", "null", "undefined", "unknown", ""].includes(String(r.summary).toLowerCase().trim()) ? "Review completed." : r.summary)}</div>
      <div class="rhi-tags">
        ${comp !== "unknown" ? `<span class="complexity-badge complexity-${comp}">${comp}</span>` : ""}
      </div>
      <div class="rhi-expand" style="display:none;">
        <div class="rhi-section"><strong>Issues:</strong>
          <p>${esc(["none", "null", "undefined", "unknown", ""].includes(String(r.issues).toLowerCase().trim()) ? "No issues found." : r.issues)}</p>
        </div>
        <div class="rhi-section"><strong>Suggestions:</strong>
          <p>${esc(r.suggestions || "No suggestions.")}</p>
        </div>
        <div class="rhi-section"><strong>Optimizations:</strong>
          <p>${(r.optimizations && r.optimizations !== "None" && r.optimizations !== "unknown" && r.optimizations !== "null" && r.optimizations !== "undefined") ? esc(r.optimizations) : "No optimization required"}</p>
        </div>
      </div>
      <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
        <button class="btn-ghost btn-sm rhi-toggle-btn">Expand &#9660;</button>
      </div>`;

    const toggleBtn = d.querySelector(".rhi-toggle-btn");
    const expandDiv = d.querySelector(".rhi-expand");
    toggleBtn.addEventListener("click", () => {
      const open = expandDiv.style.display !== "none";
      expandDiv.style.display = open ? "none" : "block";
      toggleBtn.textContent = open ? "Expand ▼" : "Collapse ▲";
    });

    list.appendChild(d);
  });
}

async function loadActivityFeed() {
  const feedEl = el("activity-feed");
  if (!feedEl) return;
  feedEl.innerHTML = "<div class='empty-state'>Loading…</div>";
  const res = await api("/collaboration/activity-feed");
  if (!res || !res.ok) { feedEl.innerHTML = "<div class='empty-state'>Failed to load.</div>"; return; }
  const items = await res.json();
  feedEl.innerHTML = "";
  if (!items.length) { feedEl.innerHTML = "<div class='empty-state'>No activity yet.</div>"; return; }
  items.slice(0, 30).forEach(a => {
    const d = document.createElement("div");
    d.className = "activity-item";
    const t = a.timestamp ? new Date(a.timestamp).toLocaleString() : "";
    d.innerHTML = `<div class="activity-dot"></div><div><div class="activity-text">${esc(a.action)}</div>${t ? `<div class="activity-time">${t}</div>` : ""}</div>`;
    feedEl.appendChild(d);
  });
}

async function loadVersionProjectSelect() {
  if (!projectList.length) {
    const projects = await fetchProjects();
    _projectsCache = projects;
    projectList = (projects.owned || []).concat(projects.invited || []);
  }
  fillProjectSelects();
}

el("load-commits-btn").addEventListener("click", async () => {
  const projectId = el("version-project-select").value;
  if (!projectId) return;
  const listEl = el("commit-history-list");
  const itemsEl = el("commit-items");
  if (listEl) listEl.style.display = "block";
  if (itemsEl) itemsEl.innerHTML = "<div class='empty-state'>Loading…</div>";
  const res = await api("/version/history/" + projectId);
  if (!res || !res.ok) { if (itemsEl) itemsEl.innerHTML = "<div class='empty-state'>Failed to load.</div>"; return; }
  const commits = await res.json();
  if (itemsEl) itemsEl.innerHTML = "";
  if (!commits.length) { if (itemsEl) itemsEl.innerHTML = "<div class='empty-state'>No commits yet. Create a commit first.</div>"; return; }
  commits.forEach((c, i) => {
    const d = document.createElement("div");
    d.className = "commit-item";
    const t = c.created_at ? new Date(c.created_at).toLocaleString() : "";
    d.innerHTML = `
      <span class="commit-hash">#${i + 1}</span>
      <div>
        <div class="commit-msg">${esc(c.commit_message || "No message")}</div>
        <div class="commit-meta">${esc(c.author || "")}${t ? " &middot; " + t : ""} &middot; ID: ${c.id}</div>
      </div>`;
    if (itemsEl) itemsEl.appendChild(d);
  });
});

el("load-versions-btn").addEventListener("click", async () => {
  const fileId = el("versions-file-id").value;
  if (!fileId) return;
  const versCard     = el("file-versions-card");
  const listEl       = el("file-versions-list");
  const timelineCard = el("version-timeline-card");
  const timelineList = el("version-timeline-list");
  const diffCard     = el("diff-viewer-card");

  if (versCard)     versCard.style.display     = "block";
  if (timelineCard) timelineCard.style.display = "none";
  if (diffCard)     diffCard.style.display     = "none";
  if (listEl)       listEl.innerHTML           = "<div class='empty-state'>Loading…</div>";

  const res = await api("/version/versions/" + fileId);
  if (!res || !res.ok) { if (listEl) listEl.innerHTML = "<div class='empty-state'>Failed to load.</div>"; return; }
  const versions = await res.json();
  if (listEl) listEl.innerHTML = "";

  if (!versions.length) {
    if (listEl) listEl.innerHTML = "<div class='empty-state'>No versions yet. Create a commit above.</div>";
    return;
  }

  versions.forEach(v => {
    const d = document.createElement("div");
    d.className = "version-item";
    const date = v.created_at ? new Date(v.created_at).toLocaleString() : "";
    d.innerHTML = `
      <span class="version-tag">v${v.version_number}</span>
      <div class="version-info">
        <div class="version-msg">${esc(v.commit_message || "No message")}</div>
        <div class="version-meta">${esc(v.author || "")}${date ? " &middot; " + date : ""} &middot; ID: ${v.id}</div>
      </div>
      <div class="version-actions">
        <button class="btn-rollback">&#8635; Rollback</button>
      </div>`;
    d.querySelector(".btn-rollback").addEventListener("click", () => {
      showCustomConfirm("Restore version?", `Restore v${v.version_number}?\n"${v.commit_message}"\n\nThis will overwrite the current file.`, () => {
        doRollback(v.id, v.version_number);
      });
    });
    if (listEl) listEl.appendChild(d);
  });

  if (timelineCard) timelineCard.style.display = "block";
  if (timelineList) {
    timelineList.innerHTML = "";
    versions.forEach(v => {
      const date = v.created_at ? new Date(v.created_at).toLocaleString() : "";
      const tl = document.createElement("div");
      tl.className = "vt-item";
      tl.innerHTML = `
        <div class="vt-dot"></div>
        <div class="vt-content">
          <div class="vt-label">Version ${v.version_number} — <strong>${esc(v.commit_message || "No message")}</strong></div>
          <div class="vt-meta">${esc(v.author || "")}${date ? " &middot; " + date : ""}</div>
        </div>`;
      timelineList.appendChild(tl);
    });
  }

  if (diffCard) diffCard.style.display = "block";
  if (versions.length >= 2) {
    const dv1 = el("diff-v1");
    const dv2 = el("diff-v2");
    if (dv1) dv1.value = versions[0].id;
    if (dv2) dv2.value = versions[versions.length - 1].id;
  }
  const diffOut = el("diff-output");
  if (diffOut) diffOut.innerHTML = "";
  setText("diff-stats", "");
});

async function doRollback(versionId, vNum) {
  const res = await api("/version/rollback/" + versionId, { method: "POST" });
  if (!res || !res.ok) { showCustomAlert("Error", "Rollback failed."); return; }
  const data = await res.json();
  showCustomAlert("Success", `Rolled back to v${vNum} — ${data.file || ""}`);
  addNotif("Rolled back to v" + vNum);
  
  if (window.currentFileId) {
    openFileViewer(window.currentFileId);
  }
}

el("compare-btn").addEventListener("click", async () => {
  const v1 = el("diff-v1").value;
  const v2 = el("diff-v2").value;
  if (!v1 || !v2) { showCustomAlert("Error", "Enter both version IDs."); return; }
  const outputEl = el("diff-output");
  const statsEl  = el("diff-stats");
  if (outputEl) outputEl.innerHTML = "<span style='color:var(--color-muted)'>Computing diff…</span>";
  if (statsEl)  statsEl.textContent = "";
  const res = await api("/version/compare/" + v1 + "/" + v2);
  if (!res || !res.ok) { if (outputEl) outputEl.textContent = "Failed to compare."; return; }
  const data = await res.json();
  if (data.error) { if (outputEl) outputEl.textContent = data.error; return; }

  if (statsEl) statsEl.textContent = `v${data.from_version} → v${data.to_version}   +${data.added} added  −${data.removed} removed`;
  if (outputEl) outputEl.innerHTML = "";

  if (!data.diff || !data.diff.length) {
    if (outputEl) outputEl.innerHTML = "<span style='color:var(--color-muted)'>No differences found — files are identical.</span>";
    return;
  }

  data.diff.forEach(line => {
    const span = document.createElement("span");
    span.className = "diff-line";
    if      (line.startsWith("+++") || line.startsWith("---")) span.classList.add("meta");
    else if (line.startsWith("+"))  span.classList.add("added");
    else if (line.startsWith("-"))  span.classList.add("removed");
    else if (line.startsWith("@@")) span.classList.add("meta");
    else                             span.classList.add("normal");
    span.textContent = line;
    if (outputEl) outputEl.appendChild(span);
  });
});

const commitForm  = el("commit-form");
const commitAlert = el("commit-alert");

commitForm.addEventListener("submit", async e => {
  e.preventDefault();
  hideAlert(commitAlert);
  const fileId  = parseInt(el("commit-file-id").value);
  const message = el("commit-message").value.trim();
  if (!fileId || !message) { showAlert(commitAlert, "File ID and message are required.", "error"); return; }
  const res = await api("/version/commit", {
    method: "POST",
    body: JSON.stringify({ file_id: fileId, commit_message: message })
  });
  if (!res || !res.ok) { const err = await res?.json(); showAlert(commitAlert, err?.detail || "Commit failed.", "error"); return; }
  const data = await res.json();
  showAlert(commitAlert, `Commit created — Version ${data.version} (ID: ${data.version_id})`, "success");
  commitForm.reset();
  addNotif("New commit: " + message);
});

let chartScore = null;
let chartTrend = null;
let chartFreq  = null;

async function loadAnalytics() {
  loadReviewAnalytics();
}

el("analytics-project-select")?.addEventListener("change", () => {
  loadReviewAnalytics();
});

async function loadReviewAnalytics() {
  const projectId = el("analytics-project-select")?.value || "";
  const qs = projectId ? "?project_id=" + projectId : "";
  
  const res1 = await api("/review/analytics/trends" + qs);
  if (res1 && res1.ok) {
    const d = await res1.json();
    setText("a-total-reviews",  d.total_reviews  ?? "0");
    setText("a-avg-score",      d.average_score  ?? "-");
    setText("a-files-reviewed", d.files_reviewed ?? "0");
  }

  const res2 = await api("/dashboard-api/score-trend" + qs);
  if (res2 && res2.ok) {
    const d2     = await res2.json();
    const labels = Object.keys(d2).sort();
    const values = labels.map(k => d2[k]);
    const canvas = el("score-trend-chart");
    const emptyEl = el("score-trend-empty");
    if (canvas) {
      if (chartScore) chartScore.destroy();
      if (labels.length) {
        canvas.style.display = "block";
        if (emptyEl) emptyEl.style.display = "none";
        chartScore = new Chart(canvas, {
          type: "line",
          data: {
            labels,
            datasets: [{
              label: "Avg Score",
              data: values,
              borderColor: "rgba(19,194,194,0.9)",
              backgroundColor: "rgba(19,194,194,0.08)",
              borderWidth: 2, fill: true, tension: 0.35,
              pointRadius: 4, pointBackgroundColor: "rgba(19,194,194,0.9)"
            }]
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
              y: { beginAtZero: true, max: 100, ticks: { precision: 1 } },
              x: { grid: { display: false } }
            }
          }
        });
      } else {
        canvas.style.display = "none";
        if (emptyEl) emptyEl.style.display = "flex";
      }
    }
  }

  const res3 = await api("/dashboard-api/review-trend" + qs);
  if (res3 && res3.ok) {
    const d3     = await res3.json();
    const labels = Object.keys(d3).sort();
    const values = labels.map(k => d3[k]);
    const canvas = el("review-trend-chart");
    const emptyEl = el("review-trend-empty");
    if (canvas) {
      if (chartTrend) chartTrend.destroy();
      if (labels.length) {
        canvas.style.display = "block";
        if (emptyEl) emptyEl.style.display = "none";
        chartTrend = new Chart(canvas, {
          type: "bar",
          data: {
            labels,
            datasets: [{
              label: "Reviews",
              data: values,
              backgroundColor: "rgba(19,194,194,0.7)",
            }]
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 } },
              x: { grid: { display: false } }
            }
          }
        });
      } else {
        canvas.style.display = "none";
        if (emptyEl) emptyEl.style.display = "block";
      }
    }
  }
}

document.getElementById("logout-btn").addEventListener("click", logout);

let _rhPage = 1, _rhSearch = "", _rhProjectId = "";

async function loadGlobalReviewHistory(page) {
  if (page !== undefined) _rhPage = page;
  const listEl = el("rh-list");
  const pagEl  = el("rh-pagination");
  if (!listEl) return;
  listEl.innerHTML = "<div class='empty-state'>Loading…</div>";
  if (pagEl) pagEl.innerHTML = "";

  const params = new URLSearchParams({
    page:      _rhPage,
    page_size: 10,
    search:    _rhSearch || "",
  });
  if (_rhProjectId) params.set("project_id", _rhProjectId);

  const res = await api("/review/all?" + params.toString());
  if (!res || !res.ok) { listEl.innerHTML = "<div class='empty-state'>Failed to load.</div>"; return; }
  const data = await res.json();

  listEl.innerHTML = "";
  if (!data.reviews.length) {
    listEl.innerHTML = "<div class='empty-state'>No reviews found.</div>";
    return;
  }

  data.reviews.forEach(r => {
    const card = document.createElement("div");
    card.className = "rh-card";
    const date  = r.created_at ? new Date(r.created_at).toLocaleString() : "";
    const score = r.score ?? "—";
    const scoreCls = score >= 8 ? "score-good" : score >= 5 ? "score-medium" : "score-low";
    const comp  = r.complexity || "unknown";
    card.innerHTML = `
      <div class="rh-card-header">
        <div>
          <span class="rh-filename">&#128196; ${esc(r.filename)}</span>
          <span class="rh-project">&#128193; ${esc(r.project_name)}</span>
        </div>
        <div class="rh-card-meta">
          <span class="rh-score ${scoreCls}">${score}/100</span>
          <span class="rh-date">${date}</span>
        </div>
      </div>
      <div class="rh-tags">
        ${comp !== "unknown" ? `<span class="complexity-badge complexity-${comp}">${comp}</span>` : ""}
      </div>
      ${r.summary ? `<div class="rh-summary"><strong>Summary:</strong><br/>${esc(r.summary)}</div>` : ""}
      <div class="rh-body" style="display:none;">
        <div class="rhi-section"><strong>Issues:</strong>
          <p>${(r.issues && r.issues.length) ? esc(r.issues.join(", ")) : "No issues found."}</p>
        </div>
        <div class="rhi-section"><strong>Suggestions:</strong>
          <p>${(r.suggestions && r.suggestions.length) ? esc(r.suggestions.join(", ")) : "No suggestions."}</p>
        </div>
        <div class="rhi-section"><strong>Optimizations:</strong>
          <p>${(r.optimizations && r.optimizations !== "None" && r.optimizations !== "unknown" && r.optimizations !== "null" && r.optimizations !== "undefined") ? esc(r.optimizations) : "No optimization required"}</p>
        </div>
      </div>
      <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
        <button class="btn-ghost btn-sm rh-expand-btn">Expand &#9660;</button>
        <button class="btn-primary btn-sm rh-review-btn">View Full Review</button>
      </div>`;

    const bodyEl = card.querySelector(".rh-body");
    card.querySelector(".rh-expand-btn").addEventListener("click", function() {
      const open = bodyEl.style.display !== "none";
      bodyEl.style.display = open ? "none" : "block";
      this.textContent = open ? "Expand ▼" : "Collapse ▲";
    });
    card.querySelector(".rh-review-btn").addEventListener("click", () => {
      const sel = el("review-project-select");
      if (sel) sel.value = r.project_id;
      showSection("reviews");
      setTimeout(() => el("load-files-btn")?.click(), 200);
    });
    listEl.appendChild(card);
  });

  if (pagEl && data.pages > 1) {
    for (let i = 1; i <= data.pages; i++) {
      const btn = document.createElement("button");
      btn.className = "pag-btn" + (i === _rhPage ? " active" : "");
      btn.textContent = i;
      btn.addEventListener("click", () => loadGlobalReviewHistory(i));
      pagEl.appendChild(btn);
    }
  }
}

function initReviewHistory() {
  const rhSearchInput   = el("rh-search");
  const rhProjectFilter = el("rh-project-filter");
  if (rhSearchInput) {
    rhSearchInput.addEventListener("input", () => {
      _rhSearch = rhSearchInput.value.trim();
      loadGlobalReviewHistory(1);
    });
  }
  if (rhProjectFilter) {
    rhProjectFilter.addEventListener("change", () => {
      _rhProjectId = rhProjectFilter.value;
      loadGlobalReviewHistory(1);
    });
  }
}

function fillReviewHistoryFilter() {
  const sel = el("rh-project-filter");
  if (!sel) return;
  while (sel.options.length > 1) sel.remove(1);
  projectList.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    sel.appendChild(opt);
  });
}

initUser();
initSocket();
initReviewHistory();
showSection("dashboard");

async function loadCollaborationPage() {
  if (!projectList.length) {
    const projects = await fetchProjects();
    _projectsCache = projects;
    projectList = (projects.owned || []).concat(projects.invited || []);
  }
  
  const sel = el("collab-page-project-select");
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = "<option value=''>— choose a project —</option>";
  projectList.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    sel.appendChild(opt);
  });
  if (cur) sel.value = cur;
}

el("collab-page-project-select")?.addEventListener("change", e => {
  const pid = e.target.value;
  activeProjectId = pid;
  const content = el("collab-page-content");
  if (!pid) {
    if (content) content.style.display = "none";
    return;
  }
  if (content) content.style.display = "block";
  loadCollaborators(pid);
  loadActivity(pid);
  loadGlobalComments(pid);
});

async function loadGlobalComments(projectId) {
  const listEl = el("global-comments-list");
  if (!listEl) return;
  listEl.innerHTML = "<div class='empty-state'>Loading comments…</div>";
  const res = await api("/collaboration/comments/project/" + projectId);
  if (!res || !res.ok) {
    listEl.innerHTML = "<div class='empty-state'>Failed to load comments.</div>";
    return;
  }
  const comments = await res.json();
  listEl.innerHTML = "";
  if (!comments.length) {
    listEl.innerHTML = "<div class='empty-state'>No comments yet.</div>";
    return;
  }
  comments.forEach(c => {
    const d   = document.createElement("div");
    d.className = "fv-comment-item";
    const ts  = c.timestamp ? new Date(c.timestamp).toLocaleString() : "";
    const isMe = currentUser && c.user_id === currentUser.user_id;
    d.innerHTML = `
      <div class="fv-comment-meta" style="display:flex; justify-content:space-between;">
        <div>
          <span class="fv-comment-user ${isMe ? "fv-comment-me" : ""}">${esc(c.username)}</span>
          <span style="font-size:0.75rem; color:var(--color-primary); margin-left:8px;">File ID: ${c.file_id}</span>
        </div>
        <span class="fv-comment-time">${ts}</span>
      </div>
      <div class="fv-comment-body">${esc(c.comment)}</div>`;
    listEl.appendChild(d);
  });
}

el("btn-add-collaborator")?.addEventListener("click", () => {
  el("add-collaborator-modal").style.display = "flex";
  el("collab-search-input").value = "";
  el("collab-search-results").innerHTML = "<div class='empty-state' style='padding:10px;'>Type to search users...</div>";
});

el("collab-modal-close-btn")?.addEventListener("click", () => {
  el("add-collaborator-modal").style.display = "none";
});

el("add-collaborator-modal")?.addEventListener("click", e => {
  if (e.target === el("add-collaborator-modal")) el("add-collaborator-modal").style.display = "none";
});

let _searchTimeout = null;
el("collab-search-input")?.addEventListener("input", e => {
  clearTimeout(_searchTimeout);
  const q = e.target.value.trim();
  if (!q) {
    el("collab-search-results").innerHTML = "<div class='empty-state' style='padding:10px;'>Type to search users...</div>";
    return;
  }
  _searchTimeout = setTimeout(async () => {
    el("collab-search-results").innerHTML = "<div class='empty-state' style='padding:10px;'>Searching...</div>";
    const res = await api("/collab-api/users/search?q=" + encodeURIComponent(q));
    if (!res || !res.ok) {
      el("collab-search-results").innerHTML = "<div class='empty-state' style='padding:10px;'>Failed to search</div>";
      return;
    }
    const users = await res.json();
    if (!users.length) {
      el("collab-search-results").innerHTML = "<div class='empty-state' style='padding:10px;'>No users found</div>";
      return;
    }
    el("collab-search-results").innerHTML = "";
    users.forEach(u => {
      const d = document.createElement("div");
      d.style.cssText = "display:flex; justify-content:space-between; padding:8px; border-bottom:1px solid var(--color-border); align-items:center;";
      d.innerHTML = `
        <div>
          <div style="font-weight:600;">${esc(u.username)}</div>
          <div style="font-size:0.8rem; color:var(--color-muted);">${esc(u.email)}</div>
        </div>
        <button class="btn-primary btn-sm">Invite</button>
      `;
      d.querySelector("button").addEventListener("click", async () => {
        const r = await api("/collab-api/projects/" + activeProjectId + "/invitations", {
          method: "POST",
          body: JSON.stringify({ invitee_id: u.id })
        });
        if (r && r.ok) {
          showCustomAlert("Success", "Invitation sent!", () => {
            el("add-collaborator-modal").style.display = "none";
          });
        } else {
          const err = await r.json();
          showCustomAlert("Error", err.detail || "Failed to invite");
        }
      });
      el("collab-search-results").appendChild(d);
    });
  }, 300);
});

async function loadCollaborators(projectId) {
  const tbody = el("collaborators-tbody");
  if (!tbody) return;
  tbody.innerHTML = "<tr><td colspan='5' style='padding:20px; text-align:center;'>Loading...</td></tr>";
  const res = await api("/collab-api/projects/" + projectId + "/collaborators");
  if (!res || !res.ok) {
    tbody.innerHTML = "<tr><td colspan='5' style='padding:20px; text-align:center; color:var(--color-danger);'>Failed to load</td></tr>";
    return;
  }
  const collabs = await res.json();
  tbody.innerHTML = "";
  if (!collabs.length) {
    tbody.innerHTML = "<tr><td colspan='5' style='padding:20px; text-align:center;'>No collaborators yet.</td></tr>";
    return;
  }
  
  collabs.forEach(c => {
    const tr = document.createElement("tr");
    tr.style.borderBottom = "1px solid var(--color-border)";
    const date = new Date(c.joined_at).toLocaleDateString();
    
    const amIOwner = collabs.find(x => x.role === "OWNER" && x.id === currentUser?.user_id) !== undefined;
    const canManage = amIOwner && c.role !== "OWNER";
    
    tr.innerHTML = `
      <td style="padding:10px;">${esc(c.username)}</td>
      <td style="padding:10px;">
        ${canManage ? `
          <select class="role-select" data-id="${c.id}" style="padding:4px; font-size:0.8rem; background:var(--color-bg); border:1px solid var(--color-border);">
            <option value="READ" ${c.role === "READ" ? "selected" : ""}>READ</option>
            <option value="WRITE" ${c.role === "WRITE" ? "selected" : ""}>WRITE</option>
          </select>
        ` : esc(c.role)}
      </td>
      <td style="padding:10px;">${date}</td>
      <td style="padding:10px;">${esc(c.status)}</td>
      <td style="padding:10px;">
        ${canManage ? `<button class="btn-danger btn-sm remove-collab-btn" data-id="${c.id}">Remove</button>` : ""}
      </td>
    `;
    tbody.appendChild(tr);
  });
  
  tbody.querySelectorAll(".role-select").forEach(sel => {
    sel.addEventListener("change", async e => {
      const uid = e.target.dataset.id;
      const role = e.target.value;
      const r = await api("/collab-api/projects/" + projectId + "/collaborators/" + uid + "/role", {
        method: "PATCH",
        body: JSON.stringify({ role })
      });
      if (!r || !r.ok) {
        showCustomAlert("Error", "Failed to change role.");
        loadCollaborators(projectId); 
      }
    });
  });
  
  tbody.querySelectorAll(".remove-collab-btn").forEach(btn => {
    btn.addEventListener("click", e => {
      showCustomConfirm("Remove collaborator?", "Remove this collaborator?", async () => {
        const uid = e.target.dataset.id;
        const r = await api("/collab-api/projects/" + projectId + "/collaborators/" + uid, {
          method: "DELETE"
        });
        if (r && r.ok) {
          loadCollaborators(projectId);
        } else {
          showCustomAlert("Error", "Failed to remove collaborator.");
        }
      });
    });
  });
}
async function loadProfile() {
  const res = await api('/auth/profile');
  if (res && res.ok) {
    const data = await res.json();
    el('prof-username').value = data.username;
    el('prof-email').value = data.email;
  }
}

const profileForm = el('profile-form');
if (profileForm) {
  profileForm.addEventListener('submit', async e => {
    e.preventDefault();
    const res = await api('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify({
        username: el('prof-username').value.trim(),
        email: el('prof-email').value.trim()
      })
    });
    if (res && res.ok) {
      showAlert(el('prof-alert'), 'Profile updated successfully!', 'success');
      const data = await res.json();
      if (currentUser) {
        currentUser.username = data.username;
        currentUser.email = data.email;
        localStorage.setItem('user', JSON.stringify(currentUser));
        initUser();
      }
    } else {
      const err = await res.json();
      showAlert(el('prof-alert'), err.detail || 'Update failed', 'danger');
    }
  });
}

const passwordForm = el('password-form');
if (passwordForm) {
  passwordForm.addEventListener('submit', async e => {
    e.preventDefault();
    const res = await api('/auth/profile/password', {
      method: 'PUT',
      body: JSON.stringify({
        old_password: el('prof-old-pwd').value,
        new_password: el('prof-new-pwd').value
      })
    });
    if (res && res.ok) {
      showAlert(el('pwd-alert'), 'Password changed successfully!', 'success');
      e.target.reset();
    } else {
      const err = await res.json();
      showAlert(el('pwd-alert'), err.detail || 'Password change failed', 'danger');
    }
  });
}

const profDeleteBtn = el('prof-delete-btn');
if (profDeleteBtn) {
  profDeleteBtn.addEventListener('click', () => {
    showCustomConfirmDelete(
      'Delete Account',
      'Are you absolutely sure you want to delete your account? This action cannot be undone.',
      async () => {
        const res = await api('/auth/profile', { method: 'DELETE' });
        if (res && res.ok) {
          showCustomAlert('Account Deleted', 'Account deleted. You will be logged out.', () => {
            logout();
          });
        } else {
          showCustomAlert('Error', 'Failed to delete account');
        }
      }
    );
  });
}

const openChatbotBtn = el('open-chatbot-btn');
const chatbotModal = el('chatbot-select-modal');
const chatbotCloseBtn = el('chatbot-modal-close-btn');
const chatbotCancelBtn = el('chatbot-modal-cancel-btn');
const chatbotOpenBtn = el('chatbot-modal-open-btn');
const chatbotProjectSelect = el('chatbot-project-select');
const chatbotFilesGroup = el('chatbot-files-group');
const chatbotFilesList = el('chatbot-files-list');

if (openChatbotBtn && chatbotModal) {
  openChatbotBtn.addEventListener('click', async () => {
    chatbotModal.style.display = 'flex';
    chatbotProjectSelect.innerHTML = '<option value="`">Loading projects...</option>';
    chatbotFilesGroup.style.display = 'none';
    chatbotOpenBtn.disabled = true;
    
    const res = await api('/projects/my-projects');
    if (res && res.ok) {
      const data = await res.json();
      const projects = [...data.owned, ...data.invited];
      chatbotProjectSelect.innerHTML = '<option value="`">-- Choose Project --</option>';
      projects.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        chatbotProjectSelect.appendChild(opt);
      });
    } else {
      chatbotProjectSelect.innerHTML = '<option value="`">Failed to load projects</option>';
    }
  });
  
  const closeChatbotModal = () => { chatbotModal.style.display = 'none'; };
  if(chatbotCloseBtn) chatbotCloseBtn.addEventListener('click', closeChatbotModal);
  if(chatbotCancelBtn) chatbotCancelBtn.addEventListener('click', closeChatbotModal);
  
  chatbotProjectSelect.addEventListener('change', async (e) => {
    const pid = e.target.value;
    if (!pid) {
      chatbotFilesGroup.style.display = 'none';
      chatbotOpenBtn.disabled = true;
      return;
    }
    chatbotFilesGroup.style.display = 'block';
    chatbotFilesList.innerHTML = 'Loading files...';
    const res = await api('/projects/' + pid + '/files');
    if (res && res.ok) {
      const files = await res.json();
      chatbotFilesList.innerHTML = '';
      if (files.length === 0) {
        chatbotFilesList.innerHTML = '<div class="empty-state">No files in this project</div>';
      } else {
        files.forEach(f => {
          const div = document.createElement('div');
          div.style.marginBottom = '5px';
          div.innerHTML = `<label><input type="checkbox" class="chatbot-file-cb" value="${f.id}"> ${f.filename || f.name}</label>`;
          chatbotFilesList.appendChild(div);
        });
      }
    } else {
      chatbotFilesList.innerHTML = '<div class="empty-state">Failed to load files</div>';
    }
  });
  
  chatbotFilesList.addEventListener('change', () => {
    const selected = document.querySelectorAll('.chatbot-file-cb:checked');
    chatbotOpenBtn.disabled = selected.length === 0;
  });
  
  chatbotOpenBtn.addEventListener('click', () => {
    const pid = chatbotProjectSelect.value;
    const selected = Array.from(document.querySelectorAll('.chatbot-file-cb:checked')).map(cb => cb.value);
    if (pid && selected.length > 0) {
      window.location.href = `/project/${pid}/chatbot?files=${selected.join(',')}`;
    }
  });
}

