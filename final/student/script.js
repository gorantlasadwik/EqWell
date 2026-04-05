const appState = {
  today: "2026-04-04",
  selectedDate: null,
  selectedHomeDate: null,
  datasets: {
    serious: [],
    casual: []
  },
  quizSession: {
    activeQuiz: null,
    questions: [],
    cursor: 0,
    answers: []
  },
  student: {
    name: "Aarav Sharma",
    age: 20,
    block: "Block C",
    hostel: "Maple Residency",
    proctor: "Dr. Nisha Kapoor",
    regNumber: "22BCE0175",
    personalInfo: "B.Tech CSE • 2nd Year • On-campus",
    sleepLevel: 74,
    sleepHours: 7.4,
    fitnessLevel: 72,
    quizScore: 66,
    counsellorAttendance: 80,
    mood: "Neutral",
    moodScore: 55,
    overallBehaviorScore: 68,
    badges: ["Calm Consistency", "Sleep Rebuilder", "VibeCheck Regular", "Support Seeker"]
  },
  quizzes: [
    { name: "MindBalance Check", focus: "Depression-focused", tone: "Calm and professional", description: "A guided emotional health scan built to catch prolonged low mood, energy loss, and withdrawal patterns early.", icon: "psychology" },
    { name: "CalmPulse Assessment", focus: "Anxiety detection", tone: "Modern and tech-driven", description: "Measures cognitive load, racing thought patterns, and nervous-system intensity through a sleek rapid assessment.", icon: "favorite" },
    { name: "StressLoad Analyzer", focus: "Stress and burnout", tone: "Clear and slightly technical", description: "Breaks down pressure, fatigue, and burnout indicators into practical markers you can track over time.", icon: "monitor_heart" },
    { name: "SocialConnect Index", focus: "Isolation and loneliness", tone: "Positive framing", description: "Looks at belonging, support networks, and connection habits without making the experience feel heavy or clinical.", icon: "groups" },
    { name: "VibeCheck Lite", focus: "Daily mood and fun check", tone: "Relatable and Gen Z friendly", description: "A lightweight everyday pulse that helps you track how the day feels without overthinking the answer.", icon: "sentiment_satisfied" },
    { name: "PersonaPlay Quiz", focus: "Personality type", tone: "Playful yet polished", description: "Maps your current personality style into a polished social-emotional archetype with friendly language and insight.", icon: "auto_awesome" }
  ],
  moodChoices: [
    { key: "very-bad", label: "Very Bad", score: 88, noteText: "VERY BAD", bgColor: "#fc7359", indicatorColor: "#790b02", pathColor: "#fc7359", smileColor: "#790b02", titleColor: "#790b02", trackColor: "#fc5b3e", eyeWidth: 52, eyeHeight: 52, eyeBorderRadius: "100%", eyeBg: "#790b02", smileRotate: 180, indicatorRotate: 180 },
    { key: "bad", label: "Bad", score: 74, noteText: "BAD", bgColor: "#f49e6c", indicatorColor: "#69300b", pathColor: "#f49e6c", smileColor: "#69300b", titleColor: "#69300b", trackColor: "#d47b3f", eyeWidth: 82, eyeHeight: 22, eyeBorderRadius: "36px", eyeBg: "#69300b", smileRotate: 180, indicatorRotate: 180 },
    { key: "not-bad", label: "Not Bad", score: 55, noteText: "NOT BAD", bgColor: "#dfa342", indicatorColor: "#482103", pathColor: "#dfa342", smileColor: "#482103", titleColor: "#482103", trackColor: "#b07615", eyeWidth: 100, eyeHeight: 20, eyeBorderRadius: "36px", eyeBg: "#482103", smileRotate: 180, indicatorRotate: 180 },
    { key: "good", label: "Good", score: 35, noteText: "GOOD", bgColor: "#9fbe59", indicatorColor: "#0b2b03", pathColor: "#9fbe59", smileColor: "#0b2b03", titleColor: "#0b2b03", trackColor: "#698b1b", eyeWidth: 118, eyeHeight: 118, eyeBorderRadius: "100%", eyeBg: "#0b2b03", smileRotate: 0, indicatorRotate: 0 },
    { key: "very-good", label: "Very Good", score: 18, noteText: "VERY GOOD", bgColor: "#79cb6a", indicatorColor: "#0d3505", pathColor: "#79cb6a", smileColor: "#0d3505", titleColor: "#0d3505", trackColor: "#44a031", eyeWidth: 126, eyeHeight: 126, eyeBorderRadius: "100%", eyeBg: "#0d3505", smileRotate: 0, indicatorRotate: 0 }
  ],
  quotes: [
    {
      title: "Small resets are still progress.",
      body: "You do not need a perfect day to protect your well-being. A short walk, one honest check-in, or a full glass of water can still shift your nervous system toward calm.",
      advice: "Block ten quiet minutes between classes, step away from screens, and let your nervous system settle before the next task pulls on your attention."
    },
    {
      title: "Rest is not falling behind.",
      body: "Recovery is part of performance. Slowing down for a moment can help your focus return with less friction and more clarity.",
      advice: "If your energy feels scattered, trade one late-night scroll for an earlier wind-down and protect tomorrow's focus tonight."
    },
    {
      title: "Support works best before overload.",
      body: "You do not have to wait for a crisis to ask for help. Booking one session early can reduce the weight you carry later.",
      advice: "Pick one person you trust this week and tell them honestly how the week has felt instead of carrying it alone."
    }
  ],
  counselling: {
    counsellors: [
      { id: "c1", name: "Dr. Mira Sen", specialty: "Anxiety and academic stress", slots: ["2026-04-08T10:30", "2026-04-10T15:00", "2026-04-14T11:30"] },
      { id: "c2", name: "Arjun Mehta", specialty: "Burnout and routine rebuilding", slots: ["2026-04-06T16:00", "2026-04-09T09:30", "2026-04-15T13:00"] },
      { id: "c3", name: "Dr. Sana Iqbal", specialty: "Sleep, mood, and transition support", slots: ["2026-04-07T14:00", "2026-04-08T12:00", "2026-04-12T10:00"] }
    ],
    appointments: [
      { date: "2026-04-01", time: "11:00 AM", counsellor: "Dr. Mira Sen", status: "Attended" },
      { date: "2026-04-03", time: "03:00 PM", counsellor: "Arjun Mehta", status: "Attended" },
      { date: "2026-04-08", time: "10:30 AM", counsellor: "Dr. Mira Sen", status: "Upcoming" }
    ]
  }
};

