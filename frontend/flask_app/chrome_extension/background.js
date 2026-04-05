import { EQWELL_CONFIG } from "./config.js";

const STORAGE_KEYS = Object.freeze({
  CONSENT: "consent",
  TOKEN: "eqwellJwtToken",
  STUDENT_PROFILE: "eqwellStudentProfile",
  INSTALLED_AT: "extensionInstalledAt",
  CONSENT_GRANTED_AT: "consentGrantedAt",
  ACTIVE_TAB_ID: "activeTabId",
  ACTIVE_TAB_STARTED_AT: "activeTabStartedAt",
  CONTINUOUS_ACTIVE_MS: "continuousActiveMs",
  UNSAFE_DETECTIONS: "unsafeDetections",
  SHOW_COUNSELLOR_ALERT: "showCounsellorAlert",
  LAST_STRESS_SIGNAL: "lastStressSignal",
  LAST_SIGNAL_CONFIDENCE: "lastSignalConfidence",
  LAST_SIGNAL_AT: "lastSignalAt"
});

const HEARTBEAT_ALARM_NAME = "eqwell-presence-heartbeat";
const BATCH_PROCESS_ALARM_NAME = "eqwell-process-collected-batch";
const STATE_CHANGE_RELOAD_THROTTLE_MS = 1800;
const TAB_REANALYZE_COOLDOWN_MS = 2500;
const IDENTITY_RECHECK_INTERVAL_MS = 45000;
let lastStateChangeReloadAt = 0;
const LAST_TAB_ANALYSIS = new Map();
let lastIdentityCheckAt = 0;
let lastIdentityCheckPassed = false;

function shouldTrackUrl(url) {
  const rawUrl = String(url || "").trim();
  if (!rawUrl) {
    return false;
  }

  if (isBrowserInternalUrl(rawUrl)) {
    return false;
  }

  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch (_error) {
    return false;
  }

  const protocol = String(parsed.protocol || "").toLowerCase();
  if (protocol !== "http:" && protocol !== "https:") {
    return false;
  }

  const allowedOrigins = getEqwellAllowedOrigins();
  if (isEqwellAppUrl(rawUrl, allowedOrigins)) {
    return false;
  }

  return true;
}

function normalizeSnippet(value, url) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length >= EQWELL_CONFIG.MIN_SNIPPET_LENGTH) {
    return text.slice(0, EQWELL_CONFIG.MAX_SNIPPET_LENGTH);
  }
  return `Visiting ${String(url || "").slice(0, EQWELL_CONFIG.MAX_SNIPPET_LENGTH - 9)}`;
}

function extractPrimaryQueryValue(rawUrl) {
  const source = String(rawUrl || "");
  const match = source.match(/[?&](?:q|query|search|p|oq)=([^&]+)/i);
  if (!match || !match[1]) {
    return "";
  }

  try {
    return decodeURIComponent(String(match[1]).replace(/\+/g, " ")).replace(/\s+/g, " ").trim();
  } catch (_error) {
    return String(match[1]).replace(/\+/g, " ").replace(/\s+/g, " ").trim();
  }
}

function extractExactQueryFromUrl(url) {
  const primary = extractPrimaryQueryValue(url);
  if (primary) {
    return primary.slice(0, 200);
  }

  try {
    const parsed = new URL(String(url || ""));
    const queryKeys = ["q", "query", "search", "p", "oq", "text", "wd", "k", "keyword"];

    for (const key of queryKeys) {
      const value = parsed.searchParams.get(key);
      if (!value) {
        continue;
      }
      const decoded = decodeURIComponent(String(value).replace(/\+/g, " ")).replace(/\s+/g, " ").trim();
      if (decoded) {
        return decoded.slice(0, 200);
      }
    }

    return "";
  } catch (_error) {
    return "";
  }
}

