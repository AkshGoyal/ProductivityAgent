import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { AgentProvider } from "@/context/AgentContext";
import AppLayout from "@/components/app/AppLayout";
import FloatingAgent from "@/components/app/FloatingAgent";
import DashboardPage from "@/pages/DashboardPage";
import TasksPage from "@/pages/TasksPage";
import GoalsPage from "@/pages/GoalsPage";
import NotesPage from "@/pages/NotesPage";
import ChatPage from "@/pages/ChatPage";
import ProfilePage from "@/pages/ProfilePage";

function Gate({ children }) {
  const { user } = useAuth();
  if (user === null || user === false) {
    return (
      <div className="min-h-screen grid place-items-center text-muted-foreground">
        <div data-testid="auth-loading" className="text-sm">Loading Momentum…</div>
      </div>
    );
  }
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <AgentProvider>
        <BrowserRouter>
          <div className="App noise-bg">
            <Routes>
              <Route path="/" element={<Gate><AppLayout /></Gate>}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="tasks" element={<TasksPage />} />
                <Route path="goals" element={<GoalsPage />} />
                <Route path="notes" element={<NotesPage />} />
                <Route path="coach" element={<ChatPage />} />
                <Route path="profile" element={<ProfilePage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            {/* Mounted at ROOT so it persists across route changes */}
            <FloatingAgent />
            <Toaster position="bottom-right" richColors />
          </div>
        </BrowserRouter>
      </AgentProvider>
    </AuthProvider>
  );
}
