import { EQWELL_CONFIG } from "./config.js";

const STORAGE_KEYS = Object.freeze({
  CONSENT: "consent",
  TOKEN: "eqwellJwtToken",
  STUDENT_PROFILE: "eqwellStudentProfile",
  INSTALLED_AT: "extensionInstalledAt",
  CONSENT_GRANTED_AT: "consentGrantedAt",
  SHOW_COUNSELLOR_ALERT: "showCounsellorAlert",
  LAST_STRESS_SIGNAL: "lastStressSignal",
  LAST_SIGNAL_CONFIDENCE: "lastSignalConfidence",
  LAST_SIGNAL_AT: "lastSignalAt",
  UNSAFE_DETECTIONS: "unsafeDetections"
});

const consentToggle = document.getElementById("consentToggle");
const statusPill = document.getElementById("statusPill");
const statusMeta = document.getElementById("statusMeta");
const loginSection = document.getElementById("loginSection");
const emailInput = document.getElementById("emailInput");
const passwordInput = document.getElementById("passwordInput");
const loginButton = document.getElementById("loginButton");
const logoutButton = document.getElementById("logoutButton");
const authMessage = document.getElementById("authMessage");
const studentInfo = document.getElementById("studentInfo");
const alertPanel = document.getElementById("alertPanel");
const clearAlertButton = document.getElementById("clearAlertButton");
let isServerVerifiedConnected = false;

function buildAppUrl(path) {
  const base = String(EQWELL_CONFIG.AUTH_BASE_URL || "").replace(/\/+$/, "");
  const suffix = String(path || "").startsWith("/") ? String(path || "") : `/${String(path || "")}`;
  return `${base}${suffix}`;
}

function isStudentProtectedTabUrl(rawUrl) {
  const urlText = String(rawUrl || "").trim();
  if (!urlText) {
    return false;
  }

  let parsed;
  let appBase;
  try {
    parsed = new URL(urlText);
    appBase = new URL(String(EQWELL_CONFIG.AUTH_BASE_URL || ""));
  } catch (_error) {
    return false;
  }

  const sameOrigin = parsed.origin === appBase.origin;
  const localhostAlias =
    parsed.port === appBase.port
    && ((parsed.hostname === "localhost" && appBase.hostname === "127.0.0.1")
      || (parsed.hostname === "127.0.0.1" && appBase.hostname === "localhost"));

  if (!sameOrigin && !localhostAlias) {
    return false;
  }

  const path = String(parsed.pathname || "").toLowerCase();
  return path.startsWith("/student") || path.startsWith("/dashboard/student");
}

async function hasOpenStudentProtectedTab() {
  const tabs = await chrome.tabs.query({});
  return tabs.some((tab) => isStudentProtectedTabUrl(tab?.url || tab?.pendingUrl || ""));
}

async function redirectEqWellPageAfterExtensionLogin() {
  const targetUrl = buildAppUrl("/login");
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs && tabs.length ? tabs[0] : null;
  if (!tab || typeof tab.id !== "number") {
    await chrome.tabs.create({ url: targetUrl });
    return;
  }

  const currentUrl = String(tab.url || "");
  const sameOrigin = currentUrl.startsWith(String(EQWELL_CONFIG.AUTH_BASE_URL || ""));
  const installPageOpen = currentUrl.includes("/install-extension");

  if (sameOrigin || installPageOpen) {
    await chrome.tabs.update(tab.id, { url: targetUrl });
    return;
  }

  await chrome.tabs.create({ url: targetUrl });
}

function setAuthUiConnected(connected) {
  if (loginSection) {
    loginSection.classList.toggle("hidden", connected);
  }
  if (logoutButton) {
    logoutButton.classList.toggle("hidden", !connected);
  }
}

async function loginWithStudentCredentials(email, password) {
  const endpoint = `${EQWELL_CONFIG.AUTH_BASE_URL}${EQWELL_CONFIG.AUTH_LOGIN_PATH}`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = String(data?.error || "Login failed");
    throw new Error(message);
  }

  return {
    token: String(data?.token || "").trim(),
    student: data?.student || null,
    message: String(data?.message || "Connected")
  };
}

