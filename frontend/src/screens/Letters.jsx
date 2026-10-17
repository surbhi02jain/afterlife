import { useEffect, useState } from "react";
import { api } from "../api";
import { orgName, t, typeLabel } from "../i18n";
import { Button, ErrorNote, PageTitle, PrimaryBar, field } from "../components/ui";

function selectedFromHash() {
  const match = window.location.hash.match(/[?&]l=([a-f0-9]+)/);
  return match ? match[1] : null;
}

export default function Letters({ c, lang, refresh }) {
  const [selected, setSelected] = useState(selectedFromHash() || c.letters[0]?.id || null);
  const letter = c.letters.find((l) => l.id === selected) || c.letters[0];
  const [draft, setDraft] = useState({ title: "", body: "" });
  const [busy, setBusy] = useState(null);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (letter) setDraft({ title: letter.title, body: letter.body });
    setSavedAt(null);
  }, [letter?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = letter && (draft.body !== letter.body || draft.title !== letter.title);
  const itemsWithoutLetter = [...c.asset_map.assets.confirmed, ...c.asset_map.assets.probable, ...c.asset_map.liabilities.confirmed,
    ...c.asset_map.liabilities.probable].filter((i) => !c.letters.some((l) => l.item_id === i.id));

  async function save() {
    setBusy("save");
    setError(null);
    try {
      await api.editLetter(c.id, letter.id, draft.title, draft.body);
      await refresh();
      setSavedAt(Date.now());
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function download() {
    if (dirty) await save();
    window.location.href = api.letterPdfUrl(c.id, letter.id);
  }

  async function makeFor(itemId) {
    if (!itemId) return;
    setBusy("make");
    setError(null);
    try {
      const made = await api.createLetter(c.id, itemId);
      await refresh();
      setSelected(made.id);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="fade-in">
      <PageTitle title={t(lang, "lettersTitle")} body={t(lang, "lettersBody")} />
      <ErrorNote lang={lang} error={error} />

      {c.letters.length === 0 && <p className="text-ink-soft">{t(lang, "noLetters")}</p>}

      {c.letters.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label={t(lang, "letterFor")}>
          {c.letters.map((l) => (
            <button
              key={l.id}
              role="tab"
              aria-selected={l.id === letter?.id}
              onClick={() => setSelected(l.id)}
              className={`min-h-11 rounded-full px-4 py-2 text-base font-semibold
                ${l.id === letter?.id ? "bg-brand text-white" : "bg-white text-ink-soft border border-sand-200 hover:border-brand"}`}
            >
              {l.title.replace(l.institution, orgName(l.institution))}
            </button>
          ))}
        </div>
      )}

      {itemsWithoutLetter.length > 0 && (
        <label className="mb-6 block max-w-md">
          <span className="font-semibold">{t(lang, "makeLetterFor")}</span>
          <select
            className={`mt-2 ${field}`}
            value=""
            disabled={busy === "make"}
            onChange={(e) => makeFor(e.target.value)}
          >
            <option value="">{t(lang, "chooseOne")}</option>
            {itemsWithoutLetter.map((i) => (
              <option key={i.id} value={i.id}>
                {orgName(i.institution)} ({typeLabel(lang, i.type)})
              </option>
            ))}
          </select>
        </label>
      )}

      {letter && (
        <div className="space-y-3">
          <label className="block">
            <span className="sr-only">Title</span>
            <input
              className={`${field} font-semibold`}
              value={draft.title}
              maxLength={200}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="sr-only">{letter.title}</span>
            <textarea
              className="min-h-[60vh] w-full rounded-2xl border-2 border-sand-300 bg-white p-5 font-serif text-base leading-relaxed"
              value={draft.body}
              onChange={(e) => setDraft({ ...draft, body: e.target.value })}
              spellCheck
            />
          </label>
          <PrimaryBar>
            <Button busy={busy === "save"} onClick={download}>
              {t(lang, "downloadPdf")}
            </Button>
            <Button variant="secondary" disabled={!dirty} busy={busy === "save"} onClick={save}>
              {t(lang, "saveChanges")}
            </Button>
            {savedAt && !dirty && <span role="status" className="text-sage-ink">✓ {t(lang, "saved")}</span>}
          </PrimaryBar>
        </div>
      )}
    </div>
  );
}
