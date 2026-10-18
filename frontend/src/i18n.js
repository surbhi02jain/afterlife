// All UI text in English and Hindi. Keep sentences short and gentle.

const en = {
  appName: "Afterlife",
  tagline: "Gentle help with a loved one's money matters",
  sampleBanner: "Sample family. Every name, number and document here is made up.",
  language: "हिन्दी",
  languageLabel: "Switch to Hindi",
  readAloud: "Read aloud",
  stopReading: "Stop reading",
  activity: "What Afterlife did",
  close: "Close",
  loading: "Getting things ready…",
  errorTitle: "Something didn't work",
  errorBody: "Your information is safe. Please try again in a moment.",
  tryAgain: "Try again",

  nav_upload: "Documents",
  nav_map: "What we found",
  nav_questions: "Questions",
  nav_plan: "Plan",
  nav_letters: "Letters",
  nav_board: "Family board",
  nav_privacy: "Privacy",

  // start
  startTitle: "We are sorry for your loss.",
  startBody:
    "Afterlife helps you find the accounts, policies and investments your loved one had, and what to do about each one. We go one gentle step at a time.",
  theirName: "Their name",
  dateOfDeath: "Date they passed away",
  yourRelationship: "You are their",
  chooseOne: "Choose one",
  rel_spouse: "Wife or husband",
  rel_son: "Son",
  rel_daughter: "Daughter",
  rel_parent: "Parent",
  rel_sibling: "Brother or sister",
  rel_other: "Other family member",
  preferredLanguage: "Language for letters and steps",
  begin: "Begin",
  tryDemo: "Try with a demo family",
  demoHint: "See how Afterlife works with a made-up family. No real data.",
  continueCase: "Continue where you left off",
  deletedNotice: "Everything has been deleted.",

  // upload
  uploadTitle: "Add whatever documents you have",
  uploadBody:
    "Photos of statements or passbooks, policy receipts, SMS or UPI screenshots. It's fine if things are incomplete; we'll help find what's missing.",
  dropHere: "Drop photos or PDFs here",
  chooseFiles: "Choose photos or PDFs",
  fileTypes: "Photos (JPG, PNG) or PDF, up to 15 MB each",
  guideTitle: "What can I upload, and where do I find it?",
  guideIntro:
    "Upload whatever you have. Even one bank statement helps: its payments often point to policies and investments nobody knew about.",
  guideItems: [
    { icon: "savings_account", what: "Bank passbooks and statements",
      where: "In cupboard files, statements that came by post, or email attachments the family already has.",
      missing: "Missing? Ask the branch for a statement as the nominee or legal heir. Afterlife can draft the letter." },
    { icon: "sms", what: "Bank SMS and UPI screenshots",
      where: "Messages about debits, credits and auto-payments on the family's phone. They are often the best clues to hidden accounts." },
    { icon: "life_insurance", what: "Insurance policies and premium receipts",
      where: "The policy document, premium receipts, or papers from the insurance agent.",
      missing: "Missing? Afterlife can draft a letter asking the insurer to confirm." },
    { icon: "mutual_fund", what: "Mutual fund and shares statements",
      where: "Consolidated statements that arrive by email or post.",
      missing: "Missing? Ask the fund house or the stockbroker." },
    { icon: "epf", what: "EPF passbook or salary slips",
      where: "Old salary slips or letters from the employer.",
      missing: "Missing? Ask the HR team of the last employer." },
    { icon: "home_loan", what: "Loan papers and EMI messages",
      where: "The loan agreement, or EMI reminders by SMS.",
      missing: "Missing? Ask the lender for the amount still owed." },
  ],
  guideSafety:
    "Please don't use their passwords, PINs or OTPs to log in and download anything. Use only papers and messages the family already has, or ask the institution. Banks and insurers share details only with the nominee or legal heir, after checking the death certificate and ID.",
  scamTitle: "Stay safe from scams",
  scamPoints: [
    "Afterlife will never call, message or email you.",
    "Banks and insurers never ask for an OTP, PIN or password, and never ask you to pay to release a claim.",
    "If anyone offers to get the money faster for a fee, it is a scam. Go to the branch or office yourself.",
  ],
  st_uploaded: "Waiting to be read",
  st_extracting: "Reading…",
  st_extracted: "Read",
  st_failed: "Couldn't read this",
  savedReading: "sample reading",
  retry: "Try again",
  removeDoc: "Remove",
  otherHolder: "This document is in the name of {holder}, not {name}. Please check it is the right document, or remove it.",
  removeDocConfirm: "Remove this file? Anything found only in it will be taken off the list.",
  removeYes: "Yes, remove",
  readDocs: "Read {n} documents",
  reading: "Reading your documents…",
  analyse: "Find what might be missing",
  analysing: "Afterlife is looking through everything…",
  analysingBody: "This usually takes under a minute. You can watch what's happening below.",
  seeFound: "See what we found",
  noDocsYet: "No documents yet.",

  // asset map
  mapTitle: "What we found",
  mapBody: "Everything your documents show, and a few things they point to.",
  fromAfterlife: "From Afterlife",
  discoveryTitle: "We may have found {n} more things",
  mapSummaryLoans: "They also show loans of {total}.",
  afterDeathTitle: "Money left an account after {name} passed away",
  afterDeathTotal: "{n} payments, {total} in total:",
  afterDeathMore: "Show {n} more",
  afterDeathBody: "Tell the bank or payment app today. It may be an auto-debit to stop, or someone using the account. It is first in your plan.",
  confirmedSoFar: "Confirmed so far, across {n} accounts and policies",
  otherAssets: "Other",
  discoveryBody: "These had no document of their own. They are not confirmed. Please check each one.",
  probableNotCounted: "Things we're not sure about are not counted.",
  confirmed: "Confirmed",
  probable: "Probably exists, please check",
  liabilities: "Loans and dues",
  notApplicable: "Not applicable",
  undo: "Undo",
  probablyA: "Probably a {type} with {institution}",
  conf_high: "We're fairly sure",
  conf_medium: "Somewhat sure",
  conf_low: "Not very sure",
  whatWeNoticed: "What we noticed",
  yesConfirm: "Yes, this is right",
  markNA: "Not applicable",
  nominee: "Nominee",
  nomineeUnknown: "Nominee not known",
  nextDebit: "Next auto-debit expected on {date}",
  asOf: "as of {date}",
  nothingFound: "Nothing found yet. Add documents and Afterlife will look through them.",
  nextQuestions: "Next: a few questions",

  // questions
  questionsTitle: "A few gentle questions",
  questionsBody: "Your answers help us fill the gaps. Skip anything you don't know.",
  typeAnswer: "Type your answer",
  save: "Save",
  answered: "Thank you, we've noted these",
  noQuestions: "No questions waiting.",
  askMe: "Ask me a few questions",
  seePlan: "See your plan",

  // plan
  planTitle: "Your plan, in a sensible order",
  planBody: "Start at the top. Each step says why it comes where it does.",
  planProgress: "{done} of {n} steps done",
  makePlan: "Prepare my plan",
  firstForEveryone: "Before anything else",
  firstStep: "First step",
  whyOrder: "Why this order",
  timeSensitive: "Time-sensitive",
  needsChecking: "Needs checking",
  allSteps: "All steps and documents",
  steps: "Steps",
  documents: "Documents to keep ready",
  timeline: "Usually takes",
  source: "Source",
  unverified: "Unverified guidance",
  prepareLetter: "Prepare letter",
  seeLetters: "See letters",

  // letters
  lettersTitle: "Letters, ready to send",
  lettersBody: "Read each letter and fill in anything in [brackets]. You can change any word.",
  noLetters: "No letters yet. Prepare one from your plan.",
  letterFor: "Letter for",
  makeLetterFor: "Make a letter for…",
  saveChanges: "Save changes",
  saved: "Saved",
  downloadPdf: "Download PDF",

  // board
  boardTitle: "Family board",
  boardBody: "Keep track together. Move each step as it happens.",
  col_todo: "To do",
  col_in_progress: "In progress",
  col_done: "Done",
  start: "Start",
  markDone: "Mark done",
  moveBack: "Move back",
  shareTitle: "Share with family",
  shareBody: "A read-only link shows this board. It never shows documents, letters or full numbers.",
  createLink: "Create read-only link",
  copy: "Copy link",
  copied: "Copied",
  noPlanYet: "Prepare your plan first, then it appears here.",
  sharedView: "Read-only view shared by your family",
  forName: "For {name}",
  linkInvalid: "This link is not valid any more.",

  // privacy
  privacyTitle: "Your privacy",
  privacyBody: "What happens to your documents, and how to remove everything.",
  privacyPoints: [
    "Your documents are read by Google Gemini to find accounts and policies. They are not used for anything else.",
    "On our cloud storage, uploaded files are set to delete themselves 24 hours after upload. The case notes stay until you delete them.",
    "We only ever show the last 4 digits of account and policy numbers.",
    "Afterlife will never ask for passwords, PINs, OTPs or card numbers.",
  ],
  deleteData: "Delete my data",
  deleteConfirm: "This deletes the case, every uploaded file and all letters. It cannot be undone.",
  deleteYes: "Yes, delete everything",
  cancel: "Cancel",
  disclaimerShort: "Afterlife gives guidance, not legal or financial advice.",
};

