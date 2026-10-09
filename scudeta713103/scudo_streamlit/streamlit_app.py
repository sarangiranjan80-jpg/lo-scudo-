import random
import io
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# SCUDO MONETA — scam-protection and statement-review prototype.
# SAFETY: This app simulates transactions only. It never connects to UPI or moves money.
# DATA MINIMIZATION: no message contents, contacts, audio, or real customer data are collected/stored.
# All generated examples and displayed performance metrics are synthetic.

st.set_page_config(page_title="SCUDO MONETA | Scam Protection", layout="wide")

ROOT = Path(__file__).parent
LOGO = ROOT / "assets" / "scudo_logo.png"

st.markdown("""
<style>
:root { --bg:#071426; --panel:#0d2037; --line:#1c3a58; --mint:#55e6b0; --cyan:#50d9ed; --amber:#ffc857; --red:#ff667d; }
.stApp { background:#0b1420; color:#eef6ff; font-family:Arial,Helvetica,sans-serif; }
h1,h2,h3 {font-family:Arial,Helvetica,sans-serif !important; color:#f4f8ff !important;}
.block-container {padding-top:1.2rem; max-width:1400px;}
[data-testid="stSidebar"] {background:#08182a; border-right:1px solid #1c3a58;}
[data-testid="stMetric"] {background:#111f2f; padding:16px; border:1px solid #23425f; border-radius:16px;}
div[data-testid="stForm"] {background:#0d2037; padding:18px; border:1px solid #1c3a58; border-radius:18px;}
.stButton>button {border-radius:12px; border:1px solid #2b5875; background:#d6e5ed; color:#061426; font-weight:800; min-height:2.8rem;}
.stButton>button:hover {border-color:#fff; color:#061426; box-shadow:0 0 20px #50d9ed33;}
div[data-testid="stAlert"] {border-radius:14px;}
.scudo-card {background:#111f2f; border:1px solid #1e4260; border-radius:18px; padding:20px; margin-bottom:12px;}
.eyebrow {font-size:11px; letter-spacing:2.5px; color:#55e6b0; font-weight:800; text-transform:uppercase;}
.big-score {font-family:'Space Grotesk'; font-size:54px; font-weight:700; line-height:1;}
.chip {display:inline-block; background:#142e48; border:1px solid #2a4e6c; padding:6px 10px; border-radius:999px; margin:4px 4px 4px 0; font-size:12px;}
.muted {color:#a7bdd1;}
.small {font-size:12px;color:#9eb6cb;}
hr {border-color:#1c3a58;}
</style>
""", unsafe_allow_html=True)

SCAMS = {
    "Digital arrest / authority threat": {
        "new_payee": True, "unusual_amount": True, "active_call": True, "screen_share": True,
        "repeated_attempts": 2, "mule_pattern": True,
        "message": "Someone claiming to be an official demands an urgent transfer to avoid arrest."
    },
    "KYC / account suspension lure": {
        "new_payee": True, "unusual_amount": True, "active_call": True, "screen_share": False,
        "repeated_attempts": 1, "mule_pattern": True,
        "message": "A caller claims your bank account or KYC will be suspended unless you pay now."
    },
    "Fake customer-care support": {
        "new_payee": True, "unusual_amount": False, "active_call": True, "screen_share": True,
        "repeated_attempts": 2, "mule_pattern": True,
        "message": "A fake support agent asks you to install a screen-sharing app or transfer a test amount."
    },
    "Cloned-voice family emergency": {
        "new_payee": True, "unusual_amount": True, "active_call": True, "screen_share": False,
        "repeated_attempts": 1, "mule_pattern": True,
        "message": "A caller sounds like a relative and says they urgently need money sent to a new account."
    },
    "QR / collect-request confusion": {
        "new_payee": True, "unusual_amount": False, "active_call": False, "screen_share": False,
        "repeated_attempts": 2, "mule_pattern": False,
        "message": "You are hurried into scanning a QR code or approving a collect request to receive money."
    },
}
NORMAL = {
    "Everyday known payee": dict(new_payee=False, unusual_amount=False, active_call=False, screen_share=False,
                                repeated_attempts=0, mule_pattern=False,
                                message="A routine payment to a known payee, with no obvious pressure signals.")
}

