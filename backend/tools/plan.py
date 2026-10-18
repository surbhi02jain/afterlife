"""Action plan: an ordered, per-institution checklist. Deterministic.

Steps and documents come ONLY from the knowledge base (kb/procedures.json). Ordering, deadlines and
"why this order" are computed here from the asset map and date arithmetic, in the case language.
"""

from datetime import date, timedelta

import kb
from app.models import ActionPlan, Asset, Case, Liability, PlanItemRef, PlanTask
from tools.asset_map import debits_after_death
from tools.finance import institution_tokens, parse_date, same_institution
from tools.i18n import inr, label, nice_date, pick

URGENT_WINDOW_DAYS = 45

DISCLAIMER = {
    "en": "This is guidance, not legal advice. The steps are general and not yet verified, so please confirm the "
          "details with each institution.",
    "hi": "यह मार्गदर्शन है, कानूनी सलाह नहीं। ये कदम सामान्य हैं और अभी सत्यापित नहीं हैं, इसलिए कृपया हर संस्था से "
          "विवरण की पुष्टि करें।",
}


def _group_by_institution(items: list[Asset | Liability]) -> list[list[Asset | Liability]]:
    groups: list[list] = []
    for item in items:
        for group in groups:
            if same_institution(group[0].institution, item.institution):
                group.append(item)
                break
        else:
            groups.append([item])
    return groups


def _last_debit_amount(item) -> float | None:
    debits = [e for e in item.evidence if e.direction == "debit" and e.amount]
    return max(debits, key=lambda e: e.date or "").amount if debits else None


def _task_id(group) -> str:
    tokens = sorted(institution_tokens(group[0].institution))
    return "task-" + ("-".join(tokens) if tokens else group[0].id)


def _why(lang: str, urgent_date: date | None, priority_key: str | None, needs_confirmation: bool,
         moved_after_death: bool = False) -> str:
    reasons = []
    if moved_after_death:
        reasons.append(pick(lang, "Money has already left this account after the death, so tell them first, today.",
                            "मृत्यु के बाद इस खाते से पैसा निकल चुका है, इसलिए सबसे पहले, आज ही बताएँ।"))
    elif urgent_date:
        reasons.append(pick(lang, f"An auto-debit is expected on {nice_date(urgent_date)}, so telling them soon stops "
                                  "money leaving the account.",
                            f"{nice_date(urgent_date, 'hi')} को पैसा अपने आप कटने वाला है, इसलिए जल्दी बताने से "
                            "खाते से पैसा जाना रुकेगा।"))
    if needs_confirmation:
        reasons.append(pick(lang, "We are not sure this exists yet, so the first step is simply to ask.",
                            "हमें अभी पक्का नहीं पता कि यह मौजूद है, इसलिए पहला कदम बस पूछना है।"))
    by_key = {
        "life_insurance": ("Insurers expect the death to be reported early, and this claim is often the largest "
                           "payment to the family.",
                           "बीमा कंपनियाँ मृत्यु की सूचना जल्दी चाहती हैं, और यह दावा अक्सर परिवार को मिलने वाली सबसे बड़ी राशि होती है।"),
        "loan": ("The lender needs to know so EMIs and any loan insurance are handled properly.",
                 "लेंडर को पता होना चाहिए ताकि EMI और लोन बीमा सही तरह से संभाले जाएँ।"),
        "bank_savings_account": ("The bank account is where most auto-debits and claim payments flow through.",
                                 "ज़्यादातर ऑटो-डेबिट और दावे की राशि इसी बैंक खाते से होकर जाती है।"),
        "fixed_deposit": ("This is usually handled at the same branch as the savings account.",
                          "यह आमतौर पर बचत खाते वाली शाखा में ही निपटता है।"),
        "epf": ("EPF goes through the employer, who can start the paperwork in parallel.",
                "EPF नियोक्ता के ज़रिए होता है, जो साथ-साथ कागज़ी काम शुरू कर सकते हैं।"),
    }
    if not reasons and priority_key in by_key:
        reasons.append(pick(lang, *by_key[priority_key]))
    if not reasons:
        reasons.append(pick(lang, "This can follow once the earlier steps are moving.",
                            "पहले के कदम शुरू होने के बाद यह किया जा सकता है।"))
    return " ".join(reasons)


