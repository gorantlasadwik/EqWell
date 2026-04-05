const DEMO_CREDENTIALS = {
  username: "developer@wellnest",
  password: "WellNest2026",
};

const state = {
  session: {
    developerName: "Aarav Dev",
    environment: "production",
    loggedIn: false,
  },
  currentView: "overview",
  currentUserTab: "students",
  userFilters: {
    search: "",
    type: "all",
    sort: "name-asc",
  },
  quizFilters: {
    search: "",
    sort: "title-asc",
  },
  data: {
    students: [
      { id: 1, name: "Aanya Kapoor", email: "aanya.k@wellnest.edu", meta: "Maple Hostel", regNumber: "STU-2401", status: "Active" },
      { id: 2, name: "Ritvik Sen", email: "ritvik.s@wellnest.edu", meta: "Cedar Hostel", regNumber: "STU-2402", status: "Review" },
      { id: 3, name: "Mira Nair", email: "mira.n@wellnest.edu", meta: "Elm Hostel", regNumber: "STU-2403", status: "Active" },
      { id: 4, name: "Dhruv Mehta", email: "dhruv.m@wellnest.edu", meta: "Pine Hostel", regNumber: "STU-2404", status: "Offline" },
    ],
    counsellors: [
      { id: 101, name: "Dr. Sana Ali", email: "sana.ali@wellnest.edu", meta: "Anxiety & Resilience", regNumber: "COU-1101", status: "Active" },
      { id: 102, name: "Rahul Joseph", email: "rahul.j@wellnest.edu", meta: "Peer Well-being", regNumber: "COU-1102", status: "Active" },
      { id: 103, name: "Dr. Meera Das", email: "meera.d@wellnest.edu", meta: "Trauma Support", regNumber: "COU-1103", status: "Review" },
    ],
    wardens: [
      { id: 201, name: "Priya Menon", email: "priya.m@wellnest.edu", meta: "Lotus Block", regNumber: "WAR-5001", status: "Active" },
      { id: 202, name: "Arjun Rao", email: "arjun.r@wellnest.edu", meta: "Riverfront Block", regNumber: "WAR-5002", status: "Active" },
      { id: 203, name: "Neha Bhat", email: "neha.b@wellnest.edu", meta: "North Residence", regNumber: "WAR-5003", status: "Offline" },
    ],
    quizzes: buildStudentQuizSeed(),
    notifications: [
      { id: 1, title: "2 new students onboarded", text: "Fresh registrations landed from Maple and Cedar hostels.", time: "Just now" },
      { id: 2, title: "Quiz review flagged", text: "Burnout Early Signal has a pending content QA note.", time: "18 min ago" },
      { id: 3, title: "Counsellor capacity updated", text: "Dr. Sana Ali opened 4 additional support slots.", time: "1 hr ago" },
    ],
    sessionLog: [
      { id: 1, title: "Dashboard initialized", text: "Mock records loaded successfully for local developer mode.", time: "Session start" },
    ],
  },
};

const elements = {};