def risk_engine(tx):
    # Transparent demo rules. In later stages, this will be supplemented by a trained model and SHAP.
    score = 0
    reasons = []
    if tx["new_payee"]:
        score += 22; reasons.append(("New recipient", "This recipient has not been paid before. Verify their identity."))
    if tx["unusual_amount"]:
        score += 18; reasons.append(("Unusual amount", "The amount is higher than this demo user's normal pattern."))
    if tx["active_call"]:
        score += 18; reasons.append(("Active call", "Scams often pressure people while they are on a call."))
    if tx["screen_share"]:
        score += 25; reasons.append(("Screen-sharing app", "Screen sharing can expose sensitive payment steps."))
    if tx["repeated_attempts"] >= 2:
        score += 12; reasons.append(("Repeated attempts", "Several attempts to pay this recipient were detected."))
    if tx["mule_pattern"]:
        score += 25; reasons.append(("Receiver risk pattern", "Synthetic network data suggests this receiver gets money from many first-time payers."))
    score = min(100, score)
    # Never decide from one weak signal: require either multiple independent signals or a strong receiver/screen-share signal.
    signal_count = sum(bool(tx[k]) for k in ["new_payee","unusual_amount","active_call","screen_share","mule_pattern"]) + int(tx["repeated_attempts"] >= 2)
    if signal_count <= 1:
        score = min(score, 24)
    if score >= 70:
        tier, action = "HIGH", "Request a bank call-back and human review"
    elif score >= 40:
        tier, action = "MEDIUM", "Offer a 10-minute pause and Trusted Circle review"
    else:
        tier, action = "LOW", "Show a gentle safety nudge"
    return score, tier, action, reasons

def synthetic_cases(n=1000, seed=21):
    rng = random.Random(seed)
    rows=[]
    labels=list(SCAMS.keys())+["Normal"]
    weights=[.11,.11,.11,.11,.11,.45]
    for i in range(n):
        label=rng.choices(labels, weights=weights, k=1)[0]
        base=(NORMAL if label=="Normal" else SCAMS[label])
        tx={k:base[k] for k in ["new_payee","unusual_amount","active_call","screen_share","repeated_attempts","mule_pattern"]}
        if label=="Normal":
            # Some legitimate first-time or unusual transactions: realistic false-positive challenge.
            tx["new_payee"] = rng.random()<.15
            tx["unusual_amount"] = rng.random()<.08
            tx["repeated_attempts"] = 1 if rng.random()<.03 else 0
        score,tier,action,reasons=risk_engine(tx)
        rows.append({"case_id":f"SC-{i+1:04d}","scenario":label,"label":int(label!="Normal"),
                     "risk_score":score,"tier":tier,"new_payee":tx["new_payee"],
                     "unusual_amount":tx["unusual_amount"],"active_call":tx["active_call"],
                     "screen_share":tx["screen_share"],"repeated_attempts":tx["repeated_attempts"],
                     "mule_pattern":tx["mule_pattern"]})
    return pd.DataFrame(rows)

