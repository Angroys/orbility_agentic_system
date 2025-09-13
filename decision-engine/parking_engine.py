from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
import re, sqlite3, json, datetime as dt
from difflib import SequenceMatcher
from fastapi import FastAPI

app = FastAPI(title="Parking Intent & Rule Engine", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}
# ==========
# Config / Policy
# ==========
class Policy(BaseModel):
    grace_minutes: int = 15
    defer_window_hours: int = 24
    penalty_eur: float = 40.0
    max_defers_per_12m: int = 1
    fuzzy_threshold: float = 0.83

DEFAULT_POLICY = Policy()

DB_PATH = "Parking.sqlite"  # set to your actual path

# ==========
# Models
# ==========
class IntentRequest(BaseModel):
    transcript: str

class DecideRequest(BaseModel):
    # Either give transcript (we infer intent) or provide intent explicitly
    transcript: Optional[str] = None
    intent: Optional[str] = None

    # Slots (some can be inferred from transcript in your DIA):
    vrn: Optional[str] = None
    ticket_id: Optional[str] = None
    entry_time_hint: Optional[str] = None  # ISO

    # Context
    queue_len: int = 0
    has_card: Optional[bool] = None
    terminal_status: Optional[str] = None  # "ok" | "error" | "unknown"

    # Policy override (optional)
    policy: Optional[Policy] = None

class DecisionOut(BaseModel):
    decision: str
    actions: List[Dict[str, Any]]
    reasoning: List[str]
    session_id: Optional[str] = None
    audit: Dict[str, Any] = {}

# ==========
# Utilities
# ==========
def now_utc() -> dt.datetime:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)

def parse_bool_from_text(t: str, yes_words=("yes","y","da","true"), no_words=("no","n","nu","false")) -> Optional[bool]:
    t = t.lower()
    if any(w in t for w in yes_words): return True
    if any(w in t for w in no_words): return False
    return None