function buildStudentQuizSeed() {
  return [
    {
      id: 801,
      title: "MindBalance Check",
      category: "Depression-focused",
      frequency: "On demand",
      badge: "Serious Track",
      questions: [
        { id: 1, text: "Waiting for synced serious dataset from student dashboard.", type: "Dataset" },
      ],
    },
    {
      id: 802,
      title: "CalmPulse Assessment",
      category: "Anxiety detection",
      frequency: "On demand",
      badge: "Serious Track",
      questions: [
        { id: 1, text: "Waiting for synced serious dataset from student dashboard.", type: "Dataset" },
      ],
    },
    {
      id: 803,
      title: "StressLoad Analyzer",
      category: "Stress and burnout",
      frequency: "On demand",
      badge: "Serious Track",
      questions: [
        { id: 1, text: "Waiting for synced serious dataset from student dashboard.", type: "Dataset" },
      ],
    },
    {
      id: 804,
      title: "SocialConnect Index",
      category: "Isolation and loneliness",
      frequency: "On demand",
      badge: "Serious Track",
      questions: [
        { id: 1, text: "Waiting for synced serious dataset from student dashboard.", type: "Dataset" },
      ],
    },
    {
      id: 805,
      title: "Fruit Persona Quiz",
      category: "Personality type",
      frequency: "On demand",
      badge: "Fun Quiz",
      questions: [
        { id: 1, text: "Waiting for synced casual dataset from student dashboard.", type: "Dataset" },
      ],
    },
    {
      id: 806,
      title: "VibeCheck Lite",
      category: "Daily mood and fun check",
      frequency: "External",
      badge: "External Quiz",
      questions: [
        { id: 1, text: "This quiz is hosted externally in the student dashboard via Smore.", type: "External" },
      ],
    },
  ];
}

async function loadIntegratedQuizzes() {
  try {
    const [seriousResponse, casualResponse] = await Promise.all([
      fetch("../student/serious.txt"),
      fetch("../student/casual.txt"),
    ]);

    if (!seriousResponse.ok || !casualResponse.ok) {
      throw new Error("Quiz datasets unavailable");
    }

    const [seriousText, casualText] = await Promise.all([
      seriousResponse.text(),
      casualResponse.text(),
    ]);

    const seriousQuestions = parseQuestionLines(seriousText);
    const casualQuestions = parseQuestionLines(casualText);

    state.data.quizzes = [
      createQuizFromBank(801, "MindBalance Check", "Depression-focused", "Serious Track", seriousQuestions.slice(0, 25)),
      createQuizFromBank(802, "CalmPulse Assessment", "Anxiety detection", "Serious Track", seriousQuestions.slice(25, 50)),
      createQuizFromBank(803, "StressLoad Analyzer", "Stress and burnout", "Serious Track", seriousQuestions.slice(50, 75)),
      createQuizFromBank(804, "SocialConnect Index", "Isolation and loneliness", "Serious Track", seriousQuestions.slice(75, 100)),
      createQuizFromBank(805, "Fruit Persona Quiz", "Personality type", "Fun Quiz", casualQuestions),
      {
        id: 806,
        title: "VibeCheck Lite",
        category: "Daily mood and fun check",
        frequency: "External",
        badge: "External Quiz",
        questions: [
          { id: 1, text: "External student quiz link: https://smore.im/quiz/1LUFTQ0t36?tm=52907f54", type: "External" },
        ],
      },
    ];

    pushSessionLog("Quiz bank synced", `Imported ${seriousQuestions.length} serious and ${casualQuestions.length} casual questions from the student dashboard.`);
    renderAll();
  } catch (error) {
    pushSessionLog("Quiz sync fallback", "Student quiz datasets could not be fetched, so the dashboard is showing catalog placeholders.");
    renderAll();
  }
}

function createQuizFromBank(id, title, category, badge, questions) {
  return {
    id,
    title,
    category,
    frequency: "On demand",
    badge,
    questions: questions.map((text, index) => ({
      id: index + 1,
      text,
      type: "Yes / No",
    })),
  };
}

function parseQuestionLines(rawText) {
  return rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) =>
      line
        .replace(/[“”]/g, "\"")
        .replace(/[’]/g, "'")
        .replace(/[•]/g, "-")
    );
}

document.addEventListener("DOMContentLoaded", () => {
  captureElements();
  bindEvents();
  syncShellVisibility();
  renderAll();
  loadIntegratedQuizzes();
});

