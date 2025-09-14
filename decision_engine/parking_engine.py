from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
import re, sqlite3, json, datetime as dt, os
from difflib import SequenceMatcher

# ==========
# App
# ==========
app = FastAPI(title="Parking Intent & Rule Engine", version="0.3.0")


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

DB_PATH = os.getenv("DB_PATH", "/data/Parking.db")
BASE_URL = os.getenv("PARKING_BASE_URL", "https://parking.local")


# ==========
# Models
# ==========
class IntentRequest(BaseModel):
    transcript: str


class DecideRequest(BaseModel):
    transcript: Optional[str] = None
    intent: Optional[str] = None
    vrn: Optional[str] = None
    ticket_id: Optional[str] = None
    entry_time_hint: Optional[str] = None
    queue_len: int = 0
    has_card: Optional[bool] = None
    terminal_status: Optional[str] = None
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


def normalize_vrn(v: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", v.upper()) if v else v


VRN_PAT = re.compile(r"\b([A-Z]{1,3}\s*\d{1,4}\s*[A-Z]{0,3}|\d{2,3}\s*[A-Z]{1,3}\s*\d{2,4})\b", re.IGNORECASE)


def extract_vrn_candidates(text: str) -> List[str]:
    cands = [normalize_vrn(m.group(1)) for m in VRN_PAT.finditer(text or "")]
    return [c for c in cands if 3 <= len(c) <= 8]


# ==========
# Intents
# ==========
INTENTS = ("payment_issue", "payment_not_registered", "lost_ticket", "vrn_mismatch", "other")

INTENT_PATTERNS = {
    "lost_ticket": [
        r"\blost\b.*\bticket\b", r"\bticket\b.*\blost\b",
        r"\bbilet\b.*\bpierdut\b", r"\bpierdut\b.*\bbilet\b",
        r"\b(can't find|cannot find|don't have)\b.*\b(ticket|card)\b",
        r"\bwithout\b.*\bticket\b", r"\bhave no ticket\b",
    ],
    "vrn_mismatch": [
        r"\b(plate|number|număr)\b.*(wrong|incorrect|mismatch)",
        r"\b(license plate|registration|tag)\b.*(not.*match|different|wrong)",
    ],
    "payment_not_registered": [r"\bpaid\b.*\bnot\b", r"\bpayment\b.*\bnot\b.*(shown|processed|registered)"],
    "payment_issue": [r"(can't|cannot|unable).*\bpay\b", r"\bmachine\b.*(broken|error)"],
}


def detect_intent(transcript: str) -> str:
    t = transcript.lower() if transcript else ""
    for intent, pats in INTENT_PATTERNS.items():
        for p in pats:
            if re.search(p, t):
                return intent
    return "other"


def extract_slots_from_transcript(transcript: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    cands = extract_vrn_candidates(transcript or "")
    if cands:
        slots["vrn"] = cands[0]
        if len(cands) > 1:
            slots["vrn_candidates"] = list(dict.fromkeys(cands))
    return slots


# ==========
# DB Adapter
# ==========
def db_conn():
    try:
        return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


def find_active_session_by_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    q = """
    SELECT s.id, s.entry_time, s.status
    FROM session s
    JOIN ticket t ON t.id = s.ticket_id
    WHERE t.id = ? AND s.status IN ('ACTIVE','PAID','OVERDUE')
    ORDER BY s.entry_time DESC LIMIT 1;
    """
    with db_conn() as c:
        row = c.execute(q, (ticket_id,)).fetchone()
    return {"session_id": row[0], "entry_ts": row[1], "status": row[2]} if row else None


def find_active_session_by_vrn(vrn: str) -> Optional[Dict[str, Any]]:
    q = """
    SELECT id, entry_time, status
    FROM session
    WHERE UPPER(REPLACE(licence_plate_entry,' ','')) = UPPER(REPLACE(?,' ',''))
      AND status IN ('ACTIVE','PAID','OVERDUE')
    ORDER BY entry_time DESC LIMIT 1;
    """
    with db_conn() as c:
        row = c.execute(q, (vrn,)).fetchone()
    return {"session_id": row[0], "entry_ts": row[1], "status": row[2]} if row else None



def fuzzy_find_vrn_candidate(vrn: str) -> Optional[str]:
    q = "SELECT DISTINCT UPPER(REPLACE(licence_plate_entry,' ','')) FROM session WHERE licence_plate_entry IS NOT NULL;"
    with db_conn() as c:
        rows = [r[0] for r in c.execute(q).fetchall()]
    target = normalize_vrn(vrn)
    best, score = None, 0.0
    for candidate in rows:
        s = SequenceMatcher(None, candidate, target).ratio()
        if s > score:
            best, score = candidate, s
    return best if score >= DEFAULT_POLICY.fuzzy_threshold else None


def payment_status_for_session(session_id: int) -> Dict[str, Any]:
    q = """
    SELECT 
        s.amount_due_cents,
        s.amount_paid_cents,
        COALESCE(SUM(p.amount_cents), 0) AS total_approved,
        s.entry_time
    FROM session s
    LEFT JOIN payment p ON p.session_id = s.id AND p.approved = 1
    WHERE s.id = ?
    GROUP BY s.id;
    """
    with db_conn() as c:
        row = c.execute(q, (session_id,)).fetchone()

    if not row:
        return {"status": "UNKNOWN", "amount_due": 0, "amount_paid": 0, "entry_ts": None}

    due, paid, approved, entry_ts = row
    paid_total = (paid or 0) + (approved or 0)

    status = "PAID" if paid_total >= due else "ACTIVE"
    return {"status": status, "amount_due": due, "amount_paid": paid_total, "entry_ts": entry_ts}


def defers_used_for_session(session_id: int) -> int:
    q = "SELECT COUNT(*) FROM event WHERE session_id = ? AND type='DEFER_CREATED';"
    with db_conn() as c:
        return c.execute(q, (session_id,)).fetchone()[0]


def create_event(session_id: int, etype: str, payload: Dict[str, Any], station_id: Optional[int] = None) -> None:
    q = "INSERT INTO event(session_id, station_id, type, occurred_at, payload_json) VALUES (?, ?, ?, ?, ?);"
    payload_json = json.dumps(payload, ensure_ascii=False)
    with db_conn() as c:
        c.execute(q, (session_id, station_id, etype, now_utc().isoformat(), payload_json))
        c.commit()


def update_vrn(session_id: int, old_vrn: str, new_vrn: str) -> None:
    payload_json = json.dumps({"old": old_vrn, "new": new_vrn}, ensure_ascii=False)
    with db_conn() as c:
        c.execute(
            "INSERT INTO event(session_id, station_id, type, occurred_at, payload_json) VALUES (?, NULL, 'UPDATE_VRN', ?, ?);",
            (session_id, now_utc().isoformat(), payload_json),
        )
        c.execute("UPDATE session SET licence_plate_entry = ? WHERE id = ?;", (new_vrn, session_id))
        c.commit()


# ==========
# Rule Engine
# ==========
# ==========
# Rule Engine
# ==========
def rule_engine(ctx: Dict[str, Any], policy: Policy) -> DecisionOut:
    rsn: List[str] = []
    intent = ctx.get("intent", "other")
    sess = ctx.get("session")
    pay = ctx.get("pay")
    vrn = ctx.get("vrn")
    fuzzy = ctx.get("fuzzy_candidate")

    def escalate(reasoning: List[str], fraud: bool = False):
        return DecisionOut(
            decision="ESCALATE",
            actions=[{"type": "ESCALATE_OPERATOR"}],
            reasoning=reasoning,
            session_id=str(sess["session_id"]) if sess else None,
            audit={"fraud": fraud}  # mark fraud here
        )

    def qr_voice(reasoning: List[str], actions_extra: Optional[List[Dict[str, Any]]] = None):
        actions = [
            {"type": "GENERATE_QR", "params": {
                "session_id": sess["session_id"],
                "qr_url": f"{BASE_URL}/pay/{sess['session_id']}"
            }},
            {"type": "VOICE_WARNING", "params": {"text": "Please complete your payment."}},
        ]
        if actions_extra:
            actions.extend(actions_extra)
        return DecisionOut(
            decision="QR_VOICE",
            actions=actions,
            reasoning=reasoning,
            session_id=str(sess["session_id"])
        )

    # LOST TICKET
    if intent == "lost_ticket":
        if sess:
            rsn += ["intent=lost_ticket", "session_found=true", f"session_status={sess['status']}"]

            if pay and pay["status"] == "PAID":
                return escalate(rsn + ["payment=PAID but ticket lost → possible fraud"], fraud=True)

            if sess["status"].upper() in ("ACTIVE", "OVERDUE"):
                return escalate(rsn + ["fraud_suspected=lost_ticket_with_active_or_overdue_session"], fraud=True)

            return escalate(rsn + ["unhandled_session_status"])
        return escalate(["intent=lost_ticket", "session_found=false"])




# ==========
# Orchestrator
# ==========
def resolve_session(vrn: Optional[str], ticket_id: Optional[str], policy: Policy) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    sess, fuzzy = None, None
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
# API Endpoints
# ==========
@app.post("/intent")
def api_intent(req: IntentRequest):
    intent = detect_intent(req.transcript)
    slots = extract_slots_from_transcript(req.transcript)
    return {"intent": intent, "slots": slots}


@app.post("/decide", response_model=DecisionOut)
def api_decide(req: DecideRequest):
    policy = req.policy or DEFAULT_POLICY
    intent = req.intent or detect_intent(req.transcript or "")
    slots = extract_slots_from_transcript(req.transcript or "") if req.transcript else {}
    vrn = normalize_vrn(req.vrn or slots.get("vrn"))

    sess, fuzzy = resolve_session(vrn, req.ticket_id, policy)

    pay, defers = None, 0
    if sess and "session_id" in sess:
        try:
            pay = payment_status_for_session(sess["session_id"])
            defers = defers_used_for_session(sess["session_id"])
        except Exception as e:
            pay = {"status": "UNKNOWN", "error": str(e)}

    ctx = {
        "intent": intent,
        "queue_len": req.queue_len,
        "has_card": req.has_card,
        "terminal_status": req.terminal_status,
        "session": sess,
        "pay": pay,
        "defers_used": defers,
        "vrn": vrn,
        "fuzzy_candidate": fuzzy,
    }

    decision = rule_engine(ctx, policy)

    # merge audit info instead of overwriting
    decision.audit.update({
        "input": {"intent": intent, "vrn": vrn},
        "session": sess,
        "payment": pay,
        "policy": policy.dict(),
    })

    return decision

