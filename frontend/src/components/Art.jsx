// Afterlife's drawings: simple geometric line art in the logo's style (violet lines, marigold accents).
// All decorative, so hidden from screen readers; the text next to them carries the meaning.

const ICONS = {
  // bank building
  savings_account: (
    <>
      <path d="M3 9.5 12 4l9 5.5" />
      <path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18" />
    </>
  ),
  // deposit locked away: a safe with a dial
  fixed_deposit: (
    <>
      <rect x="4" y="5" width="16" height="14" rx="2" />
      <circle cx="12" cy="12" r="3" />
      <path d="M12 9v1.5" />
    </>
  ),
  // umbrella: cover for the family
  life_insurance: (
    <>
      <path d="M3 12a9 9 0 0 1 18 0Z" />
      <path d="M12 12v6a2 2 0 0 1-4 0" />
    </>
  ),
  // pie: a share in a fund
  mutual_fund: (
    <>
      <path d="M12 4a8 8 0 1 0 8 8h-8Z" />
      <path d="M15 3.5A7 7 0 0 1 20.5 9H15Z" />
    </>
  ),
  // shares: a rising line
  demat_account: (
    <>
      <path d="M4 19h16" />
      <path d="m5 15 4-4 3 3 6-7" />
      <path d="M14 7h4v4" />
    </>
  ),
  // provident fund: a briefcase from work
  epf: (
    <>
      <rect x="3.5" y="8" width="17" height="11" rx="2" />
      <path d="M9 8V6a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 6v2M3.5 13h17" />
    </>
  ),
  // savings scheme: a stack of coins
  ppf: (
    <>
      <ellipse cx="12" cy="7" rx="6" ry="2.5" />
      <path d="M6 7v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V7M6 12v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5" />
    </>
  ),
  home_loan: (
    <>
      <path d="M4 11 12 4l8 7" />
      <path d="M6 10v9h12v-9M10 19v-5h4v5" />
    </>
  ),
  vehicle_loan: (
    <>
      <path d="M4 15v-3l2-5h12l2 5v3Z" />
      <circle cx="8" cy="17" r="1.8" />
      <circle cx="16" cy="17" r="1.8" />
    </>
  ),
  credit_card: (
    <>
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <path d="M3 10h18M7 15h3" />
    </>
  ),
};
// anything else: a folded document
const DOCUMENT = (
  <>
    <path d="M6 3h8l4 4v14H6Z" />
    <path d="M14 3v4h4M9 12h6M9 16h6" />
  </>
);

// Each kind of account gets its own soft tile, so a long list scans at a glance. Marigold stays for found items.
const VIOLET = "bg-brand-soft text-brand", ORANGE = "bg-[#fcebdf] text-[#a65516]", GREEN = "bg-[#e3f3ec] text-[#1f7a58]";
const BLUE = "bg-[#e6eefb] text-[#2f5fa8]", PINK = "bg-[#f8e8ef] text-[#a8416c]", SLATE = "bg-[#eceaf1] text-[#4f4a63]";
// Same hues as the asset chart on "What we found", so a colour means the same kind of account everywhere.
const TONES = {
  savings_account: VIOLET, mutual_fund: ORANGE, epf: GREEN, fixed_deposit: BLUE, life_insurance: PINK,
  demat_account: SLATE, ppf: SLATE,
  home_loan: SLATE, personal_loan: SLATE, vehicle_loan: SLATE, credit_card: SLATE, other_loan: SLATE,
};

