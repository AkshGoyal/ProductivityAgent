import { useEffect, useState, useCallback } from "react";
import api from "@/api/client";
import { useAgent } from "@/context/AgentContext";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Trash2, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function NotesPage() {
  const [notes, setNotes] = useState([]);
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState({ title: "", content: "" });
  const [saving, setSaving] = useState(false);
  const [reflection, setReflection] = useState("");
  const [reflecting, setReflecting] = useState(false);
  const { invalidations } = useAgent();

  const load = useCallback(async () => {
    const { data } = await api.get("/notes");
    setNotes(data);
    setSelected((prev) => {
      if (prev) return prev;
      if (data.length) {
        setDraft({ title: data[0].title, content: data[0].content });
        setReflection(data[0].reflection || "");
        return data[0].id;
      }
      return null;
    });
  }, []);
  useEffect(() => { load(); }, [load, invalidations.notes]);

  const createNew = async () => {
    const { data } = await api.post("/notes", { title: "Untitled", content: "" });
    setNotes([data, ...notes]);
    setSelected(data.id);
    setDraft({ title: data.title, content: data.content });
    setReflection("");
    toast.success("Note created");
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    await api.patch(`/notes/${selected}`, draft);
    setSaving(false);
    toast.success("Saved");
    load();
  };

  const remove = async (id) => {
    await api.delete(`/notes/${id}`);
    const remaining = notes.filter((n) => n.id !== id);
    setNotes(remaining);
    if (selected === id) {
      const next = remaining[0];
      setSelected(next?.id || null);
      setDraft(next ? { title: next.title, content: next.content } : { title: "", content: "" });
      setReflection(next?.reflection || "");
    }
    toast.success("Deleted");
  };

  const select = (n) => {
    setSelected(n.id);
    setDraft({ title: n.title, content: n.content });
    setReflection(n.reflection || "");
  };

  const askAgent = async (save_it = false) => {
    if (!selected) return;
    // Save any unsaved edits first so the agent reads the latest content
    if (draft.title !== (notes.find((n) => n.id === selected)?.title || "") ||
        draft.content !== (notes.find((n) => n.id === selected)?.content || "")) {
      await api.patch(`/notes/${selected}`, draft);
    }
    setReflecting(true);
    try {
      // If we're just persisting an already-visible reflection, pass it through
      // to skip the LLM re-call.
      const body = save_it && reflection
        ? { note_id: selected, save: true, reflection }
        : { note_id: selected, save: save_it };
      const { data } = await api.post("/agent/reflect-note", body);
      setReflection(data.reflection);
      if (save_it) toast.success("Reflection saved to note");
      if (save_it) load();
    } catch {
      toast.error("Could not get reflection");
    } finally {
      setReflecting(false);
    }
  };

  return (
    <div className="grid lg:grid-cols-[280px_1fr] gap-6 h-[calc(100vh-8rem)]" data-testid="notes-page">
      <aside className="border border-border rounded-xl overflow-hidden bg-card flex flex-col">
        <div className="p-4 hairline-b border-b border-border flex items-center justify-between">
          <div className="overline">Notes</div>
          <button
            data-testid="new-note-button"
            onClick={createNew}
            className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border border-border hover:border-foreground/40 transition-colors"
          >
            <Plus className="w-3 h-3" /> New
          </button>
        </div>
        <div className="flex-1 overflow-auto">
          {notes.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground">No notes yet. Start expressing.</div>
          ) : (
            <ul className="divide-y divide-border">
              {notes.map((n) => (
                <li
                  key={n.id}
                  data-testid={`note-item-${n.id}`}
                  onClick={() => select(n)}
                  className={`p-4 cursor-pointer transition-colors ${
                    selected === n.id ? "bg-[color:hsl(var(--muted))]" : "hover:bg-[color:hsl(var(--muted))]/60"
                  }`}
                >
                  <div className="font-medium truncate">{n.title || "Untitled"}</div>
                  <div className="text-xs text-muted-foreground truncate mt-1">{n.content || "…"}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <section className="border border-border rounded-xl bg-card flex flex-col overflow-hidden">
        {selected ? (
          <>
            <div className="p-6 hairline-b border-b border-border flex items-center gap-3 flex-wrap">
              <Input
                data-testid="note-title-input"
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                placeholder="Title"
                className="text-xl font-semibold border-0 shadow-none focus-visible:ring-0 px-0 font-display flex-1 min-w-0"
              />
              <button
                data-testid="save-note-button"
                onClick={save} disabled={saving}
                className="text-xs font-semibold px-3 py-1.5 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                data-testid="reflect-note-button"
                onClick={() => askAgent(false)} disabled={reflecting}
                className="text-xs font-semibold px-3 py-1.5 rounded-full border border-[color:hsl(var(--accent))] text-[color:hsl(var(--accent))] hover:bg-[color:hsl(var(--accent))] hover:text-white transition-colors disabled:opacity-60 inline-flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" /> {reflecting ? "Reflecting…" : "Ask agent"}
              </button>
              <button
                data-testid="delete-note-button"
                onClick={() => remove(selected)}
                className="text-muted-foreground hover:text-[color:hsl(var(--destructive))]"
                aria-label="delete-note"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 flex flex-col min-h-0 overflow-auto">
              <Textarea
                data-testid="note-content-input"
                value={draft.content}
                onChange={(e) => setDraft({ ...draft, content: e.target.value })}
                placeholder="Start writing…"
                className="border-0 shadow-none focus-visible:ring-0 rounded-none text-base leading-relaxed p-6 resize-none min-h-[300px]"
              />

              {reflection && (
                <div className="p-6 border-t border-border bg-[color:hsl(var(--secondary))]" data-testid="note-reflection">
                  <div className="flex items-center justify-between mb-3">
                    <div className="overline">Agent reflection</div>
                    <button
                      data-testid="save-reflection-button"
                      onClick={() => askAgent(true)}
                      disabled={reflecting}
                      className="text-xs font-semibold px-3 py-1 rounded-full border border-border hover:border-foreground/40 disabled:opacity-60"
                    >
                      Save to note
                    </button>
                  </div>
                  <div className="text-sm leading-relaxed whitespace-pre-wrap text-foreground/90">
                    {reflection}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 grid place-items-center text-muted-foreground">
            Select or create a note to begin.
          </div>
        )}
      </section>
    </div>
  );
}
