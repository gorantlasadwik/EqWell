const state = {
  currentView: "warden",
  students: [],
  activeStudent: null,
  counsellors: [],
  selectedSlotIso: null,
  charts: {},
};

const auth = {
  loggedIn: false,
  role: null,
  email: null,
};

const ROLE_CREDENTIALS = {
  student: { email: "student@eqwell.app", password: "student123" },
  warden: { email: "warden@eqwell.app", password: "warden123" },
  admin: { email: "admin@eqwell.app", password: "admin123" },
  counsellor: { email: "counsellor@eqwell.app", password: "counsellor123" },
};

const PAGE_META = {
  warden: {
    title: "Warden Dashboard",
    subtitle: "Hostel-level anonymized wellbeing insights and proactive alerts.",
  },
  student: {
    title: "Student Dashboard",
    subtitle: "Self-awareness, instant support, and burnout prevention.",
  },
  admin: {
    title: "Admin Dashboard",
    subtitle: "System control, event tuning, counsellor and report management.",
  },
  counsellor: {
    title: "Counsellor Dashboard",
    subtitle: "Daily schedule, queue prioritization, and availability controls.",
  },
  booking: {
    title: "Booking System",
    subtitle: "Slot booking, calendar scheduling, and auto suggestions for high stress.",
  },
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(payload.detail || "Request failed");
  }
  return response.json();
}

function notify(message) {
  const el = document.createElement("div");
  el.textContent = message;
  el.className = "fixed bottom-5 right-5 bg-sidebar text-white text-sm px-4 py-2 rounded-lg shadow-lg z-50";
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2200);
}

function setView(view) {
  if (auth.loggedIn && auth.role && view !== auth.role && view !== "booking") {
    notify(`Access restricted to ${auth.role} dashboard`);
    return;
  }
  state.currentView = view;
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `${view}-panel`);
  });
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.getElementById("page-title").textContent = PAGE_META[view].title;
  document.getElementById("page-subtitle").textContent = PAGE_META[view].subtitle;
}

function showLoginScreen() {
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app-shell").classList.add("hidden");
}

function showAppShell() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
}

function applyRoleAccess(role) {
  const controls = document.getElementById("header-controls");
  controls.classList.toggle("hidden", role === "student" || role === "counsellor");

  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("hidden", button.dataset.view !== role);
  });
}

function loginWithRole(role, email, password) {
  const expected = ROLE_CREDENTIALS[role];
  if (!expected) {
    return false;
  }
  return expected.email.toLowerCase() === email.toLowerCase() && expected.password === password;
}

function upsertChart(key, config) {
  if (state.charts[key]) {
    state.charts[key].destroy();
  }
  state.charts[key] = new Chart(config.ctx, config.options);
}

function renderBlockCards(blocks) {
  const holder = document.getElementById("block-cards");
  const colorClass = {
    High: "bg-pastel-pink",
    Moderate: "bg-pastel-yellow",
    Low: "bg-pastel-blue",
  };
  holder.innerHTML = blocks
    .map((item) => {
      const dist = item.distribution;
      return `
        <div class="${colorClass[item.category] || "bg-pastel-green"} rounded-2xl p-4 shadow-sm border border-white/50">
          <div class="flex items-center justify-between mb-2">
            <p class="font-bold">Block ${item.block}</p>
            <span class="text-xs font-semibold px-2 py-1 rounded-full bg-white/60">${item.category}</span>
          </div>
          <p class="text-3xl font-extrabold">${item.avg_stress_100}%</p>
          <p class="text-xs text-text-main/70 mt-1">Low ${dist.Low} | Moderate ${dist.Moderate} | High ${dist.High}</p>
        </div>
      `;
    })
    .join("");
}