const stressWeights = { counsellor: 0.3, overallBehavior: 0.3, fitness: 0.15, sleep: 0.15, mood: 0.07, quiz: 0.03 };
const els = {};
const seriousQuizDefinitions = [
  { id: "mind-balance", name: "MindBalance Check", description: "Depression-focused questions on emotional steadiness, self-worth, and low-mood patterns.", tone: "Serious Track", icon: "psychology", chunk: 0, colorClass: "stable" },
  { id: "calm-pulse", name: "CalmPulse Assessment", description: "Anxiety-oriented prompts around overthinking, overwhelm, and emotional regulation.", tone: "Serious Track", icon: "favorite", chunk: 1, colorClass: "watchlist" },
  { id: "stress-load", name: "StressLoad Analyzer", description: "Stress and burnout signals tied to pressure, coping, and day-to-day mental load.", tone: "Serious Track", icon: "monitor_heart", chunk: 2, colorClass: "watchlist" },
  { id: "social-connect", name: "SocialConnect Index", description: "Connection, loneliness, and support-system questions framed with warmth and care.", tone: "Serious Track", icon: "groups", chunk: 3, colorClass: "stable" }
];
const fruitProfiles = [
  { min: 0, max: 3, fruit: "🍇", title: "Grape Cluster", copy: "You are reflective, steady, and deeply observant. You thrive in thoughtful spaces and bring quiet emotional intelligence to the people around you." },
  { min: 4, max: 6, fruit: "🍊", title: "Citrus Spark", copy: "You balance warmth with curiosity. You lift group energy, adapt quickly, and usually bring a hopeful angle even when things are messy." },
  { min: 7, max: 9, fruit: "🍉", title: "Watermelon Heart", copy: "You are expressive, generous, and naturally social. People likely see you as approachable, playful, and emotionally big-hearted." },
  { min: 10, max: 12, fruit: "🍍", title: "Pineapple Energy", copy: "You are bold, memorable, and full of personality. You like discovery, challenge, and leaving your own signature on whatever space you enter." }
];

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  setStaticMeta();
  renderProfile();
  renderAppointments();
  renderCounsellors();
  initializeMoodSlider();
  updateDerivedState();
  renderCalendars();
  bindEvents();
  loadQuizDatasets();
});

function cacheElements() {
  [
    "page-title", "page-subtitle", "today-chip", "mental-progress-ring", "mental-progress-value", "mental-progress-label",
    "mental-state-title", "mental-state-summary", "mental-state-pill", "next-session-chip", "behavior-chip", "mood-chip",
    "sleep-metric", "sleep-note", "sleep-bar", "fitness-metric", "fitness-note", "fitness-bar", "session-metric", "session-note",
    "session-bar", "stress-score-card", "stress-score-note", "stress-score-bar", "quiz-grid", "home-quiz-grid",
    "appointment-table-body", "home-appointment-table-body", "home-next-available-tag", "profile-details-grid", "badges-grid", "profile-metrics-table", "profile-name", "profile-stress-tag",
    "pulse-modal", "stress-alert-modal", "stress-alert-copy", "booking-modal", "counsellor-list",
    "counselling-calendar-grid", "counselling-slot-list", "selected-day-copy", "counselling-calendar-month", "home-calendar-grid",
    "home-slot-list", "home-slot-summary", "home-calendar-month", "next-available-tag", "quote-title", "quote-body", "advice-copy",
    "quiz-data-status", "home-quiz-data-status", "quiz-modal", "quiz-active-tag", "quiz-counter", "quiz-question", "quiz-progress-fill", "quiz-options",
    "quiz-runner-screen", "quiz-result-screen", "quiz-result-icon", "quiz-result-kicker", "quiz-result-title", "quiz-result-copy",
    "sidebar", "sidebar-avatar", "sidebar-student-name", "sidebar-student-meta"
  ].forEach((id) => {
    els[toCamel(id)] = document.getElementById(id);
  });
}