function extractUrlSearchText(url) {
  const exact = extractExactQueryFromUrl(url);
  if (exact) {
    return exact;
  }

  try {
    const parsed = new URL(String(url || ""));
    const parts = [];
    const textPath = decodeURIComponent(String(parsed.pathname || "").replace(/\//g, " ")).replace(/\s+/g, " ").trim();
    if (textPath) {
      parts.push(textPath);
    }
    return parts.join(" ").slice(0, 200);
  } catch (_error) {
    return "";
  }
}

function buildTemporarySignalText(baseSnippet, currentUrl, extractedQuery) {
  const snippet = String(baseSnippet || "").replace(/\s+/g, " ").trim();
  const exactQuery = String(extractedQuery || "").replace(/\s+/g, " ").trim();
  if (exactQuery) {
    return snippet.slice(0, EQWELL_CONFIG.MAX_SNIPPET_LENGTH);
  }

  const extractedSearchText = extractUrlSearchText(currentUrl);

  if (!extractedSearchText) {
    return snippet.slice(0, EQWELL_CONFIG.MAX_SNIPPET_LENGTH);
  }

  const merged = `URL query context: ${extractedSearchText}. Page context: ${snippet}`.replace(/\s+/g, " ").trim();
  return merged.slice(0, EQWELL_CONFIG.MAX_SNIPPET_LENGTH);
}

function shouldSkipDuplicateAnalysis(tabId, normalizedUrl) {
  const id = Number(tabId);
  if (!Number.isFinite(id) || id < 0) {
    return false;
  }

  const now = Date.now();
  const previous = LAST_TAB_ANALYSIS.get(id);
  if (
    previous
    && previous.url === normalizedUrl
    && (now - Number(previous.at || 0)) < TAB_REANALYZE_COOLDOWN_MS
  ) {
    return true;
  }

  LAST_TAB_ANALYSIS.set(id, { url: normalizedUrl, at: now });
  return false;
}

function buildAppUrl(path) {
  const base = String(EQWELL_CONFIG.AUTH_BASE_URL || "").replace(/\/+$/, "");
  const suffix = String(path || "").startsWith("/") ? String(path || "") : `/${String(path || "")}`;
  return `${base}${suffix}`;
}

function getBatchAlarmPeriodMinutes() {
  const hours = Number(EQWELL_CONFIG.BATCH_WINDOW_HOURS || 12);
  if (!Number.isFinite(hours) || hours <= 0) {
    return 5;
  }
  return Math.max(1, Math.round(hours * 60));
}

function getEqwellAllowedOrigins() {
  const origins = new Set();
  try {
    const parsed = new URL(String(EQWELL_CONFIG.AUTH_BASE_URL || ""));
    origins.add(parsed.origin);
    if (parsed.hostname === "127.0.0.1") {
      origins.add(`${parsed.protocol}//localhost${parsed.port ? `:${parsed.port}` : ""}`);
    }
    if (parsed.hostname === "localhost") {
      origins.add(`${parsed.protocol}//127.0.0.1${parsed.port ? `:${parsed.port}` : ""}`);
    }
  } catch (_error) {
    // Ignore malformed base URL and fallback to simple matching below.
  }
  return origins;
}

function isEqwellAppUrl(rawUrl, allowedOrigins) {
  try {
    const parsed = new URL(String(rawUrl || ""));
    if (allowedOrigins.has(parsed.origin)) {
      return true;
    }
    return parsed.port === "5000" && (parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost");
  } catch (_error) {
    return false;
  }
}

function isBrowserInternalUrl(rawUrl) {
  const url = String(rawUrl || "").toLowerCase();
  return (
    url.startsWith("chrome://")
    || url.startsWith("edge://")
    || url.startsWith("about:")
    || url.startsWith("chrome-extension://")
  );
}

async function ensureUninstallRedirectUrl() {
  try {
    await chrome.runtime.setUninstallURL(buildAppUrl("/login?extension_removed=1"));
  } catch (_error) {
    // Ignore if browser rejects uninstall URL setup.
  }
}

async function forceLogoutAndReloadEqwellTabs(reason) {
  const now = Date.now();
  if (now - lastStateChangeReloadAt < STATE_CHANGE_RELOAD_THROTTLE_MS) {
    return;
  }
  lastStateChangeReloadAt = now;

  const allowedOrigins = getEqwellAllowedOrigins();
  const tabs = await chrome.tabs.query({});
  const logoutUrl = buildAppUrl(`/logout?extension_event=${encodeURIComponent(String(reason || "state-change"))}`);

  for (const tab of tabs) {
    const tabId = tab && typeof tab.id === "number" ? tab.id : null;
    if (tabId === null) {
      continue;
    }
    const candidateUrl = String(tab.url || tab.pendingUrl || "");
    const isEqwellTab = isEqwellAppUrl(candidateUrl, allowedOrigins);

    try {
      if (isEqwellTab) {
        await chrome.tabs.update(tabId, { url: logoutUrl });
      } else if (!isBrowserInternalUrl(candidateUrl)) {
        await chrome.tabs.reload(tabId);
      }
    } catch (_error) {
      // Ignore tabs that cannot be updated/reloaded (e.g., restricted pages).
    }
  }
}

async function setBadge(consent, hasAlert) {
  if (!consent) {
    await chrome.action.setBadgeText({ text: "OFF" });
    await chrome.action.setBadgeBackgroundColor({ color: "#6b7280" });
    return;
  }

  if (hasAlert) {
    await chrome.action.setBadgeText({ text: "!" });
    await chrome.action.setBadgeBackgroundColor({ color: "#b91c1c" });
    return;
  }

  await chrome.action.setBadgeText({ text: "ON" });
  await chrome.action.setBadgeBackgroundColor({ color: "#15803d" });
}

async function initializeDefaults() {
  const current = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.TOKEN,
    STORAGE_KEYS.STUDENT_PROFILE,
    STORAGE_KEYS.INSTALLED_AT,
    STORAGE_KEYS.CONSENT_GRANTED_AT,
    STORAGE_KEYS.UNSAFE_DETECTIONS,
    STORAGE_KEYS.CONTINUOUS_ACTIVE_MS,
    STORAGE_KEYS.SHOW_COUNSELLOR_ALERT
  ]);

  const updates = {};
  if (typeof current[STORAGE_KEYS.CONSENT] !== "boolean") {
    updates[STORAGE_KEYS.CONSENT] = false;
  }
  if (!current[STORAGE_KEYS.INSTALLED_AT]) {
    updates[STORAGE_KEYS.INSTALLED_AT] = new Date().toISOString();
  }
  if (typeof current[STORAGE_KEYS.UNSAFE_DETECTIONS] !== "number") {
    updates[STORAGE_KEYS.UNSAFE_DETECTIONS] = 0;
  }
  if (typeof current[STORAGE_KEYS.CONTINUOUS_ACTIVE_MS] !== "number") {
    updates[STORAGE_KEYS.CONTINUOUS_ACTIVE_MS] = 0;
  }
  if (typeof current[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT] !== "boolean") {
    updates[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT] = false;
  }

  if (Object.keys(updates).length > 0) {
    await chrome.storage.local.set(updates);
  }

  const consent = updates[STORAGE_KEYS.CONSENT] ?? current[STORAGE_KEYS.CONSENT] ?? false;
  const token = String(current[STORAGE_KEYS.TOKEN] || "").trim();
  const profile = current[STORAGE_KEYS.STUDENT_PROFILE] || null;
  const connected = Boolean(token && profile && profile.email);
  await setBadge(consent && connected, false);
}

async function getSessionDurationMinutes(tabId) {
  const now = Date.now();
  const state = await chrome.storage.local.get([
    STORAGE_KEYS.ACTIVE_TAB_ID,
    STORAGE_KEYS.ACTIVE_TAB_STARTED_AT,
    STORAGE_KEYS.CONTINUOUS_ACTIVE_MS
  ]);

  let continuousMs = Number(state[STORAGE_KEYS.CONTINUOUS_ACTIVE_MS]) || 0;
  const activeTabId = state[STORAGE_KEYS.ACTIVE_TAB_ID];
  const activeStartedAt = Number(state[STORAGE_KEYS.ACTIVE_TAB_STARTED_AT]) || 0;

  if (activeStartedAt > 0) {
    const elapsedMs = Math.max(0, now - activeStartedAt);
    continuousMs += elapsedMs;
  }

  await chrome.storage.local.set({
    [STORAGE_KEYS.ACTIVE_TAB_ID]: tabId,
    [STORAGE_KEYS.ACTIVE_TAB_STARTED_AT]: now,
    [STORAGE_KEYS.CONTINUOUS_ACTIVE_MS]: continuousMs
  });

  if (typeof activeTabId === "number" && activeTabId !== tabId) {
    return Math.floor(continuousMs / 60000);
  }
  return Math.floor(continuousMs / 60000);
}

async function readSnippetFromContent(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, {
      type: "EQWELL_GET_SNIPPET",
      maxLen: EQWELL_CONFIG.MAX_SNIPPET_LENGTH
    });
    return response && typeof response.snippet === "string" ? response.snippet : "";
  } catch (_error) {
    return "";
  }
}