async function fetchVerifiedStudentProfile(token) {
  const endpoint = `${EQWELL_CONFIG.AUTH_BASE_URL}${EQWELL_CONFIG.AUTH_ME_PATH}`;
  let response;
  try {
    response = await fetch(endpoint, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
  } catch (_error) {
    const networkError = new Error("Cannot reach EqWell server right now.");
    networkError.code = "NETWORK_ERROR";
    throw networkError;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = String(data?.error || "Session verification failed");
    const error = new Error(message);
    error.code = (response.status === 401 || response.status === 403) ? "AUTH_INVALID" : "SERVER_ERROR";
    throw error;
  }

  const student = data?.student || null;
  if (!student || !student.email) {
    const profileError = new Error("Student profile missing");
    profileError.code = "SERVER_ERROR";
    throw profileError;
  }
  return student;
}

async function registerPresence(token, studentEmail = "") {
  const state = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.INSTALLED_AT,
    STORAGE_KEYS.CONSENT_GRANTED_AT
  ]);

  const updates = {};
  let installedAt = state[STORAGE_KEYS.INSTALLED_AT] || null;
  let consentGrantedAt = state[STORAGE_KEYS.CONSENT_GRANTED_AT] || null;
  const consent = Boolean(state[STORAGE_KEYS.CONSENT]);

  if (!installedAt) {
    installedAt = new Date().toISOString();
    updates[STORAGE_KEYS.INSTALLED_AT] = installedAt;
  }

  if (consent && !consentGrantedAt) {
    consentGrantedAt = new Date().toISOString();
    updates[STORAGE_KEYS.CONSENT_GRANTED_AT] = consentGrantedAt;
  }

  if (Object.keys(updates).length > 0) {
    await chrome.storage.local.set(updates);
  }

  const endpoint = `${EQWELL_CONFIG.AUTH_BASE_URL}${EQWELL_CONFIG.AUTH_PRESENCE_PATH}`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      student_email: String(studentEmail || "").trim().toLowerCase(),
      installed_at: installedAt,
      consent_granted_at: consentGrantedAt,
      observed_at: new Date().toISOString(),
      source: "popup-login"
    })
  });

  if (!response.ok) {
    throw new Error("Presence registration failed");
  }

  return response.json().catch(() => ({}));
}

async function notifyStateChangeAndReloadPages(reason) {
  await sendRuntimeMessageSafe({
    type: "EQWELL_STATE_CHANGED",
    reason: String(reason || "state-change")
  });
}

function isIgnorableRuntimeMessageError(error) {
  const message = String(error?.message || "").toLowerCase();
  return (
    message.includes("message port closed")
    || message.includes("receiving end does not exist")
    || message.includes("context invalidated")
  );
}

async function sendRuntimeMessageSafe(payload) {
  try {
    await chrome.runtime.sendMessage(payload);
    return true;
  } catch (error) {
    if (isIgnorableRuntimeMessageError(error)) {
      return false;
    }
    throw error;
  }
}

function setStatus(active, connected) {
  if (!connected) {
    statusPill.textContent = "Login Required";
    statusPill.classList.remove("active");
    statusPill.classList.add("paused");
    return;
  }

  statusPill.textContent = active ? "Monitoring Active" : "Monitoring Paused";
  statusPill.classList.toggle("active", active);
  statusPill.classList.toggle("paused", !active);
}

function setAlertVisible(visible) {
  alertPanel.classList.toggle("hidden", !visible);
}

function formatMeta(state) {
  const signal = String(state[STORAGE_KEYS.LAST_STRESS_SIGNAL] || "-");
  const confidence = Number(state[STORAGE_KEYS.LAST_SIGNAL_CONFIDENCE] || 0);
  const detections = Number(state[STORAGE_KEYS.UNSAFE_DETECTIONS] || 0);
  const at = state[STORAGE_KEYS.LAST_SIGNAL_AT];

  if (!at) {
    return "No recent checks";
  }

  const time = new Date(at).toLocaleTimeString();
  return `Last signal: ${signal} (${confidence.toFixed(2)}) at ${time}. High streak: ${detections}`;
}