function bindEvents() {
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.viewTarget, button));
  });

  document.getElementById("pulse-check-trigger").addEventListener("click", () => openModal("pulse-modal"));
  document.getElementById("booking-trigger").addEventListener("click", () => openModal("booking-modal"));
  document.getElementById("home-book-cta").addEventListener("click", () => openModal("booking-modal"));
  document.getElementById("refresh-quote").addEventListener("click", setRandomQuote);
  document.getElementById("tracking-toggle").addEventListener("click", () => showToast("Tracking Disabled", "Real-time tracking is now paused in this mock experience."));
  document.getElementById("logout-button").addEventListener("click", () => showToast("Signed Out", "Mock logout complete. You can continue exploring the dashboard."));
  document.getElementById("sidebar-toggle").addEventListener("click", () => els.sidebar.classList.toggle("open"));
  const quizzesNavButton = document.querySelector('[data-view-target="quizzes-view"]');
  const counsellingNavButton = document.querySelector('[data-view-target="counselling-view"]');
  const homeOpenQuizzes = document.getElementById("home-open-quizzes-btn");
  const homeOpenCounselling = document.getElementById("home-open-counselling-btn");
  if (homeOpenQuizzes) {
    homeOpenQuizzes.addEventListener("click", () => switchView("quizzes-view", quizzesNavButton));
  }
  if (homeOpenCounselling) {
    homeOpenCounselling.addEventListener("click", () => switchView("counselling-view", counsellingNavButton));
  }
  document.getElementById("stress-alert-book").addEventListener("click", () => {
    closeModal("stress-alert-modal");
    switchView("counselling-view", document.querySelector('[data-view-target="counselling-view"]'));
    openModal("booking-modal");
  });
  document.getElementById("quiz-restart-btn").addEventListener("click", () => {
    closeModal("quiz-modal");
    resetQuizSession();
  });

  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => closeModal(button.dataset.closeModal));
  });

  document.querySelectorAll(".modal-overlay").forEach((modal) => {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeModal(modal.id);
    });
  });
}

function setStaticMeta() {
  const date = new Date(`${appState.today}T08:00:00`);
  els.todayChip.textContent = date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "2-digit" }).replace(",", "");
  els.sidebarAvatar.textContent = getInitials(appState.student.name);
  els.sidebarStudentName.textContent = appState.student.name;
  els.sidebarStudentMeta.textContent = `${appState.student.block} • Reg ${appState.student.regNumber}`;
  setRandomQuote();
}

function updateDerivedState() {
  const score = calculateStressScore();
  const stressState = getStressState(score);
  updateHero(score, stressState);
  updateMetricCards(score);
  renderProfileMetrics(score);
  updateStressTriggers(score);
}

function calculateStressScore() {
  const counsellingRisk = 100 - appState.student.counsellorAttendance;
  const behaviorRisk = appState.student.overallBehaviorScore;
  const fitnessRisk = 100 - appState.student.fitnessLevel;
  const sleepRisk = 100 - appState.student.sleepLevel;
  const moodRisk = appState.student.moodScore;
  const quizRisk = appState.student.quizScore;
  return Math.round(
    counsellingRisk * stressWeights.counsellor +
    behaviorRisk * stressWeights.overallBehavior +
    fitnessRisk * stressWeights.fitness +
    sleepRisk * stressWeights.sleep +
    moodRisk * stressWeights.mood +
    quizRisk * stressWeights.quiz
  );
}

function updateHero(score, state) {
  els.mentalProgressRing.style.setProperty("--pct", score);
  els.mentalProgressRing.style.setProperty("--tone", state.color);
  els.mentalProgressValue.textContent = `${score}%`;
  els.mentalProgressLabel.textContent = state.label;
  els.mentalStateTitle.textContent = state.heading;
  els.mentalStateSummary.textContent = state.summary;
  els.mentalStatePill.textContent = `Mental State • ${state.label}`;
  els.mentalStatePill.style.background = state.pillBackground;
  els.mentalStatePill.style.color = state.pillColor;
  const nextAppointment = getNextAppointment();
  els.nextSessionChip.textContent = nextAppointment ? `Next session: ${formatDisplayDate(nextAppointment.date)}, ${nextAppointment.time}` : "No upcoming session booked";
  els.behaviorChip.textContent = `Behavior score: ${appState.student.overallBehaviorScore}`;
  els.moodChip.textContent = `Mood: ${appState.student.mood}`;
  els.pageTitle.textContent = `Welcome back, ${appState.student.name.split(" ")[0]}`;
  els.pageSubtitle.textContent = `Your current weighted stress score is ${score}. ${state.microcopy}`;
}

function updateMetricCards(score) {
  els.sleepMetric.textContent = `${appState.student.sleepHours.toFixed(1)}h`;
  els.sleepBar.style.width = `${appState.student.sleepLevel}%`;
  els.fitnessMetric.textContent = `${appState.student.fitnessLevel}`;
  els.fitnessBar.style.width = `${appState.student.fitnessLevel}%`;
  const attended = appState.counselling.appointments.filter((item) => item.status === "Attended").length;
  els.sessionMetric.textContent = `${attended}/${appState.counselling.appointments.length}`;
  els.sessionBar.style.width = `${appState.student.counsellorAttendance}%`;
  els.stressScoreCard.textContent = score;
  els.stressScoreBar.style.width = `${score}%`;
  els.stressScoreBar.style.background = `linear-gradient(90deg, ${stateColor(score)}, #648dae)`;
}