async function processSignalResponse(payload) {
  const signal = String(payload?.stress_signal || "MEDIUM").toUpperCase();
  const confidence = Number(payload?.confidence || 0);

  const state = await chrome.storage.local.get([
    STORAGE_KEYS.UNSAFE_DETECTIONS,
    STORAGE_KEYS.SHOW_COUNSELLOR_ALERT
  ]);
  let unsafeDetections = Number(state[STORAGE_KEYS.UNSAFE_DETECTIONS]) || 0;
  const alreadyShowingAlert = Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]);

  if (signal === "HIGH") {
    unsafeDetections += 1;
  } else {
    unsafeDetections = Math.max(0, unsafeDetections - 1);
  }

  const showCounsellorAlert = unsafeDetections >= EQWELL_CONFIG.ALERT_THRESHOLD;

  await chrome.storage.local.set({
    [STORAGE_KEYS.UNSAFE_DETECTIONS]: unsafeDetections,
    [STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]: showCounsellorAlert,
    [STORAGE_KEYS.LAST_STRESS_SIGNAL]: signal,
    [STORAGE_KEYS.LAST_SIGNAL_CONFIDENCE]: confidence,
    [STORAGE_KEYS.LAST_SIGNAL_AT]: new Date().toISOString()
  });

  if (showCounsellorAlert && !alreadyShowingAlert) {
    await chrome.tabs.create({ url: chrome.runtime.getURL("popup.html?alert=1") });
  }

  const consentState = await chrome.storage.local.get([STORAGE_KEYS.CONSENT]);
  await setBadge(Boolean(consentState[STORAGE_KEYS.CONSENT]), showCounsellorAlert);
}