def normalize_vrn(v: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", v.upper()) if v else v

VRN_PAT = re.compile(r"\b([A-Z]{1,3}\s*\d{1,4}\s*[A-Z]{0,3}|\d{2,3}\s*[A-Z]{1,3}\s*\d{2,4})\b", re.IGNORECASE)

def extract_vrn_candidates(text: str) -> List[str]:
    cands = [normalize_vrn(m.group(1)) for m in VRN_PAT.finditer(text or "")]
    return [c for c in cands if 3 <= len(c) <= 8]

# ==========
# Intent (rule-based MVP, RO+EN phrases)
# ==========
INTENTS = ("payment_issue", "payment_not_registered", "lost_ticket", "vrn_mismatch", "other")
INTENT_PATTERNS = {
    "lost_ticket": [
        r"\blost\b.*\bticket\b", r"\bticket\b.*\blost\b",
        r"\bbilet\b.*\bpierdut\b", r"\bpierdut\b.*\bbilet\b",
    ],
    "payment_not_registered": [
        r"\bpaid\b.*\bnot\b", r"\bpayment\b.*\bnot\b.*(shown|processed|registered)",
        r"\bam plătit\b.*\bnu\b", r"\bplata\b.*\bnu\b.*(apare|procesată|înregistrată)",
    ],
    "payment_issue": [
        r"(can't|cannot|unable).*\bpay\b", r"\bno card\b", r"\bfără card\b",
        r"\bmachine\b.*(broken|error)", r"\bterminal\b.*(broken|error|stricat|eroare)",
        r"\bnu pot plăti\b", r"\bnu am card\b",
    ],
    "vrn_mismatch": [
        r"\b(plate|number|număr)\b.*(wrong|incorrect|mismatch|nu.*corect)",
        r"\bnu\b.*\b(mașina mea|numărul meu)\b",
    ],
}

def detect_intent(transcript: str) -> str:
    t = transcript.lower() if transcript else ""
    for intent, pats in INTENT_PATTERNS.items():
        for p in pats:
            if re.search(p, t): return intent
    return "other"

def extract_slots_from_transcript(transcript: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    # VRN candidates
    cands = extract_vrn_candidates(transcript or "")
    if cands:
        slots["vrn"] = cands[0]
        if len(cands) > 1:
            slots["vrn_candidates"] = list(dict.fromkeys(cands))  # unique, keep order

    # Terminal status heuristic
    t = (transcript or "").lower()
    if re.search(r"(machine|terminal).*(broken|error|stricat|eroare)", t):
        slots["terminal_status"] = "error"
    # Has card
    if re.search(r"\bno card\b|\bfără card\b", t):
        slots["has_card"] = False
    elif re.search(r"\b(am card|have (a )?card)\b", t):
        slots["has_card"] = True

    # Paid claim
    if re.search(r"\b(am plătit|i paid|i have paid)\b", t):
        slots["claims_paid"] = True

    return slots

# ==========
# DB Adapter (EVENT-centric)
# Types assumed: ENTRY, EXIT, CHARGE, PAYMENT, DEFER_CREATED, ALLOW_CROSSING, NOTE, UPDATE_VRN
# ==========
def db_conn():
    return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)

def find_active_session_by_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    if not ticket_id: return None
    q = """
    WITH entries AS (
      SELECT session_id, MIN(ts) as entry_ts
      FROM EVENT WHERE type='ENTRY' AND ticket_id = ?
      GROUP BY session_id
    ),
    exits AS (
      SELECT session_id, MAX(ts) as exit_ts
      FROM EVENT WHERE type='EXIT'
      GROUP BY session_id
    )
    SELECT e.session_id, e.entry_ts
    FROM entries e
    LEFT JOIN exits x ON x.session_id = e.session_id
    WHERE x.exit_ts IS NULL OR x.exit_ts < e.entry_ts
    ORDER BY e.entry_ts DESC LIMIT 1;
    """
    with db_conn() as c:
        row = c.execute(q, (ticket_id,)).fetchone()
    if not row: return None
    return {"session_id": row[0], "entry_ts": row[1]}

def find_active_session_by_vrn(vrn: str) -> Optional[Dict[str, Any]]:
    if not vrn: return None
    q = """
    WITH entries AS (
      SELECT session_id, vrn, MIN(ts) as entry_ts
      FROM EVENT WHERE type='ENTRY' AND UPPER(REPLACE(vrn,' ','')) = UPPER(REPLACE(?, ' ',''))
      GROUP BY session_id, vrn
    ),
    exits AS (
      SELECT session_id, MAX(ts) as exit_ts
      FROM EVENT WHERE type='EXIT'
      GROUP BY session_id
    )
    SELECT e.session_id, e.entry_ts
    FROM entries e
    LEFT JOIN exits x ON x.session_id = e.session_id
    WHERE x.exit_ts IS NULL OR x.exit_ts < e.entry_ts
    ORDER BY e.entry_ts DESC LIMIT 1;
    """
    with db_conn() as c:
        row = c.execute(q, (vrn,)).fetchone()
    if not row: return None
    return {"session_id": row[0], "entry_ts": row[1]}

def fuzzy_find_vrn_candidate(vrn: str) -> Optional[str]:
    if not vrn: return None
    query = "SELECT DISTINCT UPPER(REPLACE(vrn,' ','')) FROM EVENT WHERE vrn IS NOT NULL;"
    with db_conn() as c:
        rows = [r[0] for r in c.execute(query).fetchall()]
    target = normalize_vrn(vrn)
    best, score = None, 0.0
    for candidate in rows:
        s = SequenceMatcher(None, candidate, target).ratio()
        if s > score:
            best, score = candidate, s
    return best if score >= DEFAULT_POLICY.fuzzy_threshold else None

def payment_status_for_session(session_id: str) -> Dict[str, Any]:
    q = """
    SELECT
      SUM(CASE WHEN type='CHARGE'  THEN amount ELSE 0 END) as amount_due,
      SUM(CASE WHEN type='PAYMENT' THEN amount ELSE 0 END) as amount_paid,
      MAX(CASE WHEN type='PAYMENT' THEN ts ELSE NULL END) as last_payment_ts,
      MIN(CASE WHEN type='ENTRY'   THEN ts ELSE NULL END) as entry_ts
    FROM EVENT WHERE session_id = ?;
    """
    with db_conn() as c:
        row = c.execute(q, (session_id,)).fetchone()
    amount_due = row[0] or 0.0
    amount_paid = row[1] or 0.0
    entry_ts = row[3]
    status = "PAID" if amount_due <= amount_paid else "UNPAID"
    return {"status": status, "amount_due": amount_due, "amount_paid": amount_paid, "entry_ts": entry_ts}

def defers_used_for_session(session_id: str) -> int:
    q = "SELECT COUNT(*) FROM EVENT WHERE session_id = ? AND type='DEFER_CREATED';"
    with db_conn() as c:
        return c.execute(q, (session_id,)).fetchone()[0]

def create_event(session_id: str, etype: str, payload: Dict[str, Any]) -> None:
    q = "INSERT INTO EVENT(session_id, type, ts, payload, amount) VALUES (?, ?, ?, ?, NULL);"
    payload_json = json.dumps(payload, ensure_ascii=False)
    with db_conn() as c:
        c.execute(q, (session_id, etype, now_utc().isoformat(), payload_json))
        c.commit()

def update_vrn(session_id: str, old_vrn: str, new_vrn: str) -> None:
    q = "INSERT INTO EVENT(session_id, type, ts, vrn, payload) VALUES (?, 'UPDATE_VRN', ?, ?, ?);"
    payload_json = json.dumps({"old": old_vrn, "new": new_vrn}, ensure_ascii=False)
    with db_conn() as c:
        c.execute(q, (session_id, now_utc().isoformat(), new_vrn, payload_json))
        c.commit()

# ==========
# Rule Engine (deterministic)
# ==========
def rule_engine(ctx: Dict[str, Any], policy: Policy) -> DecisionOut:
    """
    ctx keys expected:
      intent, queue_len, has_card, terminal_status, session, pay, defers_used,
      fuzzy_candidate (optional), vrn (optional)
    """
    rsn: List[str] = []
    intent = ctx.get("intent", "other")
    qlen = int(ctx.get("queue_len", 0))
    has_card = ctx.get("has_card")
    term_stat = ctx.get("terminal_status")
    sess = ctx.get("session")
    pay = ctx.get("pay")
    defers = int(ctx.get("defers_used", 0))
    vrn = ctx.get("vrn")
    fuzzy = ctx.get("fuzzy_candidate")

    # Moderation / guardrails could go here (not shown)

    # LOST TICKET
    if intent == "lost_ticket":
        if sess:
            rsn += ["intent=lost_ticket", "session_found=true"]
            actions = [
                {"type": "ISSUE_LOST_TICKET", "params": {"session_id": sess["session_id"]}},
                {"type": "ALLOW_CROSSING", "params": {"session_id": sess["session_id"]}},
                {"type": "LOG_EVENT", "params": {"event": "lost_ticket_issued"}}
            ]
            create_event(sess["session_id"], "LOST_TICKET_ISSUED", {"by": "bot"})
            create_event(sess["session_id"], "ALLOW_CROSSING", {"reason": "lost_ticket"})
            return DecisionOut(decision="OPEN", actions=actions, reasoning=rsn, session_id=sess["session_id"])
        else:
            rsn += ["intent=lost_ticket", "session_found=false"]
            return DecisionOut(decision="ESCALATE", actions=[{"type": "ESCALATE_OPERATOR"}], reasoning=rsn)

    # VRN MISMATCH
    if intent == "vrn_mismatch":
        if sess and fuzzy:
            rsn += ["intent=vrn_mismatch", "fuzzy_match=true"]
            update_vrn(sess["session_id"], old_vrn=vrn or "unknown", new_vrn=fuzzy)
            create_event(sess["session_id"], "NOTE", {"msg": "VRN corrected via fuzzy match"})
            create_event(sess["session_id"], "ALLOW_CROSSING", {"reason": "vrn_corrected"})
            actions = [
                {"type": "UPDATE_VRN", "params": {"session_id": sess["session_id"], "new_vrn": fuzzy}},
                {"type": "ALLOW_CROSSING", "params": {"session_id": sess["session_id"]}}
            ]
            return DecisionOut(decision="OPEN", actions=actions, reasoning=rsn, session_id=sess["session_id"])
        else:
            rsn += ["intent=vrn_mismatch", "fuzzy_match=false_or_no_session"]
            return DecisionOut(decision="ESCALATE", actions=[{"type": "ESCALATE_OPERATOR"}], reasoning=rsn)

    # PAYMENT NOT REGISTERED
    if intent == "payment_not_registered":
        if pay and pay["status"] == "PAID":
            rsn += ["intent=payment_not_registered", "status=PAID → OPEN"]
            create_event(sess["session_id"], "ALLOW_CROSSING", {"reason": "payment_verified"})
            return DecisionOut(
                decision="OPEN",
                actions=[{"type": "ALLOW_CROSSING", "params": {"session_id": sess["session_id"]}}],
                reasoning=rsn, session_id=sess["session_id"]
            )
        else:
            rsn += ["intent=payment_not_registered", "status!=PAID → DENY"]
            return DecisionOut(decision="DENY", actions=[{"type": "INSTRUCT_PAY_NOW"}], reasoning=rsn, session_id=sess["session_id"] if sess else None)

    # PAYMENT ISSUE (no card / terminal error / cannot pay now)
    if intent == "payment_issue":
        # If queue is large and defers available => DEFER + OPEN
        if qlen >= 3 and defers < policy.max_defers:
            rsn += ["intent=payment_issue", f"queue_len={qlen}>=3", f"defers_used={defers}<{policy.max_defers}", "→ DEFER_OPEN"]
            create_event(sess["session_id"], "DEFER_CREATED", {
                "deadline": (now_utc() + dt.timedelta(hours=policy.defer_window_hours)).isoformat(),
                "penalty_eur": policy.penalty_eur
            })
            create_event(sess["session_id"], "ALLOW_CROSSING", {"reason": "defer"})
            actions = [
                {"type": "CREATE_DEFER", "params": {"session_id": sess["session_id"], "deadline_hours": policy.defer_window_hours, "penalty_eur": policy.penalty_eur}},
                {"type": "ALLOW_CROSSING", "params": {"session_id": sess["session_id"]}},
                {"type": "PENALIZE_IF_UNPAID", "params": {"session_id": sess["session_id"], "after_hours": policy.defer_window_hours, "penalty_eur": policy.penalty_eur}}
            ]
            return DecisionOut(decision="DEFER_OPEN", actions=actions, reasoning=rsn, session_id=sess["session_id"])
        # Else deny and instruct pay now / reverse
        rsn += ["intent=payment_issue", "→ DENY"]
        return DecisionOut(decision="DENY", actions=[{"type": "INSTRUCT_REVERSE_AND_PAY"}], reasoning=rsn, session_id=sess["session_id"] if sess else None)

    # Default / Other
    return DecisionOut(decision="ESCALATE", actions=[{"type": "ESCALATE_OPERATOR"}], reasoning=["intent=other"])

# ==========
# Orchestrator helpers
# ==========
def resolve_session(vrn: Optional[str], ticket_id: Optional[str], policy: Policy) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Returns (session_dict, fuzzy_candidate_or_None)."""
    sess = None
    fuzzy = None
    if ticket_id:
        sess = find_active_session_by_ticket(ticket_id)
    if not sess and vrn:
        sess = find_active_session_by_vrn(vrn)
        if not sess:
            fuzzy = fuzzy_find_vrn_candidate(vrn)
            if fuzzy:
                sess = find_active_session_by_vrn(fuzzy)
    return sess, fuzzy

# ==========
# FastAPI
# ==========
app = FastAPI(title="Parking Intent & Rule Engine", version="0.1.0")

@app.post("/intent")
def api_intent(req: IntentRequest):
    intent = detect_intent(req.transcript)
    slots = extract_slots_from_transcript(req.transcript)
    return {"intent": intent, "slots": slots}

@app.post("/decide", response_model=DecisionOut)
def api_decide(req: DecideRequest):
    policy = req.policy or DEFAULT_POLICY

    # 1) intent
    intent = req.intent or detect_intent(req.transcript or "")
    slots = extract_slots_from_transcript(req.transcript or "") if req.transcript else {}
    vrn = normalize_vrn(req.vrn or slots.get("vrn"))
    has_card = req.has_card if req.has_card is not None else slots.get("has_card")
    term_status = req.terminal_status or slots.get("terminal_status")

    # 2) session resolve (via ticket or vrn, with fuzzy fallback)
    sess, fuzzy = resolve_session(vrn=vrn, ticket_id=req.ticket_id, policy=policy)

    # 3) payment & defers
    pay = payment_status_for_session(sess["session_id"]) if sess else None
    defers = defers_used_for_session(sess["session_id"]) if sess else 0

    # 4) rules
    ctx = {
        "intent": intent,
        "queue_len": req.queue_len,
        "has_card": has_card,
        "terminal_status": term_status,
        "session": sess,
        "pay": pay,
        "defers_used": defers,
        "vrn": vrn,
        "fuzzy_candidate": fuzzy
    }
    decision = rule_engine(ctx, policy)

    # 5) include audit snippet
    decision.audit = {
        "input": {
            "intent": intent, "slots": {"vrn": vrn, "has_card": has_card, "terminal_status": term_status},
            "queue_len": req.queue_len
        },
        "session": sess,
        "payment": pay,
        "policy": policy.dict(),
    }
    return decision