function attachQuizCardHandlers(container) {
  if (!container) return;
  container.querySelectorAll(".quiz-card").forEach((card) => {
    card.addEventListener("click", () => {
      const type = card.dataset.quizType;
      if (type === "external") {
        window.open(card.dataset.quizLink, "_blank", "noopener,noreferrer");
        return;
      }
      if (type === "fruit") {
        launchFruitQuiz();
        return;
      }
      launchSeriousQuiz(card.dataset.quizId);
    });
  });
}

function renderQuizzes() {
  const seriousCards = seriousQuizDefinitions.map((quiz) => `
    <article class="quiz-card" data-quiz-type="serious" data-quiz-id="${quiz.id}">
      <div class="quiz-card-top">
        <div class="quiz-icon"><span class="material-symbols-outlined">${quiz.icon}</span></div>
        <span class="tag">${quiz.tone}</span>
      </div>
      <h3>${quiz.name}</h3>
      <p>${quiz.description}</p>
      <div class="quiz-card-footer"><span class="mini">25-question assessment</span><span class="material-symbols-outlined">arrow_forward</span></div>
    </article>
  `).join("");

  const fruitCard = `
    <article class="quiz-card fun" data-quiz-type="fruit" data-quiz-id="fruit-persona">
      <div class="quiz-card-top">
        <div class="quiz-icon"><span class="material-symbols-outlined">nutrition</span></div>
        <span class="tag">Fun Quiz</span>
      </div>
      <h3>Fruit Persona Quiz</h3>
      <p>A playful personality check powered by your casual dataset, ending in a fruit-based result with polished personality copy.</p>
      <div class="quiz-card-footer"><span class="mini">12-question personality flow</span><span class="material-symbols-outlined">arrow_forward</span></div>
    </article>
  `;

  const externalCard = `
    <article class="quiz-card external" data-quiz-type="external" data-quiz-link="https://smore.im/quiz/1LUFTQ0t36?tm=52907f54">
      <div class="quiz-card-top">
        <div class="quiz-icon"><span class="material-symbols-outlined">open_in_new</span></div>
        <span class="tag">External Quiz</span>
      </div>
      <h3>VibeCheck Lite</h3>
      <p>An external casual quiz experience hosted on Smore. Opens in a new tab while keeping the dashboard flow clean and professional.</p>
      <div class="quiz-card-footer"><span class="mini">Launch external experience</span><span class="material-symbols-outlined">north_east</span></div>
    </article>
  `;

  els.quizGrid.innerHTML = `${seriousCards}${fruitCard}${externalCard}`;
  if (els.homeQuizGrid) {
    const homeCards = Array.from(els.quizGrid.querySelectorAll(".quiz-card"))
      .slice(0, 3)
      .map((card) => card.outerHTML)
      .join("");
    els.homeQuizGrid.innerHTML = homeCards;
  }

  attachQuizCardHandlers(els.quizGrid);
  attachQuizCardHandlers(els.homeQuizGrid);
}

