import { useRef, useState } from "react";
import { api } from "../api";
import { niceDate, orgName, t } from "../i18n";
import { go } from "../nav";
import { Button, ErrorNote } from "./ui";

function ScamWarning({ lang, reply }) {
  return (
    <div role="alert" className="mt-4 rounded-2xl border border-rose-ink/30 bg-rose-soft p-4 text-rose-ink">
      <p className="font-semibold">{t(lang, "replyScamTitle")}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {reply.red_flags.map((flag) => <li key={flag}>{flag}</li>)}
      </ul>
      {reply.red_flag_quotes?.length > 0 && (
        <p className="mt-2 text-sm">{t(lang, "replyTheirWords")}: {reply.red_flag_quotes.map((q) => `“${q}”`).join(", ")}</p>
      )}
      <p className="mt-2">{t(lang, "replyScamBody")}</p>
      <p className="mt-2 text-sm opacity-90" data-no-read>{reply.filename}</p>
    </div>
  );
}

function ReplyCard({ c, lang, reply, refresh }) {
  const [busy, setBusy] = useState(null);
  const letter = c.letters.find((l) => l.reply_id === reply.id);
  const confirmed = reply.confirmed_item_id;

  async function tick(req) {
    setBusy(req.id);
    try {
      await api.setRequirement(c.id, reply.id, req.id, !req.done);
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  if (reply.red_flags.length) return <ScamWarning lang={lang} reply={reply} />;
  const done = reply.requirements.filter((r) => r.done).length;
  return (
    <div className="mt-4 rounded-2xl border border-sand-200 bg-sand-50 p-4">
      <p className="font-semibold">
        {t(lang, "replyFrom", { institution: orgName(reply.institution) })}
        {reply.letter_date && <span className="font-normal text-ink-soft"> · {niceDate(reply.letter_date, lang)}</span>}
      </p>
      {confirmed && <p className="mt-1 font-semibold text-sage-ink"><span aria-hidden="true">✓ </span>{t(lang, "replyConfirmed")}</p>}
      <p className="mt-2">{reply.summary}</p>
      {reply.respond_by && (
        <p className="mt-2 font-semibold text-amber-ink">⏱ {t(lang, "replyRespondBy", { date: niceDate(reply.respond_by, lang) })}</p>
      )}
      {reply.requirements.length > 0 && (
        <fieldset className="mt-3">
          <legend className="font-semibold">{t(lang, "replyTheyAsk", { done, n: reply.requirements.length })}</legend>
          <ul className="mt-2 space-y-1">
            {reply.requirements.map((req) => (
              <li key={req.id}>
                <label className="flex min-h-11 cursor-pointer items-start gap-3 py-1">
                  <input type="checkbox" className="mt-1 h-5 w-5 shrink-0" checked={req.done} disabled={busy === req.id}
                         onChange={() => tick(req)} />
                  <span className={req.done ? "text-ink-soft line-through" : ""}>
                    {req.document}{req.detail && <span className="text-ink-soft">, {req.detail}</span>}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      )}
      {letter && (
        <Button variant="quiet" className="mt-2 -ml-2" onClick={() => go(`/case/${c.id}/letters?l=${letter.id}`)}>
          {t(lang, "replyLetterReady")}
        </Button>
      )}
    </div>
  );
}

// "Got a reply?": the family uploads what the institution sent back. Gemini reads it; code updates the plan.
export default function Replies({ c, lang, task, refresh }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const replies = c.replies.filter((r) => r.task_id === task.id);
  const used = new Set(replies.map((r) => r.filename));
  const samples = (c.samples?.replies?.[task.id] || []).filter((name) => !used.has(name));

  async function send(file, label) {
    setBusy(label);
    setError(null);
    try {
      await api.addReply(c.id, task.id, file);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function sample(name) {
    try {
      await send(await api.sampleFile(name), name);
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="mt-5 border-t border-sand-200 pt-4">
      {replies.map((reply) => <ReplyCard key={reply.id} c={c} lang={lang} reply={reply} refresh={refresh} />)}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input ref={input} type="file" accept="image/*,application/pdf" className="sr-only" tabIndex={-1}
               aria-hidden="true" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) send(f, "file"); }} />
        <Button variant="quiet" className="-ml-2" busy={busy === "file"} disabled={!!busy} onClick={() => input.current?.click()}>
          {t(lang, "replyUpload")}
        </Button>
        {samples.map((name) => (
          <Button key={name} variant="quiet" busy={busy === name} disabled={!!busy} onClick={() => sample(name)}>
            {t(lang, name.startsWith("message_") ? "replySampleScam" : "replySample")}
          </Button>
        ))}
      </div>
      {busy && <p className="text-sm text-ink-soft" role="status">{t(lang, "replyReading")}</p>}
      <ErrorNote lang={lang} error={error} />
    </div>
  );
}
