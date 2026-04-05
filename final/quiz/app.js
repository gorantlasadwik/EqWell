const MOCK_ADMIN = {
  username: "admin@mindwatch.ai",
  passwordHash: "c6ef09dbdec42ef10f32f1dd5fa3055e32842972410440f7c8064c7bacce8914"
};

const hostels = [
  "A",
  "B",
  "C",
  "D1",
  "D2"
];

const riskThreshold = 58;
const sessionKey = "mindwatch-admin-session";

const dashboardState = {
  hostel: "All Hostels",
  range: 30,
  metric: "mentalScore"
};

const charts = {
  trend: null,
  hostel: null,
  distribution: null,
  engagement: null,
  sleep: null
};

const dailyData = generateMockData();

function mulberry32(seed) {
  return function random() {
    let t = seed += 0x6d2b79f5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function generateMockData() {
  const random = mulberry32(12062026);
  const records = [];
  const studentsPerHostel = 24;
  const totalDays = 45;
  const today = new Date("2026-04-03T00:00:00");

  for (let dayOffset = totalDays - 1; dayOffset >= 0; dayOffset -= 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - dayOffset);
    const isoDate = date.toISOString().slice(0, 10);

    hostels.forEach((hostel, hostelIndex) => {
      for (let studentIndex = 1; studentIndex <= studentsPerHostel; studentIndex += 1) {
        const baseline = 52 + hostelIndex * 4 + Math.sin(dayOffset / 6) * 6;
        const mentalScore = clamp(Math.round(baseline + random() * 22), 28, 98);
        const stressIndex = clamp(Math.round(100 - mentalScore + random() * 16), 18, 92);
        const sleepQuality = clamp(Math.round(48 + mentalScore * 0.46 + random() * 12), 35, 97);
        const sleepHours = +(clamp(4.8 + sleepQuality / 22 + (random() - 0.5) * 1.3, 4.5, 9.4)).toFixed(1);
        const engagement = clamp(Math.round(42 + mentalScore * 0.48 + random() * 10), 30, 99);
        const attendance = clamp(Math.round(58 + mentalScore * 0.36 + random() * 10), 48, 100);

        records.push({
          id: `${hostelIndex + 1}-${studentIndex}-${isoDate}`,
          studentName: `Student ${String.fromCharCode(64 + hostelIndex + 1)}${String(studentIndex).padStart(2, "0")}`,
          hostel,
          date: isoDate,
          mentalScore,
          stressIndex,
          sleepQuality,
          sleepHours,
          engagement,
          attendance
        });
      }
    });
  }

  return records;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

async function sha256(input) {
  const encoded = new TextEncoder().encode(input);
  const buffer = await crypto.subtle.digest("SHA-256", encoded);
  return [...new Uint8Array(buffer)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function getFilteredData() {
  const maxDate = new Date(Math.max(...dailyData.map((entry) => new Date(entry.date).getTime())));
  const minDate = new Date(maxDate);
  minDate.setDate(maxDate.getDate() - (dashboardState.range - 1));

  return dailyData.filter((entry) => {
    const entryDate = new Date(entry.date);
    const hostelMatch = dashboardState.hostel === "All Hostels" || entry.hostel === dashboardState.hostel;
    return hostelMatch && entryDate >= minDate && entryDate <= maxDate;
  });
}

function getDailyAverages(records) {
  const grouped = {};

  records.forEach((entry) => {
    if (!grouped[entry.date]) {
      grouped[entry.date] = { mentalScore: 0, engagement: 0, stressIndex: 0, count: 0 };
    }

    grouped[entry.date].mentalScore += entry.mentalScore;
    grouped[entry.date].engagement += entry.engagement;
    grouped[entry.date].stressIndex += entry.stressIndex;
    grouped[entry.date].count += 1;
  });

  return Object.entries(grouped)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, values]) => ({
      date,
      mentalScore: +(values.mentalScore / values.count).toFixed(1),
      engagement: +(values.engagement / values.count).toFixed(1),
      stressIndex: +(values.stressIndex / values.count).toFixed(1)
    }));
}

function getHostelAverages(records) {
  const grouped = {};

  records.forEach((entry) => {
    if (!grouped[entry.hostel]) {
      grouped[entry.hostel] = {
        mentalScore: 0,
        stressIndex: 0,
        sleepQuality: 0,
        sleepHours: 0,
        attendance: 0,
        engagement: 0,
        count: 0
      };
    }

    grouped[entry.hostel].mentalScore += entry.mentalScore;
    grouped[entry.hostel].stressIndex += entry.stressIndex;
    grouped[entry.hostel].sleepQuality += entry.sleepQuality;
    grouped[entry.hostel].sleepHours += entry.sleepHours;
    grouped[entry.hostel].attendance += entry.attendance;
    grouped[entry.hostel].engagement += entry.engagement;
    grouped[entry.hostel].count += 1;
  });

  return Object.entries(grouped).map(([hostel, values]) => {
    const mentalScore = +(values.mentalScore / values.count).toFixed(1);
    const stressIndex = +(values.stressIndex / values.count).toFixed(1);
    const sleepQuality = +(values.sleepQuality / values.count).toFixed(1);
    const sleepHours = +(values.sleepHours / values.count).toFixed(1);
    const attendance = +(values.attendance / values.count).toFixed(1);
    const engagement = +(values.engagement / values.count).toFixed(1);
    const blockFitness = +(
      mentalScore * 0.34 +
      sleepQuality * 0.22 +
      attendance * 0.16 +
      engagement * 0.16 +
      (100 - stressIndex) * 0.12
    ).toFixed(1);

    return {
      hostel,
      mentalScore,
      stressIndex,
      sleepQuality,
      sleepHours,
      attendance,
      engagement,
      blockFitness,
      sleepPattern: getSleepPattern(sleepHours, sleepQuality),
      condition: getBlockCondition(blockFitness)
    };
  });
}

function getUniqueStudents(records) {
  return new Set(records.map((entry) => `${entry.hostel}-${entry.studentName}`)).size;
}

function getDistribution(records) {
  const zones = { Healthy: 0, Stable: 0, Watchlist: 0, Critical: 0 };

  records.forEach((entry) => {
    if (entry.mentalScore >= 80) {
      zones.Healthy += 1;
    } else if (entry.mentalScore >= 65) {
      zones.Stable += 1;
    } else if (entry.mentalScore >= 50) {
      zones.Watchlist += 1;
    } else {
      zones.Critical += 1;
    }
  });

  return zones;
}

function updateMetricCards(records, dailyAverages, hostelAverages) {
  const averageMentalScore = dailyAverages.length
    ? dailyAverages.reduce((sum, entry) => sum + entry.mentalScore, 0) / dailyAverages.length
    : 0;
  const firstScore = dailyAverages[0]?.mentalScore || averageMentalScore;
  const lastScore = dailyAverages[dailyAverages.length - 1]?.mentalScore || averageMentalScore;
  const percentageChange = firstScore ? (((lastScore - firstScore) / firstScore) * 100) : 0;
  const riskCount = records.filter((entry) => entry.mentalScore < riskThreshold).length;
  const riskRatio = records.length ? (riskCount / records.length) * 100 : 0;
  const topHostelEntry = [...hostelAverages].sort((left, right) => right.mentalScore - left.mentalScore)[0];

  document.getElementById("avg-score").textContent = averageMentalScore.toFixed(1);
  document.getElementById("score-change").textContent = `${percentageChange >= 0 ? "+" : ""}${percentageChange.toFixed(1)}%`;
  document.getElementById("student-population").textContent = `${getUniqueStudents(records)} students`;
  document.getElementById("active-students").textContent = String(getUniqueStudents(records));
  document.getElementById("risk-ratio").textContent = `${riskRatio.toFixed(1)}%`;
  document.getElementById("risk-count").textContent = String(riskCount);
  document.getElementById("top-hostel").textContent = topHostelEntry?.hostel || "N/A";
  document.getElementById("top-hostel-score").textContent = topHostelEntry ? topHostelEntry.mentalScore.toFixed(1) : "0";
}

function buildTrendChart(dailyAverages) {
  const labels = dailyAverages.map((entry) => formatDate(entry.date));
  const dataset = dailyAverages.map((entry) => entry[dashboardState.metric]);
  const metricLabel = getMetricLabel(dashboardState.metric);

  if (charts.trend) {
    charts.trend.data.labels = labels;
    charts.trend.data.datasets[0].label = metricLabel;
    charts.trend.data.datasets[0].data = dataset;
    charts.trend.update();
    return;
  }

  charts.trend = new Chart(document.getElementById("trend-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: metricLabel,
        data: dataset,
        tension: 0.4,
        borderColor: "#2563eb",
        backgroundColor: "rgba(37, 99, 235, 0.18)",
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 6
      }]
    },
    options: getChartOptions()
  });
}