function renderAppointments() {
  const sortedAppointments = [...appState.counselling.appointments]
    .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`))
    .map((item) => ({ ...item }));

  const tableRows = sortedAppointments
    .map((item) => `<tr><td>${formatDisplayDate(item.date)}</td><td>${item.time}</td><td>${item.counsellor}</td><td><span class="tag">${item.status}</span></td></tr>`)
    .join("");

  els.appointmentTableBody.innerHTML = tableRows;
  if (els.homeAppointmentTableBody) {
    els.homeAppointmentTableBody.innerHTML = sortedAppointments
      .slice(0, 4)
      .map((item) => `<tr><td>${formatDisplayDate(item.date)}</td><td>${item.time}</td><td>${item.counsellor}</td><td><span class="tag">${item.status}</span></td></tr>`)
      .join("");
  }

  const next = findNearestAvailableSlot();
  if (next) {
    const label = `Next available: ${formatDisplayDate(next.date)}`;
    els.nextAvailableTag.textContent = label;
    if (els.homeNextAvailableTag) els.homeNextAvailableTag.textContent = label;
  }
}

function renderProfile() {
  els.profileName.textContent = appState.student.name;
  const details = [
    ["Name", appState.student.name], ["Block", appState.student.block], ["Proctor", appState.student.proctor], ["Age", `${appState.student.age}`],
    ["Registration Number", appState.student.regNumber], ["Hostel", appState.student.hostel], ["Personal Info", appState.student.personalInfo], ["Mood", appState.student.mood]
  ];
  els.profileDetailsGrid.innerHTML = details.map(([label, value]) => `<div class="profile-detail"><span>${label}</span><strong>${value}</strong></div>`).join("");
  els.badgesGrid.innerHTML = appState.student.badges.map((badge) => `<div class="badge-card"><span class="material-symbols-outlined">workspace_premium</span><strong>${badge}</strong><span class="mini">Earned through engagement and quiz consistency.</span></div>`).join("");
}

function renderProfileMetrics(score) {
  els.profileStressTag.textContent = `Stress score ${score}`;
  const rows = [
    ["Sleep Level", `${appState.student.sleepLevel}`, "Lower sleep raises stress risk"],
    ["Fitness Level", `${appState.student.fitnessLevel}`, "Higher movement lowers stress risk"],
    ["Quiz Score", `${appState.student.quizScore}`, "Quiz markers slightly affect the score"],
    ["Counselling Attendance", `${appState.student.counsellorAttendance}`, "Consistent attendance lowers risk"],
    ["Mood", `${appState.student.mood} (${appState.student.moodScore})`, "Daily mood updates from pulse check"],
    ["Overall Behavior Score", `${appState.student.overallBehaviorScore}`, "Tracks activity patterns and habits"],
    ["Stress Score", `${score}`, "Calculated dynamically in JavaScript"]
  ];
  els.profileMetricsTable.innerHTML = rows.map(([metric, value, impact]) => `<tr><td>${metric}</td><td>${value}</td><td>${impact}</td></tr>`).join("");
}

function initializeMoodSlider() {
  const selectedMoodInput = document.getElementById("selected-mood");
  const continueBtn = document.getElementById("continue-btn");
  const moodQuestion = document.getElementById("mood-question");
  const moodNote = document.getElementById("mood-note");
  const eyeLeft = document.getElementById("eye-left");
  const eyeRight = document.getElementById("eye-right");
  const smileWrap = document.getElementById("smile-wrap");
  const smilePath = document.getElementById("smile-path");
  const indicatorSmilePath = document.getElementById("indicator-smile-path");
  const moodTrack = document.getElementById("mood-track");
  const moodIndicator = document.getElementById("mood-indicator");
  const moodDots = document.getElementById("mood-dots");
  const moodLabels = document.getElementById("mood-labels");
  const pulseCard = document.querySelector(".pulse-modal-card");
  let selectedIndex = -1;
  const defaultIndicatorIndex = Math.floor(appState.moodChoices.length / 2);

  function setIndicatorVisible(visible) {
    moodIndicator.style.opacity = visible ? "1" : "0";
    moodIndicator.style.visibility = visible ? "visible" : "hidden";
    moodIndicator.setAttribute("aria-hidden", visible ? "false" : "true");
  }

  function alignTrackToDots() {
    const dots = Array.from(moodDots.children);
    if (dots.length < 2) return;
    const rowRect = moodDots.getBoundingClientRect();
    const firstCenter = dots[0].offsetLeft + dots[0].offsetWidth / 2;
    const lastCenter = dots[dots.length - 1].offsetLeft + dots[dots.length - 1].offsetWidth / 2;
    moodTrack.style.left = `${firstCenter}px`;
    moodTrack.style.right = `${Math.max(rowRect.width - lastCenter, 0)}px`;
  }

  function alignIndicatorToDot(index) {
    const dot = moodDots.children[index];
    if (!dot) return;
    moodIndicator.style.left = `${dot.offsetLeft + dot.offsetWidth / 2}px`;
  }

  function syncPositions() {
    alignTrackToDots();
    alignIndicatorToDot(selectedIndex >= 0 ? selectedIndex : defaultIndicatorIndex);
  }

  function applyState(index) {
    const state = appState.moodChoices[index];
    if (!state) return;
    selectedIndex = index;
    selectedMoodInput.value = state.key;
    continueBtn.disabled = false;
    pulseCard.style.background = state.bgColor;
    moodQuestion.style.color = state.titleColor;
    moodNote.style.color = state.titleColor;
    moodNote.textContent = state.noteText;
    eyeLeft.style.width = `${state.eyeWidth}px`;
    eyeLeft.style.height = `${state.eyeHeight}px`;
    eyeLeft.style.borderRadius = state.eyeBorderRadius;
    eyeLeft.style.backgroundColor = state.eyeBg;
    eyeRight.style.width = `${state.eyeWidth}px`;
    eyeRight.style.height = `${state.eyeHeight}px`;
    eyeRight.style.borderRadius = state.eyeBorderRadius;
    eyeRight.style.backgroundColor = state.eyeBg;
    smileWrap.style.transform = `rotate(${state.smileRotate}deg)`;
    smilePath.style.stroke = state.smileColor;
    moodTrack.style.backgroundColor = state.trackColor;
    indicatorSmilePath.style.stroke = state.pathColor;
    moodIndicator.style.backgroundColor = state.indicatorColor;
    moodIndicator.style.transform = `translate(-50%, -50%) rotate(${state.indicatorRotate}deg)`;
    setIndicatorVisible(true);
    alignIndicatorToDot(index);
    Array.from(moodDots.children).forEach((btn, i) => {
      btn.style.backgroundColor = state.trackColor;
      btn.classList.toggle("active", i === index);
    });
    Array.from(moodLabels.children).forEach((label, i) => {
      label.style.color = state.titleColor;
      label.style.opacity = i === index ? "1" : "0.6";
      label.style.fontWeight = i === index ? "800" : "600";
    });
  }

  appState.moodChoices.forEach((state, index) => {
    const dotBtn = document.createElement("button");
    dotBtn.type = "button";
    dotBtn.className = "mood-dot";
    dotBtn.setAttribute("aria-label", state.label);
    dotBtn.addEventListener("click", () => applyState(index));
    moodDots.appendChild(dotBtn);
    const label = document.createElement("span");
    label.className = "mood-label-item";
    label.textContent = state.label;
    moodLabels.appendChild(label);
  });

  continueBtn.addEventListener("click", () => {
    if (selectedIndex < 0) return;
    const choice = appState.moodChoices[selectedIndex];
    appState.student.mood = choice.label;
    appState.student.moodScore = choice.score;
    renderProfile();
    updateDerivedState();
    closeModal("pulse-modal");
    showToast("Mood Updated", `Today's mood was set to ${choice.label}.`);
  });

  setIndicatorVisible(false);
  requestAnimationFrame(syncPositions);
  setTimeout(syncPositions, 80);
  window.addEventListener("load", syncPositions);
  window.addEventListener("resize", syncPositions);
}