def chatbot_reply(question, language):
    """Give concise, practical guidance using local rules; no external service is called."""
    q = re.sub(r"\s+", " ", str(question or "").lower()).strip()
    hindi = language == "हिन्दी"
    if not q:
        return "Tell me what happened, without including account numbers, OTPs, PINs or passwords." if not hindi else "क्या हुआ, बताइए। कृपया खाता नंबर, OTP, PIN या पासवर्ड न लिखें।"

    intents = [
        (("already paid", "sent money", "money gone", "lost money", "already sent", "paid already", "पैसे भेज", "पैसा चला", "भुगतान कर दिया"), "incident"),
        (("otp", "pin", "upi pin", "password", "screen share", "anydesk", "remote access", "teamviewer", "स्क्रीन शेयर", "ओटीपी", "पिन"), "credentials"),
        (("kyc", "account blocked", "account suspended", "expire", "suspend", "केवाईसी", "खाता बंद"), "kyc"),
        (("police", "arrest", "digital arrest", "customs", "parcel", "court", "warrant", "गिरफ्तार", "पुलिस"), "authority"),
        (("family", "relative", "accident", "emergency", "son", "daughter", "friend", "परिवार", "दुर्घटना"), "emergency"),
        (("link", "url", "website", "click", "phishing", "लिंक", "वेबसाइट"), "link"),
        (("upi", "qr", "collect request", "receive money", "scan", "क्यूआर", "कलेक्ट"), "upi"),
        (("loan", "refund", "reward", "prize", "job offer", "investment", "नौकरी", "रिफंड", "इनाम"), "offer"),
    ]
    intent = next((name for words, name in intents if any(word in q for word in words)), "general")
    answers_en = {
        "incident": "Act now: call your bank using the number in its official app or on your card, and report the cyber-fraud incident through 1930 or cybercrime.gov.in. Save the transaction reference, messages and screenshots. Do not pay anyone who promises to recover the money for a fee. I cannot file the report for you.",
        "credentials": "Do not share an OTP, UPI PIN or password. You do not need to enter a UPI PIN to receive money. If you installed a remote-access app or shared credentials, disconnect the session, remove the app if safe to do so, contact your bank through an official channel and change affected credentials.",
        "kyc": "A message threatening immediate account closure unless you click a link or pay a fee is a warning sign. Do not use the message link or number. Open your bank's official app or call the number printed on your card to check whether any action is actually needed.",
        "authority": "Pause. Threats of immediate arrest over a phone or video call and demands to transfer money to prove innocence are common scam tactics. Do not transfer funds or share documents on the caller's instructions. End the call and contact the relevant organisation through an independently verified official channel.",
        "emergency": "Urgency can make it harder to check details. Contact your relative or friend using a number you already know, or ask a question only they would know. Do not rely on the incoming caller's number or voice alone before sending money.",
        "link": "Do not open the link while you are unsure. Check the exact domain carefully, but remember that a convincing-looking address is not proof that a site is safe. Open the organisation's official app or type its known address yourself. Never enter payment credentials through a message link.",
        "upi": "A QR code or collect request is not required to receive money. Before approving anything, read the screen carefully: entering your UPI PIN generally authorises a payment. Cancel if the request was unexpected and verify with the sender through another channel.",
        "offer": "Be cautious if an offer asks for an upfront fee, a deposit to unlock earnings, or guaranteed returns. Verify the company independently and do not send money or identity documents until you have checked it through trusted sources.",
        "general": "Let's check the situation step by step. What did the person ask you to do: click a link, share a code, install an app, approve a payment, or send money? Please leave out names, phone numbers, account details and any secret codes. If you feel pressured, pause and verify independently before acting."
    }
    answers_hi = {
        "incident": "अभी अपने बैंक के आधिकारिक ऐप या कार्ड पर दिए नंबर से संपर्क करें। 1930 पर कॉल करें या cybercrime.gov.in पर शिकायत दर्ज करें। ट्रांज़ैक्शन रेफरेंस, संदेश और स्क्रीनशॉट सुरक्षित रखें। पैसे वापस दिलाने के नाम पर फीस मांगने वालों से सावधान रहें। मैं आपकी ओर से शिकायत दर्ज नहीं कर सकता।",
        "credentials": "OTP, UPI PIN या पासवर्ड साझा न करें। पैसे प्राप्त करने के लिए UPI PIN डालने की जरूरत नहीं होती। यदि आपने रिमोट-एक्सेस ऐप इंस्टॉल किया या जानकारी साझा की है, तो बैंक से आधिकारिक माध्यम से तुरंत संपर्क करें और प्रभावित पासवर्ड बदलें।",
        "kyc": "तुरंत खाता बंद करने या KYC के नाम पर लिंक खोलने/फीस देने का दबाव चेतावनी का संकेत है। संदेश के लिंक या नंबर का उपयोग न करें। बैंक के आधिकारिक ऐप या कार्ड पर दिए नंबर से जांचें।",
        "authority": "फोन या वीडियो कॉल पर तुरंत गिरफ्तारी की धमकी और पैसे ट्रांसफर करने की मांग आम धोखाधड़ी के तरीके हैं। पैसे न भेजें। कॉल काटें और संबंधित संस्था से स्वतंत्र रूप से सत्यापित आधिकारिक माध्यम से संपर्क करें।",
        "emergency": "जल्दबाज़ी में पैसे भेजने से पहले रिश्तेदार या मित्र को उस नंबर पर कॉल करें जो आपके पास पहले से है। केवल आवाज़ या आने वाले कॉलर की पहचान पर भरोसा न करें।",
        "link": "संदेह होने पर लिंक न खोलें। डोमेन ध्यान से देखें, लेकिन सही दिखने वाला पता भी सुरक्षित होने का प्रमाण नहीं है। आधिकारिक ऐप खोलें या वेबसाइट का पता खुद टाइप करें।",
        "upi": "पैसे प्राप्त करने के लिए QR कोड स्कैन करना या collect request स्वीकार करना जरूरी नहीं है। स्क्रीन ध्यान से पढ़ें; UPI PIN डालने से आम तौर पर भुगतान अधिकृत होता है। अनजान अनुरोध रद्द करें और अलग माध्यम से पुष्टि करें।",
        "offer": "ऐसे ऑफर से सावधान रहें जो पहले फीस, जमा राशि या निश्चित मुनाफे का वादा करते हैं। स्वतंत्र रूप से जांच किए बिना पैसे या पहचान दस्तावेज न भेजें।",
        "general": "स्थिति को धीरे-धीरे समझते हैं। सामने वाले ने क्या करने को कहा—लिंक खोलना, कोड साझा करना, ऐप इंस्टॉल करना, भुगतान मंज़ूर करना या पैसे भेजना? कृपया निजी विवरण या गुप्त कोड न लिखें। दबाव महसूस हो तो रुकें और स्वतंत्र रूप से जांचें।"
    }
    return (answers_hi if hindi else answers_en)[intent]


