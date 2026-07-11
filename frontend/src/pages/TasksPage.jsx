import { useEffect, useState, useCallback } from "react";
import api from "@/api/client";
import { useAgent } from "@/context/AgentContext";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2, Check } from "lucide-react";
import { toast } from "sonner";

const PRIORITIES = ["low", "medium", "high"];
const STATUSES = ["todo", "in_progress", "done"];

export default function TasksPage() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", priority: "medium", due_date: "" });
  const { invalidations } = useAgent();

  const load = useCallback(async () => {
    const { data } = await api.get("/tasks");
    setTasks(data);
  }, []);
  useEffect(() => { load(); }, [load, invalidations.tasks]);

  const create = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    await api.post("/tasks", { ...form, due_date: form.due_date || null });
    setForm({ title: "", description: "", priority: "medium", due_date: "" });
    setOpen(false);
    toast.success("Task added");
    load();
  };

  const setStatus = async (id, status) => {
    await api.patch(`/tasks/${id}`, { status });
    load();
  };

  const setPriority = async (id, priority) => {
    await api.patch(`/tasks/${id}`, { priority });
    load();
  };

  const remove = async (id) => {
    await api.delete(`/tasks/${id}`);
    toast.success("Deleted");
    load();
  };

  const filtered = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);

  return (
    <div className="space-y-8" data-testid="tasks-page">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="overline mb-2">Tasks</div>
          <h1 className="font-display text-4xl font-bold tracking-tight">Move the needle.</h1>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <button
              data-testid="new-task-button"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold hover:opacity-95 transition-opacity"
            >
              <Plus className="w-4 h-4" /> New task
            </button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader><DialogTitle className="font-display">New task</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4" data-testid="new-task-form">
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required data-testid="task-title-input" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} data-testid="task-description-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                    <SelectTrigger data-testid="task-priority-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Due</Label>
                  <Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} data-testid="task-due-input" />
                </div>
              </div>
              <button type="submit" data-testid="task-submit-button" className="w-full py-2.5 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold">
                Add task
              </button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex gap-2">
        {["all", ...STATUSES].map((s) => (
          <button
            key={s}
            data-testid={`task-filter-${s}`}
            onClick={() => setFilter(s)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              filter === s ? "bg-foreground text-background border-foreground" : "border-border hover:border-foreground/40"
            }`}
          >
            {s.replace("_"," ")}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="p-10 rounded-xl border border-dashed border-border text-center text-muted-foreground">
          Nothing here. Add your first task above.
        </div>
      ) : (
        <ul className="space-y-2">
          {filtered.map((t) => (
            <li
              key={t.id}
              data-testid={`task-item-${t.id}`}
              className="p-4 rounded-xl border border-border bg-card flex items-start gap-3 card-lift"
            >
              <button
                data-testid={`task-toggle-${t.id}`}
                onClick={() => setStatus(t.id, t.status === "done" ? "todo" : "done")}
                className={`mt-0.5 w-5 h-5 rounded-full border grid place-items-center transition-colors ${
                  t.status === "done"
                    ? "bg-[color:hsl(var(--primary))] border-[color:hsl(var(--primary))]"
                    : "border-border hover:border-foreground/60"
                }`}
                aria-label="toggle-done"
              >
                {t.status === "done" && <Check className="w-3 h-3 text-[color:hsl(var(--primary-foreground))]" />}
              </button>
              <div className="flex-1 min-w-0">
                <div className={`font-medium ${t.status === "done" ? "line-through text-muted-foreground" : ""}`}>{t.title}</div>
                {t.description && <div className="text-sm text-muted-foreground mt-1">{t.description}</div>}
                <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                  <span className={`px-2 py-0.5 rounded-full border ${
                    t.priority === "high" ? "border-[color:hsl(var(--accent))] text-[color:hsl(var(--accent))]" : "border-border"
                  }`}>{t.priority}</span>
                  <Select value={t.status} onValueChange={(v) => setStatus(t.id, v)}>
                    <SelectTrigger className="h-7 w-32 text-xs" data-testid={`task-status-select-${t.id}`}><SelectValue /></SelectTrigger>
                    <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace("_"," ")}</SelectItem>)}</SelectContent>
                  </Select>
                  <Select value={t.priority} onValueChange={(v) => setPriority(t.id, v)}>
                    <SelectTrigger className="h-7 w-24 text-xs" data-testid={`task-priority-select-${t.id}`}><SelectValue /></SelectTrigger>
                    <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                  </Select>
                  {t.due_date && <span>due {t.due_date}</span>}
                </div>
              </div>
              <button
                data-testid={`task-delete-${t.id}`}
                onClick={() => remove(t.id)}
                className="text-muted-foreground hover:text-[color:hsl(var(--destructive))] transition-colors"
                aria-label="delete-task"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
