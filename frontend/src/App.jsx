import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { t } from "./i18n";
import ActivityPanel from "./components/ActivityPanel";
import ReadAloud from "./components/ReadAloud";
import { ErrorNote, Spinner } from "./components/ui";
import Start from "./screens/Start";
import Upload from "./screens/Upload";
import AssetMap from "./screens/AssetMap";
import Questions from "./screens/Questions";
import Plan from "./screens/Plan";
import Letters from "./screens/Letters";
import Board, { SharedBoard } from "./screens/Board";
import Privacy from "./screens/Privacy";
import { go, parseRoute } from "./nav";

const SCREENS = [
  ["upload", "nav_upload", Upload],
  ["map", "nav_map", AssetMap],
  ["questions", "nav_questions", Questions],
  ["plan", "nav_plan", Plan],
  ["letters", "nav_letters", Letters],
  ["board", "nav_board", Board],
  ["privacy", "nav_privacy", Privacy],
];

function useRoute() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return parseRoute(hash);
}

function storedLang() {
  try {
    return localStorage.getItem("afterlife.lang") === "hi" ? "hi" : "en";
  } catch {
    return "en";
  }
}

function Brand({ lang }) {
  return (
    <a href="#/" className="flex items-center gap-3 rounded-2xl">
      <img src="/favicon.svg" alt="" className="h-10 w-10" />
      <span>
        <span className="block font-serif text-xl leading-none text-brand-dark">{t(lang, "appName")}</span>
        <span className="hidden text-sm text-ink-soft sm:block">{t(lang, "tagline")}</span>
      </span>
    </a>
  );
}

function Header({ lang, onToggleLang, onActivity, children }) {
  return (
    <header className="border-b border-sand-200/60">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-2 px-4 py-3">
        <Brand lang={lang} />
        <div className="flex flex-wrap items-center gap-1">
          {onActivity && (
            <button onClick={onActivity} className="min-h-11 rounded-full px-3.5 py-2 text-base font-semibold text-brand hover:bg-brand-soft">
              <span aria-hidden="true">✦ </span>
              {t(lang, "activity")}
            </button>
          )}
          <ReadAloud lang={lang} />
          <button
            onClick={onToggleLang}
            aria-label={t(lang, "languageLabel")}
            className="min-h-11 rounded-full border-2 border-brand/30 px-4 py-1.5 text-base font-semibold text-brand hover:border-brand"
          >
            {t(lang, "language")}
          </button>
        </div>
      </div>
      {children}
    </header>
  );
}

function Footer({ lang, privacyHref }) {
  return (
    <footer className="mx-auto flex max-w-4xl flex-wrap justify-between gap-2 px-4 pb-10 pt-6 text-sm text-ink-soft">
      <span>{t(lang, "disclaimerShort")}</span>
      {privacyHref && (
        <a href={privacyHref} className="font-semibold text-brand underline-offset-4 hover:underline">
          {t(lang, "nav_privacy")}
        </a>
      )}
    </footer>
  );
}

function CaseShell({ id, screen, lang, setLang }) {
  const [c, setCase] = useState(null);
  const [error, setError] = useState(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [agentReply, setAgentReply] = useState(null);
  const [langSynced, setLangSynced] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await api.getCase(id);
      setCase(data);
      setError(null);
      return data;
    } catch (e) {
      if (e.status === 404) {
        try {
          localStorage.removeItem("afterlife.case");
        } catch {}
        go("/");
      } else setError(e);
    }
  }, [id]);

  useEffect(() => {
    refresh();
    try {
      localStorage.setItem("afterlife.case", id);
    } catch {}
  }, [id, refresh]);

  // On first load, follow the case's language.
  useEffect(() => {
    if (c && !langSynced) {
      setLang(c.language);
      setLangSynced(true);
    }
  }, [c, langSynced, setLang]);

  // While the agent is working, refresh so the activity list fills in live.
  useEffect(() => {
    if (!analysing) return;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [analysing, refresh]);

  async function toggleLang() {
    const next = lang === "en" ? "hi" : "en";
    setLang(next);
    try {
      await api.patchCase(id, { language: next }); // the server redoes the plan and unedited letters
      await refresh();
    } catch (e) {
      setError(e);
    }
  }

  const current = SCREENS.find(([key]) => key === screen) || SCREENS[0];
  const Screen = current[2];
  const openQuestions = c?.questions.filter((q) => q.status === "open").length || 0;

  return (
    <>
      <Header lang={lang} onToggleLang={toggleLang} onActivity={c ? () => setActivityOpen(true) : null}>
        <nav aria-label="Steps" className="mx-auto max-w-4xl">
          {/* The steps are a real sequence, so they are numbered; on phones the row scrolls instead of wrapping. */}
          <ol className="flex gap-1 overflow-x-auto px-2 pb-2 [scrollbar-width:none]">
            {SCREENS.filter(([key]) => key !== "privacy").map(([key, label], n) => (
              <li key={key} className="shrink-0">
                <a
                  href={`#/case/${id}/${key}`}
                  aria-current={key === current[0] ? "page" : undefined}
                  className={`inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-full px-3.5 py-2 text-base font-semibold
                    ${key === current[0] ? "bg-brand text-white" : "text-ink-soft hover:bg-sand-100"}`}
                >
                  <span
                    aria-hidden="true"
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-sm tabular-nums
                      ${key === current[0] ? "bg-white text-brand" : "border border-sand-300"}`}
                  >
                    {n + 1}
                  </span>
                  {t(lang, label)}
                  {key === "questions" && openQuestions > 0 && (
                    <span className="rounded-full bg-amber-soft px-2 text-sm text-amber-ink">{openQuestions}</span>
                  )}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </Header>
      {c?.is_demo && (
        <div className="bg-brand-soft px-4 py-2 text-center text-sm text-brand-dark">{t(lang, "sampleBanner")}</div>
      )}
      <main className="mx-auto max-w-4xl px-4 py-8">
        <ErrorNote lang={lang} error={error} onRetry={refresh} />
        {!c && !error && <Spinner label={t(lang, "loading")} />}
        {c && (
          <Screen
            c={c}
            lang={lang}
            refresh={refresh}
            setCase={setCase}
            analysing={analysing}
            setAnalysing={setAnalysing}
            agentReply={agentReply}
            setAgentReply={setAgentReply}
          />
        )}
      </main>
      <Footer lang={lang} privacyHref={`#/case/${id}/privacy`} />
      <ActivityPanel
        lang={lang}
        open={activityOpen}
        onClose={() => setActivityOpen(false)}
        summary={c?.activity_summary}
        entries={c?.activity}
      />
    </>
  );
}

export default function App() {
  const route = useRoute();
  const [lang, setLangState] = useState(storedLang);
  const setLang = useCallback((next) => {
    setLangState(next);
    try {
      localStorage.setItem("afterlife.lang", next);
    } catch {}
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = lang === "hi" ? "आफ्टरलाइफ़" : "Afterlife";
  }, [lang]);

  if (route.name === "case") return <CaseShell id={route.id} screen={route.screen} lang={lang} setLang={setLang} />;

  const toggle = () => setLang(lang === "en" ? "hi" : "en");
  return (
    <>
      <Header lang={lang} onToggleLang={toggle} />
      <main className="mx-auto max-w-4xl px-4 py-8">
        {route.name === "share" ? <SharedBoard token={route.token} lang={lang} /> : <Start lang={lang} />}
      </main>
      <Footer lang={lang} />
    </>
  );
}
