import { useState } from "react";
import { api } from "../api";
import { inr, niceDate, t, typeLabel } from "../i18n";
import { go } from "../nav";
import { Badge, Button, Card, ErrorNote, PageTitle, PrimaryBar } from "../components/ui";

const BALANCE_TYPES = new Set(["savings_account", "mutual_fund", "demat_account", "epf", "ppf", "home_loan",
  "personal_loan", "vehicle_loan", "credit_card", "other_loan"]);
const LOAN_TYPES = new Set(["home_loan", "personal_loan", "vehicle_loan", "credit_card", "other_loan"]);

function Amount({ lang, item }) {
  if (item.amount === null || item.amount === undefined) return null;
  return (
    <p className="text-xl font-semibold tabular-nums">
      {inr(item.amount)}
      {item.amount_as_of && BALANCE_TYPES.has(item.type) && <span className="ml-2 text-[0.85rem] font-normal text-ink-soft">{t(lang, "asOf", { date: niceDate(item.amount_as_of, lang) })}</span>}
    </p>
  );
}

function ConfirmedCard({ lang, item }) {
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-semibold capitalize">{typeLabel(lang, item.type)}</h3>
        {item.identifier_masked && <span className="tabular-nums text-ink-soft">{item.identifier_masked}</span>}
      </div>
      <p className="text-ink-soft">{item.institution}</p>
      <Amount lang={lang} item={item} />
      {!LOAN_TYPES.has(item.type) && (
        <p className="text-[0.95rem]">
          {item.nominee ? `${t(lang, "nominee")}: ${item.nominee}` : <span className="text-ink-soft">{t(lang, "nomineeUnknown")}</span>}
        </p>
      )}
      {item.next_expected_debit && (
        <p className="text-[0.95rem] text-amber-ink">⏱ {t(lang, "nextDebit", { date: niceDate(item.next_expected_debit, lang) })}</p>
      )}
    </Card>
  );
}

