import { useEffect, useState } from "react";
import { api } from "../api";
import { niceDate, orgName, t, typeLabel } from "../i18n";
import { go } from "../nav";
import { Button, Card, ErrorNote, PageTitle, Spinner } from "../components/ui";

const COLUMNS = ["todo", "in_progress", "done"];
const NEXT = { todo: "in_progress", in_progress: "done" };
const BACK = { in_progress: "todo", done: "in_progress" };

function TaskTile({ lang, task, onMove, busy, readOnly }) {
  return (
    <li className="rounded-2xl border border-sand-200 bg-white p-4">
      <p className="font-semibold">
        {task.order}. {orgName(task.institution)}
      </p>
      <p className="text-sm text-ink-soft">
        {task.items.map((i) => `${typeLabel(lang, i.type)}${i.identifier_masked ? ` ${i.identifier_masked}` : ""}`).join(", ")}
      </p>
      {!readOnly && (
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
      )}
    </li>
  );
}

function Columns({ lang, tasks, onMove, busy, readOnly }) {
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
                <TaskTile key={task.id} lang={lang} task={task} onMove={onMove} busy={busy} readOnly={readOnly} />
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
  const [copied, setCopied] = useState(false);
  const shareUrl = c.share_token ? `${window.location.origin}/#/share/${c.share_token}` : null;

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

  async function share() {
    setBusy("share");
    setError(null);
    try {
      await api.share(c.id);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function turnOff() {
    setBusy("unshare");
    setError(null);
    try {
      await api.unshare(c.id);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      /* the link stays visible to copy by hand */
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
        <>
          <Columns lang={lang} tasks={c.plan.tasks} onMove={move} busy={busy} />
          <Card className="mt-10">
            <h2 className="font-serif text-xl">{t(lang, "shareTitle")}</h2>
            <p className="mt-1 text-ink-soft">{t(lang, "shareBody")}</p>
            {shareUrl ? (
              <>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
                <input readOnly value={shareUrl} aria-label={t(lang, "shareTitle")}
                       className="min-h-12 flex-1 rounded-2xl border-2 border-sand-300 bg-sand-50 px-4 text-sm"
                       onFocus={(e) => e.target.select()} />
                <Button onClick={copy}>{copied ? `✓ ${t(lang, "copied")}` : t(lang, "copy")}</Button>
              </div>
              <p className="mt-3 text-sm text-ink-soft">
                {t(lang, "shareUntil", { date: niceDate(c.share_expires_at, lang) })}
              </p>
              <Button variant="quiet" className="mt-1 -ml-2" busy={busy === "unshare"} onClick={turnOff}>
                {t(lang, "turnOffLink")}
              </Button>
              </>
            ) : (
              <Button className="mt-4" busy={busy === "share"} onClick={share}>
                {t(lang, "createLink")}
              </Button>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

export function SharedBoard({ token, lang }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.shared(token).then(setData).catch(setError);
  }, [token]);

  if (error) return <p role="alert" className="text-rose-ink">{t(lang, "linkInvalid")}</p>;
  if (!data) return <Spinner label={t(lang, "loading")} />;
  return (
    <div className="fade-in">
      <p className="mb-4 rounded-2xl bg-brand-soft px-4 py-2 text-brand-dark">{t(lang, "sharedView")}</p>
      <PageTitle title={t(lang, "boardTitle")} body={t(lang, "forName", { name: data.deceased_name })} />
      <Columns lang={lang} tasks={data.tasks} readOnly />
    </div>
  );
}