async function refreshUi() {
  const state = await chrome.storage.local.get([
    STORAGE_KEYS.CONSENT,
    STORAGE_KEYS.TOKEN,
    STORAGE_KEYS.STUDENT_PROFILE,
    STORAGE_KEYS.SHOW_COUNSELLOR_ALERT,
    STORAGE_KEYS.LAST_STRESS_SIGNAL,
    STORAGE_KEYS.LAST_SIGNAL_CONFIDENCE,
    STORAGE_KEYS.LAST_SIGNAL_AT,
    STORAGE_KEYS.UNSAFE_DETECTIONS
  ]);

  let consent = Boolean(state[STORAGE_KEYS.CONSENT]);
  const hadConsent = consent;

  let profile = state[STORAGE_KEYS.STUDENT_PROFILE] || null;
  const token = String(state[STORAGE_KEYS.TOKEN] || "").trim();
  const hadToken = Boolean(token);

  let isConnected = false;
  let sessionInvalidated = false;
  let verificationDegraded = false;
  if (token) {
    try {
      const verifiedProfile = await fetchVerifiedStudentProfile(token);
      profile = verifiedProfile;
      isConnected = true;
      await chrome.storage.local.set({ [STORAGE_KEYS.STUDENT_PROFILE]: verifiedProfile });
    } catch (error) {
      const code = String(error?.code || "").trim();
      if (code === "AUTH_INVALID") {
        sessionInvalidated = true;
        await chrome.storage.local.set({
          [STORAGE_KEYS.TOKEN]: "",
          [STORAGE_KEYS.STUDENT_PROFILE]: null,
          [STORAGE_KEYS.CONSENT]: false
        });
        profile = null;
        isConnected = false;
        consent = false;
      } else {
        verificationDegraded = true;
        isConnected = Boolean(token && profile && profile.email);
      }
    }
  }

  if (!isConnected && verificationDegraded && token) {
    // Keep local extension session active while /me verification is temporarily unavailable.
    isConnected = true;
  }

  isServerVerifiedConnected = isConnected;
  if (sessionInvalidated && consent) {
    consent = false;
    await chrome.storage.local.set({ [STORAGE_KEYS.CONSENT]: false });
  }

  let authSummaryMessage = isConnected
    ? "Login successful. Connected to EqWell app server"
    : "Sign in with the same student credentials used in EqWell.";

  if (sessionInvalidated && hadToken) {
    authSummaryMessage = "Session expired. Please login again.";
    await notifyStateChangeAndReloadPages("session-invalidated");
  } else if (verificationDegraded && isConnected) {
    authSummaryMessage = "Extension is connected. Server check temporarily unavailable; retrying automatically.";
  } else if (!isConnected && hadConsent) {
    await notifyStateChangeAndReloadPages("monitoring-off");
  } else if (!isConnected) {
    try {
      if (await hasOpenStudentProtectedTab()) {
        await notifyStateChangeAndReloadPages("student-page-open-without-extension-login");
      }
    } catch (_error) {
      // Ignore tab query failures and keep popup responsive.
    }
  }

  consentToggle.checked = consent;
  consentToggle.disabled = !isConnected;
  setStatus(consent, isConnected);

  setAuthUiConnected(isConnected);
  if (profile && profile.email) {
    if (emailInput) {
      emailInput.value = String(profile.email);
    }
    studentInfo.textContent = `Connected: ${String(profile.name || "Student")} (${String(profile.email)})`;
  } else {
    if (emailInput) {
      emailInput.value = "";
    }
    studentInfo.textContent = "No student connected";
  }

  authMessage.textContent = authSummaryMessage;

  statusMeta.textContent = formatMeta(state);
  setAlertVisible(Boolean(state[STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]));
}

