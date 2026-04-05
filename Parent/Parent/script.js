const state = { view: 'overview', sortKey: 'date', sortDir: 'desc' };

const data = {
  credentials: { regNo: 'REG2026P001', accessCode: 'parent@123' },
  ward: {
    name: 'Aarav Sharma', registrationNumber: 'REG2026P001', hostel: 'Hostel D1',
    stressLevel: 68, happinessLevel: 79, course: 'B.Tech Computer Science', semester: 'Semester 4',
    lastQuizScore: 86, recentCounsellingCount: 5, overallStressTrend: 'Down 9% this week', overallHappinessTrend: 'Up 7% this week',
    moodTrend: [
      { label: 'Mar 22', mood: 58, stress: 78 }, { label: 'Mar 23', mood: 56, stress: 75 },
      { label: 'Mar 24', mood: 60, stress: 71 }, { label: 'Mar 25', mood: 63, stress: 68 },
      { label: 'Mar 26', mood: 66, stress: 65 }, { label: 'Mar 27', mood: 69, stress: 63 },
      { label: 'Mar 28', mood: 72, stress: 61 }, { label: 'Mar 29', mood: 73, stress: 60 },
      { label: 'Mar 30', mood: 74, stress: 58 }, { label: 'Mar 31', mood: 76, stress: 56 },
      { label: 'Apr 01', mood: 78, stress: 54 }, { label: 'Apr 02', mood: 80, stress: 52 },
      { label: 'Apr 03', mood: 77, stress: 55 }, { label: 'Apr 04', mood: 79, stress: 50 }
    ],
    behavior: [
      { label: 'Sleep Consistency', daily: '7.1 hrs', weekly: 'Stable', score: 76 },
      { label: 'Physical Activity', daily: '42 mins', weekly: 'Good', score: 72 },
      { label: 'Campus Engagement', daily: 'High', weekly: 'Up 11%', score: 83 },
      { label: 'Peer Interaction', daily: 'Healthy', weekly: 'Consistent', score: 81 }
    ],
    activities: [
      { title: 'Participated in peer wellness circle', time: 'Today, 10:30 AM', detail: 'Joined a guided group discussion focused on handling mid-semester pressure.' },
      { title: 'Completed evening fitness routine', time: 'Yesterday, 7:10 PM', detail: 'Reached weekly fitness target for the third time this month.' },
      { title: 'Academic focus score improved', time: 'Yesterday, 3:40 PM', detail: 'Faculty input indicates better class engagement and reduced fatigue signs.' }
    ]
  },
  sessions: [
    { sessionId: 'CS-401', counsellorName: 'Dr. Nisha Verma', date: '2026-01-12T10:00:00', type: 'Stress Management', feedback: 'Student was receptive and actively reflected on triggers.', notes: 'Introduced breathing routines and structured study recovery blocks.', feedbackScore: 8.2, stressScore: 76 },
    { sessionId: 'CS-428', counsellorName: 'Dr. Karan Mehta', date: '2026-02-03T15:30:00', type: 'Academic Anxiety', feedback: 'Improved clarity around academic pressure and deadlines.', notes: 'Built a realistic study plan and grounding techniques.', feedbackScore: 8.6, stressScore: 70 },
    { sessionId: 'CS-447', counsellorName: 'Dr. Nisha Verma', date: '2026-02-28T11:15:00', type: 'Follow-up', feedback: 'Reported better sleep quality and lower overwhelm.', notes: 'Suggested maintaining digital cut-off and peer check-ins.', feedbackScore: 8.8, stressScore: 64 },
    { sessionId: 'CS-462', counsellorName: 'Dr. Aditi Rao', date: '2026-03-18T09:45:00', type: 'Routine Check-in', feedback: 'Positive momentum visible in confidence and self-reporting.', notes: 'Recommended continued journaling and exercise frequency.', feedbackScore: 9.1, stressScore: 58 },
    { sessionId: 'CS-489', counsellorName: 'Dr. Aditi Rao', date: '2026-03-30T16:00:00', type: 'Follow-up', feedback: 'Student appears calmer, more engaged, and socially connected.', notes: 'No escalation required. Continue low-intensity monitoring.', feedbackScore: 9.3, stressScore: 50 }
  ],
  wardens: [
    { name: 'Mr. Rohan Sethi', hostel: 'Hostel A', contactInfo: 'Resident Warden', email: 'warden.a@eqwell.edu', phone: '+91 98765 12001', code: 'A', ladies: false },
    { name: 'Ms. Pooja Nair', hostel: 'Hostel B', contactInfo: 'Resident Warden', email: 'warden.b@eqwell.edu', phone: '+91 98765 12002', code: 'B', ladies: false },
    { name: 'Mrs. Charu Iyer', hostel: 'Hostel C', contactInfo: 'Ladies Hostel Warden', email: 'warden.c@eqwell.edu', phone: '+91 98765 12003', code: 'C', ladies: true },
    { name: 'Mr. Dev Malhotra', hostel: 'Hostel D1', contactInfo: 'Resident Warden', email: 'warden.d1@eqwell.edu', phone: '+91 98765 12004', code: 'D1', ladies: false },
    { name: 'Mr. Imran Sheikh', hostel: 'Hostel D2', contactInfo: 'Resident Warden', email: 'warden.d2@eqwell.edu', phone: '+91 98765 12005', code: 'D2', ladies: false }
  ]
};

