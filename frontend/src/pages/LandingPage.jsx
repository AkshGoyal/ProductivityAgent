import { Link } from "react-router-dom";
import { ArrowRight, Target, ListTodo, MessagesSquare, NotebookPen } from "lucide-react";

const features = [
  { icon: Target, title: "Goals that break themselves down", body: "Drop in a goal, get atomic tasks calibrated to how you actually work." },
  { icon: ListTodo, title: "Tasks with real priority", body: "Priorities, due dates and a clean status flow. No clutter." },
  { icon: MessagesSquare, title: "A coach that knows you", body: "Feed it your working style and mindset. Get honest, useful nudges." },
  { icon: NotebookPen, title: "Notes for the thoughts along the way", body: "A quiet place to think out loud while you build momentum." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground relative z-10">
      <header className="hairline-b border-b border-border">
        <div className="max-w-7xl mx-auto px-8 py-5 flex items-center justify-between">
          <div className="font-display text-xl font-bold tracking-tight">Momentum</div>
          <div className="flex items-center gap-3">
            <Link to="/login" data-testid="landing-login" className="text-sm font-medium px-4 py-2 rounded-full hover:bg-muted transition-colors">Log in</Link>
            <Link to="/register" data-testid="landing-signup" className="text-sm font-semibold px-4 py-2 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] hover:bg-[color:hsl(var(--primary))]/90 transition-colors">
              Start free
            </Link>
          </div>
        </div>
      </header>

      <section className="max-w-7xl mx-auto px-8 pt-24 pb-20 grid lg:grid-cols-12 gap-12 items-start">
        <div className="lg:col-span-7">
          <div className="overline mb-6">Personal productivity agent</div>
          <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.02]">
            Your goals. Broken down.<br />
            <span className="text-[color:hsl(var(--accent))]">Calibrated to you.</span>
          </h1>
          <p className="mt-8 text-lg text-muted-foreground max-w-xl leading-relaxed">
            Momentum turns fuzzy goals into concrete tasks, adapts to your working style and mindset,
            and gives you a coach that actually knows what you're working on.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link
              to="/register"
              data-testid="hero-start-button"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold hover:translate-y-[-1px] transition-transform"
            >
              Get started free <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-full border border-border font-semibold hover:border-foreground/40 transition-colors"
            >
              I have an account
            </Link>
          </div>
        </div>

        <div className="lg:col-span-5 relative">
          <div className="rounded-2xl overflow-hidden border border-border card-lift">
            <img
              src="https://images.pexels.com/photos/22711217/pexels-photo-22711217.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
              alt="Calm workspace"
              className="w-full h-[420px] object-cover"
            />
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-8 pb-24">
        <div className="overline mb-4">What's inside</div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map(({ icon: Icon, title, body }) => (
            <div key={title} className="p-6 rounded-xl border border-border bg-card card-lift">
              <Icon className="w-5 h-5 mb-4 text-[color:hsl(var(--accent))]" />
              <div className="font-display text-lg font-semibold mb-2">{title}</div>
              <div className="text-sm text-muted-foreground leading-relaxed">{body}</div>
            </div>
          ))}
        </div>
      </section>

      <footer className="hairline-t border-t border-border">
        <div className="max-w-7xl mx-auto px-8 py-6 text-xs text-muted-foreground flex items-center justify-between">
          <div>© {new Date().getFullYear()} Momentum</div>
          <div>Built for people who ship.</div>
        </div>
      </footer>
    </div>
  );
}