consentToggle.addEventListener("change", async () => {
  if (consentToggle.checked && !isServerVerifiedConnected) {
    consentToggle.checked = false;
    authMessage.textContent = "Please login first to enable monitoring.";
    await chrome.storage.local.set({ [STORAGE_KEYS.CONSENT]: false });
    await sendRuntimeMessageSafe({ type: "EQWELL_REFRESH" });
    await refreshUi();
    return;
  }

  const updates = { [STORAGE_KEYS.CONSENT]: consentToggle.checked };
  if (consentToggle.checked) {
    const state = await chrome.storage.local.get([STORAGE_KEYS.CONSENT_GRANTED_AT]);
    if (!state[STORAGE_KEYS.CONSENT_GRANTED_AT]) {
      updates[STORAGE_KEYS.CONSENT_GRANTED_AT] = new Date().toISOString();
    }
  } else {
    updates[STORAGE_KEYS.CONSENT_GRANTED_AT] = null;
  }
  await chrome.storage.local.set(updates);
  const state = await chrome.storage.local.get([STORAGE_KEYS.TOKEN]);
  const token = String(state[STORAGE_KEYS.TOKEN] || "").trim();
  if (token) {
    try {
      const profileState = await chrome.storage.local.get([STORAGE_KEYS.STUDENT_PROFILE]);
      const profile = profileState[STORAGE_KEYS.STUDENT_PROFILE] || null;
      await registerPresence(token, String(profile?.email || "").trim().toLowerCase());
    } catch (_error) {
      // Keep consent toggle UX non-blocking if server is temporarily unavailable.
    }
  }
  await notifyStateChangeAndReloadPages(consentToggle.checked ? "monitoring-on" : "monitoring-off");
  await sendRuntimeMessageSafe({ type: "EQWELL_REFRESH" });
  await refreshUi();
});

loginButton.addEventListener("click", async () => {
  const email = String(emailInput.value || "").trim().toLowerCase();
  const password = String(passwordInput.value || "");

  if (!email || !password) {
    authMessage.textContent = "Enter both student email and password.";
    return;
  }

  authMessage.textContent = "Connecting to EqWell...";
  try {
    const result = await loginWithStudentCredentials(email, password);
    if (!result.token) {
      throw new Error("Server did not return a token");
    }

    const verifiedProfile = await fetchVerifiedStudentProfile(result.token);

    await chrome.storage.local.set({
      [STORAGE_KEYS.TOKEN]: result.token,
      [STORAGE_KEYS.STUDENT_PROFILE]: verifiedProfile
    });
    const presence = await registerPresence(result.token, String(verifiedProfile?.email || "").trim().toLowerCase());
    passwordInput.value = "";
    authMessage.textContent = "Login successful. Connected to EqWell app server";

    if (presence && presence.extension_ready) {
      await redirectEqWellPageAfterExtensionLogin();
    } else if (presence && presence.suspicious) {
      authMessage.textContent = "Login successful. Security check running, wait a few seconds and retry.";
    }

    await sendRuntimeMessageSafe({ type: "EQWELL_REFRESH" });
    await refreshUi();
  } catch (error) {
    authMessage.textContent = error instanceof Error ? error.message : "Connection failed";
  }
});

logoutButton.addEventListener("click", async () => {
  await chrome.storage.local.set({
    [STORAGE_KEYS.TOKEN]: "",
    [STORAGE_KEYS.STUDENT_PROFILE]: null,
    [STORAGE_KEYS.CONSENT]: false,
    [STORAGE_KEYS.UNSAFE_DETECTIONS]: 0,
    [STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]: false
  });
  if (passwordInput) {
    passwordInput.value = "";
  }
  authMessage.textContent = "Disconnected from EqWell account.";
  await notifyStateChangeAndReloadPages("extension-logout");
  await sendRuntimeMessageSafe({ type: "EQWELL_REFRESH" });
  await refreshUi();
});

clearAlertButton.addEventListener("click", async () => {
  await chrome.storage.local.set({
    [STORAGE_KEYS.SHOW_COUNSELLOR_ALERT]: false,
    [STORAGE_KEYS.UNSAFE_DETECTIONS]: 0
  });
  await sendRuntimeMessageSafe({ type: "EQWELL_REFRESH" });
  await refreshUi();
});

refreshUi();
