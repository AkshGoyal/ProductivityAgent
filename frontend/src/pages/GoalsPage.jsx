import { useEffect, useState } from "react";
import api from "@/api/client";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function GoalsPage() {
  const [goals, setGoals] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", target_date: "" });
  const [breakingDown, setBreakingDown] = useState(null);

  const load = async () => {
    const { data } = await api.get("/goals");
    setGoals(data);
  };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    await api.post("/goals", { ...form, target_date: form.target_date || null });
    setForm({ title: "", description: "", target_date: "" });
    setOpen(false);
    toast.success("Goal created");
    load();
  };

  const remove = async (id) => {
    await api.delete(`/goals/${id}`);
    toast.success("Goal removed");
    load();
  };

  const breakdown = async (id) => {
    setBreakingDown(id);
    try {
      const { data } = await api.post("/ai/breakdown-goal", { goal_id: id });
      toast.success(`Created ${data.tasks.length} tasks. Check the Tasks page.`);
      load();
    } catch (e) {
      toast.error("Breakdown failed. Try again.");
    } finally {
      setBreakingDown(null);
    }
  };

  return (
    <div className="space-y-8" data-testid="goals-page">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="overline mb-2">Goals</div>
          <h1 className="font-display text-4xl font-bold tracking-tight">Where you're heading.</h1>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <button
              data-testid="new-goal-button"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold transition-opacity hover:opacity-95"
            >
              <Plus className="w-4 h-4" /> New goal
            </button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader><DialogTitle className="font-display">New goal</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4" data-testid="new-goal-form">
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required data-testid="goal-title-input" />
              </div>
              <div className="space-y-2">
                <Label>Why this matters</Label>
                <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={4} data-testid="goal-description-input" />
              </div>
              <div className="space-y-2">
                <Label>Target date</Label>
                <Input type="date" value={form.target_date} onChange={(e) => setForm({ ...form, target_date: e.target.value })} data-testid="goal-date-input" />
              </div>
              <button type="submit" data-testid="goal-submit-button" className="w-full py-2.5 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold">
                Create goal
              </button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {goals.length === 0 ? (
        <div className="p-12 rounded-xl border border-dashed border-border text-center">
          <div className="text-muted-foreground mb-6">No goals yet. Drop one in and let Momentum break it down.</div>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-6">
          {goals.map((g) => (
            <div key={g.id} className="p-6 rounded-xl border border-border bg-card card-lift" data-testid={`goal-card-${g.id}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="font-display text-xl font-semibold tracking-tight">{g.title}</div>
                  {g.description && <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{g.description}</p>}
                </div>
                <button
                  data-testid={`goal-delete-${g.id}`}
                  onClick={() => remove(g.id)}
                  className="text-muted-foreground hover:text-[color:hsl(var(--destructive))]"
                  aria-label="delete-goal"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              <div className="mt-5">
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
                  <span>{g.done_count}/{g.task_count} tasks done</span>
                  <span>{g.progress}%</span>
                </div>
                <div className="h-1.5 w-full bg-[color:hsl(var(--muted))] rounded-full overflow-hidden">
                  <div className="h-full bg-[color:hsl(var(--accent))]" style={{ width: `${g.progress}%` }} />
                </div>
              </div>

              <div className="mt-6 flex items-center gap-3">
                <button
                  data-testid={`goal-breakdown-${g.id}`}
                  onClick={() => breakdown(g.id)}
                  disabled={breakingDown === g.id}
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border border-[color:hsl(var(--accent))] text-[color:hsl(var(--accent))] hover:bg-[color:hsl(var(--accent))] hover:text-white disabled:opacity-60 transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {breakingDown === g.id ? "Breaking down…" : "AI breakdown"}
                </button>
                {g.target_date && <span className="text-xs text-muted-foreground">target {g.target_date}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