def _clean_cell(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _money(value):
    """Parse common Indian bank statement amounts, including commas and Dr/Cr suffixes."""
    text = _clean_cell(value).replace("₹", "").replace("INR", "").replace(",", "")
    if not text or text in {"-", "—", "–"}:
        return None
    match = re.search(r"-?\d+(?:\.\d{1,2})?", text)
    if not match:
        return None
    try:
        return abs(float(match.group(0)))
    except ValueError:
        return None


def extract_statement_tables(pdf_bytes):
    """Extract tables from text-based PDFs. Does not persist the uploaded PDF."""
    import pdfplumber

    tables = []
    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text_pages.append(page.extract_text() or "")
            for table in (page.extract_tables() or []):
                cleaned = [[_clean_cell(cell) for cell in row] for row in table if row]
                cleaned = [row for row in cleaned if any(row)]
                if cleaned:
                    tables.append(cleaned)
    return tables, "\n".join(text_pages)


def _header_kind(header):
    h = re.sub(r"[^a-z0-9]+", " ", _clean_cell(header).lower()).strip()
    if any(k in h for k in ["date", "txn date", "transaction date", "value date"]):
        return "date"
    if any(k in h for k in ["narration", "description", "particular", "remarks", "transaction details", "payee", "beneficiary"]):
        return "description"
    if any(k in h for k in ["withdrawal", "debit", "money out", "dr amount", "debit amount"]):
        return "debit"
    if any(k in h for k in ["deposit", "credit", "money in", "cr amount", "credit amount"]):
        return "credit"
    if h in {"amount", "txn amount", "transaction amount", "amt"}:
        return "amount"
    if "balance" in h or "closing bal" in h:
        return "balance"
    if any(k in h for k in ["dr cr", "type", "transaction type"]):
        return "type"
    return "other"


def parse_statement_tables(tables):
    """Best-effort parser for common bank-statement table layouts."""
    records = []
    for table in tables:
        header_idx = None
        for i, row in enumerate(table[:8]):
            kinds = [_header_kind(cell) for cell in row]
            if "date" in kinds and ("description" in kinds or "debit" in kinds or "credit" in kinds or "amount" in kinds):
                header_idx = i
                break
        if header_idx is None:
            continue
        headers = table[header_idx]
        kinds = [_header_kind(cell) for cell in headers]
        for row in table[header_idx + 1:]:
            if len(row) < len(kinds):
                row = row + [""] * (len(kinds) - len(row))
            if len(row) > len(kinds):
                row = row[:len(kinds)]
            vals = dict(date="", description="", debit=None, credit=None, amount=None, balance=None, type="")
            for kind, val in zip(kinds, row):
                val = _clean_cell(val)
                if kind == "date" and not vals["date"]:
                    vals["date"] = val
                elif kind == "description":
                    vals["description"] = (vals["description"] + " " + val).strip()
                elif kind in {"debit", "credit", "amount", "balance"}:
                    parsed = _money(val)
                    if parsed is not None:
                        vals[kind] = parsed
                elif kind == "type":
                    vals["type"] = val.lower()
            if not vals["date"] or not vals["description"]:
                continue
            # Ignore repeated header rows and opening/closing balance summaries.
            if _header_kind(vals["date"]) == "date" or any(x in vals["description"].lower() for x in ["opening balance", "closing balance", "brought forward", "carried forward"]):
                continue
            debit, credit, amount = vals["debit"], vals["credit"], vals["amount"]
            if debit is None and credit is None and amount is not None:
                t = vals["type"] + " " + vals["description"].lower()
                if re.search(r"\b(cr|credit|deposit|received)\b", t):
                    credit = amount
                elif re.search(r"\b(dr|debit|withdrawal|paid|sent|upi)\b", t):
                    debit = amount
            if debit is None and credit is None:
                continue
            records.append({"Date": vals["date"], "Description": vals["description"],
                            "Debit (₹)": debit or 0.0, "Credit (₹)": credit or 0.0,
                            "Balance (₹)": vals["balance"]})
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates().reset_index(drop=True)
    return df


def parse_statement_text(text):
    """Parse common text-extracted bank statements, including wrapped transaction rows.

    This is a best-effort parser: every extracted row must be checked against the PDF.
    It prioritises currency-marked amounts to avoid treating transaction/UTR IDs as money.
    """
    if not text or not text.strip():
        return pd.DataFrame()

    date_token = r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[- ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[- ,]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})"
    date_re = re.compile(r"^\s*(" + date_token + r")\s*(.*)$", re.I)
    lines = [_clean_cell(line) for line in text.splitlines()]
    blocks = []
    current_date, current_parts = None, []
    for line in lines:
        if not line:
            continue
        match = date_re.match(line)
        if match:
            if current_date:
                blocks.append((current_date, " ".join(current_parts)))
            current_date = _clean_cell(match.group(1))
            current_parts = [match.group(2)] if match.group(2) else []
        elif current_date:
            # Wrapped lines often contain time, transaction reference and UTR details.
            current_parts.append(line)
    if current_date:
        blocks.append((current_date, " ".join(current_parts)))

    rows = []
    currency_amount_re = re.compile(r"(?:₹|INR\s*)(\s*-?\s*\d[\d,]*(?:\.\d{1,2})?)", re.I)
    generic_amount_re = re.compile(r"(?<![A-Za-z0-9])(-?\d[\d,]*\.\d{2})(?:\s*(CR|DR))?\b", re.I)
    for date, block in blocks:
        lower = block.lower()
        if any(term in lower for term in ["opening balance", "closing balance", "statement of account", "brought forward", "carried forward"]):
            continue

        # Prefer amounts explicitly marked as currency; transaction IDs are not currency.
        money_hits = list(currency_amount_re.finditer(block))
        amounts = []
        if money_hits:
            for hit in money_hits:
                value = _money(hit.group(1))
                if value is not None:
                    amounts.append((value, ""))
        else:
            # Only use generic amounts when there is a decimal amount and a clear debit/credit cue.
            for hit in generic_amount_re.finditer(block):
                value = _money(hit.group(1))
                if value is not None:
                    amounts.append((value, (hit.group(2) or "").upper()))

        if not amounts:
            continue
        credit_cue = bool(re.search(r"\b(cr|credit|deposit|received|refund|cashback)\b", lower))
        debit_cue = bool(re.search(r"\b(dr|debit|withdrawal|paid|sent|purchase|payment|upi|imps|neft|rtgs)\b", lower))
        debit = credit = 0.0

        tagged = [(value, tag) for value, tag in amounts if tag in {"CR", "DR"}]
        if tagged:
            for value, tag in tagged:
                if tag == "CR":
                    credit += value
                else:
                    debit += value
        elif credit_cue and not debit_cue:
            credit = amounts[0][0]
        elif debit_cue and not credit_cue:
            debit = amounts[0][0]
        elif credit_cue:
            credit = amounts[0][0]
        elif debit_cue:
            debit = amounts[0][0]
        else:
            # No reliable direction: don't invent a debit/credit classification.
            continue

        # Remove explicit currency values and reference identifiers from the display description.
        description = re.sub(r"(?:₹|INR\s*)\s*-?\s*\d[\d,]*(?:\.\d{1,2})?", " ", block, flags=re.I)
        description = re.sub(r"\b(?:transaction\s*id|utr\s*(?:no\.?|number)?|reference\s*(?:no\.?|number)?)\s*[:#-]?\s*[A-Z0-9/-]+", " ", description, flags=re.I)
        description = re.sub(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", " ", description, flags=re.I)
        description = _clean_cell(description).strip(" |:-")
        if not description:
            description = "Transaction description not fully extracted"
        rows.append({"Date": date, "Description": description, "Debit (₹)": debit,
                     "Credit (₹)": credit, "Balance (₹)": None})

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates().reset_index(drop=True)
    return df


def analyse_transactions(df):
    """Flag patterns for review; does not determine that any person is a scammer."""
    if df.empty:
        return df
    result = df.copy()
    result["Description"] = result["Description"].fillna("").astype(str)
    result["Debit (₹)"] = pd.to_numeric(result["Debit (₹)"], errors="coerce").fillna(0.0)
    result["Credit (₹)"] = pd.to_numeric(result["Credit (₹)"], errors="coerce").fillna(0.0)
    result["Review flags"] = ""
    outgoing = result["Debit (₹)"] > 0
    debit_values = result.loc[outgoing, "Debit (₹)"]
    median = float(debit_values.median()) if not debit_values.empty else 0.0
    desc_lower = result["Description"].str.lower()
    flags = [[] for _ in range(len(result))]
    # Repeated outgoing transfers with the same description are a weak signal only.
    normalized = desc_lower.str.replace(r"\d+", "", regex=True).str.replace(r"[^a-z ]", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    repeated = normalized[outgoing].value_counts()
    repeated_keys = set(repeated[repeated >= 3].index)
    for pos, (_, row) in enumerate(result.iterrows()):
        description = desc_lower.iloc[pos]
        if row["Debit (₹)"] > 0 and median > 0 and row["Debit (₹)"] >= max(10000, median * 3):
            flags[pos].append("Outgoing amount is unusually high versus this statement's median debit")
        if row["Debit (₹)"] > 0 and normalized.iloc[pos] in repeated_keys:
            flags[pos].append("Repeated outgoing transfers with similar descriptions")
        if row["Debit (₹)"] > 0 and re.search(r"\b(upi|imps|neft|rtgs|wallet|transfer|paytm|phonepe|gpay|google pay)\b", description):
            flags[pos].append("Electronic transfer — verify recipient and purpose")
        if re.search(r"\b(loan fee|kyc fee|account unlock|refund processing|prize|reward claim)\b", description):
            flags[pos].append("Description contains a phrase sometimes used in payment scams")
        if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+", row["Description"], re.I):
            flags[pos].append("UPI-style identifier found in description; historical verification needed")
    result["Review flags"] = ["; ".join(x) if x else "No obvious rule-based flag" for x in flags]
    result["Review priority"] = ["Review" if x else "No flag" for x in flags]
    return result


if "last_result" not in st.session_state: st.session_state.last_result = None
if "cases" not in st.session_state: st.session_state.cases = []
if "chat" not in st.session_state: st.session_state.chat = []

with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO), use_container_width=True)
    else:
        st.markdown("# SCUDO MONETA")
    st.markdown('<div class="eyebrow">CLEARER DECISIONS. SAFER PAYMENTS.</div>', unsafe_allow_html=True)
    st.write("")
    page=st.radio("Navigation", ["Protection Demo","Statement Scanner","Analyst Dashboard","Moneta Assistant","Safety & Privacy"], label_visibility="visible")
    st.markdown("---")
    st.caption("DEMO MODE · SYNTHETIC DATA ONLY")
    st.caption("No real UPI connection. No payments are made.")

