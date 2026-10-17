import { useEffect, useState } from "react";
import { t } from "../i18n";

// Reads the current screen's main content with the browser's speech synthesis.
// Buttons and form controls are skipped so it reads like a page, not a menu.
function screenText() {
  const main = document.querySelector("main");
  if (!main) return "";
  const copy = main.cloneNode(true);
  copy.querySelectorAll("button, input, select, textarea, [data-no-read], [aria-hidden='true']").forEach((n) => n.remove());
  return copy.innerText.replace(/\s+\n/g, "\n").trim();
}

export default function ReadAloud({ lang }) {
  const [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => () => supported && window.speechSynthesis.cancel(), [supported]);
  useEffect(() => {
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [lang, supported]);

  if (!supported) return null;

  function toggle() {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(screenText());
    utterance.lang = lang === "hi" ? "hi-IN" : "en-IN";
    const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang === "hi" ? "hi" : "en-in"));
    if (voice) utterance.voice = voice;
    utterance.rate = 0.92;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    synth.cancel();
    synth.speak(utterance);
    setSpeaking(true);
  }

  return (
    <button
      onClick={toggle}
      aria-pressed={speaking}
      className="min-h-11 rounded-full px-3.5 py-2 text-base font-semibold text-brand hover:bg-brand-soft"
    >
      <span aria-hidden="true">{speaking ? "■ " : "🔈 "}</span>
      {speaking ? t(lang, "stopReading") : t(lang, "readAloud")}
    </button>
  );
}