const hi = {
  appName: "आफ्टरलाइफ़",
  tagline: "प्रियजन के पैसों के कामों में सहज मदद",
  sampleBanner: "नमूना परिवार। यहाँ हर नाम, नंबर और दस्तावेज़ काल्पनिक है।",
  language: "English",
  languageLabel: "Switch to English",
  readAloud: "सुनें",
  stopReading: "रोकें",
  activity: "आफ्टरलाइफ़ ने क्या किया",
  close: "बंद करें",
  loading: "तैयारी हो रही है…",
  errorTitle: "कुछ ठीक से नहीं हुआ",
  errorBody: "आपकी जानकारी सुरक्षित है। कृपया थोड़ी देर में फिर कोशिश करें।",
  tryAgain: "फिर कोशिश करें",

  nav_upload: "दस्तावेज़",
  nav_map: "क्या मिला",
  nav_questions: "प्रश्न",
  nav_plan: "योजना",
  nav_letters: "पत्र",
  nav_board: "परिवार बोर्ड",
  nav_privacy: "गोपनीयता",

  startTitle: "आपके दुःख में हम आपके साथ हैं।",
  startBody:
    "आफ्टरलाइफ़ आपके प्रियजन के खाते, पॉलिसी और निवेश खोजने में मदद करता है, और बताता है कि हर एक के लिए क्या करना है। हम एक-एक कदम आराम से चलेंगे।",
  theirName: "उनका नाम",
  dateOfDeath: "उनके निधन की तारीख़",
  yourRelationship: "आप उनके हैं",
  chooseOne: "चुनें",
  rel_spouse: "पत्नी या पति",
  rel_son: "बेटा",
  rel_daughter: "बेटी",
  rel_parent: "माता या पिता",
  rel_sibling: "भाई या बहन",
  rel_other: "परिवार के अन्य सदस्य",
  preferredLanguage: "पत्रों और कदमों की भाषा",
  begin: "शुरू करें",
  tryDemo: "नमूना परिवार के साथ देखें",
  demoHint: "एक काल्पनिक परिवार के साथ देखें कि आफ्टरलाइफ़ कैसे काम करता है। कोई असली जानकारी नहीं।",
  continueCase: "जहाँ छोड़ा था वहीं से जारी रखें",
  deletedNotice: "सब कुछ हटा दिया गया है।",

  uploadTitle: "जो भी दस्तावेज़ हैं, जोड़ें",
  uploadBody:
    "स्टेटमेंट या पासबुक की फ़ोटो, पॉलिसी रसीद, SMS या UPI स्क्रीनशॉट। अधूरा हो तो भी ठीक है; जो छूट गया है, उसे खोजने में हम मदद करेंगे।",
  dropHere: "फ़ोटो या PDF यहाँ छोड़ें",
  chooseFiles: "फ़ोटो या PDF चुनें",
  fileTypes: "फ़ोटो (JPG, PNG) या PDF, हर एक 15 MB तक",
  guideTitle: "क्या अपलोड करें, और यह कहाँ मिलेगा?",
  guideIntro:
    "जो कुछ भी आपके पास है, अपलोड करें। एक बैंक स्टेटमेंट भी मदद करता है: उसके भुगतानों से अक्सर ऐसी पॉलिसी और निवेश का पता चलता है जिनकी किसी को जानकारी नहीं थी।",
  guideItems: [
    { icon: "savings_account", what: "बैंक पासबुक और स्टेटमेंट",
      where: "अलमारी की फ़ाइलों में, डाक से आए स्टेटमेंट में, या परिवार के पास पहले से मौजूद ईमेल में।",
      missing: "नहीं मिल रहा? नॉमिनी या कानूनी वारिस के रूप में शाखा से स्टेटमेंट माँगें। आफ्टरलाइफ़ पत्र तैयार कर सकता है।" },
    { icon: "sms", what: "बैंक SMS और UPI के स्क्रीनशॉट",
      where: "परिवार के फ़ोन पर डेबिट, क्रेडिट और ऑटो-पेमेंट के संदेश। छिपे खातों के सबसे अच्छे सुराग अक्सर इन्हीं में होते हैं।" },
    { icon: "life_insurance", what: "बीमा पॉलिसी और प्रीमियम रसीदें",
      where: "पॉलिसी के कागज़, प्रीमियम रसीदें, या बीमा एजेंट से मिले कागज़।",
      missing: "नहीं मिल रहा? आफ्टरलाइफ़ बीमा कंपनी से पुष्टि माँगने का पत्र तैयार कर सकता है।" },
    { icon: "mutual_fund", what: "म्यूचुअल फ़ंड और शेयर के स्टेटमेंट",
      where: "ईमेल या डाक से आने वाले संयुक्त (कंसॉलिडेटेड) स्टेटमेंट।",
      missing: "नहीं मिल रहा? फ़ंड हाउस या स्टॉकब्रोकर से पूछें।" },
    { icon: "epf", what: "EPF पासबुक या सैलरी स्लिप",
      where: "पुरानी सैलरी स्लिप या नियोक्ता के पत्र।",
      missing: "नहीं मिल रहा? पिछले नियोक्ता की HR टीम से पूछें।" },
    { icon: "home_loan", what: "लोन के कागज़ और EMI संदेश",
      where: "लोन एग्रीमेंट, या SMS से आए EMI रिमाइंडर।",
      missing: "नहीं मिल रहा? लेंडर से बकाया राशि पूछें।" },
  ],
  guideSafety:
    "कृपया उनके पासवर्ड, PIN या OTP से लॉग इन करके कुछ भी डाउनलोड न करें। केवल वही कागज़ और संदेश इस्तेमाल करें जो परिवार के पास पहले से हैं, या संस्था से माँगें। बैंक और बीमा कंपनियाँ मृत्यु प्रमाण पत्र और पहचान पत्र जाँचने के बाद ही नॉमिनी या कानूनी वारिस को जानकारी देती हैं।",
  scamTitle: "धोखाधड़ी से सावधान रहें",
  scamPoints: [
    "आफ्टरलाइफ़ आपको कभी फ़ोन, संदेश या ईमेल नहीं करेगा।",
    "बैंक और बीमा कंपनियाँ कभी OTP, PIN या पासवर्ड नहीं माँगतीं, और दावा जारी करने के लिए कभी पैसे नहीं माँगतीं।",
    "अगर कोई फ़ीस लेकर पैसा जल्दी दिलाने की बात करे, तो यह धोखा है। ख़ुद शाखा या दफ़्तर जाएँ।",
  ],
  st_uploaded: "पढ़े जाने की प्रतीक्षा में",
  st_extracting: "पढ़ा जा रहा है…",
  st_extracted: "पढ़ लिया",
  st_failed: "यह पढ़ा नहीं जा सका",
  savedReading: "नमूना पठन",
  retry: "फिर कोशिश करें",
  removeDoc: "हटाएँ",
  otherHolder: "यह दस्तावेज़ {holder} के नाम पर है, {name} के नाम पर नहीं। कृपया जाँचें कि यह सही दस्तावेज़ है, या इसे हटा दें।",
  removeDocConfirm: "यह फ़ाइल हटाएँ? जो चीज़ें सिर्फ़ इसी में मिली थीं, वे भी सूची से हट जाएँगी।",
  removeYes: "हाँ, हटाएँ",
  readDocs: "{n} दस्तावेज़ पढ़ें",
  reading: "आपके दस्तावेज़ पढ़े जा रहे हैं…",
  analyse: "देखें कि क्या छूट गया हो सकता है",
  analysing: "आफ्टरलाइफ़ सब कुछ देख रहा है…",
  analysingBody: "इसमें आमतौर पर एक मिनट से कम लगता है। नीचे देख सकते हैं कि क्या हो रहा है।",
  seeFound: "देखें क्या मिला",
  noDocsYet: "अभी कोई दस्तावेज़ नहीं।",

  mapTitle: "क्या मिला",
  mapBody: "आपके दस्तावेज़ों में जो दिखा, और कुछ चीज़ें जिनकी ओर वे इशारा करते हैं।",
  fromAfterlife: "आफ्टरलाइफ़ की ओर से",
  discoveryTitle: "शायद {n} और चीज़ें मिली हैं",
  mapSummaryLoans: "इनमें {total} के लोन भी दिखते हैं।",
  afterDeathTitle: "{name} के निधन के बाद एक खाते से पैसा निकला",
  afterDeathTotal: "{n} भुगतान, कुल {total}:",
  afterDeathMore: "{n} और देखें",
  afterDeathBody: "आज ही बैंक या पेमेंट ऐप को बताएँ। यह रुकवाने वाला ऑटो-डेबिट हो सकता है, या कोई खाते का उपयोग कर रहा हो सकता है। यह आपकी योजना में सबसे पहले है।",
  confirmedSoFar: "अब तक पक्का, {n} खातों और पॉलिसियों में",
  otherAssets: "अन्य",
  discoveryBody: "इनका अपना कोई दस्तावेज़ नहीं था। ये पक्की नहीं हैं। कृपया हर एक की जाँच करें।",
  probableNotCounted: "जिन चीज़ों पर पक्का नहीं है, उन्हें नहीं जोड़ा गया।",
  confirmed: "पक्का",
  probable: "शायद मौजूद है, कृपया जाँचें",
  liabilities: "लोन और बकाया",
  notApplicable: "लागू नहीं",
  undo: "वापस करें",
  probablyA: "शायद {institution} में {type}",
  conf_high: "हमें काफ़ी भरोसा है",
  conf_medium: "कुछ भरोसा है",
  conf_low: "ज़्यादा भरोसा नहीं",
  whatWeNoticed: "हमने क्या देखा",
  yesConfirm: "हाँ, यह सही है",
  markNA: "लागू नहीं",
  nominee: "नॉमिनी",
  nomineeUnknown: "नॉमिनी ज्ञात नहीं",
  nextDebit: "अगला ऑटो-डेबिट {date} को अपेक्षित",
  asOf: "{date} तक",
  nothingFound: "अभी कुछ नहीं मिला। दस्तावेज़ जोड़ें, आफ्टरलाइफ़ उन्हें देखेगा।",
  nextQuestions: "आगे: कुछ प्रश्न",

  questionsTitle: "कुछ सहज प्रश्न",
  questionsBody: "आपके उत्तर कमियाँ भरने में मदद करते हैं। जो नहीं पता, उसे छोड़ दें।",
  typeAnswer: "अपना उत्तर लिखें",
  save: "सहेजें",
  answered: "धन्यवाद, हमने ये नोट कर लिए हैं",
  noQuestions: "कोई प्रश्न बाकी नहीं।",
  askMe: "मुझसे कुछ प्रश्न पूछें",
  seePlan: "अपनी योजना देखें",

  planTitle: "आपकी योजना, सही क्रम में",
  planBody: "ऊपर से शुरू करें। हर कदम बताता है कि वह वहाँ क्यों है।",
  planProgress: "{n} में से {done} कदम पूरे",
  makePlan: "मेरी योजना तैयार करें",
  firstForEveryone: "सबसे पहले",
  firstStep: "पहला कदम",
  whyOrder: "यह क्रम क्यों",
  timeSensitive: "समय पर ध्यान दें",
  needsChecking: "जाँच ज़रूरी",
  allSteps: "सभी कदम और दस्तावेज़",
  steps: "कदम",
  documents: "तैयार रखें ये दस्तावेज़",
  timeline: "आमतौर पर लगता है",
  source: "स्रोत",
  unverified: "असत्यापित मार्गदर्शन",
  prepareLetter: "पत्र तैयार करें",
  seeLetters: "पत्र देखें",

  lettersTitle: "भेजने के लिए तैयार पत्र",
  lettersBody: "हर पत्र पढ़ें और [कोष्ठक] में जो है उसे भरें। आप कोई भी शब्द बदल सकते हैं।",
  noLetters: "अभी कोई पत्र नहीं। अपनी योजना से एक तैयार करें।",
  letterFor: "पत्र",
  makeLetterFor: "इसके लिए पत्र बनाएँ…",
  saveChanges: "बदलाव सहेजें",
  saved: "सहेजा गया",
  downloadPdf: "PDF डाउनलोड करें",

  boardTitle: "परिवार बोर्ड",
  boardBody: "साथ मिलकर ध्यान रखें। हर कदम होने पर उसे आगे बढ़ाएँ।",
  col_todo: "करना है",
  col_in_progress: "चल रहा है",
  col_done: "हो गया",
  start: "शुरू करें",
  markDone: "हो गया",
  moveBack: "वापस ले जाएँ",
  shareTitle: "परिवार के साथ साझा करें",
  shareBody: "केवल-देखने वाला लिंक यह बोर्ड दिखाता है। इसमें कभी दस्तावेज़, पत्र या पूरे नंबर नहीं दिखते।",
  createLink: "केवल-देखने वाला लिंक बनाएँ",
  copy: "लिंक कॉपी करें",
  copied: "कॉपी हो गया",
  noPlanYet: "पहले अपनी योजना तैयार करें, फिर यह यहाँ दिखेगी।",
  sharedView: "आपके परिवार द्वारा साझा किया गया केवल-देखने वाला दृश्य",
  forName: "{name} के लिए",
  linkInvalid: "यह लिंक अब मान्य नहीं है।",

  privacyTitle: "आपकी गोपनीयता",
  privacyBody: "आपके दस्तावेज़ों का क्या होता है, और सब कुछ कैसे हटाएँ।",
  privacyPoints: [
    "खाते और पॉलिसी खोजने के लिए आपके दस्तावेज़ Google Gemini पढ़ता है। इनका किसी और काम में उपयोग नहीं होता।",
    "हमारे क्लाउड स्टोरेज पर अपलोड की गई फ़ाइलें अपलोड के 24 घंटे बाद अपने आप हटने के लिए सेट हैं। मामले के नोट्स तब तक रहते हैं जब तक आप उन्हें न हटाएँ।",
    "हम खाते और पॉलिसी नंबर के केवल आख़िरी 4 अंक दिखाते हैं।",
    "आफ्टरलाइफ़ कभी पासवर्ड, PIN, OTP या कार्ड नंबर नहीं माँगेगा।",
  ],
  deleteData: "मेरा डेटा हटाएँ",
  deleteConfirm: "इससे मामला, हर अपलोड की गई फ़ाइल और सभी पत्र हट जाएँगे। इसे वापस नहीं किया जा सकता।",
  deleteYes: "हाँ, सब कुछ हटाएँ",
  cancel: "रद्द करें",
  disclaimerShort: "आफ्टरलाइफ़ मार्गदर्शन देता है, कानूनी या वित्तीय सलाह नहीं।",
};