function buildHostelChart(hostelAverages) {
  const labels = hostelAverages.map((entry) => entry.hostel);
  const scores = hostelAverages.map((entry) => entry.mentalScore);

  if (charts.hostel) {
    charts.hostel.data.labels = labels;
    charts.hostel.data.datasets[0].data = scores;
    charts.hostel.update();
    return;
  }

  charts.hostel = new Chart(document.getElementById("hostel-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Mental score",
        data: scores,
        borderRadius: 14,
        backgroundColor: labels.map((_, index) => index % 2 === 0 ? "rgba(20, 184, 166, 0.8)" : "rgba(245, 158, 11, 0.76)")
      }]
    },
    options: getChartOptions({ indexAxis: "y" })
  });
}

function buildDistributionChart(distribution) {
  const labels = Object.keys(distribution);
  const values = Object.values(distribution);

  if (charts.distribution) {
    charts.distribution.data.labels = labels;
    charts.distribution.data.datasets[0].data = values;
    charts.distribution.update();
    return;
  }

  charts.distribution = new Chart(document.getElementById("distribution-chart"), {
    type: "pie",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444"],
        borderWidth: 0
      }]
    },
    options: {
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#10203a",
            font: { family: "Manrope", weight: "700" }
          }
        }
      }
    }
  });
}

