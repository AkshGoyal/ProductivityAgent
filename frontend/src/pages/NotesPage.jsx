import { useEffect, useState } from "react";
import api from "@/api/client";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

export default function NotesPage() {
  const [notes, setNotes] = useState([]);
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState({ title: "", content: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const { data } = await api.get("/notes");
    setNotes(data);
    if (data.length && !selected) {
      setSelected(data[0].id);
      setDraft({ title: data[0].title, content: data[0].content });
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const createNew = async () => {
    const { data } = await api.post("/notes", { title: "Untitled", content: "" });
    setNotes([data, ...notes]);
    setSelected(data.id);
    setDraft({ title: data.title, content: data.content });
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
    }
    toast.success("Deleted");
  };

  const select = (n) => {
    setSelected(n.id);
    setDraft({ title: n.title, content: n.content });
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
            <div className="p-6 text-sm text-muted-foreground">
              No notes yet. Start expressing.
            </div>
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
            <div className="p-6 hairline-b border-b border-border flex items-center gap-3">
              <Input
                data-testid="note-title-input"
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                placeholder="Title"
                className="text-xl font-semibold border-0 shadow-none focus-visible:ring-0 px-0 font-display"
              />
              <button
                data-testid="save-note-button"
                onClick={save} disabled={saving}
                className="text-xs font-semibold px-3 py-1.5 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                data-testid="delete-note-button"
                onClick={() => remove(selected)}
                className="text-muted-foreground hover:text-[color:hsl(var(--destructive))]"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            <Textarea
              data-testid="note-content-input"
              value={draft.content}
              onChange={(e) => setDraft({ ...draft, content: e.target.value })}
              placeholder="Start writing…"
              className="flex-1 border-0 shadow-none focus-visible:ring-0 rounded-none text-base leading-relaxed p-6 resize-none"
            />
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
