import { useState } from "react";
import { api } from "../api";
import { orgName, t, typeLabel } from "../i18n";
import { go } from "../nav";
import { Button, ErrorNote, PageTitle } from "../components/ui";

const COLUMNS = ["todo", "in_progress", "done"];
const NEXT = { todo: "in_progress", in_progress: "done" };
const BACK = { in_progress: "todo", done: "in_progress" };

function TaskTile({ lang, task, onMove, busy }) {
  return (
    <li className="rounded-2xl border border-sand-200 bg-white p-4">
      <p className="font-semibold">
        {task.order}. {orgName(task.institution)}
      </p>
      <p className="text-sm text-ink-soft">
        {task.items.map((i) => `${typeLabel(lang, i.type)}${i.identifier_masked ? ` ${i.identifier_masked}` : ""}`).join(", ")}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {NEXT[task.board_status] && (
          <Button className="min-h-11 px-4 py-2" busy={busy === task.id} onClick={() => onMove(task, NEXT[task.board_status])}>
            {task.board_status === "todo" ? t(lang, "start") : t(lang, "markDone")}
          </Button>
        )}
        {BACK[task.board_status] && (
          <Button variant="quiet" onClick={() => onMove(task, BACK[task.board_status])}>
            {t(lang, "moveBack")}
          </Button>
        )}
      </div>
    </li>
  );
}

function Columns({ lang, tasks, onMove, busy }) {
  return (
    <div className="grid gap-5 md:grid-cols-3 md:items-start">
      {COLUMNS.map((col) => {
        const items = tasks.filter((task) => task.board_status === col);
        return (
          <section key={col} aria-labelledby={`col-${col}`} className="rounded-2xl bg-sand-100 p-4">
            <h2 id={`col-${col}`} className="mb-3 font-semibold">
              {t(lang, `col_${col}`)} <span className="text-ink-soft">({items.length})</span>
            </h2>
            <ul className="space-y-3">
              {items.map((task) => (
                <TaskTile key={task.id} lang={lang} task={task} onMove={onMove} busy={busy} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export default function Board({ c, lang, refresh }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  async function move(task, status) {
    setBusy(task.id);
    setError(null);
    try {
      await api.setTask(c.id, task.id, status);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="fade-in">
      <PageTitle title={t(lang, "boardTitle")} body={t(lang, "boardBody")} />
      <ErrorNote lang={lang} error={error} />
      {!c.plan ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-ink-soft">{t(lang, "noPlanYet")}</p>
          <Button onClick={() => go(`/case/${c.id}/plan`)}>{t(lang, "makePlan")}</Button>
        </div>
      ) : (
        <Columns lang={lang} tasks={c.plan.tasks} onMove={move} busy={busy} />
      )}
    </div>
  );
}