function captureElements() {
  const ids = [
    "login-screen", "dashboard-shell", "login-form", "login-error", "username", "password", "environment",
    "developer-name-top", "developer-name-sidebar", "profile-avatar", "notification-count", "activity-list",
    "distribution-bars", "recent-records", "user-table-body", "user-search", "user-type-filter", "user-sort",
    "quiz-search", "quiz-sort", "quiz-grid", "view-title", "view-subtitle", "sidebar-nav", "user-tabs",
    "stat-students", "stat-counsellors", "stat-wardens", "stat-quizzes", "overview-engagement", "overview-risk",
    "overview-load", "analytics-bars", "donut-row", "session-timeline", "logout-btn",
    "add-user-btn", "add-quiz-btn", "user-modal", "quiz-modal", "question-modal", "user-form", "quiz-form",
    "question-form", "user-modal-title", "quiz-modal-title", "question-modal-title", "user-id", "user-name",
    "user-email", "user-category", "user-reg", "user-meta", "user-status", "user-form-error", "quiz-id",
    "quiz-title-input", "quiz-category-input", "quiz-frequency-input", "quiz-badge-input", "quiz-form-error",
    "question-id", "question-quiz-id", "question-text", "question-type", "question-form-error"
  ];

  ids.forEach((id) => {
    elements[id] = document.getElementById(id);
  });
}

function bindEvents() {
  elements["login-form"].addEventListener("submit", handleLogin);
  elements["logout-btn"].addEventListener("click", handleLogout);
  elements["add-user-btn"].addEventListener("click", () => openUserModal(state.currentUserTab));
  elements["add-quiz-btn"].addEventListener("click", () => openQuizModal());

  elements["sidebar-nav"].addEventListener("click", (event) => {
    const link = event.target.closest("[data-view]");
    if (!link) return;
    event.preventDefault();
    switchView(link.dataset.view);
  });

  elements["user-tabs"].addEventListener("click", (event) => {
    const tab = event.target.closest("[data-user-view]");
    if (!tab) return;
    state.currentUserTab = tab.dataset.userView;
    renderUserTabs();
    renderUserTable();
  });

  elements["user-search"].addEventListener("input", (event) => {
    state.userFilters.search = event.target.value.trim().toLowerCase();
    renderUserTable();
  });

  elements["user-type-filter"].addEventListener("change", (event) => {
    state.userFilters.type = event.target.value;
    renderUserTable();
  });

  elements["user-sort"].addEventListener("change", (event) => {
    state.userFilters.sort = event.target.value;
    renderUserTable();
  });

  elements["quiz-search"].addEventListener("input", (event) => {
    state.quizFilters.search = event.target.value.trim().toLowerCase();
    renderQuizGrid();
  });

  elements["quiz-sort"].addEventListener("change", (event) => {
    state.quizFilters.sort = event.target.value;
    renderQuizGrid();
  });

  elements["user-form"].addEventListener("submit", submitUserForm);
  elements["quiz-form"].addEventListener("submit", submitQuizForm);
  elements["question-form"].addEventListener("submit", submitQuestionForm);
  document.body.addEventListener("click", handleGlobalClick);
}

function handleLogin(event) {
  event.preventDefault();
  const username = elements.username.value.trim();
  const password = elements.password.value.trim();

  if (!username || !password) {
    return showNotice(elements["login-error"], "Please enter both username and password.");
  }

  if (username !== DEMO_CREDENTIALS.username || password !== DEMO_CREDENTIALS.password) {
    return showNotice(elements["login-error"], "Invalid credentials. Use the demo login shown below the form.");
  }

  hideNotice(elements["login-error"]);
  state.session.loggedIn = true;
  state.session.environment = elements.environment.value;
  syncShellVisibility();
  renderAll();
}

function handleLogout() {
  state.session.loggedIn = false;
  elements.password.value = "";
  syncShellVisibility();
}

function switchView(view) {
  state.currentView = view;
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `view-${view}`);
  });

  const meta = {
    overview: ["Overview", "Track platform health, staffing balance, and content readiness."],
    users: ["Users", "Manage students, counsellors, and wardens with searchable records."],
    quizzes: ["Quizzes", "Control assessment journeys and question banks with live previews."],
    analytics: ["Analytics", "Scan role distribution, content volume, and operational movement."],
  };

  elements["view-title"].textContent = meta[view][0];
  elements["view-subtitle"].textContent = meta[view][1];
}

