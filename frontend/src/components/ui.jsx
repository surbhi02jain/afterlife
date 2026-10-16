import { t } from "../i18n";

const VARIANTS = {
  primary: "bg-brand text-white hover:bg-brand-dark shadow-sm",
  secondary: "bg-white text-brand border-2 border-brand/30 hover:border-brand",
  quiet: "text-brand underline-offset-4 hover:underline px-2",
  danger: "bg-rose-ink text-white hover:brightness-110",
};

export function Button({ variant = "primary", className = "", busy = false, children, ...props }) {
  return (
    <button
      className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-xl px-5 py-3 text-base font-semibold
        transition disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
      disabled={busy || props.disabled}
      aria-busy={busy || undefined}
      {...props}
    >
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ label }) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <span className="h-5 w-5 animate-spin rounded-full border-[3px] border-current border-r-transparent motion-reduce:animate-none" />
      {label && <span>{label}</span>}
    </span>
  );
}

export function Card({ className = "", children, ...props }) {
  return (
    <div className={`rounded-2xl border border-sand-200 bg-white p-5 sm:p-6 ${className}`} {...props}>
      {children}
    </div>
  );
}

export function PageTitle({ title, body }) {
  return (
    <header className="mb-6">
      <h1 className="font-serif text-[1.75rem] leading-tight text-ink sm:text-[2rem]">{title}</h1>
      {body && <p className="mt-2 max-w-2xl text-ink-soft">{body}</p>}
    </header>
  );
}

export function Badge({ tone = "neutral", children }) {
  const tones = {
    neutral: "bg-sand-100 text-ink-soft",
    sage: "bg-sage-soft text-sage-ink",
    amber: "bg-amber-soft text-amber-ink border border-amber-line",
    rose: "bg-rose-soft text-rose-ink",
    brand: "bg-brand-soft text-brand-dark",
  };
  return <span className={`inline-block rounded-full px-3 py-0.5 text-[0.85rem] font-semibold ${tones[tone]}`}>{children}</span>;
}

export function ErrorNote({ lang, error, onRetry }) {
  if (!error) return null;
  return (
    <div role="alert" className="my-4 rounded-2xl border border-rose-ink/30 bg-rose-soft p-5 text-rose-ink">
      <p className="font-semibold">{t(lang, "errorTitle")}</p>
      <p className="mt-1">{t(lang, "errorBody")}</p>
      <p className="mt-2 text-[0.9rem] opacity-90">{String(error.message || error)}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-3" onClick={onRetry}>
          {t(lang, "tryAgain")}
        </Button>
      )}
    </div>
  );
}

export function PrimaryBar({ children }) {
  // One primary action per screen, always in the same place.
  return <div className="mt-8 flex flex-col gap-3 border-t border-sand-200 pt-6 sm:flex-row sm:items-center">{children}</div>;
}
