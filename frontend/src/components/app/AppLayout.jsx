import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, ListTodo, Target, NotebookPen, MessagesSquare, UserRound } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, tid: "nav-dashboard" },
  { to: "/tasks",     label: "Tasks",     icon: ListTodo,        tid: "nav-tasks" },
  { to: "/goals",     label: "Goals",     icon: Target,          tid: "nav-goals" },
  { to: "/notes",     label: "Notes",     icon: NotebookPen,     tid: "nav-notes" },
  { to: "/coach",     label: "Coach",     icon: MessagesSquare,  tid: "nav-coach" },
  { to: "/profile",   label: "Profile",   icon: UserRound,       tid: "nav-profile" },
];

export default function AppLayout() {
  const { user } = useAuth();

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
          <div className="text-xs text-muted-foreground truncate">Personal workspace</div>
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