def build_plan(case: Case, today: date | None = None) -> ActionPlan:
    today = today or date.today()
    lang = case.language
    previous = {t.id: t.board_status for t in case.plan.tasks} if case.plan else {}
    items = [i for i in [*case.assets, *case.liabilities] if i.status != "rejected"]
    after_death = debits_after_death(case)

    drafts = []
    for group in _group_by_institution(items):
        procedures = [kb.lookup(i.type, lang) for i in group]
        found = [p for p in procedures if p["found"]]
        primary = min(found, key=lambda p: p["priority"]) if found else None
        needs_confirmation = all(i.status == "probable" for i in group)
        institution = next((i.institution for i in group if i.institution), "Unknown institution")
        type_names = ", ".join(dict.fromkeys(label(i.type, lang) for i in group))

        urgent, time_sensitive = [], []
        for i in group:
            nxt = parse_date(i.next_expected_debit)
            if nxt and today <= nxt <= today + timedelta(days=URGENT_WINDOW_DAYS):
                urgent.append(nxt)
                amount = _last_debit_amount(i)
                time_sensitive.append(pick(lang, f"An auto-debit of {inr(amount)} for the {label(i.type, 'en')} is expected on "
                                         f"{nice_date(nxt)}.",
                                   f"{label(i.type, 'hi')} के लिए {inr(amount)} का ऑटो-डेबिट {nice_date(nxt, 'hi')} "
                                   "को होने की संभावना है।"))
        moved = [f for f in after_death if f["item_id"] in {i.id for i in group}]
        if moved:
            urgent.append(today)  # money is leaving now: this institution goes first
            total_out, latest = sum(f["amount"] for f in moved), nice_date(moved[-1]["date"])
            time_sensitive.insert(0, pick(
                lang, f"{inr(total_out)} left this account in {len(moved)} payment{'s' if len(moved) != 1 else ''} after "
                      f"{case.deceased_name} passed away (latest on {latest}). Tell them today: it may be an auto-debit "
                      "to stop, or someone using the account.",
                f"{case.deceased_name} के निधन के बाद इस खाते से {len(moved)} भुगतान में {inr(total_out)} निकले "
                f"(आख़िरी {nice_date(moved[-1]['date'], 'hi')} को)। आज ही बताएँ: यह रुकवाने वाला ऑटो-डेबिट हो सकता है, "
                "या कोई खाते का उपयोग कर रहा हो सकता है।"))
        time_sensitive += list(dict.fromkeys(p["time_sensitive"] for p in found if p["time_sensitive"]))

        steps = list(dict.fromkeys(step for p in found for step in p["steps"])) or [kb.NOT_FOUND[lang]]
        if needs_confirmation:
            confirm = pick(lang, f"Ask {institution} to confirm whether {case.deceased_name} had a {type_names} with "
                                 "them. A letter is ready for this.",
                           f"{institution} से पूछें कि क्या उनके यहाँ {case.deceased_name} के नाम पर {type_names} है। "
                           "इसके लिए पत्र तैयार है।")
            steps = [confirm, *steps]

        task = PlanTask(
            id=_task_id(group),
            order=0,
            institution=institution,
            items=[PlanItemRef(item_id=i.id, kind="liability" if isinstance(i, Liability) else "asset", type=i.type,
                               status=i.status, identifier_masked=i.identifier_masked, amount=i.amount)
                   for i in group],
            needs_confirmation=needs_confirmation,
            nominee=next((i.nominee for i in group if i.nominee), None),
            first_step=steps[0],
            steps=steps,
            documents_required=list(dict.fromkeys(d for p in found for d in p["documents_required"])),
            typical_timeline=primary["typical_timeline"] if primary else None,
            time_sensitive=time_sensitive,
            why_this_order=_why(lang, min(urgent) if urgent else None, primary["key"] if primary else None,
                                needs_confirmation, moved_after_death=bool(moved)),
            source_names=list(dict.fromkeys(p["source_name"] for p in found)),
            verified=bool(found) and all(p["verified"] for p in found),
            board_status=previous.get(_task_id(group), "todo"),
        )
        total = sum(i.amount or 0 for i in group)
        # soonest auto-debit first, then the knowledge base's priority, documented before probable, larger first
        sort_key = (min(urgent) if urgent else date.max, primary["priority"] if primary else 99,
                    int(needs_confirmation), -total)
        drafts.append((sort_key, task))

    tasks = [t for _, t in sorted(drafts, key=lambda d: d[0])]
    for n, task in enumerate(tasks, start=1):
        task.order = n
    general = kb.lookup("general", lang)
    return ActionPlan(
        language=lang,
        days_since_death=(today - case.date_of_death).days,
        general_steps=general["steps"],
        tasks=tasks,
        disclaimer=DISCLAIMER[lang],
    )
