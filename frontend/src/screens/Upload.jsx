import { useRef, useState } from "react";
import { api } from "../api";
import { docTypeLabel, orgName, t } from "../i18n";
import { go } from "../nav";
import { ActivityList, ActivitySummary } from "../components/ActivityPanel";
import { PapersArt, TypeIcon } from "../components/Art";
import FilePreview from "../components/FilePreview";
import MemoryCard from "../components/MemoryCard";
import { Badge, Button, Card, ErrorNote, PageTitle, PrimaryBar, Spinner, field } from "../components/ui";

const READ_AT_ONCE = 2;
const MAX_FILES = 20; // same cap as the server, which now sees one file per request

function StatusChip({ lang, doc, reading }) {
  if (reading) return <Spinner label={t(lang, "st_extracting")} />;
  if (doc.status === "extracted")
    return (
      <span className="text-sage-ink">
        <span aria-hidden="true">✓ </span>
        {t(lang, "st_extracted")}: {docTypeLabel(lang, doc.document_type)}
        {doc.institution ? `, ${orgName(doc.institution)}` : ""}
        {doc.saved_reading && <span className="ml-2 text-sm text-ink-soft">({t(lang, "savedReading")})</span>}
      </span>
    );
  if (doc.status === "failed") return <span className="text-rose-ink">{t(lang, "st_failed")}</span>;
  if (doc.status === "locked")
    return (
      <span className="font-semibold text-brand-dark">
        <span aria-hidden="true">🔒 </span>
        {t(lang, "st_locked")}
      </span>
    );
  return <span className="text-ink-soft">{t(lang, "st_uploaded")}</span>;
}

// The password goes to the server once, to open this file; it is never kept in the app or on the server.
function UnlockForm({ lang, caseId, doc, isDemo, onUnlocked }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    if (!password) return;
    setBusy(true);
    setError(null);
    try {
      await api.unlock(caseId, doc.id, password);
      setPassword("");
      onUnlocked(doc.id);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-2 flex flex-col gap-2 sm:basis-full" data-no-read>
      <p className="text-sm text-ink-soft">{t(lang, "unlockHint")}</p>
      {isDemo && <p className="text-sm font-semibold text-brand-dark">{t(lang, "demoPassword")}</p>}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="block flex-1 font-semibold">
          {t(lang, "pdfPassword")}
          <input
            type="password"
            autoComplete="off"
            maxLength={200}
            className={`mt-2 ${field}`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <Button variant="secondary" type="submit" busy={busy} disabled={!password}>
          {t(lang, "unlock")}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-rose-ink">
          {String(error.message || error)}
        </p>
      )}
    </form>
  );
}