async function sendCollectedEventToAppServer({
  token,
  studentEmail,
  sessionDuration,
  currentUrl,
  extractedQuery,
  pageContext,
  observedAt,
  installedAt,
  consentGrantedAt
}) {
  const endpoint = `${EQWELL_CONFIG.AUTH_BASE_URL}${EQWELL_CONFIG.AUTH_COLLECT_EVENT_PATH}`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      session_duration: Number(sessionDuration || 0),
      current_url: String(currentUrl || "").slice(0, 500),
      extracted_query: String(extractedQuery || "").slice(0, 300),
      page_context: String(pageContext || "").slice(0, EQWELL_CONFIG.MAX_SNIPPET_LENGTH),
      observed_at: observedAt || new Date().toISOString(),
      student_email: String(studentEmail || "").trim().toLowerCase(),
      installed_at: installedAt || null,
      consent_granted_at: consentGrantedAt || null,
      source: "background-collect"
    })
  });

  if (!response.ok) {
    throw new Error(`Collect event failed: ${response.status}`);
  }

  return response.json().catch(() => ({}));
}

async function processCollectedEventsOnServer({ token, studentEmail, installedAt, consentGrantedAt }) {
  const endpoint = `${EQWELL_CONFIG.AUTH_BASE_URL}${EQWELL_CONFIG.AUTH_PROCESS_COLLECTED_PATH}`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      observed_at: new Date().toISOString(),
      student_email: String(studentEmail || "").trim().toLowerCase(),
      installed_at: installedAt || null,
      consent_granted_at: consentGrantedAt || null,
      source: "background-batch-tick"
    })
  });

  if (!response.ok) {
    throw new Error(`Batch process failed: ${response.status}`);
  }

  return response.json().catch(() => ({}));
}

