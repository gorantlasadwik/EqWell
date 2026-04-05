export const EQWELL_CONFIG = Object.freeze({
  AUTH_BASE_URL: "https://eq-well.vercel.app",
  AUTH_LOGIN_PATH: "/api/extension/student/login",
  AUTH_ME_PATH: "/api/extension/student/me",
  AUTH_PRESENCE_PATH: "/api/extension/student/presence",
  AUTH_COLLECT_EVENT_PATH: "/api/extension/student/collect-event",
  AUTH_PROCESS_COLLECTED_PATH: "/api/extension/student/process-collected",
  BATCH_WINDOW_HOURS: 12,
  PROCESS_IMMEDIATELY_AFTER_COLLECT: true,
  PRESENCE_HEARTBEAT_MINUTES: 1,
  MAX_SNIPPET_LENGTH: 300,
  ALERT_THRESHOLD: 3,
  MIN_SNIPPET_LENGTH: 24
});
