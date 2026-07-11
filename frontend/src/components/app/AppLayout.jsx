import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, ListTodo, Target, NotebookPen, MessagesSquare, UserRound, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard, tid: "nav-dashboard" },
  { to: "/app/tasks",     label: "Tasks",     icon: ListTodo,        tid: "nav-tasks" },
  { to: "/app/goals",     label: "Goals",     icon: Target,          tid: "nav-goals" },
  { to: "/app/notes",     label: "Notes",     icon: NotebookPen,     tid: "nav-notes" },
  { to: "/app/coach",     label: "Coach",     icon: MessagesSquare,  tid: "nav-coach" },
  { to: "/app/profile",   label: "Profile",   icon: UserRound,       tid: "nav-profile" },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const doLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen flex bg-background text-foreground relative z-10">
      <aside
        data-testid="app-sidebar"
        className="w-64 shrink-0 hairline-b border-r border-border bg-[color:hsl(var(--secondary))] p-6 flex flex-col"
      >
        <div className="mb-10">
          <div className="overline mb-2">Momentum</div>
          <div className="font-display text-2xl font-bold tracking-tight">
            Move on what matters.
          </div>
        </div>

        <nav className="flex-1 space-y-1">
          {nav.map(({ to, label, icon: Icon, tid }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={tid}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))]"
                  : "text-foreground/80 hover:bg-[color:hsl(var(--muted))]"
              )}
            >
              <Icon className="w-4 h-4" strokeWidth={2} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-6 pt-6 border-t border-border">
          <div className="text-sm font-medium truncate" data-testid="sidebar-user-name">{user?.name}</div>
          <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
          <button
            data-testid="logout-button"
            onClick={doLogout}
            className="mt-4 w-full flex items-center gap-2 justify-center py-2 px-3 rounded-full text-xs font-semibold border border-border hover:border-foreground/40 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-auto">
        <div className="max-w-7xl mx-auto px-8 py-10 animate-fade-up">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
