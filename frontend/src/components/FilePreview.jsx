import { useState } from "react";
import { t } from "../i18n";

// A small preview of a file the family sent; opens full size in a new tab. Photos show as a thumbnail; PDFs, and
// photos the browser can't draw (HEIC in Chrome), show their file type instead.
export default function FilePreview({ lang, url, name, type, size = "h-20 w-16" }) {
  const [broken, setBroken] = useState(false);
  const image = type ? type.startsWith("image/") : /\.(png|jpe?g|webp|heic|heif)$/i.test(name);
  const ext = (name.split(".").pop() || "").toUpperCase().slice(0, 4);
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title={t(lang, "openFile", { name })}
      aria-label={t(lang, "openFile", { name })}
      className={`${size} block shrink-0 overflow-hidden rounded-lg border border-sand-200 bg-sand-50
        transition hover:border-brand focus-visible:border-brand`}
      data-no-read
    >
      {image && !broken ? (
        <img src={url} alt="" loading="lazy" onError={() => setBroken(true)} className="h-full w-full object-cover object-top" />
      ) : (
        <span className="grid h-full w-full place-items-center text-xs font-semibold text-brand-dark">{ext || "FILE"}</span>
      )}
    </a>
  );
}