function renderAll() {
  renderSessionMeta();
  renderStats();
  renderNotifications();
  renderOverview();
  renderUserTabs();
  renderUserTable();
  renderQuizGrid();
  renderAnalytics();
}

function renderSessionMeta() {
  elements["developer-name-top"].textContent = `${state.session.developerName} · ${capitalize(state.session.environment)}`;
  elements["developer-name-sidebar"].textContent = state.session.developerName;
  elements["profile-avatar"].textContent = initials(state.session.developerName);
  elements["notification-count"].textContent = String(state.data.notifications.length);
}

function renderStats() {
  elements["stat-students"].textContent = state.data.students.length;
  elements["stat-counsellors"].textContent = state.data.counsellors.length;
  elements["stat-wardens"].textContent = state.data.wardens.length;
  elements["stat-quizzes"].textContent = state.data.quizzes.length;
}

function renderNotifications() {
  elements["activity-list"].innerHTML = state.data.notifications
    .map((item) => `
      <article class="activity-item">
        <div class="activity-item-top">
          <strong>${escapeHtml(item.title)}</strong>
          <span class="tag">${escapeHtml(item.time)}</span>
        </div>
        <p>${escapeHtml(item.text)}</p>
      </article>
    `)
    .join("");
}

function renderOverview() {
  const totalUsers = state.data.students.length + state.data.counsellors.length + state.data.wardens.length;
  const watchlist = [...state.data.students, ...state.data.counsellors, ...state.data.wardens].filter((item) => item.status === "Review").length;
  const avgLoad = (state.data.students.length / Math.max(state.data.counsellors.length, 1)).toFixed(1);

  elements["overview-engagement"].textContent = `${Math.min(99, 72 + state.data.quizzes.length * 4)}%`;
  elements["overview-risk"].textContent = watchlist;
  elements["overview-load"].textContent = avgLoad;

  const bars = [
    { label: "Students", value: state.data.students.length, color: "#8aa8d6" },
    { label: "Counsellors", value: state.data.counsellors.length, color: "#d99bb0" },
    { label: "Wardens", value: state.data.wardens.length, color: "#d9c27a" },
    { label: "Quizzes", value: state.data.quizzes.length, color: "#8bc69a" },
  ];
  const maxValue = Math.max(...bars.map((bar) => bar.value), 1);

  elements["distribution-bars"].innerHTML = bars
    .map((bar) => `
      <div class="bar-card">
        <div class="bar-label-row">
          <strong>${bar.label}</strong>
          <span class="mini">${bar.value}</span>
        </div>
        <div class="bar-track"><span style="width:${(bar.value / maxValue) * 100}%;background:${bar.color};"></span></div>
      </div>
    `)
    .join("");

  const recent = [
    ...state.data.students.slice(-2).map((item) => ({ title: item.name, text: `Student added to ${item.meta}` })),
    ...state.data.quizzes.slice(-2).map((item) => ({ title: item.title, text: `${item.questions.length} questions in ${item.category}` })),
  ].slice(-4).reverse();

  elements["recent-records"].innerHTML = recent
    .map((record) => `
      <article class="record-item">
        <div class="record-item-top">
          <strong>${escapeHtml(record.title)}</strong>
          <span class="pill info">Recent</span>
        </div>
        <p>${escapeHtml(record.text)}</p>
      </article>
    `)
    .join("");
}

function renderUserTabs() {
  document.querySelectorAll(".type-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.userView === state.currentUserTab);
  });
}

