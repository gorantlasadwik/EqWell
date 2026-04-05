function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

const STORAGE_KEYS = Object.freeze({
  TOKEN: "eqwellJwtToken",
  STUDENT_PROFILE: "eqwellStudentProfile"
});

const PROOF_REFRESH_INTERVAL_MS = 5000;
const PORTAL_SYNC_INTERVAL_MS = 6000;
const BOOTSTRAP_SCRIPT_ID = "eqwell-extension-bootstrap";
let proofRequestInFlight = null;
let submitReplayAllowed = false;
let lastProofNonce = "";
let lastProofAt = 0;

function collectSnippet(maxLength) {
  const chunks = [];

  const title = cleanText(document.title);
  if (title) {
    chunks.push(title);
  }

  const selectors = ["main", "article", "h1", "h2", "p"];
  const seen = new Set();

  for (const selector of selectors) {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) {
      const text = cleanText(node.innerText || node.textContent || "");
      if (text.length < 20) {
        continue;
      }
      if (!seen.has(text)) {
        seen.add(text);
        chunks.push(text);
      }
      const joined = cleanText(chunks.join(" "));
      if (joined.length >= maxLength) {
        return joined.slice(0, maxLength);
      }
      if (chunks.length >= 14) {
        return joined.slice(0, maxLength);
      }
    }
  }

  return cleanText(chunks.join(" ")).slice(0, maxLength);
}

function isEqwellLoginPage() {
  const pathname = String(window.location.pathname || "").toLowerCase();
  return pathname === "/login" || pathname.startsWith("/login/");
}

function getStorageSnapshot(keys) {
  return new Promise((resolve) => {
    try {
      chrome.storage.local.get(keys, (items) => {
        resolve(items || {});
      });
    } catch (_error) {
      resolve({});
    }
  });
}

function setStorageSnapshot(values) {
  return new Promise((resolve) => {
    try {
      chrome.storage.local.set(values || {}, () => {
        resolve(true);
      });
    } catch (_error) {
      resolve(false);
    }
  });
}

function sendRuntimeMessageSafe(payload) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage(payload, () => {
        resolve(true);
      });
    } catch (_error) {
      resolve(false);
    }
  });
}

function getStudentEmailFromProfile(profileValue) {
  if (!profileValue || typeof profileValue !== "object") {
    return "";
  }
  return String(profileValue.email || "").trim().toLowerCase();
}

function getLoginProofElements() {
  const form = document.querySelector("form.auth-form");
  if (!form) {
    return null;
  }

  return {
    form,
    roleInput: document.getElementById("role"),
    nonceInput: document.getElementById("extension-portal-nonce"),
    proofInput: document.getElementById("extension-portal-proof"),
    statusNode: document.getElementById("extension-proof-status")
  };
}

function setProofStatus(statusNode, message, isError) {
  if (!statusNode) {
    return;
  }
  statusNode.textContent = String(message || "").trim();
  statusNode.setAttribute("data-status", isError ? "error" : "ok");
}

async function requestPortalProof(nonce, token, studentEmail) {
  const response = await fetch("/api/extension/student/portal-proof", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      nonce,
      student_email: studentEmail,
      source: "portal-login-content-script"
    })
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }

  if (!response.ok) {
    return {
      ok: false,
      error: String(payload.error || "Extension verification failed for this browser tab.").trim()
    };
  }

  return {
    ok: true,
    proof: String(payload.proof || "").trim()
  };
}

async function ensureStudentPortalProof(forceRefresh) {
  if (!isEqwellLoginPage()) {
    return true;
  }

  const elements = getLoginProofElements();
  if (!elements) {
    return true;
  }

  const roleValue = String((elements.roleInput && elements.roleInput.value) || "").trim().toLowerCase();
  if (roleValue && roleValue !== "student") {
    if (elements.proofInput) {
      elements.proofInput.value = "";
    }
    setProofStatus(elements.statusNode, "Extension check is required only for student login.", false);
    return true;
  }

  const nonce = String((elements.nonceInput && elements.nonceInput.value) || "").trim();
  if (!nonce) {
    if (elements.proofInput) {
      elements.proofInput.value = "";
    }
    setProofStatus(elements.statusNode, "Login session expired. Reload this page before student login.", true);
    return false;
  }

  const now = Date.now();
  const hasFreshProof = (
    !forceRefresh
    && elements.proofInput
    && elements.proofInput.value
    && lastProofNonce === nonce
    && (now - lastProofAt) < 45000
  );
  if (hasFreshProof) {
    setProofStatus(elements.statusNode, "Extension verified for this browser tab.", false);
    return true;
  }

  if (proofRequestInFlight) {
    await proofRequestInFlight;
    return Boolean(elements.proofInput && elements.proofInput.value);
  }

  proofRequestInFlight = (async () => {
    const storage = await getStorageSnapshot([STORAGE_KEYS.TOKEN, STORAGE_KEYS.STUDENT_PROFILE]);
    const token = String(storage[STORAGE_KEYS.TOKEN] || "").trim();
    const studentEmail = getStudentEmailFromProfile(storage[STORAGE_KEYS.STUDENT_PROFILE]);

    if (!token || !studentEmail) {
      if (elements.proofInput) {
        elements.proofInput.value = "";
      }
      setProofStatus(
        elements.statusNode,
        "Open EqWell extension in this browser and login as student before portal login.",
        true
      );
      return false;
    }

    try {
      const proofResponse = await requestPortalProof(nonce, token, studentEmail);
      if (!proofResponse.ok || !proofResponse.proof) {
        if (elements.proofInput) {
          elements.proofInput.value = "";
        }
        setProofStatus(elements.statusNode, proofResponse.error, true);
        return false;
      }

      if (elements.proofInput) {
        elements.proofInput.value = proofResponse.proof;
      }
      lastProofNonce = nonce;
      lastProofAt = Date.now();
      setProofStatus(elements.statusNode, "Extension verified for this browser tab.", false);
      return true;
    } catch (_error) {
      if (elements.proofInput) {
        elements.proofInput.value = "";
      }
      setProofStatus(elements.statusNode, "Unable to verify extension right now. Try again.", true);
      return false;
    }
  })();

  const isReady = await proofRequestInFlight;
  proofRequestInFlight = null;
  return Boolean(isReady);
}