function buildEngagementChart(hostelAverages) {
  const labels = hostelAverages.map((entry) => entry.hostel);
  const engagement = hostelAverages.map((entry) => entry.engagement);
  const score = hostelAverages.map((entry) => entry.mentalScore);

  if (charts.engagement) {
    charts.engagement.data.labels = labels;
    charts.engagement.data.datasets[0].data = engagement;
    charts.engagement.data.datasets[1].data = score;
    charts.engagement.update();
    return;
  }

  charts.engagement = new Chart(document.getElementById("engagement-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Engagement",
          data: engagement,
          backgroundColor: "rgba(20, 184, 166, 0.82)",
          borderRadius: 14
        },
        {
          label: "Mental score",
          data: score,
          type: "line",
          borderColor: "#2563eb",
          backgroundColor: "rgba(37, 99, 235, 0.18)",
          tension: 0.4,
          pointRadius: 3
        }
      ]
    },
    options: getChartOptions()
  });
}

function buildSleepChart(hostelAverages) {
  const labels = hostelAverages.map((entry) => entry.hostel);
  const sleepHours = hostelAverages.map((entry) => entry.sleepHours);
  const sleepQuality = hostelAverages.map((entry) => entry.sleepQuality);

  if (charts.sleep) {
    charts.sleep.data.labels = labels;
    charts.sleep.data.datasets[0].data = sleepHours;
    charts.sleep.data.datasets[1].data = sleepQuality;
    charts.sleep.update();
    return;
  }

  charts.sleep = new Chart(document.getElementById("sleep-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Sleep hours",
          data: sleepHours,
          backgroundColor: "rgba(53, 95, 142, 0.82)",
          borderRadius: 14,
          yAxisID: "y"
        },
        {
          label: "Sleep quality",
          data: sleepQuality,
          type: "line",
          borderColor: "#13a4ec",
          backgroundColor: "rgba(19, 164, 236, 0.18)",
          tension: 0.35,
          pointRadius: 3,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: {
            color: "#10203a",
            font: { family: "Manrope", weight: "700" }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: "#54637f" },
          grid: { color: "rgba(16, 32, 58, 0.06)" }
        },
        y: {
          beginAtZero: true,
          suggestedMax: 10,
          ticks: { color: "#54637f" },
          grid: { color: "rgba(16, 32, 58, 0.06)" }
        },
        y1: {
          beginAtZero: true,
          suggestedMax: 100,
          position: "right",
          ticks: { color: "#54637f" },
          grid: { display: false }
        }
      }
    }
  });
}

