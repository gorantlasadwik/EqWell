const counsellors = [
  { id: "c1", username: "anika.rao", password: "Care@2026", name: "Dr. Anika Rao", initials: "AR", specialty: "Trauma-informed care" },
  { id: "c2", username: "samir.khan", password: "Calm@2026", name: "Dr. Samir Khan", initials: "SK", specialty: "Academic burnout" },
  { id: "c3", username: "meera.iyer", password: "Thrive@2026", name: "Dr. Meera Iyer", initials: "MI", specialty: "Behavioural therapy" },
];

const students = [
  { id: "s1", counsellorId: "c1", name: "Aarav Menon", regNumber: "23CS1041", hostel: "Maple Residency", year: "2nd Year", department: "Computer Science", stressLevel: 76, wellbeing: { stress: 76, anxiety: 69, focus: 48, sleep: 42, mood: 61, resilience: 67 }, trends: [{ m: "Jan", stress: 62, anxiety: 55, focus: 63, mood: 64 }, { m: "Feb", stress: 68, anxiety: 58, focus: 58, mood: 62 }, { m: "Mar", stress: 73, anxiety: 65, focus: 53, mood: 59 }, { m: "Apr", stress: 76, anxiety: 69, focus: 48, mood: 61 }], heatmap: [62, 71, 66, 74, 81, 69, 58, 61, 72, 79, 84, 68, 63, 57], notes: ["Reduced sleep consistency.", "Needs structured decompression after labs."] },
  { id: "s2", counsellorId: "c1", name: "Nisha Patel", regNumber: "22EC2088", hostel: "Cedar Heights", year: "3rd Year", department: "Electronics", stressLevel: 41, wellbeing: { stress: 41, anxiety: 37, focus: 71, sleep: 73, mood: 74, resilience: 78 }, trends: [{ m: "Jan", stress: 59, anxiety: 48, focus: 61, mood: 62 }, { m: "Feb", stress: 49, anxiety: 42, focus: 65, mood: 70 }, { m: "Mar", stress: 44, anxiety: 40, focus: 68, mood: 72 }, { m: "Apr", stress: 41, anxiety: 37, focus: 71, mood: 74 }], heatmap: [44, 46, 39, 41, 42, 37, 36, 40, 43, 38, 35, 39, 42, 41], notes: ["Stable recovery pattern.", "Monitor during assessment cycles."] },
  { id: "s3", counsellorId: "c2", name: "Kabir Singh", regNumber: "24ME3012", hostel: "Oak Block", year: "1st Year", department: "Mechanical", stressLevel: 84, wellbeing: { stress: 84, anxiety: 88, focus: 34, sleep: 29, mood: 38, resilience: 44 }, trends: [{ m: "Jan", stress: 58, anxiety: 61, focus: 55, mood: 57 }, { m: "Feb", stress: 69, anxiety: 72, focus: 48, mood: 50 }, { m: "Mar", stress: 81, anxiety: 84, focus: 39, mood: 43 }, { m: "Apr", stress: 84, anxiety: 88, focus: 34, mood: 38 }], heatmap: [78, 82, 88, 85, 91, 79, 74, 83, 87, 90, 86, 88, 84, 81], notes: ["High volatility this month.", "Requires closer monitoring."] },
  { id: "s4", counsellorId: "c3", name: "Isha Verma", regNumber: "24AR0917", hostel: "Cedar Heights", year: "1st Year", department: "Architecture", stressLevel: 67, wellbeing: { stress: 67, anxiety: 63, focus: 52, sleep: 46, mood: 55, resilience: 60 }, trends: [{ m: "Jan", stress: 51, anxiety: 46, focus: 62, mood: 66 }, { m: "Feb", stress: 59, anxiety: 55, focus: 59, mood: 62 }, { m: "Mar", stress: 64, anxiety: 61, focus: 55, mood: 58 }, { m: "Apr", stress: 67, anxiety: 63, focus: 52, mood: 55 }], heatmap: [59, 61, 63, 66, 68, 71, 64, 60, 67, 69, 70, 66, 65, 68], notes: ["Creative fatigue before reviews.", "Sleep hygiene support recommended."] },
];