function renderWardenCharts(data) {
  upsertChart("wardenHeatmap", {
    ctx: document.getElementById("warden-heatmap-chart"),
    options: {
      type: "bar",
      data: {
        labels: data.blocks.map((item) => item.block),
        datasets: [
          {
            label: "Stress Score",
            data: data.blocks.map((item) => item.avg_stress_100),
            borderRadius: 14,
            backgroundColor: ["#C4D8F2", "#F2C4CE", "#C4F2CD", "#F2E7C4", "#F2C4CE", "#C4F2CD"],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, max: 100 } },
      },
    },
  });

  upsertChart("wardenTrend", {
    ctx: document.getElementById("warden-trend-chart"),
    options: {
      type: "line",
      data: {
        labels: data.trend.labels,
        datasets: [
          {
            label: "Campus Stress",
            data: data.trend.values,
            borderColor: "#13a4ec",
            backgroundColor: "rgba(19,164,236,0.15)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, max: 100 } },
      },
    },
  });

  upsertChart("wardenMood", {
    ctx: document.getElementById("warden-mood-chart"),
    options: {
      type: "doughnut",
      data: {
        labels: ["Low", "Neutral", "Good"],
        datasets: [
          {
            data: [data.mood_distribution.low, data.mood_distribution.neutral, data.mood_distribution.good],
            backgroundColor: ["#F2C4CE", "#F2E7C4", "#C4F2CD"],
            borderWidth: 0,
          },
        ],
      },
      options: {
        plugins: { legend: { position: "bottom" } },
      },
    },
  });
}

async function loadWardenDashboard() {
  const data = await api("/api/warden/dashboard");
  renderBlockCards(data.blocks);

  document.getElementById("warden-factors").innerHTML = data.top_factors
    .map((item) => `<li class="rounded-lg bg-background-light p-2">${item.name}: ${item.percent}%</li>`)
    .join("");

  document.getElementById("warden-alerts").innerHTML = data.alerts
    .map((alert) => `<li class="rounded-lg bg-background-light p-2">${alert}</li>`)
    .join("");

  document.getElementById("warden-bookings-total").textContent = data.bookings.total;
  document.getElementById("warden-bookings-pending").textContent = data.bookings.pending;
  document.getElementById("warden-bookings-completed").textContent = data.bookings.completed;

  renderWardenCharts(data);
}

function renderStudentDashboard(data) {
  document.getElementById("student-score-1-5").textContent = data.stress.stress_1_5;
  document.getElementById("student-score-100").textContent = data.stress.stress_100;
  document.getElementById("student-category").textContent = data.stress.category;
  document.getElementById("mental-battery-value").textContent = `${data.mental_battery}%`;
  document.getElementById("mental-battery-bar").style.width = `${data.mental_battery}%`;
  document.getElementById("auto-booking-hint").classList.toggle("hidden", !data.auto_suggest_booking);

  upsertChart("studentTrend", {
    ctx: document.getElementById("student-trend-chart"),
    options: {
      type: "line",
      data: {
        labels: data.trend.map((point) => point.date),
        datasets: [
          {
            label: "Stress",
            data: data.trend.map((point) => point.stress_100),
            borderColor: "#1A1A1A",
            backgroundColor: "rgba(26,26,26,0.07)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, max: 100 } },
      },
    },
  });
}

async function loadStudentDashboard() {
  if (!state.activeStudent) {
    return;
  }
  const data = await api(`/api/student/${state.activeStudent}/dashboard`);
  renderStudentDashboard(data);
}

async function submitPulse(value) {
  await api(`/api/student/${state.activeStudent}/pulse`, {
    method: "POST",
    body: JSON.stringify({ mood_1_5: Number(value) }),
  });
  notify("Pulse submitted");
  await refreshAll();
}

async function submitQuiz() {
  const category = document.getElementById("quiz-category").value;
  const score = Number(document.getElementById("quiz-score").value);
  await api(`/api/student/${state.activeStudent}/quiz`, {
    method: "POST",
    body: JSON.stringify({ category, score_1_5: score }),
  });
  notify("Quiz signal submitted");
  await refreshAll();
}

async function submitCounsellorSignal() {
  const counsellor_name = document.getElementById("counsellor-name").value;
  const rating_1_5 = Number(document.getElementById("counsellor-rating").value);
  const note = document.getElementById("counsellor-note").value;
  await api(`/api/student/${state.activeStudent}/counsellor`, {
    method: "POST",
    body: JSON.stringify({ counsellor_name, rating_1_5, note }),
  });
  document.getElementById("counsellor-note").value = "";
  notify("Counsellor signal recorded");
  await refreshAll();
}

async function submitVent() {
  const text = document.getElementById("vent-text").value.trim();
  if (!text) {
    notify("Enter vent text first");
    return;
  }
  const result = await api(`/api/student/${state.activeStudent}/vent`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  document.getElementById("vent-topic").textContent = result.topic;
  document.getElementById("vent-stress").textContent = result.stress_1_5;
  document.getElementById("vent-text").value = "";
  notify("Vent analyzed. Raw text not stored.");
  await refreshAll();
}

function renderAdminStats(data) {
  document.getElementById("admin-students").textContent = data.stats.students;
  document.getElementById("admin-counsellors").textContent = data.stats.active_counsellors;
  document.getElementById("admin-avg-stress").textContent = `${data.stats.avg_stress_100}%`;
  document.getElementById("admin-high-risk").textContent = data.stats.high_risk_students;

  const counsellorList = document.getElementById("admin-counsellor-list");
  counsellorList.innerHTML = data.counsellors
    .map((c) => `
      <div class="rounded-xl bg-background-light p-3 flex items-center justify-between">
        <div>
          <p class="font-semibold">${c.name}</p>
          <p class="text-xs text-text-muted">Next slot: ${c.next_slot}</p>
        </div>
        <button class="toggle-counsellor px-3 py-1 rounded-full text-xs font-semibold ${c.available ? "bg-pastel-green" : "bg-pastel-pink"}" data-name="${c.name}" data-available="${c.available}">
          ${c.available ? "Available" : "Busy"}
        </button>
      </div>
    `)
    .join("");

  const labels = Object.keys(data.block_report);
  const values = labels.map((label) => data.block_report[label]);
  upsertChart("adminBlock", {
    ctx: document.getElementById("admin-block-chart"),
    options: {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: "#13a4ec",
            borderRadius: 10,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, max: 100 } },
      },
    },
  });

  document.getElementById("event-log").innerHTML = data.events
    .map((eventItem) => `<li class="rounded-lg bg-background-light p-2">${eventItem.name} | scope ${eventItem.scope} | bias ${eventItem.bias}</li>`)
    .join("");

  document.querySelectorAll(".toggle-counsellor").forEach((button) => {
    button.addEventListener("click", async () => {
      const name = button.dataset.name;
      const current = button.dataset.available === "true";
      await api(`/api/counsellors/${encodeURIComponent(name)}/availability`, {
        method: "PUT",
        body: JSON.stringify({ available: !current }),
      });
      notify(`Updated ${name} availability`);
      await refreshAll();
    });
  });
}

async function loadAdminDashboard() {
  const data = await api("/api/admin/dashboard");
  state.counsellors = data.counsellors;
  renderAdminStats(data);
}

function renderCounsellorDashboard(data) {
  const scheduleBody = document.getElementById("counsellor-schedule");
  scheduleBody.innerHTML = data.schedule
    .map(
      (row) => `
      <tr class="border-b border-border-color">
        <td class="py-2">${row.booking_id}</td>
        <td class="py-2">${row.anon_id}</td>
        <td class="py-2">${new Date(row.slot_time).toLocaleString()}</td>
        <td class="py-2">${row.status}</td>
      </tr>
    `
    )
    .join("");

  document.getElementById("counsellor-queue").innerHTML = data.queue
    .map((item) => `<li class="rounded-lg bg-background-light p-2">${item.anon_id} | ${item.topic} | ${item.stress} (${item.score}%)</li>`)
    .join("");

  document.getElementById("counsellor-availability").innerHTML = data.availability
    .map(
      (item) => `
      <div class="rounded-xl bg-background-light p-3 flex items-center justify-between">
        <div>
          <p class="font-semibold">${item.name}</p>
          <p class="text-xs text-text-muted">${item.next_slot}</p>
        </div>
        <span class="px-2 py-1 rounded-full text-xs font-semibold ${item.available ? "bg-pastel-green" : "bg-pastel-pink"}">
          ${item.available ? "Available" : "Busy"}
        </span>
      </div>
    `
    )
    .join("");

  const counsellorSelect = document.getElementById("booking-counsellor");
  counsellorSelect.innerHTML = data.availability
    .map((item) => `<option value="${item.name}">${item.name} (${item.available ? "Available" : "Busy"})</option>`)
    .join("");

  const counsellorNameSelect = document.getElementById("counsellor-name");
  counsellorNameSelect.innerHTML = data.availability
    .map((item) => `<option value="${item.name}">${item.name}</option>`)
    .join("");
}

async function loadCounsellorDashboard() {
  const data = await api("/api/counsellor/dashboard");
  renderCounsellorDashboard(data);
}

function renderBookingData(data) {
  document.getElementById("booking-total").textContent = data.counts.total;
  document.getElementById("booking-pending").textContent = data.counts.pending;
  document.getElementById("booking-completed").textContent = data.counts.completed;

  document.getElementById("booking-table").innerHTML = data.bookings
    .map(
      (b) => `
      <tr class="border-b border-border-color">
        <td class="py-2">${b.booking_id}</td>
        <td class="py-2">${b.anon_id}</td>
        <td class="py-2">${b.counsellor}</td>
        <td class="py-2">${new Date(b.slot_time).toLocaleString()}</td>
        <td class="py-2">${b.status}</td>
      </tr>
    `
    )
    .join("");
}

async function loadBookings() {
  const data = await api("/api/bookings");
  renderBookingData(data);
}

async function loadSlots() {
  const day = document.getElementById("booking-date").value;
  if (!day) {
    notify("Select a date first");
    return;
  }
  const data = await api(`/api/bookings/slots?target_date=${day}`);
  const holder = document.getElementById("slot-container");
  holder.innerHTML = data.slots
    .map((slot) => {
      const cls = slot.available ? "bg-pastel-blue hover:brightness-95 cursor-pointer" : "bg-gray-100 text-gray-400 cursor-not-allowed";
      return `<button class="slot-btn px-3 py-2 rounded-full text-sm font-semibold ${cls}" data-iso="${slot.iso}" ${slot.available ? "" : "disabled"}>${slot.label}</button>`;
    })
    .join("");

  document.querySelectorAll(".slot-btn:not([disabled])").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedSlotIso = button.dataset.iso;
      document.querySelectorAll(".slot-btn").forEach((btn) => btn.classList.remove("ring-2", "ring-primary"));
      button.classList.add("ring-2", "ring-primary");
    });
  });
}