const el = id => document.getElementById(id);
const loginForm = el('loginForm');
const loginError = el('loginError');
const sidebar = el('sidebar');
const SESSION_KEY = 'parentDashboardSession';

function pill(text, cls='info') { return `<span class="pill ${cls}">${text}</span>`; }
function fmtDate(date) { return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(date)); }
function shortDate(date) { return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(date)); }
function colorForScore(v) { return v >= 80 ? '#4FA8B0' : v >= 65 ? '#648DAE' : '#E9A07E'; }
function stressColor(v) { return v >= 75 ? '#D46666' : v >= 60 ? '#E9A07E' : '#4FA8B0'; }
function toast(msg) { const t = el('toast'); t.hidden = false; t.textContent = msg; clearTimeout(window.toastTimer); window.toastTimer = setTimeout(() => t.hidden = true, 3200); }
function saveSession(session) { sessionStorage.setItem(SESSION_KEY, JSON.stringify(session)); }
function getSession() {
  try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null'); }
  catch { return null; }
}
function clearSession() { sessionStorage.removeItem(SESSION_KEY); }
function isLoginPage() { return Boolean(loginForm); }
function isDashboardPage() { return Boolean(el('appShell')); }

function setRing(id, value, color) {
  const ring = el(id); const radius = 46; const circ = 2 * Math.PI * radius;
  ring.style.strokeDasharray = `${circ}`;
  ring.style.strokeDashoffset = `${circ * (1 - value / 100)}`;
  ring.style.stroke = color;
}