const appointments = [
  { id: "a1", counsellorId: "c1", studentId: "s1", date: "2026-04-05", time: "10:00 AM", status: "pending", urgency: "high", reason: "Panic episodes before lab evaluations" },
  { id: "a2", counsellorId: "c1", studentId: "s2", date: "2026-04-06", time: "02:30 PM", status: "upcoming", urgency: "medium", reason: "Routine monthly check-in" },
  { id: "a3", counsellorId: "c1", studentId: "s1", date: "2026-04-02", time: "11:00 AM", status: "completed", urgency: "medium", reason: "Stress management follow-up" },
  { id: "a4", counsellorId: "c2", studentId: "s3", date: "2026-04-04", time: "04:15 PM", status: "pending", urgency: "high", reason: "Acute anxiety support request" },
  { id: "a5", counsellorId: "c3", studentId: "s4", date: "2026-04-07", time: "03:00 PM", status: "upcoming", urgency: "high", reason: "Sleep disruption and review anxiety" },
];

const parameters = ["Communication", "Stress Response", "Mood Stability", "Engagement", "Focus", "Self-awareness", "Resilience", "Sleep Hygiene", "Academic Coping", "Social Support"];
const keys = { user: "mindtrack-user", sessions: "mindtrack-sessions" };

const state = {
  user: load(keys.user, null),
  route: { page: "login", studentId: null },
  filters: { search: "", hostel: "all", urgency: "all", status: "all", sort: "date-asc" },
  ratings: Object.fromEntries(parameters.map((p) => [p, 5])),
  comments: "",
  manualScore: "",
  toast: "",
};

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}