function getFilteredUsers() {
  const allUsers = ["students", "counsellors", "wardens"].flatMap((type) =>
    state.data[type].map((item) => ({
      ...item,
      type,
      typeLabel: singularLabel(type),
    }))
  );

  const base = state.userFilters.type === "all"
    ? allUsers.filter((item) => item.type === state.currentUserTab)
    : allUsers.filter((item) => item.type === state.userFilters.type);

  const query = state.userFilters.search;
  const filtered = base.filter((item) => {
    const haystack = `${item.name} ${item.email} ${item.meta} ${item.regNumber}`.toLowerCase();
    return haystack.includes(query);
  });

  return filtered.sort((a, b) => {
    switch (state.userFilters.sort) {
      case "name-desc":
        return b.name.localeCompare(a.name);
      case "type-asc":
        return a.typeLabel.localeCompare(b.typeLabel) || a.name.localeCompare(b.name);
      default:
        return a.name.localeCompare(b.name);
    }
  });
}

function renderUserTable() {
  const data = getFilteredUsers();

  if (!data.length) {
    elements["user-table-body"].innerHTML = `
      <tr>
        <td colspan="6"><div class="empty-state">No users match the current search and filter settings.</div></td>
      </tr>
    `;
    return;
  }

  elements["user-table-body"].innerHTML = data
    .map((user) => `
      <tr>
        <td><strong>${escapeHtml(user.name)}</strong><br /><span class="mini">${escapeHtml(user.typeLabel)}</span></td>
        <td>${escapeHtml(user.email)}</td>
        <td>${escapeHtml(user.meta)}</td>
        <td>${escapeHtml(user.regNumber)}</td>
        <td>${renderStatus(user.status)}</td>
        <td>
          <div class="row-actions">
            <button class="ghost-btn" type="button" data-action="edit-user" data-type="${user.type}" data-id="${user.id}">Edit</button>
            <button class="ghost-btn" type="button" data-action="delete-user" data-type="${user.type}" data-id="${user.id}">Delete</button>
          </div>
        </td>
      </tr>
    `)
    .join("");
}

function getFilteredQuizzes() {
  const query = state.quizFilters.search;
  const quizzes = state.data.quizzes.filter((quiz) => {
    const haystack = `${quiz.title} ${quiz.category}`.toLowerCase();
    return haystack.includes(query);
  });

  return quizzes.sort((a, b) => {
    switch (state.quizFilters.sort) {
      case "title-desc":
        return b.title.localeCompare(a.title);
      case "questions-desc":
        return b.questions.length - a.questions.length;
      default:
        return a.title.localeCompare(b.title);
    }
  });
}

function renderQuizGrid() {
  const quizzes = getFilteredQuizzes();

  if (!quizzes.length) {
    elements["quiz-grid"].innerHTML = `<div class="empty-state">No quizzes match the current search.</div>`;
    return;
  }

  elements["quiz-grid"].innerHTML = quizzes
    .map((quiz) => `
      <article class="quiz-card">
        <div class="quiz-card-head">
          <div>
            <h4>${escapeHtml(quiz.title)}</h4>
            <p class="mini">${escapeHtml(quiz.category)} · ${escapeHtml(quiz.frequency)}</p>
            <div class="quiz-meta">
              <span class="pill info">${escapeHtml(quiz.badge)}</span>
              <span class="tag">${quiz.questions.length} questions</span>
            </div>
          </div>
          <div class="row-actions">
            <button class="ghost-btn" type="button" data-action="edit-quiz" data-id="${quiz.id}">Edit</button>
            <button class="ghost-btn" type="button" data-action="delete-quiz" data-id="${quiz.id}">Delete</button>
            <button class="ghost-btn" type="button" data-action="add-question" data-id="${quiz.id}">Add Question</button>
          </div>
        </div>
        <div class="question-list">
          ${quiz.questions.map((question) => `
            <div class="question-row">
              <div>
                <div class="question-type">${escapeHtml(question.type)}</div>
                <p>${escapeHtml(question.text)}</p>
              </div>
              <div class="row-actions">
                <button class="ghost-btn" type="button" data-action="edit-question" data-quiz-id="${quiz.id}" data-question-id="${question.id}">Edit</button>
                <button class="ghost-btn" type="button" data-action="delete-question" data-quiz-id="${quiz.id}" data-question-id="${question.id}">Delete</button>
              </div>
            </div>
          `).join("")}
        </div>
      </article>
    `)
    .join("");
}

