import { useEffect, useRef } from "react";
import { t } from "../i18n";

export function ActivitySummary({ lang, summary }) {
  if (!summary?.length) return null;
  return (
    <ul className="flex flex-wrap gap-2">
      {summary.map((line) => (
        <li key={line.en} className="rounded-full bg-brand-soft px-3 py-1 text-sm font-semibold text-brand-dark">
          {line[lang] || line.en}
        </li>
      ))}
    </ul>
  );
}

export function ActivityList({ lang, entries, limit }) {
  const shown = [...(entries || [])].reverse().slice(0, limit || undefined);
  return (
    <ol className="space-y-2">
      {shown.map((a, n) => (
        <li key={`${a.at}-${n}`} className={`flex gap-3 rounded-2xl px-3 py-2 ${a.ok ? "bg-sand-50" : "bg-rose-soft text-rose-ink"}`}>
          <span className="shrink-0 tabular-nums text-ink-soft text-sm pt-0.5">
            {new Date(a.at).toLocaleTimeString(lang === "hi" ? "hi-IN" : "en-IN", { hour: "2-digit", minute: "2-digit" })}
          </span>
          <span>{lang === "hi" ? a.summary_hi : a.summary_en}</span>
        </li>
      ))}
    </ol>
  );
}

export default function ActivityPanel({ lang, open, onClose, summary, entries }) {
  const closeRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/30" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="activity-title"
        className="fade-in flex h-full w-full max-w-md flex-col gap-4 overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 id="activity-title" className="font-serif text-2xl">{t(lang, "activity")}</h2>
          <button ref={closeRef} onClick={onClose} className="min-h-11 rounded-full px-4 font-semibold text-brand hover:bg-brand-soft">
            {t(lang, "close")}
          </button>
        </div>
        <ActivitySummary lang={lang} summary={summary} />
        <ActivityList lang={lang} entries={entries} />
      </div>
    </div>
  );
}
