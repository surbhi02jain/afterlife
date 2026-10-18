import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { Button, Card, ErrorNote } from "./ui";

// Names written differently on different papers stall claims. Gemini compares them; what to do comes from the
// knowledge base (name_guidance), never from the model.
export default function NameCheck({ c, lang, refresh }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const check = c.name_check;
  const read = c.documents.filter((d) => d.status === "extracted").length;

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await api.checkNames(c.id);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (!check) {
    if (!read) return null;
    return (
      <Card className="mb-5">
        <h2 className="font-serif text-xl">{t(lang, "namesTitle")}</h2>
        <p className="mt-1 text-ink-soft">{t(lang, "namesBody")}</p>
        <Button variant="secondary" className="mt-4" busy={busy} onClick={run}>{t(lang, "namesRun")}</Button>
        <ErrorNote lang={lang} error={error} />
      </Card>
    );
  }

  if (!check.issues.length) {
    return (
      <Card className="mb-5">
        <p className="text-sage-ink"><span aria-hidden="true">✓ </span>{t(lang, "namesMatch", { n: check.compared })}</p>
      </Card>
    );
  }

  const guide = c.name_guidance;
  return (
    <section aria-labelledby="names-h" className="mb-5 rounded-3xl border border-amber-line bg-amber-soft/60 p-5 sm:p-6">
      <h2 id="names-h" className="font-serif text-xl text-amber-ink">{t(lang, "namesDiffer", { n: check.issues.length })}</h2>
      <p className="mt-1">{t(lang, "namesWhy")}</p>
      {check.issues.map((issue, n) => (
        <div key={n} className="mt-4 rounded-2xl bg-white p-4">
          <p className="font-semibold">{t(lang, `names_${issue.kind}`)}</p>
          <ul className="mt-2 space-y-1">
            {issue.names.map((row) => (
              <li key={row.name} className="flex flex-wrap gap-x-3">
                <span className="font-semibold">“{row.name}”</span>
                <span className="text-sm text-ink-soft" data-no-read>{row.where.join(", ")}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-ink-soft">{issue.explanation}</p>
        </div>
      ))}
      {guide?.found && (
        <details className="mt-4 rounded-2xl bg-white px-4 py-3">
          <summary className="cursor-pointer font-semibold text-brand">{t(lang, "namesWhatToDo")}</summary>
          <ol className="mt-2 list-decimal space-y-1 pl-6">
            {guide.steps.map((step) => <li key={step}>{step}</li>)}
          </ol>
          <p className="mt-3 font-semibold">{t(lang, "documents")}</p>
          <ul className="mt-1 list-disc space-y-1 pl-6">
            {guide.documents_required.map((d) => <li key={d}>{d}</li>)}
          </ul>
          <p className="mt-3 text-sm text-ink-soft">
            {t(lang, "source")}: {guide.source_name}{!guide.verified && ` (${t(lang, "unverified")})`}.{" "}
            {t(lang, "notLegalAdvice")}
          </p>
        </details>
      )}
    </section>
  );
}