async function sendPresenceHeartbeat({ token, studentEmail, installedAt, consentGrantedAt }) {
  const endpoint = `${EQWELL_CONFIG.AUTH_BASE_URL}${EQWELL_CONFIG.AUTH_PRESENCE_PATH}`;
  try {
    await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        student_email: String(studentEmail || "").trim().toLowerCase(),
        installed_at: installedAt || null,
        consent_granted_at: consentGrantedAt || null,
        observed_at: new Date().toISOString(),
        source: "background-heartbeat"
      })
    });
  } catch (_error) {
    // Presence heartbeat is best-effort only.
  }
}

async function verifyServerStudentIdentity(token, profile, force = false) {
  const now = Date.now();
  if (!force && lastIdentityCheckPassed && (now - lastIdentityCheckAt) < IDENTITY_RECHECK_INTERVAL_MS) {
    return true;
  }

  const expectedEmail = String(profile?.email || "").trim().toLowerCase();
  if (!expectedEmail || !token) {
    lastIdentityCheckAt = now;
    lastIdentityCheckPassed = false;
    return false;
  }

  const endpoint = `${EQWELL_CONFIG.AUTH_BASE_URL}${EQWELL_CONFIG.AUTH_ME_PATH}`;
  try {
    const response = await fetch(endpoint, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    if (response.status === 401 || response.status === 403) {
      lastIdentityCheckAt = now;
      lastIdentityCheckPassed = false;
      return false;
    }
    if (!response.ok) {
      lastIdentityCheckAt = now;
      return null;
    }

    const data = await response.json().catch(() => ({}));
    const serverEmail = String(data?.student?.email || "").trim().toLowerCase();
    if (!serverEmail) {
      lastIdentityCheckAt = now;
      return null;
    }
    const matches = serverEmail === expectedEmail;
    lastIdentityCheckAt = now;
    lastIdentityCheckPassed = Boolean(matches);
    return Boolean(matches);
  } catch (_error) {
    lastIdentityCheckAt = now;
    return null;
  }
}

async function resetExtensionSessionForIdentityMismatch(reason) {
  await chrome.storage.local.set({
    [STORAGE_KEYS.TOKEN]: "",
    [STORAGE_KEYS.STUDENT_PROFILE]: null,
    [STORAGE_KEYS.CONSENT]: false,
    [STORAGE_KEYS.CONSENT_GRANTED_AT]: null,
    [STORAGE_KEYS.UNSAFE_DETECTIONS]: 0,
    [STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]: false
  });
  lastIdentityCheckPassed = false;
  lastIdentityCheckAt = Date.now();
  await setBadge(false, false);
  await forceLogoutAndReloadEqwellTabs(String(reason || "identity-mismatch"));
}

async function runPresenceHeartbeatTick() {
  const state = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.TOKEN,
    STORAGE_KEYS.STUDENT_PROFILE,
    STORAGE_KEYS.INSTALLED_AT,
    STORAGE_KEYS.CONSENT_GRANTED_AT
  ]);

  const consent = Boolean(state[STORAGE_KEYS.CONSENT]);
  const token = String(state[STORAGE_KEYS.TOKEN] || "").trim();
  const profile = state[STORAGE_KEYS.STUDENT_PROFILE] || null;
  const hasProfile = Boolean(profile && profile.email);
  if (!consent || !token || !hasProfile) {
    return;
  }

  const identityOk = await verifyServerStudentIdentity(token, profile);
  if (identityOk === false) {
    await resetExtensionSessionForIdentityMismatch("heartbeat-identity-mismatch");
    return;
  }

  await sendPresenceHeartbeat({
    token,
    studentEmail: String(profile.email || "").trim().toLowerCase(),
    installedAt: state[STORAGE_KEYS.INSTALLED_AT] || null,
    consentGrantedAt: state[STORAGE_KEYS.CONSENT_GRANTED_AT] || null
  });
}

