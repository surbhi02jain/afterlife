import { useState } from "react";
import { api } from "../api";
import { inr, niceDate, orgName, t, typeLabel } from "../i18n";
import { go } from "../nav";
import { Badge, Button, Card, ErrorNote, PageTitle, PrimaryBar, SectionTitle } from "../components/ui";
import { TypeIcon } from "../components/Art";

const BALANCE_TYPES = new Set(["savings_account", "mutual_fund", "demat_account", "epf", "ppf", "home_loan",
  "personal_loan", "vehicle_loan", "credit_card", "other_loan"]);
const LOAN_TYPES = new Set(["home_loan", "personal_loan", "vehicle_loan", "credit_card", "other_loan"]);

function Amount({ lang, item }) {
  if (item.amount === null || item.amount === undefined) return null;
  return (
    <p className="text-xl font-semibold tabular-nums">
      {inr(item.amount)}
      {item.amount_as_of && BALANCE_TYPES.has(item.type) && <span className="ml-2 text-sm font-normal text-ink-soft">{t(lang, "asOf", { date: niceDate(item.amount_as_of, lang) })}</span>}
    </p>
  );
}

function ConfirmedCard({ lang, item }) {
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <TypeIcon type={item.type} />
        <div className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-2">
          <h3 className="text-lg font-semibold capitalize">{typeLabel(lang, item.type)}</h3>
          {item.identifier_masked && <span className="tabular-nums text-ink-soft">{item.identifier_masked}</span>}
        </div>
      </div>
      <p className="text-ink-soft">{orgName(item.institution)}</p>
      <Amount lang={lang} item={item} />
      {!LOAN_TYPES.has(item.type) && (
        <p className="text-base">
          {item.nominee ? `${t(lang, "nominee")}: ${item.nominee}` : <span className="text-ink-soft">{t(lang, "nomineeUnknown")}</span>}
        </p>
      )}
      {item.next_expected_debit && (
        <p className="text-base text-amber-ink">⏱ {t(lang, "nextDebit", { date: niceDate(item.next_expected_debit, lang) })}</p>
      )}
    </Card>
  );
}