export function TypeIcon({ type, found = false, className = "" }) {
  const tone = found ? "bg-amber-soft text-amber-ink" : TONES[type] || "bg-brand-soft text-brand";
  return (
    <span aria-hidden="true" className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${tone} ${className}`}>
      <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        {ICONS[type] || DOCUMENT}
      </svg>
    </span>
  );
}

function Sprig({ x, y, flip = false }) {
  // a thin stem with three soft leaves
  return (
    <g transform={`translate(${x} ${y}) scale(${flip ? -1 : 1} 1)`} fill="#A9CDB4">
      <path d="M0 0C2-14 4-26 10-38" fill="none" stroke="#8DB89B" strokeWidth="1.6" strokeLinecap="round" />
      <ellipse cx="9" cy="-36" rx="4" ry="9" transform="rotate(25 9 -36)" />
      <ellipse cx="-2" cy="-20" rx="3.5" ry="8" transform="rotate(-35 -2 -20)" />
      <ellipse cx="8" cy="-16" rx="3.5" ry="7.5" transform="rotate(40 8 -16)" />
    </g>
  );
}

// Start screen backdrop: a pale dawn over far hills and a lotus on still water, along the bottom of the page.
// Wide and light so the heading and form sit on top of it; `slice` keeps it filling any screen width.
export function StartBackdrop({ className = "" }) {
  return (
    <svg viewBox="0 0 1440 420" preserveAspectRatio="xMidYMax slice" aria-hidden="true" className={className}>
      <defs>
        <radialGradient id="glow">
          <stop offset="0" stopColor="#FCE3AE" stopOpacity="0.9" />
          <stop offset="1" stopColor="#FCE3AE" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FBF1E4" stopOpacity="0" />
          <stop offset="1" stopColor="#FBF1E4" stopOpacity="0.8" />
        </linearGradient>
      </defs>
      <rect y="80" width="1440" height="200" fill="url(#haze)" />
      <circle cx="1330" cy="150" r="190" fill="url(#glow)" />
      <circle cx="1330" cy="150" r="52" fill="#FCE9C4" />
      <path d="M0 250c170-90 350-110 530-56s320 22 470-30 300-46 440 0v256H0Z" fill="#E6DCF6" />
      <path d="M0 300c210-62 410-62 620-24s420 30 590-14 170-16 230 0v158H0Z" fill="#D8CAF0" />
      {/* still water with a few ripples */}
      <rect y="336" width="1440" height="84" fill="#EEE7F9" />
      <path d="M600 372h80M760 372h80M650 396h140" stroke="#D8CAF0" strokeWidth="3" strokeLinecap="round" />
      <g transform="translate(672 268) scale(1.5)">
        <path d="M32 46C22 45 12 37 10 24c10 1 18 8 22 22Z" fill="#B9A4E0" />
        <path d="M32 46c10-1 20-9 22-22-10 1-18 8-22 22Z" fill="#B9A4E0" />
        <path d="M32 10c8 9 9 25 0 36-9-11-8-27 0-36Z" fill="#7458A8" />
        <circle cx="32" cy="44" r="3.5" fill="#F2B33D" />
      </g>
      <g transform="translate(120 420) scale(2.2)"><Sprig x={0} y={0} /></g>
      <g transform="translate(1320 420) scale(2.2)"><Sprig x={0} y={0} flip /></g>
    </svg>
  );
}

// Upload area: a little stack of the kinds of papers families usually have.
export function PapersArt({ className = "" }) {
  return (
    <svg viewBox="0 0 120 72" aria-hidden="true" className={className}>
      <rect x="10" y="16" width="44" height="50" rx="5" fill="#FFFFFF" stroke="#C7BEDB" strokeWidth="2" transform="rotate(-8 32 41)" />
      <rect x="38" y="8" width="44" height="56" rx="5" fill="#FFFFFF" stroke="#4B2E83" strokeWidth="2" />
      <path d="M46 22h28M46 32h20M46 42h26" stroke="#C7BEDB" strokeWidth="2.5" strokeLinecap="round" />
      {/* a phone with a message: SMS and UPI screenshots */}
      <rect x="80" y="20" width="28" height="46" rx="6" fill="#FFFFFF" stroke="#4B2E83" strokeWidth="2" transform="rotate(8 94 43)" />
      <rect x="86" y="32" width="16" height="8" rx="3" fill="#F2B33D" transform="rotate(8 94 43)" />
    </svg>
  );
}