async function runBatchProcessingTick() {
  const state = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.TOKEN,
    STORAGE_KEYS.STUDENT_PROFILE,
    STORAGE_KEYS.INSTALLED_AT,
    STORAGE_KEYS.CONSENT_GRANTED_AT,
    STORAGE_KEYS.SHOW_COUNSELLOR_ALERT
  ]);

  const consent = Boolean(state[STORAGE_KEYS.CONSENT]);
  const token = String(state[STORAGE_KEYS.TOKEN] || "").trim();
  const profile = state[STORAGE_KEYS.STUDENT_PROFILE] || null;
  const hasProfile = Boolean(profile && profile.email);

  if (!consent || !token || !hasProfile) {
    await setBadge(false, Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]));
    return;
  }

  const identityOk = await verifyServerStudentIdentity(token, profile);
  if (identityOk === false) {
    await resetExtensionSessionForIdentityMismatch("batch-identity-mismatch");
    return;
  }

  try {
    const result = await processCollectedEventsOnServer({
      token,
      studentEmail: String(profile.email || "").trim().toLowerCase(),
      installedAt: state[STORAGE_KEYS.INSTALLED_AT] || null,
      consentGrantedAt: state[STORAGE_KEYS.CONSENT_GRANTED_AT] || null
    });

    if (result && result.has_update) {
      await processSignalResponse(result);
      return;
    }

    await setBadge(consent, Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]));
  } catch (_error) {
    await setBadge(consent, Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]));
  }
}

async function analyzeTab(tabId, url) {
  const normalizedUrl = String(url || "").slice(0, 500);
  if (!shouldTrackUrl(normalizedUrl)) {
    return;
  }

  if (shouldSkipDuplicateAnalysis(tabId, normalizedUrl)) {
    return;
  }

  const state = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.TOKEN,
    STORAGE_KEYS.STUDENT_PROFILE,
    STORAGE_KEYS.INSTALLED_AT,
    STORAGE_KEYS.CONSENT_GRANTED_AT,
    STORAGE_KEYS.SHOW_COUNSELLOR_ALERT
  ]);

  const consent = Boolean(state[STORAGE_KEYS.CONSENT]);
  const token = String(state[STORAGE_KEYS.TOKEN] || "").trim();
  const profile = state[STORAGE_KEYS.STUDENT_PROFILE] || null;
  const hasProfile = Boolean(profile && profile.email);
  const installedAt = state[STORAGE_KEYS.INSTALLED_AT] || null;
  const consentGrantedAt = state[STORAGE_KEYS.CONSENT_GRANTED_AT] || null;

  if (!consent || !token || !hasProfile) {
    await setBadge(false, Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]));
    return;
  }

  const identityOk = await verifyServerStudentIdentity(token, profile);
  if (identityOk === false) {
    await resetExtensionSessionForIdentityMismatch("collect-identity-mismatch");
    return;
  }

  const sessionDuration = await getSessionDurationMinutes(tabId);
  const observedAt = new Date().toISOString();
  let text = await readSnippetFromContent(tabId);
  const extractedQuery = extractExactQueryFromUrl(normalizedUrl);
  text = normalizeSnippet(text, normalizedUrl);
  const pageContext = buildTemporarySignalText(text, normalizedUrl, extractedQuery);

  try {
    await sendCollectedEventToAppServer({
      token,
      studentEmail: String(profile.email || "").trim().toLowerCase(),
      sessionDuration,
      currentUrl: normalizedUrl,
      extractedQuery,
      pageContext,
      observedAt,
      installedAt,
      consentGrantedAt
    });

    if (Boolean(EQWELL_CONFIG.PROCESS_IMMEDIATELY_AFTER_COLLECT)) {
      const result = await processCollectedEventsOnServer({
        token,
        studentEmail: String(profile.email || "").trim().toLowerCase(),
        installedAt,
        consentGrantedAt
      });

      if (result && result.has_update) {
        await processSignalResponse(result);
      }
    }
  } catch (_error) {
    // Keep collection resilient if app server is temporarily unavailable.
    await setBadge(consent, Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]));
  }
}