# Header
col1,col2=st.columns([3,1])
with col1:
    st.markdown('<div class="eyebrow">AI-ASSISTED UPI SCAM PROTECTION</div>', unsafe_allow_html=True)
    st.title("SCUDO MONETA")
    st.markdown("### Make a more informed decision before you pay.")
    st.markdown('<span class="muted">A decision-support prototype designed to help people spot pressure tactics before they pay.</span>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="scudo-card" style="text-align:center"><div style="font-size:22px">SCUDO MONETA</div><b>YOU STAY IN CONTROL</b><br><span class="small">Never auto-blocks or accuses</span></div>', unsafe_allow_html=True)

if page=="Protection Demo":
    st.markdown("## Payment risk check")
    left,right=st.columns([1.05,0.95], gap="large")
    with left:
        with st.form("payment_form"):
            st.markdown("#### Payee & payment details")
            scenario=st.selectbox("Choose a synthetic scenario", list(SCAMS.keys())+list(NORMAL.keys()))
            defaults = NORMAL if scenario in NORMAL else SCAMS[scenario]
            payee=st.text_input("Recipient display name", value="Ravi Kumar" if scenario in NORMAL else "Unknown Receiver")
            amount=st.number_input("Amount (₹)", min_value=1, max_value=500000, value=25000 if scenario in SCAMS else 850, step=100)
            st.caption("All recipient names and amounts are fictional.")
            st.markdown("#### Context signals (simulated)")
            new_payee=st.checkbox("First payment to this recipient", value=defaults["new_payee"])
            unusual=st.checkbox("Amount is unusual for this payer", value=defaults["unusual_amount"])
            call=st.checkbox("Payer is currently on a call", value=defaults["active_call"])
            share=st.checkbox("Screen-sharing / remote-access app detected", value=defaults["screen_share"])
            repeats=st.slider("Recent payment attempts to this recipient",0,5,int(defaults["repeated_attempts"]))
            mule=st.checkbox("Receiver has synthetic mule-network pattern", value=defaults["mule_pattern"])
            submitted=st.form_submit_button("Check payment details", use_container_width=True)
        if submitted:
            tx={"new_payee":new_payee,"unusual_amount":unusual,"active_call":call,"screen_share":share,
                "repeated_attempts":repeats,"mule_pattern":mule}
            score,tier,action,reasons=risk_engine(tx)
            result={"scenario":scenario,"payee":payee,"amount":amount,"score":score,"tier":tier,"action":action,"reasons":reasons,"tx":tx}
            st.session_state.last_result=result
            st.session_state.cases.insert(0, {"time":datetime.now().strftime("%H:%M:%S"),"payee":payee,"amount":amount,"score":score,"tier":tier,"scenario":scenario})
    with right:
        result=st.session_state.last_result
        if result is None:
            st.markdown('<div class="scudo-card"><div class="eyebrow">LIVE RISK PREVIEW</div><h2>Ready when you are</h2><p class="muted">Choose a scenario and select “Check with SCUDO” to see how multiple signals change the recommended response.</p><hr><span class="chip">🟢 Low · Nudge</span><span class="chip">🟡 Medium · Pause</span><span class="chip">🔴 High · Human review</span></div>', unsafe_allow_html=True)
        else:
            color={"LOW":"#55e6b0","MEDIUM":"#ffc857","HIGH":"#ff667d"}[result["tier"]]
            st.markdown(f'<div class="scudo-card"><div class="eyebrow">SCUDO RISK ASSESSMENT</div><div style="display:flex;align-items:end;gap:12px"><div class="big-score" style="color:{color}">{result["score"]}</div><div class="muted">/ 100 risk indicator</div></div><h2 style="color:{color}!important">{result["tier"]} RISK</h2><p>{result["action"]}</p><div class="small">Scenario: {result["scenario"]}</div></div>', unsafe_allow_html=True)
            st.progress(result["score"]/100)
            st.markdown("#### Why SCUDO raised this")
            if result["reasons"]:
                for title,desc in result["reasons"]:
                    st.markdown(f'<div class="scudo-card" style="padding:12px 15px;margin-bottom:7px"><b>⚠️ {title}</b><br><span class="muted">{desc}</span></div>', unsafe_allow_html=True)
            else:
                st.success("No strong risk signals were selected. Stay alert and verify payment details.")
            if result["tier"]=="LOW":
                st.info("Safety nudge: verify the payee name and amount before continuing.")
            elif result["tier"]=="MEDIUM":
                st.warning("Suggested demo flow: wait 10 minutes and ask a trusted person to review. This is a simulation; no real hold is placed.")
                st.button("Simulate 10-minute pause", key="pause_low")
            else:
                st.error("Suggested demo flow: contact your bank through its official channel for human review. SCUDO does not accuse the recipient or block a payment.")
            st.caption("Risk score is a prototype heuristic, not a validated probability of fraud.")
    st.markdown("---")
    st.markdown("## Scam patterns covered")
    cols=st.columns(5)
    for c,(name,details) in zip(cols,SCAMS.items()):
        with c:
            st.markdown(f'<div class="scudo-card" style="min-height:150px"><div style="font-size:22px">{"📞" if "call" in name.lower() or "arrest" in name.lower() else "🧾"}</div><b>{name}</b><p class="small">{details["message"]}</p></div>', unsafe_allow_html=True)

