const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEFAULT_TIMEOUT_MS = 30000;

async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(id);
  }
}

export async function fetchHealth() {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/health`, {}, 5000);
    if (!response.ok) {
      throw new Error(`Health check failed with status ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error("API health check error:", error);
    throw error;
  }
}

export async function healthCheck() {
  return fetchHealth();
}

export async function solveProblem(text) {
  if (!text || !text.trim()) {
    throw new Error("Planning text is required.");
  }

  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/solve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text: text.trim() }),
    }, 45000);

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const errorMessage = data?.detail || `Server returned error (${response.status})`;
      const err = new Error(errorMessage);
      err.status = response.status;
      err.data = data;
      throw err;
    }

    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The request timed out. Please try again.");
    }
    console.error("solveProblem API error:", error);
    throw error;
  }
}

export async function getHistory() {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/history`, {}, 10000);
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || `Failed to fetch history (${response.status})`);
    }
    return await response.json();
  } catch (error) {
    console.error("getHistory API error:", error);
    throw error;
  }
}

export async function getHistoryRun(id) {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/history/${id}`, {}, 10000);
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || `Failed to fetch run details (${response.status})`);
    }
    return await response.json();
  } catch (error) {
    console.error(`getHistoryRun API error for id ${id}:`, error);
    throw error;
  }
}