function renderOverview() {
  const w = data.ward;
  el('wardHeading').textContent = `${w.name}'s well-being snapshot`;
  el('wardMeta').textContent = `${w.registrationNumber} • ${w.hostel} • ${w.course} • ${w.semester}`;
  el('stressValue').textContent = `${w.stressLevel}%`;
  el('happyValue').textContent = `${w.happinessLevel}%`;
  el('stressState').textContent = w.stressLevel >= 65 ? 'Watch closely' : 'Stable';
  el('happyState').textContent = w.happinessLevel >= 75 ? 'Positive trend' : 'Needs support';
  el('heroTags').innerHTML = [pill(`Quiz ${w.lastQuizScore}%`), pill(`${w.recentCounsellingCount} recent sessions`, 'success'), pill(w.overallStressTrend, 'warn'), pill(w.overallHappinessTrend, 'success')].join('');
  setRing('stressRing', w.stressLevel, stressColor(w.stressLevel));
  setRing('happyRing', w.happinessLevel, colorForScore(w.happinessLevel));

  el('summaryGrid').innerHTML = [
    { title: 'Last Quiz Score', value: `${w.lastQuizScore}%`, note: 'Strong academic recovery', tone: 'pastel-blue', progress: w.lastQuizScore },
    { title: 'Recent Counselling', value: `${w.recentCounsellingCount}`, note: 'Sessions attended this cycle', tone: 'pastel-pink', progress: 80 },
    { title: 'Stress Trend', value: '9% Down', note: 'Improvement since last week', tone: 'pastel-yellow', progress: 72 },
    { title: 'Happiness Trend', value: '+7%', note: 'Positive emotional momentum', tone: 'pastel-green', progress: 84 }
  ].map(card => `<article class="card ${card.tone}"><p class="login-kicker">${card.title}</p><div class="metric">${card.value}</div><p class="mini">${card.note}</p><div class="progress"><span style="width:${card.progress}%"></span></div></article>`).join('');

  const avg = Math.round(w.behavior.reduce((a, b) => a + b.score, 0) / w.behavior.length);
  el('healthChip').textContent = avg >= 80 ? 'Thriving' : avg >= 70 ? 'Balanced' : 'Needs support';
  el('behaviorList').innerHTML = w.behavior.map(item => `<div class="detail-item"><div><strong>${item.label}</strong><p class="mini">${item.daily} daily average • ${item.weekly}</p></div><div><div class="wellness-meter"><span style="width:${item.score}%; background:${colorForScore(item.score)}"></span></div><p class="mini" style="text-align:right; margin-top:6px;">${item.score}%</p></div></div>`).join('');
  el('activityFeed').innerHTML = w.activities.map(item => `<article class="activity-item"><div class="section-head"><strong>${item.title}</strong>${pill(item.time)}</div><p>${item.detail}</p></article>`).join('');
  lineChart('moodChart', w.moodTrend, [{ key: 'mood', color: '#4FA8B0', name: 'Mood' }, { key: 'stress', color: '#E9A07E', name: 'Stress' }]);
  barChart('stressChart', data.sessions.map(s => ({ label: shortDate(s.date), value: s.stressScore })), '#648DAE');
}

function filteredSessions() {
  const q = el('searchInput').value.trim().toLowerCase();
  const counsellor = el('counsellorFilter').value;
  const type = el('typeFilter').value;
  const dateRange = el('dateFilter').value;
  const now = new Date('2026-04-04T00:00:00');
  return data.sessions.filter(s => {
    const matchQ = !q || [s.sessionId, s.counsellorName, s.type, s.feedback, s.notes].join(' ').toLowerCase().includes(q);
    const matchC = counsellor === 'all' || s.counsellorName === counsellor;
    const matchT = type === 'all' || s.type === type;
    let matchD = true;
    if (dateRange !== 'all') { const cutoff = new Date(now); cutoff.setDate(cutoff.getDate() - Number(dateRange)); matchD = new Date(s.date) >= cutoff; }
    return matchQ && matchC && matchT && matchD;
  }).sort((a, b) => {
    const k = state.sortKey; const dir = state.sortDir === 'asc' ? 1 : -1;
    if (k === 'date') return (new Date(a.date) - new Date(b.date)) * dir;
    if (typeof a[k] === 'number') return (a[k] - b[k]) * dir;
    return String(a[k]).localeCompare(String(b[k])) * dir;
  });
}

function renderSessions() {
  const rows = filteredSessions();
  el('sessionCount').textContent = `${rows.length} Sessions`;
  el('sessionsBody').innerHTML = rows.map(s => `<tr><td><strong>${s.sessionId}</strong></td><td>${s.counsellorName}</td><td>${fmtDate(s.date)}</td><td>${pill(s.type)}</td><td>${s.feedback}</td><td>${s.notes}</td><td><span class="status-badge" style="background:#dcf4e3; color:#20533a;">${s.feedbackScore.toFixed(1)}</span></td></tr>`).join('');
  barChart('sessionChart', rows.map(s => ({ label: shortDate(s.date), value: s.stressScore })), '#E9A07E');
  const breakdown = rows.reduce((acc, s) => { acc[s.type] = (acc[s.type] || 0) + 1; return acc; }, {});
  el('sessionBreakdown').innerHTML = Object.entries(breakdown).map(([type, count]) => `<article class="session-stat"><div class="section-head"><strong>${type}</strong>${pill(`${count} session${count > 1 ? 's' : ''}`, 'success')}</div><p>${count > 1 ? 'Recurring support has helped establish continuity in care.' : 'A targeted session for a specific support need.'}</p></article>`).join('');
}