function getChartOptions(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        labels: {
          color: "#10203a",
          font: { family: "Manrope", weight: "700" }
        }
      },
      tooltip: {
        backgroundColor: "#081122",
        titleColor: "#ffffff",
        bodyColor: "#dbeafe",
        padding: 12
      }
    },
    scales: {
      x: {
        ticks: { color: "#54637f" },
        grid: { color: "rgba(16, 32, 58, 0.06)" }
      },
      y: {
        beginAtZero: true,
        ticks: { color: "#54637f" },
        grid: { color: "rgba(16, 32, 58, 0.06)" }
      }
    },
    ...extra
  };
}

function renderHeatmap(hostelAverages) {
  const heatmapGrid = document.getElementById("heatmap-grid");
  const ranked = [...hostelAverages].sort((left, right) => right.blockFitness - left.blockFitness);

  heatmapGrid.innerHTML = ranked.map((entry) => `
    <article class="wellness-matrix-card ${getConditionClass(entry.condition)}">
      <div class="wellness-matrix-head">
        <div>
          <h4>${entry.hostel}</h4>
          <p>${entry.sleepPattern}</p>
        </div>
        <span class="tag risk-tag ${getConditionClass(entry.condition)}">${entry.condition}</span>
      </div>
      <div class="wellness-matrix-score-row">
        <div>
          <span class="mini">Block fitness</span>
          <div class="wellness-matrix-score">${entry.blockFitness.toFixed(1)}</div>
        </div>
        <div class="wellness-score-chip">
          Sleep ${entry.sleepHours.toFixed(1)}h
        </div>
      </div>
      <div class="wellness-metrics">
        ${renderMetricMeter("Mental", entry.mentalScore)}
        ${renderMetricMeter("Sleep", entry.sleepQuality)}
        ${renderMetricMeter("Attendance", entry.attendance)}
        ${renderMetricMeter("Engagement", entry.engagement)}
        ${renderMetricMeter("Stress", 100 - entry.stressIndex)}
      </div>
    </article>
  `).join("");
}

function renderMetricMeter(label, value) {
  return `
    <div class="wellness-metric-row">
      <div class="wellness-metric-label">
        <span>${label}</span>
        <strong>${value.toFixed(1)}</strong>
      </div>
      <div class="wellness-meter">
        <span style="width:${Math.max(8, Math.min(100, value))}%; background:${getMeterColor(value)}"></span>
      </div>
    </div>
  `;
}

function getMeterColor(value) {
  if (value >= 80) return "linear-gradient(90deg, #63d38b, #b6e0bf)";
  if (value >= 65) return "linear-gradient(90deg, #7cb3f1, #aec0d9)";
  if (value >= 50) return "linear-gradient(90deg, #e0b54f, #e6dab2)";
  return "linear-gradient(90deg, #dc7d95, #e4b7c3)";
}

function renderBlockConditionBoard(hostelAverages) {
  const board = document.getElementById("block-condition-grid");
  const ranked = [...hostelAverages].sort((left, right) => right.blockFitness - left.blockFitness);

  board.innerHTML = ranked.map((entry) => `
    <article class="block-condition-card ${getConditionClass(entry.condition)}">
      <div class="block-condition-top">
        <div>
          <h4>${entry.hostel}</h4>
          <p>${entry.sleepPattern}</p>
        </div>
        <span class="tag risk-tag ${getConditionClass(entry.condition)}">${entry.condition}</span>
      </div>
      <div class="block-fitness-score">${entry.blockFitness.toFixed(1)}</div>
      <div class="block-condition-meta">
        <span>Sleep ${entry.sleepHours.toFixed(1)}h</span>
        <span>Quality ${entry.sleepQuality.toFixed(1)}</span>
        <span>Stress ${entry.stressIndex.toFixed(1)}</span>
      </div>
      <div class="progress">
        <span style="width:${entry.blockFitness}%;"></span>
      </div>
    </article>
  `).join("");
}