function renderCounsellors() {
  els.counsellorList.innerHTML = appState.counselling.counsellors.map((counsellor) => `
    <button class="counsellor-option" data-counsellor-id="${counsellor.id}">
      <strong>${counsellor.name}</strong>
      <span>${counsellor.specialty}</span>
    </button>
  `).join("");

  document.querySelectorAll(".counsellor-option").forEach((button) => {
    button.addEventListener("click", () => {
      const counsellor = appState.counselling.counsellors.find((item) => item.id === button.dataset.counsellorId);
      bookNearestSlot(counsellor);
      closeModal("booking-modal");
    });
  });
}

function renderCalendars() {
  const availableDates = [...new Set(flattenSlots().map((slot) => slot.date))];
  els.counsellingCalendarMonth.textContent = "April 2026";
  els.homeCalendarMonth.textContent = "April 2026";
  els.counsellingCalendarGrid.innerHTML = buildCalendarMarkup(2026, 3, availableDates, "counselling");
  els.homeCalendarGrid.innerHTML = buildCalendarMarkup(2026, 3, availableDates, "home");

  document.querySelectorAll('[data-calendar="counselling"]').forEach((button) => {
    button.addEventListener("click", () => {
      els.selectedDayCopy.textContent = `Slots for ${formatDisplayDate(button.dataset.date)}`;
      highlightSelectedDate("counselling", button.dataset.date);
      renderSlotList(button.dataset.date, els.counsellingSlotList, true);
    });
  });

  document.querySelectorAll('[data-calendar="home"]').forEach((button) => {
    button.addEventListener("click", () => {
      els.homeSlotSummary.textContent = `Available slots on ${formatDisplayDate(button.dataset.date)}`;
      highlightSelectedDate("home", button.dataset.date);
      renderSlotList(button.dataset.date, els.homeSlotList, false);
    });
  });
}

