const KEY = "constraintcanvas.session";
let memorySession = null;

export function clearSession() {
  memorySession = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* Storage can be disabled. */
  }
}

export function readSession() {
  let value = memorySession;
  try {
    const saved = sessionStorage.getItem(KEY);
    if (saved) value = JSON.parse(saved);
  } catch {
    /* Retain an in-memory session when browser storage is unavailable. */
  }
  if (
    !value ||
    typeof value.token !== "string" ||
    !value.token ||
    !Number.isFinite(value.expiresAt) ||
    value.expiresAt <= Date.now()
  ) {
    clearSession();
    return null;
  }
  return value;
}

export function saveSession(data) {
  if (
    typeof data.access_token !== "string" ||
    !data.access_token ||
    data.token_type?.toLowerCase() !== "bearer" ||
    !Number.isFinite(data.expires_in) ||
    data.expires_in <= 0
  ) {
    throw new Error(
      "The server returned an invalid session. Please try again.",
    );
  }
  memorySession = {
    token: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  try {
    sessionStorage.setItem(KEY, JSON.stringify(memorySession));
  } catch {
    /* Memory-only fallback. */
  }
  return memorySession;
}
