import { useState } from "react";
import { api } from "../api";
import { orgName, t, typeLabel } from "../i18n";
import { go } from "../nav";
import { Badge, Button, Card, ErrorNote, PageTitle, PrimaryBar, ScamNotice } from "../components/ui";
import NameCheck from "../components/NameCheck";
import Replies from "../components/Replies";

function TaskCard({ c, lang, task, onLetter, busy, refresh }) {
  return (
    <Card className="fade-in">
      <div className="flex gap-4">
        <span aria-hidden="true" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand text-lg font-bold text-white">
          {task.order}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold">
            <span className="sr-only">{task.order}. </span>
            {orgName(task.institution)}
          </h3>
          <p className="mt-1 text-ink-soft">
            {task.items.map((i) => `${typeLabel(lang, i.type)}${i.identifier_masked ? ` ${i.identifier_masked}` : ""}`).join(", ")}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {task.needs_confirmation && <Badge tone="amber">{t(lang, "needsChecking")}</Badge>}
            {task.nominee && <Badge tone="neutral">{t(lang, "nominee")}: {task.nominee}</Badge>}
          </div>

          {task.time_sensitive.length > 0 && (
            <div className="mt-4 rounded-2xl border border-amber-line bg-amber-soft px-4 py-3 text-amber-ink">
              <p className="font-semibold">⏱ {t(lang, "timeSensitive")}</p>
              <ul className="mt-1 list-disc pl-5">
                {task.time_sensitive.map((flag) => (
                  <li key={flag}>{flag}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-4">
            <span className="font-semibold">{t(lang, "firstStep")}: </span>
            {task.first_step}
          </p>
          <p className="mt-2 text-ink-soft">
            <span className="font-semibold">{t(lang, "whyOrder")}: </span>
            {task.why_this_order}
          </p>

          <details className="mt-4 rounded-2xl bg-sand-50 px-4 py-3">
            <summary className="cursor-pointer font-semibold text-brand">{t(lang, "allSteps")}</summary>
            <p className="mt-3 font-semibold">{t(lang, "steps")}</p>
            <ol className="mt-1 list-decimal space-y-1 pl-6">
              {task.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
            {task.documents_required.length > 0 && (
              <>
                <p className="mt-3 font-semibold">{t(lang, "documents")}</p>
                <ul className="mt-1 list-disc space-y-1 pl-6">
                  {task.documents_required.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </>
            )}
            {task.typical_timeline && (
              <p className="mt-3">
                <span className="font-semibold">{t(lang, "timeline")}: </span>
                {task.typical_timeline}
              </p>
            )}
            <p className="mt-3 text-sm text-ink-soft">
              {t(lang, "source")}: {task.source_names.join(", ")}{!task.verified && ` (${t(lang, "unverified")})`}
            </p>
          </details>

          <Button variant="secondary" className="mt-4" busy={busy === task.id} onClick={() => onLetter(task)}>
            {t(lang, "prepareLetter")}
          </Button>
          <Replies c={c} lang={lang} task={task} refresh={refresh} />
        </div>
      </div>
    </Card>
  );
}

function PlanProgress({ lang, tasks }) {
  const done = tasks.filter((task) => task.board_status === "done").length;
  return (
    <Card className="mb-5">
      <p className="font-semibold">{t(lang, "planProgress", { done, n: tasks.length })}</p>
      <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-sand-100" role="progressbar" aria-valuemin={0}
           aria-valuemax={tasks.length} aria-valuenow={done}>
        <div className="h-full rounded-full bg-brand transition-[width]" style={{ width: `${(done / (tasks.length || 1)) * 100}%` }} />
      </div>
    </Card>
  );
}

export default function Plan({ c, lang, refresh }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const plan = c.plan;

  async function makePlan() {
    setBusy("plan");
    setError(null);
    try {
      await api.buildPlan(c.id);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function letter(task) {
    setBusy(task.id);
    setError(null);
    try {
      const made = await api.createLetter(c.id, task.items[0].item_id);
      await refresh();
      go(`/case/${c.id}/letters?l=${made.id}`);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  return (
    <div className="fade-in">
      <PageTitle title={t(lang, "planTitle")} body={plan ? t(lang, "planBody") : null} />
      {plan && <ScamNotice lang={lang} />}
      <NameCheck c={c} lang={lang} refresh={refresh} />
      <ErrorNote lang={lang} error={error} />
      {!plan ? (
        <PrimaryBar>
          <Button busy={busy === "plan"} onClick={makePlan}>
            {t(lang, "makePlan")}
          </Button>
        </PrimaryBar>
      ) : (
        <>
          <PlanProgress lang={lang} tasks={plan.tasks} />
          <Card className="mb-5 bg-brand-soft/50">
            <h2 className="font-serif text-xl">{t(lang, "firstForEveryone")}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              {plan.general_steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </Card>
          <div className="space-y-5">
            {plan.tasks.map((task) => (
              <TaskCard key={task.id} c={c} lang={lang} task={task} onLetter={letter} busy={busy} refresh={refresh} />
            ))}
          </div>
          <p className="mt-6 text-ink-soft">{plan.disclaimer}</p>
          <PrimaryBar>
            <Button onClick={() => go(`/case/${c.id}/letters`)}>{t(lang, "seeLetters")}</Button>
          </PrimaryBar>
        </>
      )}
    </div>
  );
}