function renderWardens() {
  el('wardenGrid').innerHTML = data.wardens.map(w => `<article class="warden-card ${w.ladies ? 'highlight' : ''}"><div class="warden-top"><div>${pill(w.ladies ? 'Ladies Hostel Warden' : 'Hostel Warden', w.ladies ? 'warn' : 'info')}<h3 class="card-title" style="margin-top:12px;">${w.name}</h3><p>${w.hostel}</p></div><div class="warden-avatar">${w.code}</div></div><div class="detail-list" style="margin-top:16px;"><div class="detail-item"><span>Role</span><strong>${w.contactInfo}</strong></div><div class="detail-item"><span>Email</span><strong>${w.email}</strong></div><div class="detail-item"><span>Phone</span><strong>${w.phone}</strong></div></div><div class="warden-actions"><a class="btn-dark link-button" href="mailto:${w.email}">Contact Warden</a><a class="btn-light link-button" href="tel:${w.phone.replace(/\s+/g, '')}">Call</a></div></article>`).join('');
}

function lineChart(id, points, series) {
  const svg = el(id); const width = 640, height = 260, p = { top: 24, right: 24, bottom: 38, left: 36 }, iw = width - p.left - p.right, ih = height - p.top - p.bottom;
  const x = i => p.left + (iw / Math.max(points.length - 1, 1)) * i; const y = v => p.top + ih - (v / 100) * ih;
  const grid = [20,40,60,80].map(v => `<line x1="${p.left}" y1="${y(v)}" x2="${width-p.right}" y2="${y(v)}" stroke="rgba(95,124,131,.12)" stroke-dasharray="4 6" />`).join('');
  const lines = series.map((s, idx) => {
    const path = points.map((pt, i) => `${i ? 'L' : 'M'} ${x(i)} ${y(pt[s.key])}`).join(' ');
    const dots = points.map((pt, i) => `<circle cx="${x(i)}" cy="${y(pt[s.key])}" r="4" fill="${s.color}" />`).join('');
    return `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>${dots}<g transform="translate(${p.left + idx * 120}, 12)"><rect x="0" y="-8" width="18" height="4" rx="2" fill="${s.color}"></rect><text x="24" y="-4" font-size="12" fill="#5f7c83">${s.name}</text></g>`;
  }).join('');
  const labels = points.map((pt, i) => `<text x="${x(i)}" y="${height-14}" text-anchor="middle" font-size="11" fill="#7c8391">${pt.label}</text>`).join('');
  svg.innerHTML = `${grid}<line x1="${p.left}" y1="${height-p.bottom}" x2="${width-p.right}" y2="${height-p.bottom}" stroke="rgba(95,124,131,.18)"/>${lines}${labels}`;
}

function barChart(id, points, color) {
  const svg = el(id); const width = 640, height = 260, p = { top: 18, right: 18, bottom: 42, left: 32 }, iw = width - p.left - p.right, ih = height - p.top - p.bottom;
  const gap = 18; const bw = (iw - gap * Math.max(points.length - 1, 0)) / Math.max(points.length, 1);
  svg.innerHTML = `<line x1="${p.left}" y1="${height-p.bottom}" x2="${width-p.right}" y2="${height-p.bottom}" stroke="rgba(95,124,131,.18)"/>` + points.map((pt, i) => {
    const x = p.left + i * (bw + gap); const bh = (pt.value / 100) * ih; const y = p.top + ih - bh;
    return `<rect x="${x}" y="${y}" width="${bw}" height="${bh}" rx="10" fill="${color}" opacity=".88"></rect><text x="${x + bw/2}" y="${y-8}" text-anchor="middle" font-size="11" fill="#5f7c83">${pt.value}</text><text x="${x + bw/2}" y="${height-14}" text-anchor="middle" font-size="11" fill="#7c8391">${pt.label}</text>`;
  }).join('');
}