const TYPE = {
  en: {
    savings_account: "savings account", fixed_deposit: "fixed deposit", life_insurance: "life insurance policy",
    mutual_fund: "mutual fund", demat_account: "demat (shares) account", epf: "EPF account", ppf: "PPF account",
    other_asset: "asset", home_loan: "home loan", personal_loan: "personal loan", vehicle_loan: "vehicle loan",
    credit_card: "credit card", other_loan: "loan",
  },
  hi: {
    savings_account: "बचत खाता", fixed_deposit: "फ़िक्स्ड डिपॉज़िट", life_insurance: "जीवन बीमा पॉलिसी",
    mutual_fund: "म्यूचुअल फ़ंड", demat_account: "डीमैट (शेयर) खाता", epf: "EPF खाता", ppf: "PPF खाता",
    other_asset: "संपत्ति", home_loan: "होम लोन", personal_loan: "पर्सनल लोन", vehicle_loan: "वाहन लोन",
    credit_card: "क्रेडिट कार्ड", other_loan: "लोन",
  },
};

const DOC_TYPE = {
  en: {
    bank_statement: "bank statement", passbook: "passbook", insurance_policy: "insurance policy",
    premium_receipt: "premium receipt", mutual_fund_statement: "mutual fund statement",
    demat_statement: "demat statement", epf_passbook: "EPF passbook", loan_sms: "loan SMS",
    upi_history: "UPI history", other: "document",
  },
  hi: {
    bank_statement: "बैंक स्टेटमेंट", passbook: "पासबुक", insurance_policy: "बीमा पॉलिसी",
    premium_receipt: "प्रीमियम रसीद", mutual_fund_statement: "म्यूचुअल फ़ंड स्टेटमेंट",
    demat_statement: "डीमैट स्टेटमेंट", epf_passbook: "EPF पासबुक", loan_sms: "लोन SMS",
    upi_history: "UPI इतिहास", other: "दस्तावेज़",
  },
};