function renderAnalytics() {
  const bars = [
    { label: "Students", value: state.data.students.length, color: "#8aa8d6" },
    { label: "Counsellors", value: state.data.counsellors.length, color: "#d99bb0" },
    { label: "Wardens", value: state.data.wardens.length, color: "#d9c27a" },
    { label: "Quizzes", value: state.data.quizzes.length, color: "#8bc69a" },
  ];
  const maxValue = Math.max(...bars.map((bar) => bar.value), 1);

  elements["analytics-bars"].innerHTML = bars
    .map((bar) => `
      <div class="bar-card">
        <div class="bar-label-row">
          <strong>${bar.label}</strong>
          <span class="mini">${bar.value}</span>
        </div>
        <div class="bar-track"><span style="width:${(bar.value / maxValue) * 100}%;background:${bar.color};"></span></div>
      </div>
    `)
    .join("");

  const totalUsers = state.data.students.length + state.data.counsellors.length + state.data.wardens.length;
  const donutData = [
    { label: "Students", count: state.data.students.length, color: "#8aa8d6" },
    { label: "Counsellors", count: state.data.counsellors.length, color: "#d99bb0" },
    { label: "Wardens", count: state.data.wardens.length, color: "#d9c27a" },
  ];

  elements["donut-row"].innerHTML = donutData
    .map((item) => `
      <div class="donut-item">
        <div class="donut-item-head">
          <div>
            <strong>${item.label}</strong>
            <p class="mini">${item.count} records</p>
          </div>
          <div class="donut-visual" style="--color:${item.color};--value:${Math.round((item.count / totalUsers) * 100)};">
            <span>${Math.round((item.count / totalUsers) * 100)}%</span>
          </div>
        </div>
      </div>
    `)
    .join("");

  elements["session-timeline"].innerHTML = [...state.data.sessionLog].reverse()
    .map((item) => `
      <article class="timeline-item">
        <div class="timeline-item-top">
          <strong>${escapeHtml(item.title)}</strong>
          <span class="tag">${escapeHtml(item.time)}</span>
        </div>
        <p>${escapeHtml(item.text)}</p>
      </article>
    `)
    .join("");
}

function handleGlobalClick(event) {
  const actionButton = event.target.closest("[data-action]");
  if (actionButton) {
    const action = actionButton.dataset.action;
    if (action === "edit-user") {
      const user = findUser(actionButton.dataset.type, Number(actionButton.dataset.id));
      if (user) openUserModal(actionButton.dataset.type, user);
    }
    if (action === "delete-user") {
      deleteUser(actionButton.dataset.type, Number(actionButton.dataset.id));
    }
    if (action === "edit-quiz") {
      const quiz = state.data.quizzes.find((item) => item.id === Number(actionButton.dataset.id));
      if (quiz) openQuizModal(quiz);
    }
    if (action === "delete-quiz") {
      deleteQuiz(Number(actionButton.dataset.id));
    }
    if (action === "add-question") {
      openQuestionModal(Number(actionButton.dataset.id));
    }
    if (action === "edit-question") {
      openQuestionModal(Number(actionButton.dataset.quizId), Number(actionButton.dataset.questionId));
    }
    if (action === "delete-question") {
      deleteQuestion(Number(actionButton.dataset.quizId), Number(actionButton.dataset.questionId));
    }
  }

  const closeBtn = event.target.closest("[data-close-modal]");
  if (closeBtn) {
    closeModal(closeBtn.dataset.closeModal);
  }

  if (event.target.classList.contains("modal-overlay")) {
    closeModal(event.target.id);
  }
}