function setView(view) {
  state.view = view;
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-link[data-view]').forEach(v => v.classList.toggle('active', v.dataset.view === view));
  el(view + 'View').classList.add('active');
  const titles = {
    overview: ['Ward Overview', 'Track well-being, counselling progress, and support contacts.'],
    insights: ['Counselling Insights', 'Review sessions, trend charts, and evaluation notes.'],
    wardens: ['Warden Info', 'Reach hostel wardens quickly with the right contact details.']
  };
  el('pageTitle').textContent = titles[view][0];
  el('pageSubtitle').textContent = titles[view][1];
  if (sidebar) sidebar.classList.remove('open');
}

function initFilters() {
  const counsellors = [...new Set(data.sessions.map(s => s.counsellorName))];
  const types = [...new Set(data.sessions.map(s => s.type))];
  el('counsellorFilter').innerHTML = `<option value="all">All Counsellors</option>` + counsellors.map(v => `<option>${v}</option>`).join('');
  el('typeFilter').innerHTML = `<option value="all">All Types</option>` + types.map(v => `<option>${v}</option>`).join('');
}

function initLoginPage() {
  loginForm.addEventListener('submit', e => {
    e.preventDefault();
    const regNo = el('regNo').value.trim().toUpperCase();
    const accessCode = el('accessCode').value.trim();
    const relation = el('relation').value.trim();
    if (!regNo || !accessCode || !relation) {
      loginError.hidden = false; loginError.textContent = 'Please complete all required fields.'; return;
    }
    if (regNo !== data.credentials.regNo || accessCode !== data.credentials.accessCode) {
      loginError.hidden = false; loginError.textContent = 'Credentials do not match the secure parent access record.'; return;
    }
    loginError.hidden = true;
    saveSession({ relation, loggedInAt: new Date().toISOString() });
    window.location.href = 'dashboard.html';
  });
}

function initDashboardPage() {
  const session = getSession();
  if (!session?.relation) {
    window.location.replace('index.html');
    return;
  }

  el('profileAvatar').textContent = session.relation[0];
  el('profileRole').textContent = session.relation;
  el('profileText').textContent = `${session.relation} of ${data.ward.name}`;

  document.querySelectorAll('.nav-link[data-view]').forEach(btn => btn.addEventListener('click', () => setView(btn.dataset.view)));
  el('logoutBtn').addEventListener('click', () => {
    clearSession();
    if (sidebar) sidebar.classList.remove('open');
    window.location.replace('index.html');
  });
  el('menuBtn').addEventListener('click', () => sidebar.classList.toggle('open'));
  document.querySelectorAll('.sort-button').forEach(btn => btn.addEventListener('click', () => {
    const key = btn.dataset.sort;
    if (state.sortKey === key) state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
    else { state.sortKey = key; state.sortDir = 'asc'; }
    renderSessions();
  }));
  ['searchInput', 'counsellorFilter', 'typeFilter', 'dateFilter'].forEach(id => el(id).addEventListener('input', renderSessions));
  ['counsellorFilter', 'typeFilter', 'dateFilter'].forEach(id => el(id).addEventListener('change', renderSessions));

  el('todayChip').textContent = new Intl.DateTimeFormat('en-US', { dateStyle: 'full' }).format(new Date('2026-04-04'));
  initFilters();
  renderOverview();
  renderSessions();
  renderWardens();
  if (data.ward.stressLevel >= 65) toast('Alert: Stress level is elevated. A follow-up session may be helpful.');
}

if (isLoginPage()) initLoginPage();
if (isDashboardPage()) initDashboardPage();
