import { useEffect, useState, useCallback } from "react";
import api from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { useAgent } from "@/context/AgentContext";
import { Link } from "react-router-dom";
import { ArrowUpRight, Target, ListTodo, NotebookPen, Sparkles, RefreshCw, Clock } from "lucide-react";
import { toast } from "sonner";

const PLAN_STORAGE_KEY = "momentum:daily-plan";

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [openTasks, setOpenTasks] = useState([]);
  const [goals, setGoals] = useState([]);
  const [plan, setPlan] = useState(null);
  const [planning, setPlanning] = useState(false);
  const { invalidations } = useAgent();

  useEffect(() => {
    (async () => {
      const [s, t, g] = await Promise.all([
        api.get("/dashboard/stats"),
        api.get("/tasks"),
        api.get("/goals"),
      ]);
      setStats(s.data);
      setOpenTasks(t.data.filter((x) => x.status !== "done").slice(0, 6));
      setGoals(g.data.slice(0, 3));
    })();
  }, [invalidations.tasks, invalidations.goals, invalidations.notes]);

  // Restore cached plan from today
  useEffect(() => {
    try {
      const raw = localStorage.getItem(PLAN_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      const today = new Date().toISOString().slice(0, 10);
      const genDate = (parsed.generated_at || "").slice(0, 10);
      if (genDate === today) setPlan(parsed);
    } catch {
      // ignore
    }
  }, []);

  const generatePlan = useCallback(async () => {
    setPlanning(true);
    try {
      const { data } = await api.post("/agent/plan-day");
      setPlan(data);
      localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(data));
      toast.success("Today's plan is ready");
    } catch {
      toast.error("Couldn't generate a plan. Try again.");
    } finally {
      setPlanning(false);
    }
  }, []);

  const markDone = async (taskId) => {
    if (!taskId) return;
    await api.patch(`/tasks/${taskId}`, { status: "done" });
    // Update the plan item locally
    setPlan((prev) => prev ? {
      ...prev,
      items: prev.items.map((it) => it.task_id === taskId ? { ...it, _done: true } : it),
    } : prev);
    // Refresh dashboard stats/tasks
    const [s, t] = await Promise.all([api.get("/dashboard/stats"), api.get("/tasks")]);
    setStats(s.data);
    setOpenTasks(t.data.filter((x) => x.status !== "done").slice(0, 6));
    toast.success("Marked done");
  };

  return (
    <div className="space-y-10" data-testid="dashboard-page">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <div className="overline mb-2">Today</div>
          <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight">
            Hey {user?.name?.split(" ")[0] || "there"}, one focused hour beats three scattered ones.
          </h1>
        </div>
        <button
          data-testid="plan-my-day-button"
          onClick={generatePlan}
          disabled={planning}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[color:hsl(var(--accent))] text-white font-semibold shadow-sm hover:translate-y-[-1px] transition-transform disabled:opacity-60 disabled:translate-y-0"
        >
          {planning ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Planning your day…
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              {plan ? "Regenerate today's plan" : "Plan my day"}
            </>
          )}
        </button>
      </div>

      {plan && (
        <div data-testid="today-plan" className="p-6 rounded-xl border border-border bg-card animate-fade-up">
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <div className="overline mb-1">Today's focus</div>
              <div className="font-display text-xl font-semibold leading-snug max-w-2xl">
                {plan.focus}
              </div>
            </div>
            <div className="text-xs text-muted-foreground shrink-0 hidden sm:block">
              {plan.items.length} item{plan.items.length === 1 ? "" : "s"}
            </div>
          </div>

          <ol className="space-y-3">
            {plan.items.map((it, i) => (
              <li
                key={i}
                data-testid={`today-plan-item-${i}`}
                className={`p-4 rounded-lg border border-border flex items-start gap-4 card-lift ${it._done ? "opacity-60" : ""}`}
              >
                <div className="w-7 h-7 shrink-0 grid place-items-center rounded-full bg-[color:hsl(var(--secondary))] border border-border text-xs font-semibold">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`font-medium ${it._done ? "line-through" : ""}`}>{it.title}</div>
                  {it.why && <div className="text-sm text-muted-foreground mt-1 leading-relaxed">{it.why}</div>}
                  <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                    <span className={`px-2 py-0.5 rounded-full border ${
                      it.priority === "high" ? "border-[color:hsl(var(--accent))] text-[color:hsl(var(--accent))]" : "border-border"
                    }`}>{it.priority}</span>
                    <span className="inline-flex items-center gap-1"><Clock className="w-3 h-3" /> ~{it.estimated_minutes}m</span>
                    {!it.task_id && <span className="text-[color:hsl(var(--accent))]">new</span>}
                  </div>
                </div>
                {it.task_id && !it._done && (
                  <button
                    data-testid={`today-plan-done-${i}`}
                    onClick={() => markDone(it.task_id)}
                    className="text-xs font-semibold px-3 py-1.5 rounded-full border border-border hover:border-foreground/40 transition-colors shrink-0"
                  >
                    Mark done
                  </button>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Active goals"    value={stats?.active_goals ?? "—"} icon={Target} testid="stat-active-goals" />
        <StatCard label="Open tasks"      value={(stats?.total_tasks ?? 0) - (stats?.done_tasks ?? 0)} icon={ListTodo} testid="stat-open-tasks" />
        <StatCard label="Completion rate" value={stats ? `${stats.completion_rate}%` : "—"} icon={Sparkles} testid="stat-completion-rate" />
        <StatCard label="Notes"           value={stats?.notes_count ?? "—"} icon={NotebookPen} testid="stat-notes-count" />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-6 rounded-xl border border-border bg-card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="overline mb-1">Open tasks</div>
              <h2 className="font-display text-2xl font-semibold">What's next</h2>
            </div>
            <Link to="/tasks" data-testid="dashboard-all-tasks" className="text-sm font-semibold underline underline-offset-4">All tasks</Link>
          </div>
          {openTasks.length === 0 ? (
            <div className="text-sm text-muted-foreground">Nothing open. Enjoy the calm — or open a new goal.</div>
          ) : (
            <ul className="space-y-2">
              {openTasks.map((t) => (
                <li key={t.id} className="p-3 rounded-lg border border-border flex items-center justify-between card-lift" data-testid={`dashboard-task-${t.id}`}>
                  <div className="min-w-0">
                    <div className="font-medium truncate">{t.title}</div>
                    <div className="text-xs text-muted-foreground">
                      <span className="uppercase tracking-wider">{t.priority}</span> · {t.status.replace("_"," ")}
                    </div>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-muted-foreground" />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="p-6 rounded-xl border border-border bg-card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="overline mb-1">Goals</div>
              <h2 className="font-display text-2xl font-semibold">North star</h2>
            </div>
            <Link to="/goals" data-testid="dashboard-all-goals" className="text-sm font-semibold underline underline-offset-4">All</Link>
          </div>
          {goals.length === 0 ? (
            <div className="text-sm text-muted-foreground">No goals yet. Create one — Momentum will break it down for you.</div>
          ) : (
            <ul className="space-y-4">
              {goals.map((g) => (
                <li key={g.id} data-testid={`dashboard-goal-${g.id}`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="font-medium truncate mr-2">{g.title}</div>
                    <div className="text-xs text-muted-foreground">{g.progress}%</div>
                  </div>
                  <div className="h-1.5 w-full bg-[color:hsl(var(--muted))] rounded-full overflow-hidden">
                    <div className="h-full bg-[color:hsl(var(--accent))]" style={{ width: `${g.progress}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, testid }) {
  return (
    <div className="p-5 rounded-xl border border-border bg-card card-lift" data-testid={testid}>
      <div className="flex items-center justify-between mb-3">
        <div className="overline">{label}</div>
        <Icon className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="font-display text-3xl font-bold tracking-tight">{value}</div>
    </div>
  );
}