function openUserModal(type = "students", user = null) {
  elements["user-modal-title"].textContent = user ? "Edit User" : "Add User";
  elements["user-id"].value = user?.id ?? "";
  elements["user-name"].value = user?.name ?? "";
  elements["user-email"].value = user?.email ?? "";
  elements["user-category"].value = type;
  elements["user-reg"].value = user?.regNumber ?? "";
  elements["user-meta"].value = user?.meta ?? "";
  elements["user-status"].value = user?.status ?? "Active";
  hideNotice(elements["user-form-error"]);
  openModal("user-modal");
}

function submitUserForm(event) {
  event.preventDefault();
  const id = Number(elements["user-id"].value);
  const type = elements["user-category"].value;
  const payload = {
    name: elements["user-name"].value.trim(),
    email: elements["user-email"].value.trim(),
    regNumber: elements["user-reg"].value.trim(),
    meta: elements["user-meta"].value.trim(),
    status: elements["user-status"].value,
  };

  if (!payload.name || !payload.email || !payload.regNumber || !payload.meta) {
    return showNotice(elements["user-form-error"], "Please complete all user fields before saving.");
  }

  if (!/\S+@\S+\.\S+/.test(payload.email)) {
    return showNotice(elements["user-form-error"], "Please enter a valid email address.");
  }

  hideNotice(elements["user-form-error"]);

  if (id) {
    const currentType = findUserTypeById(id);
    if (currentType && currentType !== type) {
      state.data[currentType] = state.data[currentType].filter((item) => item.id !== id);
      state.data[type].push({ id, ...payload });
    } else {
      state.data[type] = state.data[type].map((item) => item.id === id ? { id, ...payload } : item);
    }
    pushSessionLog("User updated", `${payload.name} was updated in ${singularLabel(type)} records.`);
  } else {
    state.data[type].push({ id: generateId(), ...payload });
    pushSessionLog("User added", `${payload.name} was added as a ${singularLabel(type).toLowerCase()}.`);
  }

  state.currentUserTab = type;
  closeModal("user-modal");
  renderAll();
}

function deleteUser(type, id) {
  const user = findUser(type, id);
  state.data[type] = state.data[type].filter((item) => item.id !== id);
  pushSessionLog("User deleted", `${user?.name || "Record"} was removed from ${singularLabel(type)}.`);
  renderAll();
}

function findUser(type, id) {
  return state.data[type].find((item) => item.id === id);
}

function findUserTypeById(id) {
  return ["students", "counsellors", "wardens"].find((type) =>
    state.data[type].some((item) => item.id === id)
  );
}

function openQuizModal(quiz = null) {
  elements["quiz-modal-title"].textContent = quiz ? "Edit Quiz" : "Add Quiz";
  elements["quiz-id"].value = quiz?.id ?? "";
  elements["quiz-title-input"].value = quiz?.title ?? "";
  elements["quiz-category-input"].value = quiz?.category ?? "";
  elements["quiz-frequency-input"].value = quiz?.frequency ?? "";
  elements["quiz-badge-input"].value = quiz?.badge ?? "";
  hideNotice(elements["quiz-form-error"]);
  openModal("quiz-modal");
}

function submitQuizForm(event) {
  event.preventDefault();
  const id = Number(elements["quiz-id"].value);
  const payload = {
    title: elements["quiz-title-input"].value.trim(),
    category: elements["quiz-category-input"].value.trim(),
    frequency: elements["quiz-frequency-input"].value.trim(),
    badge: elements["quiz-badge-input"].value.trim(),
  };

  if (!payload.title || !payload.category || !payload.frequency || !payload.badge) {
    return showNotice(elements["quiz-form-error"], "Please complete all quiz fields.");
  }

  hideNotice(elements["quiz-form-error"]);

  if (id) {
    state.data.quizzes = state.data.quizzes.map((quiz) => quiz.id === id ? { ...quiz, ...payload } : quiz);
    pushSessionLog("Quiz updated", `${payload.title} was updated successfully.`);
  } else {
    state.data.quizzes.unshift({ id: generateId(), ...payload, questions: [] });
    pushSessionLog("Quiz added", `${payload.title} was created with an empty question set.`);
  }

  closeModal("quiz-modal");
  renderAll();
}

