import { readSession } from "./session";

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");
let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
  return () => {
    if (onUnauthorized === handler) onUnauthorized = () => {};
  };
}

export class ApiError extends Error {
  constructor(message, status = 0, fields = {}, detail = null) {
    super(message);
    this.status = status;
    this.fields = fields;
    this.detail = detail;
  }
}

export async function api(
  path,
  { method = "GET", body, authenticated = true, timeoutMs = 15000 } = {},
) {
  const session = authenticated ? readSession() : null;
  if (authenticated && !session) {
    onUnauthorized();
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(BASE_URL + path, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(session ? { Authorization: "Bearer " + session.token } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
      credentials: "omit",
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      // An older request must never invalidate a newer login.
      if (
        response.status === 401 &&
        session &&
        readSession()?.token === session.token
      )
        onUnauthorized();
      const fields = {};
      if (response.status === 422 && Array.isArray(data?.detail)) {
        for (const issue of data.detail) {
          const field = issue.loc?.[1];
          if (["name", "email", "password"].includes(field))
            fields[field] = issue.msg;
        }
      }
      const message =
        response.status >= 500
          ? "The service is temporarily unavailable. Please try again."
          : data?.detail?.message || (typeof data?.detail === "string"
            ? data.detail
            : response.status === 422
              ? "Please check the highlighted fields."
              : "The request could not be completed. Please try again.");
      throw new ApiError(message, response.status, fields, response.status < 500 ? data?.detail : null);
    }
    if (response.status === 204) return null;
    if (!data)
      throw new ApiError(
        "The server returned an unreadable response. Please try again.",
      );
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      error.name === "AbortError"
        ? "The request timed out. Please try again."
        : "Cannot reach the server. Check your connection and try again.",
    );
  } finally {
    clearTimeout(timeout);
  }
}
