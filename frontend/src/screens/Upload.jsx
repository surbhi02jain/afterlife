import { useRef, useState } from "react";
import { api } from "../api";
import { docTypeLabel, t } from "../i18n";
import { go } from "../nav";
import { ActivityList, ActivitySummary } from "../components/ActivityPanel";
import { Badge, Button, Card, ErrorNote, PageTitle, PrimaryBar, Spinner } from "../components/ui";

const READ_AT_ONCE = 2;

function StatusChip({ lang, doc, reading }) {
  if (reading) return <Spinner label={t(lang, "st_extracting")} />;
  if (doc.status === "extracted")
    return (
      <span className="text-sage-ink">
        <span aria-hidden="true">✓ </span>
        {t(lang, "st_extracted")}: {docTypeLabel(lang, doc.document_type)}
        {doc.institution ? ` · ${doc.institution}` : ""}
        {doc.saved_reading && <span className="ml-2 text-[0.85rem] text-ink-soft">({t(lang, "savedReading")})</span>}
      </span>
    );
  if (doc.status === "failed") return <span className="text-rose-ink">{t(lang, "st_failed")}</span>;
  return <span className="text-ink-soft">{t(lang, "st_uploaded")}</span>;
}

export default function Upload({ c, lang, refresh, setCase, analysing, setAnalysing, setAgentReply }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reading, setReading] = useState(new Set());
  const [error, setError] = useState(null);

  const pending = c.documents.filter((d) => d.status !== "extracted");
  const allRead = c.documents.length > 0 && pending.length === 0;
  const analysed = c.activity.some((a) => a.tool === "infer_hidden_assets" && a.ok);

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

  async function addFiles(files) {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    try {
      const docs = await api.upload(c.id, files);
      await refresh();
      readDocuments(docs.map((d) => d.id));
    } catch (e) {
      setError(e);
    } finally {
      setUploading(false);
    }
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
          <p className="text-lg font-semibold">{t(lang, "dropHere")}</p>
          <p className="mt-1 text-ink-soft text-[0.9rem]">{t(lang, "fileTypes")}</p>
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

      <ErrorNote lang={lang} error={error} />

      {c.documents.length > 0 && (
        <ul className="mt-6 divide-y divide-sand-200 rounded-2xl border border-sand-200 bg-white" aria-live="polite">
          {c.documents.map((d) => (
            <li key={d.id} className="flex flex-col gap-1 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <span className="break-all font-semibold">{d.filename}</span>
              <span className="flex flex-wrap items-center gap-3">
                <StatusChip lang={lang} doc={d} reading={reading.has(d.id)} />
                {d.status === "failed" && !reading.has(d.id) && (
                  <Button variant="quiet" onClick={() => readDocuments([d.id])}>
                    {t(lang, "retry")}
                  </Button>
                )}
              </span>
              {d.status === "failed" && d.error && (
                <span className="text-[0.85rem] text-rose-ink sm:basis-full" data-no-read>
                  {d.error.slice(0, 220)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

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
          <Badge tone="sage">{c.activity_summary.map((l) => l[lang] || l.en).slice(0, 2).join(" · ")}</Badge>
        )}
      </PrimaryBar>
    </div>
  );
}
