import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import api, { formatApiError } from "@/api/client";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=loading, false=guest, object=user
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (err) {
      // Not authenticated is expected on first visit — swallow but log for debugging.
      if (err?.response?.status && err.response.status !== 401) {
        console.error("Auth refresh failed:", err);
      }
      setUser(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email, password) => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      return true;
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return false;
    }
  }, []);

  const register = useCallback(async (email, password, name) => {
    setError("");
    try {
      const { data } = await api.post("/auth/register", { email, password, name });
      setUser(data);
      return true;
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return false;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      console.error("Logout error:", err);
    }
    setUser(false);
  }, []);

  const updateProfile = useCallback(async (patch) => {
    const { data } = await api.patch("/auth/profile", patch);
    setUser(data);
    return data;
  }, []);

  const value = useMemo(
    () => ({ user, error, login, register, logout, refresh, updateProfile }),
    [user, error, login, register, logout, refresh, updateProfile]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
