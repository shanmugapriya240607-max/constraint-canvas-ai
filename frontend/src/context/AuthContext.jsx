import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { authService } from "../services/auth";
import { readSession } from "../services/session";
import { setUnauthorizedHandler } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const generation = useRef(0);

  const logout = useCallback(() => {
    generation.current += 1;
    authService.logout();
    setUser(null);
    setError("");
    setStatus("anonymous");
  }, []);

  const restore = useCallback(async () => {
    const current = ++generation.current;
    setError("");
    setStatus("loading");
    if (!readSession()) {
      setStatus("anonymous");
      return;
    }
    try {
      const verifiedUser = await authService.me();
      if (generation.current === current) {
        setUser(verifiedUser);
        setStatus("authenticated");
      }
    } catch (err) {
      if (generation.current !== current) return;
      if (err.status === 401) {
        logout();
        return;
      }
      // Network failures do not discard a valid token or reveal protected content.
      setError(err.message);
      setStatus("error");
    }
  }, [logout]);

  useEffect(() => {
    const unsubscribe = setUnauthorizedHandler(logout);
    restore();
    return () => {
      generation.current += 1;
      unsubscribe();
    };
  }, [logout, restore]);

  useEffect(() => {
    if (status !== "authenticated") return;
    const checkExpiry = () => {
      if (!readSession()) logout();
    };
    const remaining = (readSession()?.expiresAt || Date.now()) - Date.now();
    const timer = setTimeout(
      checkExpiry,
      Math.min(Math.max(remaining, 0), 2147483647),
    );
    window.addEventListener("focus", checkExpiry);
    document.addEventListener("visibilitychange", checkExpiry);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("focus", checkExpiry);
      document.removeEventListener("visibilitychange", checkExpiry);
    };
  }, [status, user, logout]);

  async function login(email, password) {
    const current = ++generation.current;
    const verifiedUser = await authService.login(email, password);
    if (generation.current === current) {
      setUser(verifiedUser);
      setStatus("authenticated");
      setError("");
    }
  }

  return (
    <AuthContext.Provider
      value={{ user, status, error, login, logout, retry: restore }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth requires AuthProvider");
  return context;
}
