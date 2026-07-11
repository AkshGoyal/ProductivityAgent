import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api from "@/api/client";
import { toast } from "sonner";

const AgentCtx = createContext(null);

export function AgentProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // {id, role, content, actions[], created_at}
  const [thinking, setThinking] = useState(false);
  // Bump counters — components that fetch tasks/goals/notes can watch these to refresh.
  const [invalidations, setInvalidations] = useState({ tasks: 0, goals: 0, notes: 0 });

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await api.get("/agent/history");
      setMessages(data);
    } catch (err) {
      console.error("Agent history load failed:", err);
    }
  }, []);

  useEffect(() => {
    loadHistory();
    const savedOpen = localStorage.getItem("agent:open");
    if (savedOpen === "1") setOpen(true);
  }, [loadHistory]);

  useEffect(() => {
    localStorage.setItem("agent:open", open ? "1" : "0");
  }, [open]);

  const send = useCallback(async (message) => {
    const text = message?.trim();
    if (!text || thinking) return;

    // Optimistic user message
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", content: text, actions: [], created_at: new Date().toISOString() },
    ]);
    setThinking(true);
    try {
      const { data } = await api.post("/agent/chat", { message: text });
      setMessages((prev) => [...prev, data.assistant]);

      if (Array.isArray(data.invalidate) && data.invalidate.length) {
        setInvalidations((prev) => {
          const next = { ...prev };
          for (const key of data.invalidate) {
            if (key in next) next[key] += 1;
          }
          return next;
        });
        for (const a of data.actions || []) {
          if (a.status === "ok" && a.summary) toast.success(a.summary);
          if (a.status === "error") toast.error(a.error || "Action failed");
        }
      }
    } catch (err) {
      toast.error("Agent could not respond");
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: "I hit an error reaching the model. Try again in a moment.",
          actions: [],
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setThinking(false);
    }
  }, [thinking]);

  const clear = useCallback(async () => {
    await api.delete("/agent/history");
    setMessages([]);
  }, []);

  const value = useMemo(
    () => ({ open, setOpen, messages, thinking, send, clear, invalidations }),
    [open, messages, thinking, send, clear, invalidations]
  );

  return <AgentCtx.Provider value={value}>{children}</AgentCtx.Provider>;
}

export const useAgent = () => useContext(AgentCtx);
