import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { go } from "../nav";
import { Button, Card, ErrorNote, PageTitle, PrimaryBar } from "../components/ui";

function QuestionCard({ lang, q, onAnswer, busy }) {
  const [text, setText] = useState("");
  return (
    <Card className="fade-in">
      <p className="text-lg font-semibold">{q.text}</p>
      {q.why && <p className="mt-1 text-ink-soft">{q.why}</p>}
      {q.options.length > 0 ? (
        <div className="mt-4 flex flex-col gap-3 sm:flex-row" role="group" aria-label={q.text}>
          {q.options.map((option, n) => (
            <Button key={option} variant={n === 0 ? "primary" : "secondary"} busy={busy === `${q.id}:${option}`}
                    onClick={() => onAnswer(q, option)}>
              {option}
            </Button>
          ))}
        </div>
      ) : (
        <form
          className="mt-4 flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) onAnswer(q, text.trim());
          }}
        >
          <label className="sr-only" htmlFor={`a-${q.id}`}>{t(lang, "typeAnswer")}</label>
          <input
            id={`a-${q.id}`}
            className="min-h-12 flex-1 rounded-xl border-2 border-sand-300 px-4 py-3 focus:border-brand"
            placeholder={t(lang, "typeAnswer")}
            maxLength={500}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" variant="secondary" busy={busy === `${q.id}:${text.trim()}`} disabled={!text.trim()}>
            {t(lang, "save")}
          </Button>
        </form>
      )}
    </Card>
  );
}

export default function Questions({ c, lang, refresh }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const open = c.questions.filter((q) => q.status === "open");
  const done = c.questions.filter((q) => q.status === "answered");

  async function answer(q, value) {
    setBusy(`${q.id}:${value}`);
    setError(null);
    try {
      await api.answer(c.id, q.id, value);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function ask() {
    setBusy("generate");
    setError(null);
    try {
      await api.generateQuestions(c.id);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="fade-in">
      <PageTitle title={t(lang, "questionsTitle")} body={t(lang, "questionsBody")} />
      <ErrorNote lang={lang} error={error} />
      <div className="space-y-4">
        {open.map((q) => (
          <QuestionCard key={q.id} lang={lang} q={q} onAnswer={answer} busy={busy} />
        ))}
      </div>
      {open.length === 0 && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-ink-soft">{t(lang, "noQuestions")}</p>
          <Button variant="secondary" busy={busy === "generate"} onClick={ask}>
            {t(lang, "askMe")}
          </Button>
        </div>
      )}
      {done.length > 0 && (
        <section className="mt-8">
          <h2 className="font-serif text-xl">{t(lang, "answered")}</h2>
          <ul className="mt-3 space-y-2">
            {done.map((q) => (
              <li key={q.id} className="rounded-xl bg-sage-soft px-4 py-3">
                <span className="block text-ink-soft">{q.text}</span>
                <span className="font-semibold text-sage-ink">{q.answer}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <PrimaryBar>
        <Button onClick={() => go(`/case/${c.id}/plan`)}>{t(lang, "seePlan")}</Button>
      </PrimaryBar>
    </div>
  );
}
