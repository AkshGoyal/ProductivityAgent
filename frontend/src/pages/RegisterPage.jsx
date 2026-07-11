import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function RegisterPage() {
  const { register, error } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const ok = await register(email, password, name);
    setLoading(false);
    if (ok) {
      toast.success("Account created");
      nav("/app/dashboard", { replace: true });
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background relative z-10">
      <div className="hidden lg:block relative">
        <img
          src="https://images.unsplash.com/photo-1533630160910-65f5a1718c65?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzR8MHwxfHNlYXJjaHwzfHx6ZW4lMjBzdG9uZSUyMGNhbG18ZW58MHx8fHwxNzgzNzYwOTcwfDA&ixlib=rb-4.1.0&q=85"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <div className="overline mb-3 text-white/80">Momentum</div>
          <div className="font-display text-4xl font-bold tracking-tight max-w-sm">
            Start where you are.<br />Move what matters.
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm space-y-6" data-testid="register-form">
          <div>
            <div className="overline mb-2">Create account</div>
            <h1 className="font-display text-3xl font-bold tracking-tight">Set the pace.</h1>
            <p className="text-sm text-muted-foreground mt-2">Takes under a minute.</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="name">Your name</Label>
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} data-testid="register-name-input" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="register-email-input" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} data-testid="register-password-input" />
          </div>

          {error && (
            <div data-testid="register-error" className="text-sm text-[color:hsl(var(--destructive))]">
              {error}
            </div>
          )}

          <button
            type="submit" disabled={loading}
            data-testid="register-submit-button"
            className="w-full py-3 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold hover:opacity-95 disabled:opacity-60 transition-opacity"
          >
            {loading ? "Creating…" : "Create account"}
          </button>

          <div className="text-sm text-muted-foreground text-center">
            Already have one?{" "}
            <Link to="/login" data-testid="register-to-login" className="text-foreground font-semibold underline underline-offset-4">
              Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