elif page=="Statement Scanner":
    st.markdown("## Statement review")
    st.markdown("Upload a PDF statement you are authorised to use. SCUDO will attempt to extract transaction tables and flag patterns that may deserve a closer look.")
    st.warning("Privacy: use a demo or redacted statement where possible. This prototype processes the uploaded PDF in memory and does not save it. Never upload your UPI PIN, OTP, passwords or banking login details.")
    pdf_file = st.file_uploader("Upload transaction history PDF", type=["pdf"], key="statement_pdf")
    if pdf_file is not None:
        if pdf_file.size > 15 * 1024 * 1024:
            st.error("This prototype accepts PDFs up to 15 MB.")
        else:
            if st.button("Analyse statement", use_container_width=True):
                try:
                    tables, extracted_text = extract_statement_tables(pdf_file.getvalue())
                    parsed = parse_statement_tables(tables)
                    parser_method = "table extraction"
                    if parsed.empty and extracted_text.strip():
                        parsed = parse_statement_text(extracted_text)
                        parser_method = "text-line fallback"
                    if parsed.empty:
                        if not extracted_text.strip():
                            st.error("No selectable text was found. This may be a scanned/image-only PDF; OCR is not enabled in this prototype.")
                        else:
                            st.warning("SCUDO could read text, but could not confidently identify a transaction table in this statement layout.")
                            st.caption("Bank statement formats vary. Do not treat unparsed content as analysed.")
                            with st.expander("Preview extracted text (check for private information before sharing)"):
                                st.text(extracted_text[:6000])
                    else:
                        analysed = analyse_transactions(parsed)
                        outgoing_total = float(analysed["Debit (₹)"].sum())
                        incoming_total = float(analysed["Credit (₹)"].sum())
                        flagged = int((analysed["Review priority"] == "Review").sum())
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Transactions extracted", f"{len(analysed)}")
                        m2.metric("Total outgoing", f"₹{outgoing_total:,.2f}")
                        m3.metric("Total incoming", f"₹{incoming_total:,.2f}")
                        m4.metric("Transactions to review", f"{flagged}")
                        st.caption(f"Extraction method: {parser_method}. Please check dates and amounts against the original statement before relying on this result.")
                        st.markdown("### Transactions that may need review")
                        review_rows = analysed[analysed["Review priority"] == "Review"]
                        if review_rows.empty:
                            st.success("No transactions matched the current prototype rules. This does not prove the statement is safe.")
                        else:
                            st.dataframe(review_rows, use_container_width=True, hide_index=True)
                        with st.expander("View all extracted transactions"):
                            st.dataframe(analysed, use_container_width=True, hide_index=True)
                        st.download_button("Download analysis as CSV", analysed.to_csv(index=False).encode("utf-8"), "scudo_statement_review.csv", "text/csv")
                        st.info("These are explainable screening signals, not proof of fraud. SCUDO cannot identify a person as a scammer from a transaction description alone, verify ownership of an account, contact a recipient, or reverse/block a payment. Confirm concerns with your bank through an official channel.")
                except Exception as exc:
                    st.error("The PDF could not be processed. Try a text-based PDF statement or a redacted statement exported directly from your bank.")
                    st.caption(f"Technical detail: {type(exc).__name__}")