function installLoginProofBinding() {
  if (!isEqwellLoginPage()) {
    return;
  }

  const elements = getLoginProofElements();
  if (!elements || !elements.form) {
    return;
  }

  const triggerProofRefreshSoon = () => {
    window.setTimeout(() => {
      ensureStudentPortalProof(false).catch(() => {});
    }, 60);
  };

  elements.form.addEventListener("submit", async (event) => {
    if (submitReplayAllowed) {
      submitReplayAllowed = false;
      return;
    }

    const roleValue = String((elements.roleInput && elements.roleInput.value) || "").trim().toLowerCase();
    if (roleValue && roleValue !== "student") {
      return;
    }

    event.preventDefault();
    const proofReady = await ensureStudentPortalProof(true);
    if (!proofReady) {
      alert("Student login is blocked. Keep EqWell extension installed and logged in on this same browser tab.");
      return;
    }

    submitReplayAllowed = true;
    if (typeof elements.form.requestSubmit === "function") {
      elements.form.requestSubmit();
      return;
    }
    elements.form.submit();
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    if (target.closest(".role-option") || target.closest(".auth-role-card") || target.closest("#role-trigger")) {
      triggerProofRefreshSoon();
    }
  });

  const emailInput = document.getElementById("email");
  if (emailInput) {
    emailInput.addEventListener("change", triggerProofRefreshSoon);
    emailInput.addEventListener("blur", triggerProofRefreshSoon);
  }

  ensureStudentPortalProof(true).catch(() => {});
  window.setInterval(() => {
    ensureStudentPortalProof(false).catch(() => {});
  }, PROOF_REFRESH_INTERVAL_MS);
}

function parseBootstrapPayloadFromDom() {
  const node = document.getElementById(BOOTSTRAP_SCRIPT_ID);
  if (!node) {
    return null;
  }

  try {
    const payload = JSON.parse(String(node.textContent || "").trim() || "{}");
    if (!payload || typeof payload !== "object") {
      return null;
    }
    const token = String(payload.token || "").trim();
    const student = payload.student && typeof payload.student === "object" ? payload.student : null;
    const email = student ? String(student.email || "").trim().toLowerCase() : "";
    if (!token || !student || !email) {
      return null;
    }
    return {
      token,
      student: {
        name: String(student.name || "Student").trim() || "Student",
        email,
        role: "student"
      }
    };
  } catch (_error) {
    return null;
  }
}

async function syncExtensionSessionFromPortalBootstrap() {
  const bootstrap = parseBootstrapPayloadFromDom();
  if (!bootstrap) {
    return false;
  }

  const existing = await getStorageSnapshot([STORAGE_KEYS.TOKEN, STORAGE_KEYS.STUDENT_PROFILE]);
  const currentToken = String(existing[STORAGE_KEYS.TOKEN] || "").trim();
  const currentProfile = existing[STORAGE_KEYS.STUDENT_PROFILE] || {};
  const currentEmail = String((currentProfile && currentProfile.email) || "").trim().toLowerCase();

  if (currentToken === bootstrap.token && currentEmail === bootstrap.student.email) {
    return true;
  }

  const saved = await setStorageSnapshot({
    [STORAGE_KEYS.TOKEN]: bootstrap.token,
    [STORAGE_KEYS.STUDENT_PROFILE]: bootstrap.student
  });

  if (saved) {
    await sendRuntimeMessageSafe({ type: "EQWELL_REFRESH" });
  }

  return Boolean(saved);
}

installLoginProofBinding();

syncExtensionSessionFromPortalBootstrap().catch(() => {});
window.setInterval(() => {
  syncExtensionSessionFromPortalBootstrap().catch(() => {});
}, PORTAL_SYNC_INTERVAL_MS);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "EQWELL_GET_SNIPPET") {
    return false;
  }

  const maxLength = Number(message.maxLen) || 300;
  const snippet = collectSnippet(Math.min(Math.max(maxLength, 50), 300));
  sendResponse({ snippet });
  return true;
});
