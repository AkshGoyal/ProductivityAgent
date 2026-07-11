import { useEffect, useRef, useState, useCallback } from "react";
import api, { API_BASE } from "@/api/client";
import { Textarea } from "@/components/ui/textarea";
import { Send, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const endRef = useRef(null);

  const load = useCallback(async () => {
    const { data } = await api.get("/chat/history");
    setMessages(data);
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, streaming]);

  const send = async (e) => {
    e?.preventDefault();
    if (!input.trim() || streaming) return;
    const userMsg = { role: "user", content: input, id: `tmp-${Date.now()}` };
    setMessages((prev) => [...prev, userMsg, { role: "assistant", content: "", id: `tmp-a-${Date.now()}` }]);
    const messageText = input;
    setInput("");
    setStreaming(true);

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: messageText }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let assistantText = "";

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        // SSE frames: split by double newline
        let parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const part of parts) {
          if (!part.trim()) continue;
          if (part.startsWith("event: done")) continue;
          if (part.startsWith("event: error")) {
            const m = part.match(/data: (.*)/);
            toast.error(m?.[1] || "Chat error");
            continue;
          }
          const lines = part.split("\n").filter((l) => l.startsWith("data:"));
          const chunk = lines.map((l) => l.slice(5).replace(/^ /, "")).join("\n");
          assistantText += chunk;
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: assistantText };
            return copy;
          });
        }
      }
    } catch (err) {
      toast.error("Could not reach the coach");
    } finally {
      setStreaming(false);
      // Reload to sync persisted IDs
      load();
    }
  };

  const clearHistory = async () => {
    await api.delete("/chat/history");
    setMessages([]);
    toast.success("Cleared");
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]" data-testid="chat-page">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="overline mb-2">Coach</div>
          <h1 className="font-display text-4xl font-bold tracking-tight">Think out loud. Get moving.</h1>
        </div>
        <button
          data-testid="clear-history-button"
          onClick={clearHistory}
          className="text-xs font-semibold px-3 py-1.5 rounded-full border border-border hover:border-foreground/40 transition-colors inline-flex items-center gap-1.5"
        >
          <Trash2 className="w-3.5 h-3.5" /> Clear
        </button>
      </div>

      <div
        data-testid="chat-messages"
        className="flex-1 overflow-auto rounded-xl border border-border bg-[color:hsl(var(--secondary))] p-6 space-y-4"
      >
        {messages.length === 0 && !streaming && (
          <div className="text-sm text-muted-foreground max-w-md">
            Try: <span className="text-foreground italic">"I'm stuck on my launch prep. Where should I start?"</span>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={m.id || i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              data-testid={`chat-msg-${m.role}-${i}`}
              className={`max-w-[75%] px-4 py-3 rounded-2xl leading-relaxed ${
                m.role === "user"
                  ? "bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] rounded-br-sm"
                  : "bg-card border border-border rounded-bl-sm"
              }`}
            >
              <div className="whitespace-pre-wrap text-sm">{m.content || (streaming && i === messages.length - 1 ? "…" : "")}</div>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form onSubmit={send} className="mt-4 flex gap-3 items-end" data-testid="chat-form">
        <Textarea
          data-testid="chat-input"
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="What's on your mind?"
          className="resize-none"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          data-testid="chat-send-button"
          className="h-11 w-11 shrink-0 grid place-items-center rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] disabled:opacity-60 transition-opacity"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