function getHeatColor(metric, value) {
  if (metric === "stressIndex") {
    if (value <= 35) return "linear-gradient(135deg, #16a34a, #22c55e)";
    if (value <= 50) return "linear-gradient(135deg, #0ea5e9, #3b82f6)";
    if (value <= 65) return "linear-gradient(135deg, #f59e0b, #f97316)";
    return "linear-gradient(135deg, #ef4444, #dc2626)";
  }

  if (value >= 80) return "linear-gradient(135deg, #16a34a, #22c55e)";
  if (value >= 65) return "linear-gradient(135deg, #0ea5e9, #3b82f6)";
  if (value >= 50) return "linear-gradient(135deg, #f59e0b, #f97316)";
  return "linear-gradient(135deg, #ef4444, #dc2626)";
}

function getRiskLabel(score) {
  if (score >= 80) return "Healthy";
  if (score >= 65) return "Stable";
  if (score >= 50) return "Watchlist";
  return "Critical";
}

function getRiskClass(score) {
  return getRiskLabel(score).toLowerCase();
}

function getSleepPattern(hours, quality) {
  if (hours >= 7.8 && quality >= 78) return "Strong recovery pattern";
  if (hours >= 6.8 && quality >= 68) return "Balanced sleep pattern";
  if (hours >= 6.0 && quality >= 58) return "Inconsistent sleep pattern";
  return "Sleep debt risk pattern";
}

function getBlockCondition(fitness) {
  if (fitness >= 80) return "Excellent";
  if (fitness >= 68) return "Stable";
  if (fitness >= 56) return "Needs attention";
  return "Critical";
}

function getConditionClass(condition) {
  return condition.toLowerCase().replace(/\s+/g, "-");
}

function getMetricLabel(metric) {
  if (metric === "engagement") return "Engagement";
  if (metric === "stressIndex") return "Stress Index";
  return "Mental Score";
}

function formatDate(date) {
  return new Date(date).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function populateHostelFilter() {
  const select = document.getElementById("hostel-filter");
  select.innerHTML = [`<option value="All Hostels">All Hostels</option>`, ...hostels.map((hostel) => `<option value="${hostel}">${hostel}</option>`)].join("");
}

function updateDashboard() {
  const filteredData = getFilteredData();
  const dailyAverages = getDailyAverages(filteredData);
  const hostelAverages = getHostelAverages(filteredData);
  const distribution = getDistribution(filteredData);

  updateMetricCards(filteredData, dailyAverages, hostelAverages);
  buildTrendChart(dailyAverages);
  buildHostelChart(hostelAverages);
  buildDistributionChart(distribution);
  buildEngagementChart(hostelAverages);
  buildSleepChart(hostelAverages);
  renderHeatmap(hostelAverages);
  renderBlockConditionBoard(hostelAverages);
}

function showView(viewId) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.getElementById(viewId).classList.add("active");
}

function closeSidebarOnMobile() {
  if (window.innerWidth > 980) {
    return;
  }

  document.querySelector(".sidebar").classList.remove("open");
}

function handleSectionChange(section) {
  document.querySelectorAll(".nav-item, .nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.section === section);
  });

  const matchingPanels = [...document.querySelectorAll(".section-panel")].filter((panel) => (
    panel.dataset.panel === section || section === "overview"
  ));

  document.querySelectorAll(".section-panel").forEach((panel) => {
    const visible = matchingPanels.includes(panel);
    panel.style.opacity = visible ? "1" : "0.55";
    panel.style.transform = visible ? "translateY(0)" : "scale(0.99)";
  });

  const targetPanel = matchingPanels[0];
  if (targetPanel) {
    targetPanel.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  }
}

function openModal(title, copy) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-copy").textContent = copy;
  document.getElementById("modal-overlay").classList.add("active");
}

function closeModal() {
  document.getElementById("modal-overlay").classList.remove("active");
}

