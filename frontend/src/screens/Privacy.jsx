import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { go } from "../nav";
import { Button, Card, ErrorNote, PageTitle } from "../components/ui";

export default function Privacy({ c, lang }) {
  const [confirming, setConfirming] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function deleteEverything() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteCase(c.id);
      try {
        localStorage.removeItem("afterlife.case");
      } catch {}
      go("/deleted");
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  async function leave() {
    setBusy(true);
    setError(null);
    try {
      await api.leaveCase(c.id);
      try {
        localStorage.removeItem("afterlife.case");
      } catch {}
      go("/left");
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  return (
    <div className="fade-in">
      <PageTitle title={t(lang, "privacyTitle")} body={t(lang, "privacyBody")} />
      <Card>
        <ul className="list-disc space-y-3 pl-6">
          {t(lang, "privacyPoints").map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </Card>
      <ErrorNote lang={lang} error={error} />
      <Card className="mt-5">
        <h2 className="font-serif text-xl">{t(lang, "sharedComputerTitle")}</h2>
        <p className="mt-1 text-ink-soft">{t(lang, "sharedComputerBody")}</p>
        {!leaving ? (
          <Button variant="secondary" className="mt-4" onClick={() => setLeaving(true)}>
            {t(lang, "leaveCase")}
          </Button>
        ) : (
          <div role="alertdialog" aria-labelledby="leave-q" className="mt-4">
            <p id="leave-q" className="font-semibold">{t(lang, "leaveConfirm")}</p>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <Button busy={busy} onClick={leave} autoFocus>
                {t(lang, "leaveYes")}
              </Button>
              <Button variant="secondary" onClick={() => setLeaving(false)}>
                {t(lang, "cancel")}
              </Button>
            </div>
          </div>
        )}
      </Card>
      <Card className="mt-5 border-rose-ink/30">
        {!confirming ? (
          <Button variant="danger" onClick={() => setConfirming(true)}>
            {t(lang, "deleteData")}
          </Button>
        ) : (
          <div role="alertdialog" aria-labelledby="del-q">
            <p id="del-q" className="font-semibold text-rose-ink">{t(lang, "deleteConfirm")}</p>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <Button variant="danger" busy={busy} onClick={deleteEverything} autoFocus>
                {t(lang, "deleteYes")}
              </Button>
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                {t(lang, "cancel")}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