export default function Upload({ c, lang, refresh, setCase, analysing, setAnalysing, setAgentReply }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [queue, setQueue] = useState([]); // files on their way up: { key, name, type, url (local preview), sent }
  const [reading, setReading] = useState(new Set());
  const [removing, setRemoving] = useState(null); // { id, busy } while asking "remove this file?"
  const [error, setError] = useState(null);

  const locked = c.documents.filter((d) => d.status === "locked");
  const pending = c.documents.filter((d) => d.status !== "extracted" && d.status !== "locked");
  const allRead = c.documents.length > 0 && pending.length === 0 && locked.length === 0;
  // Analysed = the hidden-asset search ran after the documents or memories last changed.
  const lastChange = c.activity.findLastIndex(
    (a) => a.tool === "remove_document" || (["extract_document", "add_memory"].includes(a.tool) && a.ok),
  );
  const analysed = c.activity.findLastIndex((a) => a.tool === "infer_hidden_assets" && a.ok) > lastChange;

  async function removeDocument(id) {
    setRemoving({ id, busy: true });
    setError(null);
    try {
      setCase(await api.removeDocument(c.id, id));
      setRemoving(null);
    } catch (e) {
      setError(e);
      setRemoving({ id, busy: false });
    }
  }

  async function readDocuments(ids) {
    const queue = [...ids];
    const worker = async () => {
      while (queue.length) {
        const id = queue.shift();
        setReading((s) => new Set(s).add(id));
        try {
          await api.extract(c.id, id);
        } catch {
          // the failure is recorded on the document and shown with a retry button
        }
        setReading((s) => {
          const next = new Set(s);
          next.delete(id);
          return next;
        });
        await refresh();
      }
    };
    await Promise.all(Array.from({ length: READ_AT_ONCE }, worker));
  }

  async function addFiles(fileList) {
    // Copy now: the browser empties a FileList once the input is reset or the drop event ends.
    const files = [...(fileList || [])];
    if (!files.length) return;
    setError(null);
    if (files.length > MAX_FILES) return setError(new Error(t(lang, "tooManyFiles", { n: MAX_FILES })));
    setUploading(true);
    const queued = files.map((f) => ({ key: `${Date.now()}-${Math.random()}`, name: f.name, type: f.type,
                                       url: URL.createObjectURL(f), sent: false }));
    setQueue((q) => [...q, ...queued]);
    const settle = (key, sent) => setQueue((q) => (sent ? q.map((x) => (x.key === key ? { ...x, sent } : x))
                                                        : q.filter((x) => x.key !== key)));
    // One file per request: Cloud Run refuses any request over 32 MiB, and a few phone photos together pass that.
    const docs = [];
    for (const [n, file] of files.entries()) {
      try {
        docs.push(...(await api.upload(c.id, [file])));
        settle(queued[n].key, true);
      } catch (e) {
        settle(queued[n].key, false);
        setError(e); // the server names the file; the other files still upload
      }
    }
    setUploading(false);
    await refresh(); // the uploaded files now come from the case, with the server's copy as their preview
    const done = new Set(queued.map((x) => x.key));
    setQueue((q) => q.filter((x) => !done.has(x.key)));
    queued.forEach((x) => URL.revokeObjectURL(x.url));
    readDocuments(docs.filter((d) => d.status !== "locked").map((d) => d.id)); // locked PDFs wait for a password
  }

  async function analyse() {
    setAnalysing(true);
    setError(null);
    try {
      const result = await api.analyse(c.id);
      setCase(result.case);
      setAgentReply(result.reply);
      go(`/case/${c.id}/map`);
    } catch (e) {
      setError(e);
      refresh();
    } finally {
      setAnalysing(false);
    }
  }

  const busyReading = reading.size > 0;

  return (
    <div className="fade-in">
      <PageTitle title={t(lang, "uploadTitle")} body={t(lang, "uploadBody")} />

      {!analysing && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
          className={`rounded-2xl border-[3px] border-dashed p-8 text-center transition
            ${dragging ? "border-brand bg-brand-soft" : "border-sand-300 bg-white"}`}
        >
          <PapersArt className="mx-auto mb-3 h-16 w-auto" />
          <p className="text-lg font-semibold">{t(lang, "dropHere")}</p>
          <p className="mt-1 text-ink-soft text-sm">{t(lang, "fileTypes")}</p>
          <input
            ref={input}
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp,image/heic,application/pdf"
            className="sr-only"
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <Button variant="secondary" className="mt-4" busy={uploading} onClick={() => input.current?.click()}>
            {t(lang, "chooseFiles")}
          </Button>
        </div>
      )}

      {/* Open until the first upload, then tucked away; the family can still open it. */}
      <details open={c.documents.length === 0} className="mt-5 rounded-2xl border border-sand-200 bg-white px-5 py-4">
        <summary className="cursor-pointer font-semibold text-brand">{t(lang, "guideTitle")}</summary>
        <p className="mt-3 text-ink-soft">{t(lang, "guideIntro")}</p>
        <ul className="mt-4 space-y-4">
          {t(lang, "guideItems").map((g) => (
            <li key={g.icon} className="flex gap-3">
              <TypeIcon type={g.icon} />
              <div className="min-w-0">
                <p className="font-semibold">{g.what}</p>
                <p>{g.where}</p>
                {g.missing && <p className="mt-1 text-sm text-ink-soft">{g.missing}</p>}
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-4 rounded-2xl bg-brand-soft px-4 py-3 text-sm text-brand-dark">{t(lang, "guideSafety")}</p>
      </details>

      <ErrorNote lang={lang} error={error} />

      {(c.documents.length > 0 || queue.length > 0) && (
        <ul className="mt-5 divide-y divide-sand-200 rounded-2xl border border-sand-200 bg-white" aria-live="polite">
          {c.documents.map((d) => (
            <li key={d.id} className="flex gap-4 px-5 py-4">
              <FilePreview lang={lang} url={api.documentFileUrl(c.id, d.id)} thumb={`${api.documentFileUrl(c.id, d.id)}?thumb=1`}
                           name={d.filename} type={d.content_type} />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="break-all font-semibold">{d.filename}</span>
                <span className="flex flex-wrap items-center gap-3">
                  <StatusChip lang={lang} doc={d} reading={reading.has(d.id)} />
                  {d.status === "failed" && !reading.has(d.id) && (
                    <Button variant="quiet" onClick={() => readDocuments([d.id])}>
                      {t(lang, "retry")}
                    </Button>
                  )}
                  {!reading.has(d.id) && !analysing && removing?.id !== d.id && (
                    <Button variant="quiet" onClick={() => setRemoving({ id: d.id, busy: false })}>
                      {t(lang, "removeDoc")}
                    </Button>
                  )}
                </span>
                {d.other_holder && (
                  <span className="text-sm text-rose-ink">
                    {t(lang, "otherHolder", { holder: d.other_holder, name: c.deceased_name })}
                  </span>
                )}
                {d.status === "locked" && !analysing && removing?.id !== d.id && (
                  <UnlockForm
                    lang={lang}
                    caseId={c.id}
                    doc={d}
                    isDemo={c.is_demo}
                    onUnlocked={async (id) => {
                      await refresh();
                      readDocuments([id]);
                    }}
                  />
                )}
                {d.status === "failed" && d.error && (
                  <span className="text-sm text-rose-ink sm:basis-full" data-no-read>
                    {d.error.slice(0, 220)}
                  </span>
                )}
                {removing?.id === d.id && (
                  <span role="alertdialog" aria-label={t(lang, "removeDocConfirm")}
                        className="flex flex-col gap-2 sm:basis-full sm:flex-row sm:items-center" data-no-read>
                    <span>{t(lang, "removeDocConfirm")}</span>
                    <Button variant="danger" busy={removing.busy} onClick={() => removeDocument(d.id)} autoFocus>
                      {t(lang, "removeYes")}
                    </Button>
                    <Button variant="secondary" onClick={() => setRemoving(null)}>
                      {t(lang, "cancel")}
                    </Button>
                  </span>
                )}
              </div>
            </li>
          ))}
          {queue.map((f) => (
            <li key={f.key} className="flex gap-4 px-5 py-4">
              <FilePreview lang={lang} url={f.url} name={f.name} type={f.type} />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="break-all font-semibold">{f.name}</span>
                {f.sent ? <span className="text-ink-soft">{t(lang, "st_uploaded")}</span>
                        : <Spinner label={t(lang, "st_uploading")} />}
              </div>
            </li>
          ))}
        </ul>
      )}

      {!analysing && <MemoryCard c={c} lang={lang} refresh={refresh} />}

      {analysing && (
        <Card className="fade-in mt-6 border-brand/30 bg-brand-soft/50">
          <Spinner label={<span className="text-lg font-semibold">{t(lang, "analysing")}</span>} />
          <p className="mt-2 text-ink-soft">{t(lang, "analysingBody")}</p>
          <div className="mt-4">
            <ActivitySummary lang={lang} summary={c.activity_summary} />
          </div>
          <div className="mt-4">
            <ActivityList lang={lang} entries={c.activity} limit={6} />
          </div>
        </Card>
      )}

      <PrimaryBar>
        {c.documents.length === 0 ? (
          <p className="text-ink-soft">{t(lang, "noDocsYet")}</p>
        ) : pending.length === 0 && locked.length > 0 ? (
          <p className="text-ink-soft">{t(lang, "unlockFirst")}</p>
        ) : !allRead ? (
          <Button busy={busyReading} onClick={() => readDocuments(pending.map((d) => d.id))}>
            {busyReading ? t(lang, "reading") : t(lang, "readDocs", { n: pending.length })}
          </Button>
        ) : !analysed ? (
          <Button busy={analysing} onClick={analyse}>
            {analysing ? t(lang, "analysing") : t(lang, "analyse")}
          </Button>
        ) : (
          <Button onClick={() => go(`/case/${c.id}/map`)}>{t(lang, "seeFound")}</Button>
        )}
        {analysed && allRead && !analysing && (
          <Badge tone="sage">{c.activity_summary.map((l) => l[lang] || l.en).slice(0, 2).join(", ")}</Badge>
        )}
      </PrimaryBar>
    </div>
  );
}
