import { api } from "./api";
import { clearSession, saveSession } from "./session";

export const authService = {
  async login(email, password) {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: { email: email.trim(), password },
      authenticated: false,
    });
    saveSession(data);
    try {
      return await this.me();
    } catch (error) {
      clearSession();
      throw error;
    }
  },
  register({ name, email, password }) {
    return api("/api/auth/register", {
      method: "POST",
      body: { name: name.trim(), email: email.trim(), password },
      authenticated: false,
    });
  },
  me() {
    return api("/api/auth/me");
  },
  logout: clearSession,
};
