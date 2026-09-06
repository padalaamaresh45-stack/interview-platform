import { useState, type FormEvent } from "react";
import { useAuth } from "../hooks/useAuth";
import { browserTimezone } from "../utils/timezone";

function supportedTimezones(): string[] {
  // Intl.supportedValuesOf is widely available in evergreen browsers; fall
  // back to just the browser's own zone if it's missing so the picker still
  // works rather than rendering empty.
  const intlWithSupportedValues = Intl as typeof Intl & {
    supportedValuesOf?: (key: string) => string[];
  };
  return intlWithSupportedValues.supportedValuesOf?.("timeZone") ?? [browserTimezone()];
}

export function ProfilePage() {
  const { user, updateTimezone } = useAuth();
  const [timezone, setTimezone] = useState(user?.timezone ?? browserTimezone());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (!user) {
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateTimezone(timezone);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <h1>Profile</h1>
      </div>
      {error && <p role="alert">{error}</p>}
      <p className="detail-meta">
        {user.full_name} · {user.email}
      </p>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="profile-timezone">Timezone</label>
          <select
            id="profile-timezone"
            value={timezone}
            onChange={(e) => {
              setTimezone(e.target.value);
              setSaved(false);
            }}
          >
            {supportedTimezones().map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>
        <p className="field-hint">
          Used to show your local time when an admin schedules an interview for you, and to display your
          scorecard due dates.
        </p>
        {saved && <p role="status">Timezone saved.</p>}
        <button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </form>
    </main>
  );
}