async function createBooking() {
  if (!state.selectedSlotIso) {
    notify("Select a slot first");
    return;
  }
  const anon_id = document.getElementById("booking-student").value;
  const counsellor_name = document.getElementById("booking-counsellor").value;

  await api("/api/bookings", {
    method: "POST",
    body: JSON.stringify({ anon_id, counsellor_name, slot_time_iso: state.selectedSlotIso }),
  });
  notify("Booking created");
  state.selectedSlotIso = null;
  await refreshAll();
}

async function addEventSignal() {
  const name = document.getElementById("event-name").value.trim();
  const bias = Number(document.getElementById("event-bias").value);
  const scope = document.getElementById("event-scope").value;
  if (!name) {
    notify("Event name is required");
    return;
  }
  await api("/api/events", {
    method: "POST",
    body: JSON.stringify({ name, bias, scope }),
  });
  document.getElementById("event-name").value = "";
  notify("Event signal added");
  await refreshAll();
}

async function loadStudents() {
  const payload = await api("/api/students");
  state.students = payload.students;

  if (!state.activeStudent && state.students.length > 0) {
    state.activeStudent = state.students[0].anon_id;
  }

  const studentSelect = document.getElementById("student-select");
  const bookingStudent = document.getElementById("booking-student");

  studentSelect.innerHTML = state.students
    .map((s) => `<option value="${s.anon_id}">${s.anon_id} (${s.block})</option>`)
    .join("");
  studentSelect.value = state.activeStudent;

  bookingStudent.innerHTML = state.students
    .map((s) => `<option value="${s.anon_id}">${s.anon_id}</option>`)
    .join("");
  bookingStudent.value = state.activeStudent;
}

