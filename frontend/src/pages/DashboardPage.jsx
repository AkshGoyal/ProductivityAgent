import { useEffect, useState } from "react";
import api from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Link } from "react-router-dom";
import { ArrowUpRight, Target, ListTodo, NotebookPen, Sparkles } from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [openTasks, setOpenTasks] = useState([]);
  const [goals, setGoals] = useState([]);

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
  }, []);

  return (
    <div className="space-y-10" data-testid="dashboard-page">
      <div>
        <div className="overline mb-2">Today</div>
        <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight">
          Hey {user?.name?.split(" ")[0] || "there"}, one focused hour beats three scattered ones.
        </h1>
      </div>

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
