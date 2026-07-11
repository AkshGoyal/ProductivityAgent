import { useEffect, useRef, useState } from "react";
import { useAgent } from "@/context/AgentContext";
import { Textarea } from "@/components/ui/textarea";
import { Sparkles, X, Send, CheckCircle2, Trash2, AlertCircle } from "lucide-react";

export default function FloatingAgent() {
  const { open, setOpen, messages, thinking, send, clear } = useAgent();
  const [input, setInput] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open, thinking]);

  const submit = (e) => {
    e?.preventDefault();
    if (!input.trim() || thinking) return;
    send(input);
    setInput("");
  };

  return (
    <>
      {/* Floating trigger button — visible on every route */}
      <button
        data-testid="agent-fab"
        onClick={() => setOpen(!open)}
        aria-label="Open Momentum agent"
        className="fixed bottom-6 right-6 z-[60] h-14 w-14 rounded-full bg-[color:hsl(var(--accent))] text-white shadow-lg hover:translate-y-[-2px] transition-transform grid place-items-center"
      >
        {open ? <X className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
      </button>

      {/* Slide-in panel */}
      <div
        data-testid="agent-panel"
        className={`fixed right-6 bottom-24 z-[55] w-[calc(100vw-3rem)] sm:w-[420px] h-[70vh] max-h-[640px]
          rounded-2xl border border-border bg-card shadow-2xl overflow-hidden flex flex-col
          transition-all duration-200 origin-bottom-right
          ${open ? "opacity-100 scale-100 pointer-events-auto" : "opacity-0 scale-95 pointer-events-none"}`}
      >
        <div className="p-4 border-b border-border flex items-center justify-between bg-[color:hsl(var(--secondary))]">
          <div>
            <div className="overline">Companion</div>
            <div className="font-display font-semibold text-lg tracking-tight">Momentum</div>
          </div>
          <button
            data-testid="agent-clear"
            onClick={clear}
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <Trash2 className="w-3.5 h-3.5" /> Clear
          </button>
        </div>

        <div data-testid="agent-messages" className="flex-1 overflow-auto p-4 space-y-3">
          {messages.length === 0 && !thinking && (
            <div className="text-sm text-muted-foreground leading-relaxed">
              Ask me to plan your day, brainstorm, or take action.<br />
              Try: <em className="text-foreground">"Create a task to draft the launch email — high priority"</em>
            </div>
          )}
          {messages.map((m, i) => (
            <MessageBubble key={m.id || i} m={m} idx={i} />
          ))}
          {thinking && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="agent-thinking">
              <span className="w-1.5 h-1.5 rounded-full bg-[color:hsl(var(--accent))] animate-pulse" />
              Thinking…
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={submit} className="p-3 border-t border-border flex gap-2 items-end bg-background">
          <Textarea
            data-testid="agent-input"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder="Ask, ideate, or ask me to do something…"
            className="resize-none min-h-10 max-h-32 text-sm"
          />
          <button
            type="submit"
            disabled={thinking || !input.trim()}
            data-testid="agent-send"
            className="h-10 w-10 shrink-0 grid place-items-center rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] disabled:opacity-60 transition-opacity"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </>
  );
}

function MessageBubble({ m, idx }) {
  const isUser = m.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        data-testid={`agent-msg-${m.role}-${idx}`}
        className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? "bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] rounded-br-sm"
            : "bg-[color:hsl(var(--muted))] border border-border rounded-bl-sm"
        }`}
      >
        <div className="whitespace-pre-wrap">{m.content}</div>
        {Array.isArray(m.actions) && m.actions.length > 0 && (
          <div className="mt-2 space-y-1">
            {m.actions.map((a, i) => (
              <ActionChip key={i} action={a} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionChip({ action }) {
  const ok = action.status === "ok";
  const Icon = ok ? CheckCircle2 : AlertCircle;
  const label = ok ? action.summary : `Action failed: ${action.error}`;
  return (
    <div
      data-testid={`agent-action-${action.tool}-${ok ? "ok" : "err"}`}
      className={`text-xs inline-flex items-center gap-1.5 px-2 py-1 rounded-md border ${
        ok
          ? "border-[color:hsl(var(--accent))] text-[color:hsl(var(--accent))] bg-[color:hsl(var(--accent))]/10"
          : "border-[color:hsl(var(--destructive))] text-[color:hsl(var(--destructive))] bg-[color:hsl(var(--destructive))]/10"
      }`}
    >
      <Icon className="w-3.5 h-3.5" />
      <span>{label}</span>
    </div>
  );
}