function ProbableCard({ lang, item, onDecide, busy }) {
  const evidence = item.evidence.filter((e) => e.date);
  return (
    <article className="fade-in rounded-2xl border-2 border-amber-line bg-amber-soft p-5 sm:p-6" aria-label={t(lang, "probable")}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="amber">{t(lang, "probable")}</Badge>
        <Badge tone="neutral">{t(lang, `conf_${item.confidence}`)}</Badge>
      </div>
      <h3 className="mt-3 text-xl font-semibold">
        {t(lang, "probablyA", { type: typeLabel(lang, item.type), institution: item.institution })}
      </h3>
      {item.reason && <p className="mt-2">{item.reason}</p>}
      {evidence.length > 0 && (
        <div className="mt-4">
          <p className="font-semibold">{t(lang, "whatWeNoticed")}</p>
          <ul className="mt-2 space-y-2">
            {evidence.map((e, n) => (
              <li key={n} className="rounded-xl bg-white/80 px-4 py-2">
                <span className="flex flex-wrap justify-between gap-x-4">
                  <span className="tabular-nums">{niceDate(e.date, lang)}</span>
                  <span className="font-semibold tabular-nums">
                    {e.direction === "credit" ? "+ " : e.direction === "debit" ? "− " : ""}
                    {inr(e.amount)}
                  </span>
                </span>
                <span className="block break-words text-[0.9rem] text-ink-soft">{e.description}</span>
                <span className="block text-[0.8rem] text-ink-soft" data-no-read>{e.document_name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {item.next_expected_debit && (
        <p className="mt-3 text-amber-ink">⏱ {t(lang, "nextDebit", { date: niceDate(item.next_expected_debit, lang) })}</p>
      )}
      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <Button busy={busy === `${item.id}:confirmed`} onClick={() => onDecide(item.id, "confirmed")}>
          {t(lang, "yesConfirm")}
        </Button>
        <Button variant="secondary" busy={busy === `${item.id}:rejected`} onClick={() => onDecide(item.id, "rejected")}>
          {t(lang, "markNA")}
        </Button>
      </div>
    </article>
  );
}

export default function AssetMap({ c, lang, refresh, agentReply }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const map = c.asset_map;
  const probable = [...map.assets.probable, ...map.liabilities.probable];
  const rejected = [...map.assets.rejected, ...map.liabilities.rejected];
  const totals = map.totals;
  const nothing = !map.assets.confirmed.length && !probable.length && !map.liabilities.confirmed.length;

  async function decide(itemId, status) {
    setBusy(`${itemId}:${status}`);
    setError(null);
    try {
      await api.setItemStatus(c.id, itemId, status);
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="fade-in">
      <PageTitle title={t(lang, "mapTitle")} />

      {agentReply && (
        <Card className="mb-6 border-brand/30 bg-brand-soft/50">
          <p className="font-semibold text-brand-dark">{t(lang, "fromSaath")}</p>
          <p className="mt-2 whitespace-pre-line">{agentReply}</p>
        </Card>
      )}

      <ErrorNote lang={lang} error={error} />
      {nothing && <p className="text-ink-soft">{t(lang, "nothingFound")}</p>}

      {probable.length > 0 && (
        <section aria-labelledby="probable-h" className="mb-10">
          <h2 id="probable-h" className="font-serif text-2xl">{t(lang, "discoveryTitle", { n: probable.length })}</h2>
          <p className="mt-1 text-ink-soft">{t(lang, "discoveryBody")}</p>
          <div className="mt-4 space-y-4">
            {probable.map((item) => (
              <ProbableCard key={item.id} lang={lang} item={item} onDecide={decide} busy={busy} />
            ))}
          </div>
        </section>
      )}

      {!nothing && (
        <Card className="mb-8 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-ink-soft">{t(lang, "confirmedTotal")}</p>
            <p className="font-serif text-3xl tabular-nums text-sage-ink">{inr(totals.confirmed_assets_total)}</p>
            <p className="mt-1 text-[0.85rem] text-ink-soft">{t(lang, "probableNotCounted")}</p>
          </div>
          {totals.confirmed_liabilities_count > 0 && (
            <div>
              <p className="text-ink-soft">{t(lang, "owed")}</p>
              <p className="font-serif text-3xl tabular-nums">{inr(totals.confirmed_liabilities_total)}</p>
            </div>
          )}
        </Card>
      )}

      {map.assets.confirmed.length > 0 && (
        <section aria-labelledby="confirmed-h" className="mb-10">
          <h2 id="confirmed-h" className="mb-4 flex items-center gap-3 font-serif text-2xl">
            {t(lang, "confirmed")} <Badge tone="sage">{map.assets.confirmed.length}</Badge>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {map.assets.confirmed.map((item) => (
              <ConfirmedCard key={item.id} lang={lang} item={item} />
            ))}
          </div>
        </section>
      )}

      {map.liabilities.confirmed.length > 0 && (
        <section aria-labelledby="liab-h" className="mb-10">
          <h2 id="liab-h" className="mb-4 font-serif text-2xl">{t(lang, "liabilities")}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {map.liabilities.confirmed.map((item) => (
              <ConfirmedCard key={item.id} lang={lang} item={item} />
            ))}
          </div>
        </section>
      )}

      {rejected.length > 0 && (
        <details className="mb-6 rounded-2xl border border-sand-200 bg-white p-5">
          <summary className="cursor-pointer font-semibold">
            {t(lang, "notApplicable")} ({rejected.length})
          </summary>
          <ul className="mt-3 space-y-2">
            {rejected.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {typeLabel(lang, item.type)} · {item.institution}
                </span>
                <Button variant="quiet" busy={busy === `${item.id}:probable`} onClick={() => decide(item.id, "probable")}>
                  {t(lang, "undo")}
                </Button>
              </li>
            ))}
          </ul>
        </details>
      )}

      <PrimaryBar>
        <Button onClick={() => go(`/case/${c.id}/questions`)}>{t(lang, "nextQuestions")}</Button>
      </PrimaryBar>
    </div>
  );
}