// A found item reads like a page from the family's own passbook: the clue transactions, each marked in marigold.
function ProbableCard({ lang, item, onDecide, busy }) {
  const evidence = item.evidence.filter((e) => e.date).sort((a, b) => a.date.localeCompare(b.date));
  return (
    <article className="fade-in rounded-3xl border border-amber-line bg-white p-5 shadow-soft sm:p-7" aria-label={t(lang, "probable")}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="amber">{t(lang, "probable")}</Badge>
        <Badge tone="neutral">{t(lang, `conf_${item.confidence}`)}</Badge>
      </div>
      <div className="mt-3 flex items-start gap-3">
        <TypeIcon type={item.type} found className="mt-1" />
        <h3 className="font-serif text-xl leading-snug">
          {t(lang, "probablyA", { type: typeLabel(lang, item.type), institution: orgName(item.institution) })}
        </h3>
      </div>
      {item.reason && <p className="mt-1 max-w-[60ch]">{item.reason}</p>}
      {evidence.length > 0 && (
        <div className="mt-5">
          <p className="text-base font-semibold text-ink-soft">{t(lang, "whatWeNoticed")}</p>
          <ol className="mt-2 border-t border-sand-200">
            {evidence.map((e, n) => (
              <li key={n} className="grid grid-cols-[auto_1fr] gap-x-4 border-b border-sand-200 py-3 pl-1">
                <span aria-hidden="true" className="ledger-mark row-span-2 w-1.5 rounded-full" style={{ "--row": n }} />
                <span className="flex flex-wrap justify-between gap-x-4">
                  <span className="tabular-nums text-ink-soft">{niceDate(e.date, lang)}</span>
                  <span className="font-semibold tabular-nums">
                    {e.direction === "credit" ? "+ " : e.direction === "debit" ? "− " : ""}
                    {inr(e.amount)}
                  </span>
                </span>
                <span className="col-start-2 break-words">
                  {e.description}
                  <span className="ml-2 text-sm text-ink-soft" data-no-read>{e.document_name}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {item.next_expected_debit && (
        <p className="mt-3 text-amber-ink">⏱ {t(lang, "nextDebit", { date: niceDate(item.next_expected_debit, lang) })}</p>
      )}
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
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

// Colour follows the kind of account, never its rank. Checked for colour-blind separation; the labelled legend
// is the secondary encoding. Marigold is kept out: it means "found, not confirmed".
const MIX_COLOURS = { savings_account: "#5B3F9E", mutual_fund: "#D2702A", epf: "#0F9468", fixed_deposit: "#3F7FD1",
  life_insurance: "#CC5A8A" };
const OTHER_COLOUR = "#8A8496";

function AssetMix({ lang, assets, totals, probableCount }) {
  const [active, setActive] = useState(null);
  const groups = {};
  for (const a of assets) {
    if (!a.amount) continue;
    const key = MIX_COLOURS[a.type] ? a.type : "other";
    groups[key] = (groups[key] || 0) + a.amount;
  }
  const total = Object.values(groups).reduce((s, v) => s + v, 0);
  const rows = Object.entries(groups).sort((a, b) => b[1] - a[1]);
  if (!total) return null;
  const label = (key) => (key === "other" ? t(lang, "otherAssets") : typeLabel(lang, key));
  const pct = (v) => `${Math.round((v / total) * 100)}%`;

  return (
    <Card className="mb-10">
      <p className="font-semibold text-ink-soft">{t(lang, "confirmedSoFar", { n: totals.confirmed_assets_count })}</p>
      <p className="mt-1 font-serif text-[2.6rem] leading-none tabular-nums text-ink">{inr(totals.confirmed_assets_total)}</p>
      <div className="mt-5 flex h-4 gap-[2px] overflow-hidden rounded-full" role="img"
           aria-label={rows.map(([k, v]) => `${label(k)} ${pct(v)}`).join(", ")}>
        {rows.map(([key, value]) => (
          <span key={key} onMouseEnter={() => setActive(key)} onMouseLeave={() => setActive(null)}
                className="h-full transition-opacity first:rounded-l-full last:rounded-r-full"
                style={{ flexGrow: value, background: MIX_COLOURS[key] || OTHER_COLOUR,
                         opacity: active && active !== key ? 0.35 : 1 }} />
        ))}
      </div>
      <ul className="mt-4 grid gap-x-8 gap-y-1 sm:grid-cols-2">
        {rows.map(([key, value]) => (
          <li key={key} onMouseEnter={() => setActive(key)} onMouseLeave={() => setActive(null)}
              className={`flex items-center gap-3 rounded-full px-3 py-1.5 ${active === key ? "bg-sand-100" : ""}`}>
            <span aria-hidden="true" className="h-3 w-3 shrink-0 rounded-full" style={{ background: MIX_COLOURS[key] || OTHER_COLOUR }} />
            <span className="flex-1 capitalize">{label(key)}</span>
            <span className="tabular-nums text-ink-soft">{pct(value)}</span>
            <span className="w-32 text-right font-semibold tabular-nums">{inr(value)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-sm text-ink-soft">
        {[totals.confirmed_liabilities_count > 0 && t(lang, "mapSummaryLoans", { total: inr(totals.confirmed_liabilities_total) }),
          probableCount > 0 && t(lang, "probableNotCounted")].filter(Boolean).join(" ")}
      </p>
    </Card>
  );
}

// Money that left an account after the death: the one thing on this page that needs action today.
function AfterDeathAlert({ lang, name, moved }) {
  if (!moved.length) return null;
  return (
    <section role="alert" className="mb-10 rounded-3xl border border-rose-ink/30 bg-rose-soft p-5 text-rose-ink sm:p-6">
      <h2 className="font-serif text-xl leading-snug">{t(lang, "afterDeathTitle", { name })}</h2>
      <p className="mt-1">{t(lang, "afterDeathBody")}</p>
      <p className="mt-3 font-semibold">
        {t(lang, "afterDeathTotal", { n: moved.length, total: inr(moved.reduce((s, f) => s + f.amount, 0)) })}
      </p>
      <ol className="mt-3 border-t border-rose-ink/20">
        {moved.slice(0, 4).map((f, n) => (
          <li key={n} className="flex flex-wrap justify-between gap-x-4 border-b border-rose-ink/20 py-2.5">
            <span className="min-w-0">
              <span className="tabular-nums">{niceDate(f.date, lang)}</span>
              <span className="block break-words text-sm">{f.description}</span>
              <span className="block text-sm opacity-80" data-no-read>{f.document_name}</span>
            </span>
            <span className="font-semibold tabular-nums">− {inr(f.amount)}</span>
          </li>
        ))}
      </ol>
      {moved.length > 4 && (
        <details className="mt-2">
          <summary className="cursor-pointer py-1 font-semibold">{t(lang, "afterDeathMore", { n: moved.length - 4 })}</summary>
          <ol className="border-t border-rose-ink/20">
            {moved.slice(4).map((f, n) => (
              <li key={n} className="flex flex-wrap justify-between gap-x-4 border-b border-rose-ink/20 py-2.5">
                <span className="min-w-0">
                  <span className="tabular-nums">{niceDate(f.date, lang)}</span>
                  <span className="block break-words text-sm">{f.description}</span>
                </span>
                <span className="font-semibold tabular-nums">− {inr(f.amount)}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
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
      <PageTitle title={t(lang, "mapTitle")} body={t(lang, "mapBody")} />

      <AfterDeathAlert lang={lang} name={c.deceased_name} moved={map.after_death || []} />

      <AssetMix lang={lang} assets={map.assets.confirmed} totals={totals} probableCount={probable.length} />

      {agentReply && (
        <Card className="mb-6 border-brand/30 bg-brand-soft/50">
          <p className="font-semibold text-brand-dark">{t(lang, "fromVirasat")}</p>
          <p className="mt-2 whitespace-pre-line">{agentReply}</p>
        </Card>
      )}

      <ErrorNote lang={lang} error={error} />
      {nothing && <p className="text-ink-soft">{t(lang, "nothingFound")}</p>}

      {probable.length > 0 && (
        <section aria-labelledby="probable-h" className="mb-10">
          <h2 id="probable-h" className="font-serif text-2xl leading-tight text-amber-ink">
            {t(lang, "discoveryTitle", { n: probable.length })}
          </h2>
          <p className="mt-1 text-ink-soft">{t(lang, "discoveryBody")}</p>
          <div className="mt-5 space-y-5">
            {probable.map((item) => (
              <ProbableCard key={item.id} lang={lang} item={item} onDecide={decide} busy={busy} />
            ))}
          </div>
        </section>
      )}

      {map.assets.confirmed.length > 0 && (
        <section aria-labelledby="confirmed-h" className="mb-10">
          <h2 id="confirmed-h" className="mb-5 flex items-center gap-3 font-serif text-2xl leading-tight">
            {t(lang, "confirmed")} <Badge tone="sage">{map.assets.confirmed.length}</Badge>
          </h2>
          <div className="grid gap-5 sm:grid-cols-2">
            {map.assets.confirmed.map((item) => (
              <ConfirmedCard key={item.id} lang={lang} item={item} />
            ))}
          </div>
        </section>
      )}

      {map.liabilities.confirmed.length > 0 && (
        <section aria-labelledby="liab-h" className="mb-10">
          <SectionTitle id="liab-h" className="mb-5">{t(lang, "liabilities")}</SectionTitle>
          <div className="grid gap-5 sm:grid-cols-2">
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
                  {typeLabel(lang, item.type)}, {orgName(item.institution)}
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
