import { useEffect, useState } from "react";
import { api } from "../api";
import { MAX_SECONDS, canRecord, startRecording } from "../audio";
import { orgName, t, typeLabel } from "../i18n";
import { Button, Card, ErrorNote, field } from "./ui";

function Result({ lang, memory }) {
  return (
    <div className="mt-5 rounded-2xl bg-sand-50 p-4" role="status">
      <p className="font-semibold">{t(lang, "memoryHeard")}</p>
      <ul className="mt-2 space-y-2">
        {memory.results.map((r) => (
          <li key={r.item_id} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-semibold capitalize">
              {typeLabel(lang, r.type)}{r.institution ? `, ${orgName(r.institution)}` : ""}
            </span>
            <span className={r.matched_transactions ? "text-sage-ink" : "text-ink-soft"}>
              {r.matched_transactions
                ? t(lang, "memoryMatched", { n: r.matched_transactions })
                : t(lang, "memoryNoMatch")}
            </span>
          </li>
        ))}
        {!memory.results.length && <li className="text-ink-soft">{t(lang, "memoryNothing")}</li>}
      </ul>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-semibold text-brand">{t(lang, "memoryTranscript")}</summary>
        <p className="mt-2 whitespace-pre-line">{memory.transcript}</p>
      </details>
    </div>
  );
}

// "Tell us what you remember": the family speaks (or types); Gemini listens; code checks it against the statements.
// Asked on the documents screen, so the hidden-asset search can use it; `later` tucks it away on the asset map.
export default function MemoryCard({ c, lang, refresh, later = false }) {
  const [recording, setRecording] = useState(null); // { stop } while the microphone is on
  const [seconds, setSeconds] = useState(0);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const memory = c.memories?.at(-1); // re-checked at each analysis, so read it from the case

  useEffect(() => {
    if (!recording) return;
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [recording]);

  async function send(input, label) {
    setBusy(label);
    setError(null);
    try {
      await api.addMemory(c.id, input);
      setText("");
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function toggle() {
    if (recording) {
      setRecording(null);
      const audio = await recording.stop();
      return send({ audio }, "voice");
    }
    setError(null);
    try {
      const rec = await startRecording();
      setSeconds(0);
      setRecording(rec);
    } catch {
      setError(new Error(t(lang, "micBlocked")));
    }
  }

  // stop automatically at the limit
  useEffect(() => {
    if (recording && seconds >= MAX_SECONDS) toggle();
  }, [seconds]); // eslint-disable-line react-hooks/exhaustive-deps

  async function useSample() {
    try {
      const file = await api.sampleFile(c.samples.memory);
      await send({ audio: file }, "sample");
    } catch (e) {
      setError(e);
    }
  }

  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  const body = (
    <>
      <p className="mt-1 max-w-[60ch] text-ink-soft">{t(lang, "memoryBody")}</p>

      {c.samples?.memory && (
        <div className="mt-4 rounded-2xl bg-brand-soft/60 p-4" data-no-read>
          <p className="font-semibold text-brand-dark">{t(lang, "memorySample")}</p>
          <audio controls preload="none" src={api.sampleUrl(c.samples.memory)} className="mt-2 w-full max-w-md" />
          <Button variant="secondary" className="mt-3" busy={busy === "sample"} disabled={!!busy || !!recording}
                  onClick={useSample}>
            {t(lang, "memoryUseSample")}
          </Button>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {canRecord() && (
          <Button variant={recording ? "danger" : "secondary"} busy={busy === "voice"} disabled={!!busy}
                  aria-pressed={!!recording} onClick={toggle}>
            <span aria-hidden="true">{recording ? "■" : "🎙"}</span>
            {recording ? t(lang, "memoryStop", { time: clock }) : t(lang, "memoryRecord")}
          </Button>
        )}
        {recording && <span className="text-sm text-ink-soft" role="status">{t(lang, "memoryListening")}</span>}
      </div>

      <form className="mt-4" onSubmit={(e) => { e.preventDefault(); if (text.trim()) send({ text: text.trim() }, "text"); }}>
        <label className="block font-semibold" htmlFor="memory-text">{t(lang, "memoryOrType")}</label>
        <textarea id="memory-text" rows={3} maxLength={2000} className={`mt-2 ${field}`} value={text}
                  placeholder={t(lang, "memoryPlaceholder")} onChange={(e) => setText(e.target.value)} />
        <Button variant="secondary" type="submit" className="mt-3" busy={busy === "text"}
                disabled={!!busy || !!recording || !text.trim()}>
          {t(lang, "memorySend")}
        </Button>
      </form>

      <ErrorNote lang={lang} error={error} />
      {busy && <p className="mt-3 text-ink-soft" role="status">{t(lang, "memoryWorking")}</p>}
      {memory && <Result lang={lang} memory={memory} />}
      <p className="mt-4 text-sm text-ink-soft">{t(lang, "memoryPrivacy")}</p>
    </>
  );

  if (later)
    return (
      <details className="mb-10 rounded-2xl border border-sand-200 bg-white px-5 py-4">
        <summary className="cursor-pointer font-semibold text-brand">{t(lang, "memoryMore")}</summary>
        <div className="mt-2">{body}</div>
      </details>
    );
  return (
    <Card className="mt-6">
      <h2 className="font-serif text-xl">{t(lang, "memoryTitle")}</h2>
      {body}
    </Card>
  );
}
