import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function ProfilePage() {
  const { user, updateProfile } = useAuth();
  const [form, setForm] = useState({ name: "", working_style: "", mindset: "", preferences: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) setForm({
      name: user.name || "",
      working_style: user.working_style || "",
      mindset: user.mindset || "",
      preferences: user.preferences || "",
    });
  }, [user]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateProfile(form);
      toast.success("Profile updated — the coach will adapt.");
    } catch {
      toast.error("Could not save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-8" data-testid="profile-page">
      <div>
        <div className="overline mb-2">Profile</div>
        <h1 className="font-display text-4xl font-bold tracking-tight">Teach the coach who you are.</h1>
        <p className="text-sm text-muted-foreground mt-3 leading-relaxed">
          Momentum feeds this into every AI response — from goal breakdowns to daily nudges.
          Be honest and specific.
        </p>
      </div>

      <form onSubmit={save} className="space-y-6" data-testid="profile-form">
        <div className="space-y-2">
          <Label>Name</Label>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="profile-name-input" />
        </div>
        <div className="space-y-2">
          <Label>How you like to work</Label>
          <Textarea
            data-testid="profile-working-style-input"
            rows={4}
            placeholder="e.g. Deep work mornings. Batch admin. Hate long meetings. Prefer 25-min sprints."
            value={form.working_style}
            onChange={(e) => setForm({ ...form, working_style: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label>Mindset & motivators</Label>
          <Textarea
            data-testid="profile-mindset-input"
            rows={4}
            placeholder="e.g. I get anxious when scope creeps. I move faster when I know why. Direct feedback works best."
            value={form.mindset}
            onChange={(e) => setForm({ ...form, mindset: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label>Preferences</Label>
          <Textarea
            data-testid="profile-preferences-input"
            rows={3}
            placeholder="e.g. Bullet points, not paragraphs. Push back when I'm avoiding hard tasks."
            value={form.preferences}
            onChange={(e) => setForm({ ...form, preferences: e.target.value })}
          />
        </div>

        <button
          type="submit" disabled={saving}
          data-testid="profile-save-button"
          className="px-6 py-2.5 rounded-full bg-[color:hsl(var(--primary))] text-[color:hsl(var(--primary-foreground))] font-semibold disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save profile"}
        </button>
      </form>
    </div>
  );
}