async function analyzeFromTabObject(tab) {
  if (!tab || typeof tab.id !== "number") {
    return;
  }
  await analyzeTab(tab.id, tab.url || tab.pendingUrl || "");
}

async function collectAllOpenTabsSnapshot() {
  const tabs = await chrome.tabs.query({});
  for (const tab of tabs) {
    if (!tab || typeof tab.id !== "number") {
      continue;
    }
    await analyzeTab(tab.id, tab.url || tab.pendingUrl || "");
  }
}

chrome.runtime.onInstalled.addListener(async (details) => {
  await initializeDefaults();
  await ensureUninstallRedirectUrl();
  await chrome.storage.local.set({ [STORAGE_KEYS.INSTALLED_AT]: new Date().toISOString() });
  await chrome.alarms.create(HEARTBEAT_ALARM_NAME, {
    periodInMinutes: Math.max(1, Number(EQWELL_CONFIG.PRESENCE_HEARTBEAT_MINUTES || 1))
  });
  await chrome.alarms.create(BATCH_PROCESS_ALARM_NAME, {
    delayInMinutes: 1,
    periodInMinutes: getBatchAlarmPeriodMinutes()
  });
  await collectAllOpenTabsSnapshot();
  await forceLogoutAndReloadEqwellTabs("extension-installed");
  if (details.reason === "install") {
    await chrome.tabs.create({ url: chrome.runtime.getURL("popup.html?firstRun=1") });
  }
});

chrome.runtime.onStartup.addListener(async () => {
  await initializeDefaults();
  await ensureUninstallRedirectUrl();
  await chrome.alarms.create(HEARTBEAT_ALARM_NAME, {
    periodInMinutes: Math.max(1, Number(EQWELL_CONFIG.PRESENCE_HEARTBEAT_MINUTES || 1))
  });
  await chrome.alarms.create(BATCH_PROCESS_ALARM_NAME, {
    delayInMinutes: 1,
    periodInMinutes: getBatchAlarmPeriodMinutes()
  });
  await collectAllOpenTabsSnapshot();
  await forceLogoutAndReloadEqwellTabs("extension-startup");
});

initializeDefaults().catch(() => {
  // Ignore startup race errors from service worker initialization.
});

chrome.tabs.onCreated.addListener(async (tab) => {
  await analyzeFromTabObject(tab);
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    await analyzeFromTabObject(tab);
  } catch (_error) {
    // Ignore inaccessible tab events.
  }
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (typeof changeInfo.url === "string" && changeInfo.url) {
    await analyzeTab(tabId, changeInfo.url);
  }

  if (changeInfo.status === "complete") {
    await analyzeTab(tabId, tab.url || changeInfo.url || "");
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  LAST_TAB_ANALYSIS.delete(Number(tabId));
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || !message.type) {
    return false;
  }

  if (message.type === "EQWELL_STATE_CHANGED") {
    sendResponse({ ok: true });
    forceLogoutAndReloadEqwellTabs(String(message.reason || "state-changed")).catch(() => {
      // Best-effort refresh only.
    });
    return false;
  }

  if (message.type !== "EQWELL_REFRESH") {
    return false;
  }

  sendResponse({ ok: true });

  chrome.storage.local
    .get([STORAGE_KEYS.CONSENT, STORAGE_KEYS.SHOW_COUNSELLOR_ALERT])
    .then((state) => setBadge(Boolean(state[STORAGE_KEYS.CONSENT]), Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT])))
    .catch(() => {
      // Ignore badge refresh failures.
    });

  return false;
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (!alarm) {
    return;
  }
  if (alarm.name === HEARTBEAT_ALARM_NAME) {
    await runPresenceHeartbeatTick();
    return;
  }
  if (alarm.name === BATCH_PROCESS_ALARM_NAME) {
    await runBatchProcessingTick();
  }
});

chrome.runtime.onSuspend.addListener(() => {
  // Best-effort flush right before worker suspension/disable/uninstall.
  forceLogoutAndReloadEqwellTabs("extension-suspend").catch(() => {});
});