function exportSnapshot() {
  const filteredData = getFilteredData();
  const payload = {
    exportedAt: new Date().toISOString(),
    filters: { ...dashboardState },
    records: filteredData.slice(0, 50)
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "mindwatch-dashboard-snapshot.json";
  link.click();
  URL.revokeObjectURL(url);
}

async function handleLogin(event) {
  event.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const rememberSession = document.getElementById("remember-session").checked;
  const usernameError = document.getElementById("username-error");
  const passwordError = document.getElementById("password-error");
  const feedback = document.getElementById("login-feedback");

  usernameError.textContent = "";
  passwordError.textContent = "";
  feedback.textContent = "";
  feedback.className = "feedback";

  let valid = true;

  if (!username) {
    usernameError.textContent = "Username is required.";
    valid = false;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(username)) {
    usernameError.textContent = "Enter a valid email address.";
    valid = false;
  }

  if (!password) {
    passwordError.textContent = "Password is required.";
    valid = false;
  } else if (password.length < 10) {
    passwordError.textContent = "Password must be at least 10 characters.";
    valid = false;
  }

  if (!valid) {
    feedback.textContent = "Please fix the highlighted fields and try again.";
    return;
  }

  const passwordHash = await sha256(password);
  const authenticated = username === MOCK_ADMIN.username && passwordHash === MOCK_ADMIN.passwordHash;

  if (!authenticated) {
    feedback.textContent = "Invalid username or password.";
    return;
  }

  if (rememberSession) {
    localStorage.setItem(sessionKey, JSON.stringify({ username, timestamp: Date.now() }));
  } else {
    sessionStorage.setItem(sessionKey, JSON.stringify({ username, timestamp: Date.now() }));
  }

  feedback.textContent = "Authentication successful. Redirecting...";
  feedback.classList.add("success");

  setTimeout(() => {
    showView("dashboard-view");
    updateDashboard();
  }, 500);
}

function handleLogout() {
  localStorage.removeItem(sessionKey);
  sessionStorage.removeItem(sessionKey);
  showView("login-view");
}

function restoreSession() {
  const stored = localStorage.getItem(sessionKey) || sessionStorage.getItem(sessionKey);
  if (stored) {
    showView("dashboard-view");
    updateDashboard();
  }
}

function attachEventListeners() {
  document.getElementById("login-form").addEventListener("submit", handleLogin);

  document.getElementById("toggle-password").addEventListener("click", () => {
    const passwordField = document.getElementById("password");
    const hidden = passwordField.type === "password";
    passwordField.type = hidden ? "text" : "password";
    document.getElementById("toggle-password").textContent = hidden ? "Hide" : "Show";
  });

  document.getElementById("hostel-filter").addEventListener("change", (event) => {
    dashboardState.hostel = event.target.value;
    updateDashboard();
  });

  document.getElementById("range-filter").addEventListener("change", (event) => {
    dashboardState.range = Number(event.target.value);
    updateDashboard();
  });

  document.getElementById("metric-filter").addEventListener("change", (event) => {
    dashboardState.metric = event.target.value;
    updateDashboard();
  });

  document.getElementById("logout-button").addEventListener("click", handleLogout);
  document.getElementById("menu-toggle").addEventListener("click", () => {
    document.querySelector(".sidebar").classList.toggle("open");
  });

  document.querySelectorAll(".nav-item, .nav-link").forEach((button) => {
    button.addEventListener("click", () => {
      handleSectionChange(button.dataset.section);
      closeSidebarOnMobile();
    });
  });

  document.querySelectorAll(".info-trigger").forEach((button) => {
    button.addEventListener("click", () => {
      openModal(button.dataset.modalTitle, button.dataset.modalCopy);
    });
  });

  document.getElementById("close-modal").addEventListener("click", closeModal);
  document.getElementById("modal-overlay").addEventListener("click", (event) => {
    if (event.target.id === "modal-overlay") {
      closeModal();
    }
  });

  document.getElementById("export-button").addEventListener("click", exportSnapshot);
  window.addEventListener("resize", closeSidebarOnMobile);
}

populateHostelFilter();
attachEventListeners();
restoreSession();