function buildCalendarMarkup(year, monthIndex, availableDates, mode) {
  const firstDay = new Date(year, monthIndex, 1).getDay();
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDay; i += 1) cells.push('<button class="day-cell empty" tabindex="-1"></button>');
  for (let day = 1; day <= daysInMonth; day += 1) {
    const iso = `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const available = availableDates.includes(iso);
    cells.push(`<button class="day-cell ${available ? "available" : ""}" ${available ? `data-date="${iso}" data-calendar="${mode}"` : "disabled"}>${day}</button>`);
  }
  return cells.join("");
}

function highlightSelectedDate(mode, date) {
  document.querySelectorAll(`[data-calendar="${mode}"]`).forEach((button) => {
    button.classList.toggle("selected", button.dataset.date === date);
  });
}

function renderSlotList(date, container, allowBooking) {
  const slots = flattenSlots().filter((slot) => slot.date === date);
  if (!slots.length) {
    container.innerHTML = '<span class="slot-chip empty">No free slots available</span>';
    return;
  }
  container.innerHTML = slots.map((slot) => `<button class="slot-chip" data-slot-date="${slot.date}" data-slot-time="${slot.time}" data-slot-counsellor="${slot.counsellor}">${slot.time} • ${slot.counsellor}</button>`).join("");
  if (!allowBooking) return;
  container.querySelectorAll(".slot-chip").forEach((button) => {
    button.addEventListener("click", () => {
      const counsellor = appState.counselling.counsellors.find((item) => item.name === button.dataset.slotCounsellor);
      bookSpecificSlot(counsellor, `${button.dataset.slotDate}T${to24Hour(button.dataset.slotTime)}`);
    });
  });
}

function bookNearestSlot(counsellor) {
  const nextSlot = counsellor.slots.filter((slot) => slot >= `${appState.today}T00:00`).sort()[0];
  if (!nextSlot) {
    showToast("No Slots Found", `${counsellor.name} has no free mock slots right now.`);
    return;
  }
  bookSpecificSlot(counsellor, nextSlot);
}

function bookSpecificSlot(counsellor, slot) {
  const [date, time24] = slot.split("T");
  appState.counselling.appointments.push({ date, time: formatTime(time24), counsellor: counsellor.name, status: "Upcoming" });
  counsellor.slots = counsellor.slots.filter((item) => item !== slot);
  appState.student.counsellorAttendance = Math.min(100, appState.student.counsellorAttendance + 4);
  renderAppointments();
  renderCalendars();
  updateDerivedState();
  showToast("Appointment Booked", `${counsellor.name} booked for ${formatDisplayDate(date)} at ${formatTime(time24)}.`);
}

function updateStressTriggers(score) {
  if (score > 75) {
    els.stressAlertCopy.textContent = `Your weighted stress score is ${score}. Booking a counselling session could help reduce overload early.`;
    openModal("stress-alert-modal");
  } else {
    closeModal("stress-alert-modal");
  }
}

function switchView(viewId, trigger) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === viewId));
  document.querySelectorAll("[data-view-target]").forEach((button) => button.classList.toggle("active", button === trigger));
  els.sidebar.classList.remove("open");
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add("active");
  modal.setAttribute("aria-hidden", "false");
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove("active");
  modal.setAttribute("aria-hidden", "true");
  if (id === "quiz-modal") resetQuizSession();
}

function setRandomQuote() {
  const quote = appState.quotes[Math.floor(Math.random() * appState.quotes.length)];
  els.quoteTitle.textContent = quote.title;
  els.quoteBody.textContent = quote.body;
  els.adviceCopy.textContent = quote.advice;
}

async function loadQuizDatasets() {
  try {
    const [seriousText, casualText] = await Promise.all([
      fetch("./serious.txt").then((response) => response.text()),
      fetch("./casual.txt").then((response) => response.text())
    ]);
    appState.datasets.serious = seriousText.split(/\r?\n/).map((line) => sanitizeText(line)).filter(Boolean);
    appState.datasets.casual = casualText.split(/\r?\n/).map((line) => sanitizeText(line)).filter(Boolean);
    const readyMessage = `Datasets ready • ${appState.datasets.serious.length} serious, ${appState.datasets.casual.length} casual`;
    els.quizDataStatus.textContent = readyMessage;
    if (els.homeQuizDataStatus) els.homeQuizDataStatus.textContent = readyMessage;
    renderQuizzes();
  } catch (error) {
    const failMessage = "Dataset load failed • keep files with the app";
    els.quizDataStatus.textContent = failMessage;
    if (els.homeQuizDataStatus) els.homeQuizDataStatus.textContent = failMessage;
    showToast("Quiz Data Missing", "Run the dashboard from a local server so the text datasets can load.");
    renderQuizzes();
  }
}

function launchSeriousQuiz(quizId) {
  if (appState.datasets.serious.length < 100) {
    showToast("Serious Dataset Missing", "The serious quiz dataset is not fully loaded yet.");
    return;
  }
  const config = seriousQuizDefinitions.find((item) => item.id === quizId);
  const startIndex = config.chunk * 25;
  appState.quizSession.activeQuiz = { type: "serious", config };
  appState.quizSession.questions = appState.datasets.serious.slice(startIndex, startIndex + 25);
  appState.quizSession.cursor = 0;
  appState.quizSession.answers = [];
  els.quizActiveTag.textContent = config.name;
  els.quizActiveTag.className = `risk-tag ${config.colorClass}`;
  showQuizRunner();
  renderQuizQuestion();
  openModal("quiz-modal");
}

function launchFruitQuiz() {
  if (appState.datasets.casual.length < 10) {
    showToast("Casual Dataset Missing", "The fruit personality dataset is not fully loaded yet.");
    return;
  }
  appState.quizSession.activeQuiz = { type: "fruit", config: { name: "Fruit Persona Quiz" } };
  appState.quizSession.questions = shuffleArray([...appState.datasets.casual]).slice(0, 12);
  appState.quizSession.cursor = 0;
  appState.quizSession.answers = [];
  els.quizActiveTag.textContent = "Fruit Persona Quiz";
  els.quizActiveTag.className = "risk-tag healthy";
  showQuizRunner();
  renderQuizQuestion();
  openModal("quiz-modal");
}

function showQuizRunner() {
  els.quizRunnerScreen.classList.remove("hidden");
  els.quizResultScreen.classList.add("hidden");
}

function renderQuizQuestion() {
  const { questions, cursor, activeQuiz } = appState.quizSession;
  const question = questions[cursor];
  els.quizCounter.textContent = `${cursor + 1} / ${questions.length}`;
  els.quizQuestion.textContent = question;
  els.quizProgressFill.style.width = `${((cursor + 1) / questions.length) * 100}%`;

  const options = activeQuiz.type === "fruit"
    ? [
        { label: "Yes, that sounds like me", value: 1 },
        { label: "No, not really me", value: 0 }
      ]
    : [
        { label: "Yes", value: inferSeriousScore(question, true) },
        { label: "No", value: inferSeriousScore(question, false) }
      ];

  els.quizOptions.innerHTML = options.map((option) => `
    <button class="quiz-option-btn" data-answer="${option.value}">${option.label}</button>
  `).join("");

  els.quizOptions.querySelectorAll(".quiz-option-btn").forEach((button) => {
    button.addEventListener("click", () => handleQuizAnswer(Number(button.dataset.answer)));
  });
}

function handleQuizAnswer(score) {
  appState.quizSession.answers.push(score);
  appState.quizSession.cursor += 1;
  if (appState.quizSession.cursor < appState.quizSession.questions.length) {
    renderQuizQuestion();
    return;
  }
  showQuizResult();
}

function showQuizResult() {
  els.quizRunnerScreen.classList.add("hidden");
  els.quizResultScreen.classList.remove("hidden");
  const { type, config } = appState.quizSession.activeQuiz;
  const totalScore = appState.quizSession.answers.reduce((sum, value) => sum + value, 0);

  if (type === "fruit") {
    const result = fruitProfiles.find((profile) => totalScore >= profile.min && totalScore <= profile.max) || fruitProfiles[1];
    els.quizResultIcon.textContent = result.fruit;
    els.quizResultKicker.textContent = "Fruit Personality Result";
    els.quizResultTitle.textContent = result.title;
    els.quizResultCopy.textContent = result.copy;
    return;
  }

  const maxScore = appState.quizSession.questions.length;
  const percent = Math.round((totalScore / maxScore) * 100);
  const state = percent > 70
    ? { icon: "🧭", title: "Support is worth considering", copy: `${config.name} suggests elevated concern markers. This is not a diagnosis, but it may be a good time to check in with a counsellor or a trusted adult.` }
    : percent > 40
      ? { icon: "🌿", title: "Mixed but manageable", copy: `${config.name} shows moderate pressure signals. A few routines around sleep, movement, and support could help stabilize things.` }
      : { icon: "☀️", title: "Steady right now", copy: `${config.name} reflects a fairly balanced pattern at the moment. Keep using the routines that are helping you feel grounded.` };

  els.quizResultIcon.textContent = state.icon;
  els.quizResultKicker.textContent = `${config.name} complete`;
  els.quizResultTitle.textContent = `${percent}% concern index`;
  els.quizResultCopy.textContent = state.copy;
}

function resetQuizSession() {
  appState.quizSession.activeQuiz = null;
  appState.quizSession.questions = [];
  appState.quizSession.cursor = 0;
  appState.quizSession.answers = [];
  els.quizRunnerScreen.classList.remove("hidden");
  els.quizResultScreen.classList.add("hidden");
}

function showToast(title, message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `<strong>${title}</strong><span>${message}</span>`;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 220);
  }, 2600);
}

function findNearestAvailableSlot() {
  return flattenSlots().filter((slot) => slot.date >= appState.today).sort((a, b) => a.iso.localeCompare(b.iso))[0];
}

function getNextAppointment() {
  return appState.counselling.appointments.filter((item) => item.status === "Upcoming").sort((a, b) => a.date.localeCompare(b.date))[0];
}

function flattenSlots() {
  return appState.counselling.counsellors.flatMap((counsellor) => counsellor.slots.map((slot) => {
    const [date, time24] = slot.split("T");
    return { iso: slot, date, time: formatTime(time24), counsellor: counsellor.name };
  }));
}

function getStressState(score) {
  if (score > 75) return { label: "High Stress", heading: "Support is worth prioritizing", summary: "Your current pattern suggests elevated strain across mood, behavior, and recovery. A counselling session could be a useful next step.", microcopy: "We recommend checking your support options today.", color: "#D15A5A", pillBackground: "#fde7e7", pillColor: "#9a3030" };
  if (score > 55) return { label: "Moderate", heading: "A little overloaded, still manageable", summary: "Some wellness inputs are trending upward, but there’s still room to stabilize with sleep, routine, and support check-ins.", microcopy: "A small reset today could keep things from escalating.", color: "#E9A07E", pillBackground: "#fff0e8", pillColor: "#9a5839" };
  return { label: "Stable", heading: "Grounded and steady", summary: "Your stress markers are in a manageable range. Sleep recovery is supporting focus, and your mood log looks balanced.", microcopy: "Your current signals look calm and sustainable.", color: "#4FA86E", pillBackground: "#e9f8ee", pillColor: "#2f6b47" };
}

function stateColor(score) {
  if (score > 75) return "#D15A5A";
  if (score > 55) return "#E9A07E";
  return "#4FA86E";
}

function formatDisplayDate(date) {
  return new Date(`${date}T08:00:00`).toLocaleDateString("en-US", { month: "short", day: "2-digit" });
}

function formatTime(time24) {
  const [hourValue, minute] = time24.split(":").map(Number);
  const suffix = hourValue >= 12 ? "PM" : "AM";
  const hour = ((hourValue + 11) % 12) + 1;
  return `${hour}:${String(minute).padStart(2, "0")} ${suffix}`;
}

function to24Hour(time12) {
  const [time, meridiem] = time12.split(" ");
  let [hour, minute] = time.split(":").map(Number);
  if (meridiem === "PM" && hour !== 12) hour += 12;
  if (meridiem === "AM" && hour === 12) hour = 0;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function getInitials(name) {
  return name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function toCamel(id) {
  return id.replace(/-([a-z])/g, (_, char) => char.toUpperCase());
}

function sanitizeText(text) {
  return text
    .replace(/â€™/g, "'")
    .replace(/â€¢/g, "•")
    .trim();
}

function shuffleArray(arr) {
  const copy = [...arr];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
  }
  return copy;
}

function inferSeriousScore(question, answerYes) {
  const positivePatterns = [
    "genuinely happy",
    "easy to express your emotions",
    "identify your triggers",
    "confident in handling your emotions",
    "feel in control",
    "practice mindfulness",
    "feel grateful",
    "forgive easily",
    "feel proud",
    "enjoy spending time with yourself",
    "recognize when you're stressed",
    "feel at peace",
    "comfortable being vulnerable",
    "feel hopeful",
    "laugh at yourself",
    "accept your flaws",
    "let go of grudges",
    "emotionally supported",
    "stay calm",
    "healthy coping",
    "take breaks",
    "practice deep breathing",
    "sleep well when stressed",
    "have someone to talk",
    "feel rested",
    "maintain a regular sleep schedule",
    "wake up feeling refreshed",
    "feel energetic",
    "supportive relationships",
    "good listener",
    "comfortable in social settings",
    "make new friends"
  ];

  const normalized = question.toLowerCase();
  const isPositive = positivePatterns.some((pattern) => normalized.includes(pattern));
  if (isPositive) return answerYes ? 0 : 1;
  return answerYes ? 1 : 0;
}
