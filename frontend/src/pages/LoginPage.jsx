import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function LoginPage() {
  const { login, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const ok = await login(email, password);
    setLoading(false);
    if (ok) {
      toast.success("Welcome back");
      nav("/app/dashboard", { replace: true });
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background relative z-10">
      <div className="hidden lg:block relative">
        <img
          src="https://images.pexels.com/photos/22711217/pexels-photo-22711217.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=1080&w=1200"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-[color:hsl(var(--background))]/20" />
        <div className="absolute bottom-10 left-10 right-10 text-foreground">
          <div className="overline mb-3">Momentum</div>
          <div className="font-display text-4xl font-bold tracking-tight max-w-sm">
            Quiet mornings.<br />Loud results.
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm space-y-6" data-testid="login-form">
          <div>
            <div className="overline mb-2">Sign in</div>
            <h1 className="font-display text-3xl font-bold tracking-tight">Welcome back</h1>
            <p className="text-sm text-muted-foreground mt-2">Continue your momentum.</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email" type="email" value={email} required
              onChange={(e) => setEmail(e.target.value)}
              data-testid="login-email-input" placeholder="you@work.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password" type="password" value={password} required
              onChange={(e) => setPassword(e.target.value)}
              data-testid="login-password-input" placeholder="••••••••"
            />
          </div>

          {error && (
            <div data-testid="login-error" className="text-sm text-[color:hsl(var(--destructive))]">
              {error}
            </div>
          )}

          <button
            type="submit" disabled={loading}
            data-testid="login-submit-button"
            className="w-full py-3 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold hover:opacity-95 disabled:opacity-60 transition-opacity"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>

          <div className="text-sm text-muted-foreground text-center">
            No account?{" "}
            <Link to="/register" data-testid="login-to-register" className="text-foreground font-semibold underline underline-offset-4">
              Create one
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