function deleteQuiz(id) {
  const quiz = state.data.quizzes.find((item) => item.id === id);
  state.data.quizzes = state.data.quizzes.filter((item) => item.id !== id);
  pushSessionLog("Quiz deleted", `${quiz?.title || "Quiz"} was deleted.`);
  renderAll();
}

function openQuestionModal(quizId, questionId = null) {
  const quiz = state.data.quizzes.find((item) => item.id === quizId);
  if (!quiz) return;
  const question = quiz.questions.find((item) => item.id === questionId);
  elements["question-modal-title"].textContent = question ? `Edit Question - ${quiz.title}` : `Add Question - ${quiz.title}`;
  elements["question-quiz-id"].value = String(quizId);
  elements["question-id"].value = question?.id ?? "";
  elements["question-text"].value = question?.text ?? "";
  elements["question-type"].value = question?.type ?? "Scale";
  hideNotice(elements["question-form-error"]);
  openModal("question-modal");
}

function submitQuestionForm(event) {
  event.preventDefault();
  const quizId = Number(elements["question-quiz-id"].value);
  const questionId = Number(elements["question-id"].value);
  const text = elements["question-text"].value.trim();
  const type = elements["question-type"].value;

  if (!text) {
    return showNotice(elements["question-form-error"], "Question text is required.");
  }

  const quiz = state.data.quizzes.find((item) => item.id === quizId);
  if (!quiz) return;

  if (questionId) {
    quiz.questions = quiz.questions.map((question) => question.id === questionId ? { ...question, text, type } : question);
    pushSessionLog("Question updated", `A question in ${quiz.title} was updated.`);
  } else {
    quiz.questions.push({ id: Date.now(), text, type });
    pushSessionLog("Question added", `A new question was added to ${quiz.title}.`);
  }

  closeModal("question-modal");
  renderAll();
}

function deleteQuestion(quizId, questionId) {
  const quiz = state.data.quizzes.find((item) => item.id === quizId);
  if (!quiz) return;
  quiz.questions = quiz.questions.filter((question) => question.id !== questionId);
  pushSessionLog("Question deleted", `A question was removed from ${quiz.title}.`);
  renderAll();
}

function openModal(id) {
  document.getElementById(id).classList.add("active");
}

function closeModal(id) {
  document.getElementById(id).classList.remove("active");
}

function showNotice(element, message) {
  element.hidden = false;
  element.textContent = message;
}

function hideNotice(element) {
  element.hidden = true;
  element.textContent = "";
}

function renderStatus(status) {
  return `<span class="status-pill ${status.toLowerCase()}">${escapeHtml(status)}</span>`;
}

function pushSessionLog(title, text) {
  state.data.sessionLog.push({
    id: generateId(),
    title,
    text,
    time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  });
}

function generateId() {
  return Math.floor(Math.random() * 1000000);
}

function singularLabel(type) {
  return {
    students: "Student",
    counsellors: "Counsellor",
    wardens: "Warden",
  }[type];
}

function initials(name) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function syncShellVisibility() {
  const showDashboard = state.session.loggedIn;
  elements["login-screen"].hidden = showDashboard;
  elements["dashboard-shell"].hidden = !showDashboard;
  elements["login-screen"].style.display = showDashboard ? "none" : "grid";
  elements["dashboard-shell"].style.display = showDashboard ? "grid" : "none";
}