function save(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function sessions() {
  return load(keys.sessions, []);
}

function getStudent(id) {
  return students.find((s) => s.id === id);
}

function userAppointments() {
  if (!state.user) return [];
  return appointments.filter((a) => a.counsellorId === state.user.id).map((a) => ({ ...a, student: getStudent(a.studentId) }));
}

function risk(score) {
  if (score >= 80) return ["Critical", "#f26b8a"];
  if (score >= 65) return ["Watchlist", "#f0b54b"];
  if (score >= 45) return ["Stable", "#13a4ec"];
  return ["Healthy", "#3ca06d"];
}

function esc(v) {
  return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function toast(msg) {
  state.toast = msg;
  render();
  clearTimeout(toast.t);
  toast.t = setTimeout(() => { state.toast = ""; render(); }, 2600);
}

function parseRoute() {
  const hash = location.hash.replace("#", "");
  if (!state.user) {
    state.route = { page: "login", studentId: null };
    return;
  }
  if (!hash || hash === "dashboard") state.route = { page: "dashboard", studentId: null };
  else if (hash.startsWith("student/")) state.route = { page: "student", studentId: hash.split("/")[1] };
  else if (hash.startsWith("session/")) state.route = { page: "session", studentId: hash.split("/")[1] };
  else state.route = { page: "dashboard", studentId: null };
}

function go(path) {
  location.hash = path;
}

function metricCard(label, count, text, klass) {
  return `<article class="card ${klass}"><span class="pill dark">${label}</span><div class="metric">${count}</div><div class="mini">${text}</div><div class="progress"><span style="width:${Math.min(count * 22, 100)}%"></span></div></article>`;
}

function loginView() {
  return `<section class="login-screen">
    <div class="blob top-soft"></div><div class="blob right-ring"></div><div class="blob bottom-dot"></div>
    <div class="login-grid">
      <div class="login-card">
        <div class="login-top"><div><p class="login-kicker">MindTrack Counsellor Access</p><h1 class="login-title">Calm care,<br>clear signals.</h1><p class="login-subtitle">Secure access to wellbeing insights, appointment triage, and session evaluation.</p></div><div class="shield"><span class="material-symbols-outlined">shield_lock</span></div></div>
        <form id="login-form">
          <div class="form-group"><label class="form-label">Username</label><input class="input" name="username" placeholder="e.g. anika.rao"></div>
          <div class="form-group"><label class="form-label">Password</label><input class="input" type="password" name="password" placeholder="Enter secure password"></div>
          <div id="login-error" class="notice"></div>
          <div class="login-actions"><button class="btn-dark" type="submit">Login</button></div>
        </form>
        <div class="demo-box"><h4>Demo counsellor accounts</h4>${counsellors.map((c) => `<p><strong>${esc(c.name)}</strong> · ${esc(c.username)} / ${esc(c.password)}</p>`).join("")}</div>
      </div>
      <aside class="info-card">
        <div><p class="info-kicker">Student Mental Well-being Monitoring System</p><h2 style="margin:4px 0 0;font-size:clamp(46px,5.2vw,70px);line-height:.95;font-weight:500;letter-spacing:-.03em;">Early support.<br>Better outcomes.</h2><p class="desc">One console for appointment triage, student analytics, and structured counselling sessions.</p><div class="portal-grid"><div class="portal counsellor"><span class="material-symbols-outlined">monitor_heart</span><h5>Analytics</h5><p>Track emotional risk and recovery trends.</p></div><div class="portal student"><span class="material-symbols-outlined">calendar_month</span><h5>Scheduling</h5><p>Handle pending, upcoming, and completed sessions.</p></div><div class="portal admin"><span class="material-symbols-outlined">neurology</span><h5>Sessions</h5><p>Capture structured observations with clean scoring.</p></div><div class="portal warden"><span class="material-symbols-outlined">notifications_active</span><h5>Signals</h5><p>Respond quickly to high-urgency student needs.</p></div></div></div>
        <div><div class="trust-strip"><span class="material-symbols-outlined">encrypted</span>Mock authentication now, backend-ready structure later.</div></div>
      </aside>
    </div>
  </section>`;
}

function shell(content, active) {
  const user = state.user;
  const pending = userAppointments().filter((a) => a.status === "pending").length;
  return `<div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-badge"><span class="material-symbols-outlined">favorite</span></div><div><p class="brand-title">MindTrack</p><p class="brand-subtitle">Counsellor Console</p></div></div>
      <div class="nav">
        <a class="nav-link ${active === "dashboard" ? "active" : ""}" data-go="dashboard"><span><span class="material-symbols-outlined">space_dashboard</span> Dashboard</span><span>${pending}</span></a>
        <a class="nav-link ${active === "student" ? "active" : ""}" data-go="student/${students.find((s) => s.counsellorId === user.id)?.id || ""}"><span><span class="material-symbols-outlined">insights</span> Student Analytics</span></a>
        <a class="nav-link ${active === "session" ? "active" : ""}" data-go="session/${students.find((s) => s.counsellorId === user.id)?.id || ""}"><span><span class="material-symbols-outlined">clinical_notes</span> Session Evaluation</span></a>
      </div>
      <div class="profile-box"><div class="profile-avatar">${esc(user.initials)}</div><div><div>${esc(user.name)}</div><div class="brand-subtitle">${esc(user.specialty)}</div></div></div>
    </aside>
    <main class="main">
      <div class="privacy-strip"><span class="material-symbols-outlined">verified_user</span>Campus wellbeing data is visible only within counsellor workflows.</div>
      ${content}
    </main>
    ${state.toast ? `<div class="toast">${esc(state.toast)}</div>` : ""}
  </div>`;
}

function dashboardView() {
  const list = filteredAppointments();
  const all = userAppointments();
  const pending = all.filter((a) => a.status === "pending").length;
  const upcoming = all.filter((a) => a.status === "upcoming").length;
  const completed = all.filter((a) => a.status === "completed").length;
  return shell(`<header class="topbar"><div><h1 class="title">Appointments Dashboard</h1><p class="subtitle">Search, sort, and prioritize student requests for ${esc(state.user.name)}.</p></div><div class="top-controls"><span class="role-chip">${esc(state.user.specialty)}</span><button id="logout-btn" class="btn-dark">Logout</button></div></header>
    <div class="content">
      <section class="grid four">${metricCard("Pending", pending, "Need triage or response", "pastel-yellow")}${metricCard("Upcoming", upcoming, "Scheduled next-touch sessions", "pastel-blue")}${metricCard("Completed", completed, "Closed conversations", "pastel-green")}${metricCard("High urgency", all.filter((a) => a.urgency === "high").length, "Cases to prioritize today", "pastel-pink")}</section>
      <section class="card">
        <div class="section-head"><div><h3>Appointment Requests</h3><p class="mini">Filter by hostel, urgency, status, or student name.</p></div><span class="pill info">${list.length} results</span></div>
        <div class="filters-grid" style="margin-top:16px;">
          <label><span class="form-label">Search Student</span><input id="search" class="input" value="${esc(state.filters.search)}" placeholder="Name or registration number"></label>
          <label><span class="form-label">Hostel</span><select id="hostel" class="select">${["all", ...new Set(all.map((a) => a.student.hostel))].map((h) => `<option value="${h}" ${state.filters.hostel === h ? "selected" : ""}>${h === "all" ? "All hostels" : h}</option>`).join("")}</select></label>
          <label><span class="form-label">Urgency</span><select id="urgency" class="select">${enumOptions(["all", "low", "medium", "high"], state.filters.urgency)}</select></label>
          <label><span class="form-label">Sort</span><select id="sort" class="select"><option value="date-asc" ${state.filters.sort === "date-asc" ? "selected" : ""}>Soonest first</option><option value="date-desc" ${state.filters.sort === "date-desc" ? "selected" : ""}>Latest first</option><option value="stress-desc" ${state.filters.sort === "stress-desc" ? "selected" : ""}>Highest stress</option></select></label>
        </div>
        <div class="filters-row" style="margin-top:12px;"><label><span class="form-label">Status</span><select id="status" class="select">${enumOptions(["all", "pending", "upcoming", "completed"], state.filters.status)}</select></label><button id="reset-filters" class="btn-light">Reset filters</button></div>
        <table class="table" style="margin-top:18px;"><thead><tr><th>Student</th><th>Hostel</th><th>Reg. Number</th><th>Appointment</th><th>Urgency</th><th>Status</th></tr></thead><tbody>${list.map((a) => `<tr><td><a href="#student/${a.student.id}" class="student-link">${esc(a.student.name)}</a><div class="mini">${esc(a.reason)}</div></td><td>${esc(a.student.hostel)}</td><td>${esc(a.student.regNumber)}</td><td>${fmt(a.date)} · ${esc(a.time)}</td><td><span class="urgency-badge urgency-${a.urgency}">${a.urgency}</span></td><td><span class="status-badge status-${a.status}">${a.status}</span></td></tr>`).join("")}</tbody></table>
      </section>
    </div>`, "dashboard");
}

function studentView(studentId) {
  const s = getStudent(studentId) || students.find((x) => x.counsellorId === state.user.id);
  const recent = sessions().filter((x) => x.studentId === s.id).at(-1);
  const score = recent ? recent.stressScore : s.stressLevel;
  const [label, color] = risk(score);
  return shell(`<header class="topbar"><div><h1 class="title">Student Analytics & Info</h1><p class="subtitle">Mental well-being signals, trend lines, and intervention context.</p></div><div class="top-controls"><span class="role-chip">${esc(s.regNumber)}</span><button id="logout-btn" class="btn-dark">Logout</button></div></header>
    <div class="content">
      <section class="grid two">
        <div class="card student-hero-card"><div class="student-hero-glow"></div><div class="student-hero-layout"><div class="student-hero-copy"><span class="pill ${score >= 65 ? "warn" : "info"}">${label}</span><h3>${esc(s.name)}</h3><p class="mini">${esc(s.department)} · ${esc(s.year)} · ${esc(s.hostel)}</p><div class="student-hero-tags"><span class="tag">${esc(s.regNumber)}</span><span class="tag">${esc(s.hostel)}</span><span class="tag">${esc(s.department)}</span></div><div style="margin-top:20px;"><button data-go="session/${s.id}" class="btn-dark">Start Session</button></div></div><div class="battery-ring" style="--pct:${score};--tone:${color};"><div class="battery-ring-inner"><div><p>${score}</p><span>Stress Score</span></div></div></div></div></div>
        <div class="card"><div class="card-header-row"><h3>Student Profile</h3><span class="tag">${esc(state.user.name)}</span></div><div class="detail-list" style="margin-top:16px;"><div class="detail-item"><span>Registration Number</span><strong>${esc(s.regNumber)}</strong></div><div class="detail-item"><span>Hostel</span><strong>${esc(s.hostel)}</strong></div><div class="detail-item"><span>Department</span><strong>${esc(s.department)}</strong></div><div class="detail-item"><span>Year</span><strong>${esc(s.year)}</strong></div><div class="detail-item"><span>Risk Category</span><strong>${label}</strong></div></div><div style="margin-top:16px;"><p class="form-label">Counsellor Notes</p>${s.notes.map((n) => `<div class="mini">${esc(n)}</div>`).join("")}</div></div>
      </section>
      <section class="grid two">
        <div class="card"><div class="card-header-row"><h3>Mental Score Trends</h3><span class="pill dark">Last 4 months</span></div><svg class="trend-chart" viewBox="0 0 640 260">${trendSvg(s.trends)}</svg></div>
        <div class="card"><div class="card-header-row"><h3>Weekly Heatmap</h3><span class="pill info">Mood pressure intensity</span></div><div class="heatmap-labels"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div><div class="heatmap" style="margin-top:8px;">${s.heatmap.map((v) => `<div class="heat-cell" style="background:${heat(v)}" title="${v}"></div>`).join("")}</div></div>
      </section>
      <section class="grid two" id="heatmap-grid">${Object.entries(s.wellbeing).map(([k, v]) => `<article class="wellness-matrix-card"><div class="wellness-matrix-head"><div><h4>${cap(k)}</h4><p class="mini">${wellnessText(v)}</p></div><span class="pill ${v >= 65 ? "warn" : "info"}">${risk(v)[0]}</span></div><div class="wellness-matrix-score-row"><div class="wellness-matrix-score">${v}</div><div class="wellness-score-chip">/ 100</div></div><div style="margin-top:16px;"><div class="wellness-metric-label"><span>Current reading</span><strong>${v}%</strong></div><div class="wellness-meter"><span style="width:${v}%;background:${risk(v)[1]}"></span></div></div></article>`).join("")}</section>
    </div>`, "student");
}

function sessionView(studentId) {
  const s = getStudent(studentId) || students.find((x) => x.counsellorId === state.user.id);
  const total = Object.values(state.ratings).reduce((a, b) => a + Number(b), 0);
  return shell(`<header class="topbar"><div><h1 class="title">Session Evaluation</h1><p class="subtitle">Structured rating form with comments and auto-calculated total.</p></div><div class="top-controls"><span class="role-chip">${esc(s.name)}</span><button id="logout-btn" class="btn-dark">Logout</button></div></header>
    <div class="content">
      <section class="grid two">
        <div class="card dark"><div class="card-header-row"><h3>Live Session Score</h3><span class="tag">Auto-calculated</span></div><div class="metric">${total}<span style="font-size:26px;">/100</span></div><div class="mini" style="color:#d7deee;">Composite score updates as you move each slider.</div><div class="progress"><span style="width:${total}%;background:${risk(total)[1]}"></span></div></div>
        <div class="card"><div class="card-header-row"><h3>Session Guidance</h3><span class="pill info">1 to 10 scale</span></div><div class="mini">Lower scores indicate stronger support need on that parameter. You can optionally override the final score before saving.</div></div>
      </section>
      <form id="session-form" class="session-grid">${parameters.map((p) => `<div class="rating-card"><div class="rating-card-head"><div><strong>${p}</strong><div class="mini">${hint(p)}</div></div><span class="pill dark">${state.ratings[p]}/10</span></div><input class="slider" type="range" min="1" max="10" name="${p}" value="${state.ratings[p]}"><div class="slider-scale"><span>Needs support</span><span>Balanced</span><span>Strong</span></div></div>`).join("")}
        <section class="card"><div class="card-header-row"><h3>Observations</h3><span class="pill info">Required</span></div><div class="grid two" style="margin-top:14px;"><label><span class="form-label">Session Comments</span><textarea id="comments" class="textarea" rows="6" placeholder="Add short observations, triggers, and next-step notes.">${esc(state.comments)}</textarea></label><label><span class="form-label">Final Stress Score Override</span><input id="manual-score" class="input" type="number" min="1" max="100" value="${esc(state.manualScore)}" placeholder="Leave blank to use auto-calculated score"><div class="mini" style="margin-top:8px;">Optional override for clinical judgement.</div></label></div><div id="session-error" class="notice"></div><div class="session-footer" style="margin-top:16px;"><div class="mini">Saved records appear in analytics on this device through mock JSON persistence.</div><button class="btn-dark" type="submit">Submit Session</button></div></section>
      </form>
    </div>`, "session");
}

function enumOptions(items, current) {
  return items.map((i) => `<option value="${i}" ${current === i ? "selected" : ""}>${i === "all" ? "All" : cap(i)}</option>`).join("");
}

function filteredAppointments() {
  return userAppointments().filter((a) => {
    const q = state.filters.search.toLowerCase();
    const matchesSearch = !q || a.student.name.toLowerCase().includes(q) || a.student.regNumber.toLowerCase().includes(q);
    const matchesHostel = state.filters.hostel === "all" || a.student.hostel === state.filters.hostel;
    const matchesUrgency = state.filters.urgency === "all" || a.urgency === state.filters.urgency;
    const matchesStatus = state.filters.status === "all" || a.status === state.filters.status;
    return matchesSearch && matchesHostel && matchesUrgency && matchesStatus;
  }).sort((a, b) => {
    if (state.filters.sort === "date-desc") return (`${b.date} ${b.time}`).localeCompare(`${a.date} ${a.time}`);
    if (state.filters.sort === "stress-desc") return b.student.stressLevel - a.student.stressLevel;
    return (`${a.date} ${a.time}`).localeCompare(`${b.date} ${b.time}`);
  });
}

function fmt(date) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function cap(v) {
  return v.charAt(0).toUpperCase() + v.slice(1);
}

function heat(v) {
  if (v >= 80) return "linear-gradient(180deg,#f7a8b7,#f26b8a)";
  if (v >= 65) return "linear-gradient(180deg,#ffe5a4,#f4c35d)";
  if (v >= 45) return "linear-gradient(180deg,#d8ecff,#8ec6f5)";
  return "linear-gradient(180deg,#dff5e4,#95d5a6)";
}

function wellnessText(v) {
  if (v >= 80) return "High-alert range needing active intervention.";
  if (v >= 65) return "Needs close observation and support.";
  if (v >= 45) return "Manageable but should still be monitored.";
  return "Currently in a healthier range.";
}

function path(values, key, color) {
  const d = values.map((x, i) => `${i ? "L" : "M"} ${40 + i * 180} ${230 - x[key] * 2}`).join(" ");
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round"></path>`;
}

function trendSvg(values) {
  return `<rect x="0" y="0" width="640" height="260" rx="18" fill="#fff"></rect>
    ${[20, 40, 60, 80].map((v) => `<line x1="40" y1="${230 - v * 2}" x2="616" y2="${230 - v * 2}" stroke="#e8ebf1" stroke-dasharray="4 6"></line>`).join("")}
    ${path(values, "stress", "#f26b8a")}${path(values, "anxiety", "#13a4ec")}${path(values, "focus", "#3ca06d")}${path(values, "mood", "#9f7aea")}
    ${values.map((v, i) => `<text x="${40 + i * 180}" y="250" fill="#7b869b" font-size="12" text-anchor="middle">${v.m}</text>`).join("")}`;
}

function hint(p) {
  const map = {
    Communication: "Openness and clarity during the session.",
    "Stress Response": "Reaction while discussing current stressors.",
    "Mood Stability": "Observed emotional consistency.",
    Engagement: "Participation and willingness to collaborate.",
    Focus: "Ability to stay present and coherent.",
    "Self-awareness": "Insight into patterns and triggers.",
    Resilience: "Capacity to recover and adapt.",
    "Sleep Hygiene": "Rest quality and bedtime routine.",
    "Academic Coping": "Handling workload and deadlines.",
    "Social Support": "Access to supportive relationships.",
  };
  return map[p];
}

function bind() {
  const login = document.getElementById("login-form");
  if (login) login.addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(login);
    const user = counsellors.find((c) => c.username === fd.get("username") && c.password === fd.get("password"));
    const error = document.getElementById("login-error");
    if (!fd.get("username") || !fd.get("password")) return error.textContent = "Please enter both username and password.";
    if (!user) return error.textContent = "Invalid credentials. Use one of the demo counsellor accounts.";
    state.user = user;
    save(keys.user, user);
    toast(`Welcome back, ${user.name}.`);
    go("dashboard");
  });

  document.querySelectorAll("[data-go]").forEach((el) => el.addEventListener("click", () => go(el.dataset.go)));
  const logout = document.getElementById("logout-btn");
  if (logout) logout.addEventListener("click", () => { localStorage.removeItem(keys.user); state.user = null; render(); });

  ["search", "hostel", "urgency", "status", "sort"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener(id === "search" ? "input" : "change", () => { state.filters[id === "search" ? "search" : id] = el.value; render(); });
  });
  const reset = document.getElementById("reset-filters");
  if (reset) reset.addEventListener("click", () => { state.filters = { search: "", hostel: "all", urgency: "all", status: "all", sort: "date-asc" }; render(); });

  const form = document.getElementById("session-form");
  if (form) {
    form.addEventListener("input", (e) => {
      if (e.target.name && parameters.includes(e.target.name)) { state.ratings[e.target.name] = Number(e.target.value); render(); return; }
      if (e.target.id === "comments") state.comments = e.target.value;
      if (e.target.id === "manual-score") state.manualScore = e.target.value;
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const error = document.getElementById("session-error");
      if (!state.comments.trim()) return error.textContent = "Please add session observations before submitting.";
      const manual = state.manualScore.trim() ? Number(state.manualScore) : null;
      if (manual !== null && (Number.isNaN(manual) || manual < 1 || manual > 100)) return error.textContent = "Manual stress score must be between 1 and 100.";
      const records = sessions();
      records.push({ id: `sess-${Date.now()}`, studentId: state.route.studentId, counsellorId: state.user.id, ratings: { ...state.ratings }, comments: state.comments.trim(), stressScore: manual ?? Object.values(state.ratings).reduce((a, b) => a + Number(b), 0), submittedAt: new Date().toISOString() });
      save(keys.sessions, records);
      state.ratings = Object.fromEntries(parameters.map((p) => [p, 5]));
      state.comments = "";
      state.manualScore = "";
      toast("Session saved.");
      go(`student/${state.route.studentId}`);
    });
  }
}

function render() {
  parseRoute();
  const app = document.getElementById("app");
  app.innerHTML = !state.user ? loginView() : state.route.page === "student" ? studentView(state.route.studentId) : state.route.page === "session" ? sessionView(state.route.studentId) : dashboardView();
  bind();
}

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", () => {
  if (!location.hash) location.hash = state.user ? "#dashboard" : "#login";
  render();
});