const STRINGS = { en, hi };

export function t(lang, key, vars = {}) {
  let s = STRINGS[lang]?.[key] ?? en[key] ?? key;
  if (typeof s === "string") {
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  }
  return s;
}

export const typeLabel = (lang, type) => TYPE[lang]?.[type] ?? type.replaceAll("_", " ");
export const docTypeLabel = (lang, type) => DOC_TYPE[lang]?.[type] ?? type;

// Statements often print names in capitals ("SAHYADRI NATIONAL BANK"). Show them in normal case, but keep
// short or vowel-less words as acronyms (SBI, LIC, HDFC, LTD).
const SMALL_WORDS = new Set(["of", "and", "the", "for"]);
export function orgName(name) {
  if (!name || name !== name.toUpperCase()) return name;
  return name.replace(/[A-Z]+/g, (word, at) => {
    const lower = word.toLowerCase();
    if (SMALL_WORDS.has(lower) || name[at - 1] === "-") return lower; // "Co-operative"
    if (["co", "ltd", "pvt"].includes(lower)) return word[0] + lower.slice(1);
    if (word.length <= 3 || !/[AEIOU]/.test(word)) return word;
    return word[0] + lower.slice(1);
  });
}

export function inr(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(value);
}

export function niceDate(iso, lang) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "short", year: "numeric" });
}