async function refreshAll() {
  await Promise.all([
    loadWardenDashboard(),
    loadStudentDashboard(),
    loadAdminDashboard(),
    loadCounsellorDashboard(),
    loadBookings(),
  ]);
}

function attachEvents() {
  document.getElementById("login-form").addEventListener("submit", (event) => {
    event.preventDefault();

    const role = document.getElementById("login-role").value;
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const errorEl = document.getElementById("login-error");

    if (!loginWithRole(role, email, password)) {
      errorEl.classList.remove("hidden");
      return;
    }

    errorEl.classList.add("hidden");
    auth.loggedIn = true;
    auth.role = role;
    auth.email = email;

    applyRoleAccess(role);
    showAppShell();
    setView(role);
    notify(`${role.charAt(0).toUpperCase() + role.slice(1)} logged in`);
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    auth.loggedIn = false;
    auth.role = null;
    auth.email = null;
    document.getElementById("login-password").value = "";
    showLoginScreen();
  });

  document.querySelectorAll(".nav-link").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  document.getElementById("refresh-all").addEventListener("click", refreshAll);

  document.getElementById("student-select").addEventListener("change", (event) => {
    state.activeStudent = event.target.value;
    document.getElementById("booking-student").value = state.activeStudent;
    loadStudentDashboard().catch((error) => notify(error.message));
  });

  document.querySelectorAll(".pulse-btn").forEach((button) => {
    button.addEventListener("click", () => {
      submitPulse(button.dataset.value).catch((error) => notify(error.message));
    });
  });

  document.getElementById("submit-quiz").addEventListener("click", () => {
    submitQuiz().catch((error) => notify(error.message));
  });

  document.getElementById("submit-counsellor").addEventListener("click", () => {
    submitCounsellorSignal().catch((error) => notify(error.message));
  });

  document.getElementById("submit-vent").addEventListener("click", () => {
    submitVent().catch((error) => notify(error.message));
  });

  document.getElementById("jump-booking").addEventListener("click", () => {
    setView("booking");
  });

  document.getElementById("add-event").addEventListener("click", () => {
    addEventSignal().catch((error) => notify(error.message));
  });

  document.getElementById("load-slots").addEventListener("click", () => {
    loadSlots().catch((error) => notify(error.message));
  });

  document.getElementById("slot-container").addEventListener("dblclick", () => {
    createBooking().catch((error) => notify(error.message));
  });
}

async function bootstrap() {
  const today = new Date();
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  document.getElementById("booking-date").value = tomorrow.toISOString().slice(0, 10);

  attachEvents();
  await loadStudents();
  await refreshAll();
  await loadSlots();
  showLoginScreen();
}

bootstrap().catch((error) => notify(error.message));
