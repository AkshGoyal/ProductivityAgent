import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/api/client";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=loading, false=guest, object=user
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email, password) => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      return true;
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return false;
    }
  };

  const register = async (email, password, name) => {
    setError("");
    try {
      const { data } = await api.post("/auth/register", { email, password, name });
      setUser(data);
      return true;
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return false;
    }
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    setUser(false);
  };

  const updateProfile = async (patch) => {
    const { data } = await api.patch("/auth/profile", patch);
    setUser(data);
    return data;
  };

  return (
    <AuthCtx.Provider value={{ user, error, login, register, logout, refresh, updateProfile }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
