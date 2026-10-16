import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { go } from "../nav";
import { Button, Card, ErrorNote } from "../components/ui";

const RELATIONSHIPS = ["spouse", "son", "daughter", "parent", "sibling", "other"];

function lastCase() {
  try {
    return localStorage.getItem("saath.case");
  } catch {
    return null;
  }
}

const field = "mt-2 block w-full min-h-12 rounded-xl border-2 border-sand-300 bg-white px-4 py-3 text-base focus:border-brand";

export default function Start({ lang }) {
  const [form, setForm] = useState({ deceased_name: "", date_of_death: "", relationship: "", language: lang });
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const previous = lastCase();
  const deleted = window.location.hash.includes("deleted");
  const today = new Date().toISOString().slice(0, 10);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function begin(e) {
    e.preventDefault();
    setBusy("begin");
    setError(null);
    try {
      // Stored in plain English because letters say "I am the <relationship> of the deceased".
      const relationship = form.relationship === "other" ? "family member" : form.relationship;
      const c = await api.createCase({ ...form, relationship });
      go(`/case/${c.id}/upload`);
    } catch (err) {
      setError(err);
      setBusy(null);
    }
  }

  async function demo() {
    setBusy("demo");
    setError(null);
    try {
      const c = await api.demo();
      go(`/case/${c.id}/upload`);
    } catch (err) {
      setError(err);
      setBusy(null);
    }
  }

  return (
    <div className="fade-in grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-start">
      <section>
        {deleted && (
          <p role="status" className="mb-4 rounded-xl bg-sage-soft px-4 py-3 text-sage-ink">
            {t(lang, "deletedNotice")}
          </p>
        )}
        <h1 className="font-serif text-[2rem] leading-tight sm:text-[2.4rem]">{t(lang, "startTitle")}</h1>
        <p className="mt-4 text-ink-soft">{t(lang, "startBody")}</p>
        <Card className="mt-6 bg-brand-soft/60">
          <p className="text-ink-soft">{t(lang, "demoHint")}</p>
          <Button variant="secondary" className="mt-3 w-full sm:w-auto" busy={busy === "demo"} onClick={demo}>
            {t(lang, "tryDemo")}
          </Button>
        </Card>
        {previous && (
          <a href={`#/case/${previous}/upload`} className="mt-4 inline-block font-semibold text-brand underline underline-offset-4">
            {t(lang, "continueCase")}
          </a>
        )}
      </section>

      <Card>
        <form onSubmit={begin} className="space-y-5">
          <label className="block font-semibold">
            {t(lang, "theirName")}
            <input required maxLength={120} className={field} value={form.deceased_name} onChange={set("deceased_name")} autoComplete="off" />
          </label>
          <label className="block font-semibold">
            {t(lang, "dateOfDeath")}
            <input required type="date" max={today} className={field} value={form.date_of_death} onChange={set("date_of_death")} />
          </label>
          <label className="block font-semibold">
            {t(lang, "yourRelationship")}
            <select required className={field} value={form.relationship} onChange={set("relationship")}>
              <option value="" disabled>
                —
              </option>
              {RELATIONSHIPS.map((r) => (
                <option key={r} value={r}>
                  {t(lang, `rel_${r}`)}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend className="font-semibold">{t(lang, "preferredLanguage")}</legend>
            <div className="mt-2 flex gap-3">
              {[["en", "English"], ["hi", "हिन्दी"]].map(([value, name]) => (
                <label key={value} className={`flex min-h-12 flex-1 cursor-pointer items-center gap-2 rounded-xl border-2 px-4
                  ${form.language === value ? "border-brand bg-brand-soft" : "border-sand-300"}`}>
                  <input type="radio" name="language" value={value} checked={form.language === value} onChange={set("language")} />
                  {name}
                </label>
              ))}
            </div>
          </fieldset>
          <ErrorNote lang={lang} error={error} />
          <Button type="submit" className="w-full" busy={busy === "begin"}>
            {t(lang, "begin")}
          </Button>
        </form>
      </Card>
    </div>
  );
}