elif page=="Analyst Dashboard":
    st.markdown("## Analyst dashboard")
    df=synthetic_cases(1000)
    if st.session_state.cases:
        cases=pd.DataFrame(st.session_state.cases)
        high=int((cases["tier"]=="HIGH").sum())
        med=int((cases["tier"]=="MEDIUM").sum())
        low=int((cases["tier"]=="LOW").sum())
    else:
        high,med,low=124,283,593
    a,b,c,d=st.columns(4)
    a.metric("Synthetic transactions", "1,000")
    b.metric("High-risk flags", f"{high}")
    c.metric("Alerts / 1,000 demo users", "42.0")
    d.metric("Precision / recall", "Synthetic only")
    st.caption("All dashboard data and metrics are synthetic placeholders. They are not real-world model results.")
    left,right=st.columns(2)
    with left:
        st.markdown("### Risk tiers in synthetic dataset")
        tier_counts=df["tier"].value_counts().reindex(["LOW","MEDIUM","HIGH"],fill_value=0)
        st.bar_chart(tier_counts)
    with right:
        st.markdown("### Scam pattern mix")
        st.bar_chart(df[df["label"]==1]["scenario"].value_counts())
    st.markdown("### Recent demo cases")
    if st.session_state.cases:
        st.dataframe(pd.DataFrame(st.session_state.cases), use_container_width=True, hide_index=True)
    else:
        st.info("Run a payment simulation first to create local demo cases.")
    st.markdown("### Synthetic receiver fan-in example")
    graph_df=pd.DataFrame({"Receiver":["RX-104","RX-104","RX-104","RX-104","RX-104","RX-221","RX-221"],
                           "Payer":["New payer A","New payer B","New payer C","New payer D","New payer E","New payer F","New payer G"],
                           "Amount (₹)":[9500,12000,8900,15000,9900,2100,1800]})
    st.dataframe(graph_df,use_container_width=True,hide_index=True)
    st.warning("A fan-in pattern is a review signal, not proof of wrongdoing. Human review is required.")
    st.download_button("Download synthetic case data (CSV)", df.to_csv(index=False).encode("utf-8"), "scudo_synthetic_cases.csv", "text/csv")

elif page=="Moneta Assistant":
    st.markdown("## Moneta Assistant")
    st.markdown("Describe what happened and get practical next steps. Do not enter personal or banking details.")
    st.caption("Local guidance assistant. Replies are based on common scam scenarios; it does not contact banks or file reports.")
    language=st.radio("Response language",["English","हिन्दी"],horizontal=True)
    for who,msg in st.session_state.chat:
        with st.chat_message(who):
            st.write(msg)
    question=st.chat_input("Describe the situation (please don't enter personal or account details)…")
    if question:
        # Do not persist raw question in a backend or file; shown only in current Streamlit session.
        st.session_state.chat.append(("user",question))
        answer=chatbot_reply(question,language)
        st.session_state.chat.append(("assistant",answer))
        st.rerun()
    st.markdown("**Quick questions**")
    qcols=st.columns(3)
    quick=["Someone says my KYC will expire","A caller says a family member is in danger","I already sent money, how do I report?"]
    for col,q in zip(qcols,quick):
        with col:
            if st.button(q, use_container_width=True):
                st.session_state.chat.append(("user",q))
                st.session_state.chat.append(("assistant",chatbot_reply(q,language)))
                st.rerun()

else:
    st.markdown("## Safety, privacy and limitations")
    st.markdown('<div class="scudo-card"><h3>What SCUDO does</h3><p>It combines several simulated signals, explains why a transaction may deserve a second look, and recommends a proportionate next step.</p><h3>What SCUDO never collects in this prototype</h3><ul><li>No message contents stored</li><li>No contacts or address book</li><li>No audio or call recordings</li><li>No UPI PIN, OTP, bank login, or real account data</li><li>No real payment or automatic payment block</li></ul><h3>False positives & false negatives</h3><p>A legitimate payment can look unusual (false positive); a carefully staged scam can look normal (false negative). Keep messages actionable, allow users to continue after an informed review in the simulation, and route high-risk cases to a bank/human review rather than accusation.</p><h3>Bias & adaptation</h3><p>Validate separately across languages, age groups, regions, and accessibility needs. Do not use age or language as a standalone risk signal. Scammers adapt; monitor drift and update synthetic test scenarios with expert review.</p><h3>Alert budget</h3><p>This demo displays illustrative alert counts only. A production alert budget should cap alerts per 1,000 users/day, deduplicate repeated warnings, and tune thresholds using audited feedback.</p></div>', unsafe_allow_html=True)
    st.caption("This is a hackathon prototype, not a bank product or a validated fraud detector. Verify current reporting instructions through official RBI, NPCI, bank, and cybercrime channels.")

st.markdown("---")
st.markdown('<div style="text-align:center;color:#87a4bc;font-size:12px">SCUDO MONETA · Demonstration prototype · You stay in control</div>', unsafe_allow_html=True)
