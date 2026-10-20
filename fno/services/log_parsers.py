"""
Authoritative Log Parsers and Evaluators for Phase 22 Acceptance Audits.

Provides shared, fail-safe parsers for watchdog reconnection logs,
desired-universe reconciliation logs, and look-ahead-free completed spot bar timing.
Used across live-session audits, automated regression suites, and verification scripts.
"""

import datetime
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# 1. AC-1-L03: Watchdog Reconnection Parser & Pairing Evaluator
# ============================================================================

WATCHDOG_INIT_PATTERN = re.compile(
    r"^\[(.*?)\]\s+\[WATCHDOG\] Connection inactive\. Attempting reconnect #(\d+)(?:\s+\(backoff:\s+[0-9.]+s\)\.\.\.)?$"
)
WATCHDOG_SUCC_PATTERN = re.compile(
    r"^\[(.*?)\]\s+\[WATCHDOG\] Reconnected successfully on attempt #(\d+)\.\s+Restored (\d+) instrument subscriptions\.$"
)
WATCHDOG_PENDING_PATTERN = re.compile(
    r"^\[(.*?)\]\s+\[WATCHDOG\] Reconnection #(\d+) pending\.\s+Next attempt in [0-9.]+s\.$"
)


def evaluate_watchdog_log(
    text: str,
    expected_subscriptions: Optional[int] = None,
    min_subscriptions: int = 1,
    max_duration_sec: float = 5.0
) -> Dict[str, Any]:
    """
    Authoritative watchdog reconnection log parser and pairing evaluator.

    Parses timestamped watchdog events, strictly validates ISO-8601 timestamps,
    enforces timezone awareness and non-decreasing chronological order,
    and pairs each reconnect initiation attempt #N with its corresponding
    success attempt #N.

    Args:
        text: Raw log text containing watchdog events.
        expected_subscriptions: Optional exact count of subscriptions expected
            (e.g., 22 for NIFTY K=5 option universe). If None, requires count >= min_subscriptions.
        min_subscriptions: Minimum required restored subscriptions (default: 1).
        max_duration_sec: Maximum allowable reconnect elapsed seconds (default: 5.0s).

    Returns:
        dict containing:
            - verdict: Short classification string (e.g. PASS, FAIL, INCONCLUSIVE (...))
            - status: AC-1-L03 status string
            - evidence: DATA_CHECK classification
            - details: Human-readable diagnostic description
            - pairs: List of validated event pairs with calculated duration and restored count
            - events: All parsed recognized events
    """
    events: List[Dict[str, Any]] = []
    lines = text.strip().splitlines()

    for line_idx, line in enumerate(lines, 1):
        line_clean = line.strip()
        if not line_clean:
            continue

        if "[WATCHDOG]" in line_clean or "Attempting reconnect" in line_clean:
            m_init = WATCHDOG_INIT_PATTERN.search(line_clean)
            m_succ = WATCHDOG_SUCC_PATTERN.search(line_clean)
            m_pend = WATCHDOG_PENDING_PATTERN.search(line_clean)

            if not (m_init or m_succ or m_pend):
                return {
                    "verdict": "INCONCLUSIVE (UNRECOGNIZED_WATCHDOG_EVENT)",
                    "status": "NOT TESTED (UNRECOGNIZED_WATCHDOG_EVENT)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Unrecognized/malformed watchdog event on line {line_idx}: \"{line_clean[:80]}\"",
                    "pairs": [],
                    "events": []
                }

            matched = m_init or m_succ or m_pend
            ts_str = matched.group(1)
            try:
                ts = datetime.datetime.fromisoformat(ts_str)
            except Exception as e:
                return {
                    "verdict": "INCONCLUSIVE (MALFORMED_TIMESTAMPS)",
                    "status": "NOT TESTED (MALFORMED_TIMESTAMPS)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Malformed timestamp \"{ts_str}\" on line {line_idx}: {e}",
                    "pairs": [],
                    "events": []
                }

            if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
                return {
                    "verdict": "INCONCLUSIVE (MISSING_TIMEZONE_OFFSET)",
                    "status": "NOT TESTED (MISSING_TIMEZONE_OFFSET)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Missing timezone offset in timestamp on line {line_idx}: {ts_str}",
                    "pairs": [],
                    "events": []
                }

            if events and ts < events[-1]["ts"]:
                prev_raw = events[-1]["raw"]
                return {
                    "verdict": "INCONCLUSIVE (INVALID_CHRONOLOGICAL_ORDER)",
                    "status": "NOT TESTED (INVALID_CHRONOLOGICAL_ORDER)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Invalid chronological order on line {line_idx}: timestamp {ts_str} precedes previous {prev_raw}",
                    "pairs": [],
                    "events": []
                }

            if m_init:
                events.append({"type": "init", "ts": ts, "attempt": int(m_init.group(2)), "raw": ts_str, "line": line_idx})
            elif m_succ:
                events.append({"type": "succ", "ts": ts, "attempt": int(m_succ.group(2)), "count": int(m_succ.group(3)), "raw": ts_str, "line": line_idx})
            elif m_pend:
                events.append({"type": "pending", "ts": ts, "attempt": int(m_pend.group(2)), "raw": ts_str, "line": line_idx})

    if not events:
        return {
            "verdict": "NOT TESTED (NO_EVENTS)",
            "status": "NOT TESTED (NO_NATURAL_DISCONNECT)",
            "evidence": "DATA_CHECK_INCONCLUSIVE",
            "details": "Zero [WATCHDOG] reconnect events found. Network connection remained stable throughout session.",
            "pairs": [],
            "events": []
        }

    pairs: List[Dict[str, Any]] = []
    active_init: Optional[Dict[str, Any]] = None
    active_pending: Optional[Dict[str, Any]] = None
    cycle_start: Optional[datetime.datetime] = None

    for ev in events:
        ev_type = ev["type"]
        att = ev["attempt"]

        if ev_type == "init":
            if active_init is not None:
                if active_init["attempt"] == att:
                    return {
                        "verdict": "INCONCLUSIVE (DUPLICATE_INITIATION_UNMATCHED)",
                        "status": "NOT TESTED (DUPLICATE_INITIATION_UNMATCHED)",
                        "evidence": "DATA_CHECK_INCONCLUSIVE",
                        "details": f"Duplicate initiation for attempt #{att}",
                        "pairs": [],
                        "events": events
                    }
                if active_pending is None:
                    return {
                        "verdict": "INCONCLUSIVE (DUPLICATE_INITIATION_UNMATCHED)",
                        "status": "NOT TESTED (DUPLICATE_INITIATION_UNMATCHED)",
                        "evidence": "DATA_CHECK_INCONCLUSIVE",
                        "details": f"Attempt #{att} initiated while attempt #{active_init['attempt']} was still pending without retry status",
                        "pairs": [],
                        "events": events
                    }
            active_init = ev
            active_pending = None
            if cycle_start is None:
                cycle_start = ev["ts"]

        elif ev_type == "pending":
            if active_init is None:
                return {
                    "verdict": "INCONCLUSIVE (UNCORRELATED_WATCHDOG_EVENTS)",
                    "status": "NOT TESTED (UNCORRELATED_WATCHDOG_EVENTS)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Retry/pending event for attempt #{att} without preceding initiation",
                    "pairs": [],
                    "events": events
                }
            if active_init["attempt"] != att:
                return {
                    "verdict": "INCONCLUSIVE (ATTEMPT_ID_MISMATCH)",
                    "status": "NOT TESTED (ATTEMPT_ID_MISMATCH)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Retry event attempt #{att} does not match active initiation attempt #{active_init['attempt']}",
                    "pairs": [],
                    "events": events
                }
            if active_pending is not None:
                return {
                    "verdict": "INCONCLUSIVE (CONTRADICTORY_WATCHDOG_EVENTS)",
                    "status": "NOT TESTED (CONTRADICTORY_WATCHDOG_EVENTS)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Duplicate retry/pending event for attempt #{att}",
                    "pairs": [],
                    "events": events
                }
            active_pending = ev

        elif ev_type == "succ":
            if active_init is None:
                return {
                    "verdict": "INCONCLUSIVE (ORPHAN_SUCCESS_EVENT)",
                    "status": "NOT TESTED (ORPHAN_SUCCESS_EVENT)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Success event for attempt #{att} arrived without preceding initiation",
                    "pairs": [],
                    "events": events
                }
            if active_init["attempt"] != att:
                return {
                    "verdict": "INCONCLUSIVE (ATTEMPT_ID_MISMATCH)",
                    "status": "NOT TESTED (ATTEMPT_ID_MISMATCH)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Success attempt #{att} does not match initiation attempt #{active_init['attempt']}",
                    "pairs": [],
                    "events": events
                }
            if active_pending is not None and active_pending["attempt"] == att:
                return {
                    "verdict": "INCONCLUSIVE (CONTRADICTORY_WATCHDOG_EVENTS)",
                    "status": "NOT TESTED (CONTRADICTORY_WATCHDOG_EVENTS)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Attempt #{att} contains contradictory pending retry and success events",
                    "pairs": [],
                    "events": events
                }

            cycle_dur = (ev["ts"] - cycle_start).total_seconds()
            attempt_dur = (ev["ts"] - active_init["ts"]).total_seconds()
            if cycle_dur < 0.0 or attempt_dur < 0.0:
                return {
                    "verdict": "INCONCLUSIVE (INVALID_CHRONOLOGICAL_ORDER)",
                    "status": "NOT TESTED (INVALID_CHRONOLOGICAL_ORDER)",
                    "evidence": "DATA_CHECK_INCONCLUSIVE",
                    "details": f"Negative reconnect duration: success at {ev['raw']} precedes initiation at {active_init['raw']}",
                    "pairs": [],
                    "events": events
                }

            pairs.append({
                "init": active_init,
                "succ": ev,
                "attempt": att,
                "cycle_start": cycle_start,
                "duration": cycle_dur,
                "attempt_duration": attempt_dur,
                "count": ev["count"]
            })
            active_init = None
            active_pending = None
            cycle_start = None

    if active_init is not None:
        if active_pending is not None:
            return {
                "verdict": "INCONCLUSIVE (UNRESOLVED_RETRY_SEQUENCE)",
                "status": "NOT TESTED (UNRESOLVED_RETRY_SEQUENCE)",
                "evidence": "DATA_CHECK_INCONCLUSIVE",
                "details": f"Reconnection attempt #{active_init['attempt']} pending but subsequent recovery never succeeded",
                "pairs": [],
                "events": events
            }
        return {
            "verdict": "INCONCLUSIVE (UNRESOLVED_RECONNECT_INITIATION)",
            "status": "NOT TESTED (UNRESOLVED_RECONNECT_INITIATION)",
            "evidence": "DATA_CHECK_INCONCLUSIVE",
            "details": f"Reconnection attempt #{active_init['attempt']} initiated but never concluded",
            "pairs": [],
            "events": events
        }

    if not pairs:
        return {
            "verdict": "INCONCLUSIVE (UNCORRELATED_WATCHDOG_EVENTS)",
            "status": "NOT TESTED (UNCORRELATED_WATCHDOG_EVENTS)",
            "evidence": "DATA_CHECK_INCONCLUSIVE",
            "details": "Uncorrelated watchdog events detected: no complete reconnect pairs found",
            "pairs": [],
            "events": events
        }

    fail_reasons: List[str] = []
    unverified_reasons: List[str] = []

    for idx, p in enumerate(pairs, 1):
        dur = p["duration"]
        cnt = p["count"]
        att = p["attempt"]

        if dur > max_duration_sec:
            fail_reasons.append(f"Pair #{idx} (attempt #{att}): recovery duration {dur:.3f}s exceeded {max_duration_sec:.1f}s threshold")

        if cnt is None or cnt < min_subscriptions:
            fail_reasons.append(f"Pair #{idx} (attempt #{att}): invalid restored subscription count {cnt} (must be >= {min_subscriptions})")
        elif expected_subscriptions is None:
            unverified_reasons.append(
                f"Pair #{idx} (attempt #{att}): restored {cnt} subscriptions, but expected_subscriptions was not provided by caller and cannot be verified"
            )
        elif cnt != expected_subscriptions:
            fail_reasons.append(
                f"Pair #{idx} (attempt #{att}): restored {cnt} subscriptions, but expected universe count is {expected_subscriptions}"
            )

    if fail_reasons:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": "DATA_CHECK_FAIL",
            "details": f"Reconnection quality criteria failed: {'; '.join(fail_reasons)}",
            "pairs": pairs,
            "events": events
        }

    if unverified_reasons:
        return {
            "verdict": "INCONCLUSIVE (UNVERIFIED_SUBSCRIPTION_COUNT)",
            "status": "NOT TESTED (UNVERIFIED_SUBSCRIPTION_COUNT)",
            "evidence": "DATA_CHECK_INCONCLUSIVE",
            "details": f"Subscription count unverified: {'; '.join(unverified_reasons)}",
            "pairs": pairs,
            "events": events
        }

    pair_cnt = len(pairs)
    return {
        "verdict": "PASS",
        "status": "PASS",
        "evidence": "DATA_CHECK_PASS",
        "details": f"All {pair_cnt} reconnect event(s) recovered in <= {max_duration_sec:.1f}s with subscriptions restored ({expected_subscriptions})",
        "pairs": pairs,
        "events": events
    }


# ============================================================================
# 2. AC-1-L05: Desired-Universe Reconciliation Log Parser
# ============================================================================

RECONCILE_LINE_PATTERN = re.compile(
    r"^\[([^\]]+)\]\s+(?:.*?\b)?Universe reconciled:\s+\+(\d+)\s+subscribed,\s+-(\d+)\s+unsubscribed\.\s+Active tokens:\s+(\d+)\s+\(ATM:\s+([0-9.]+)\)$"
)


def parse_reconciliation_events(text: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Parses and strictly validates reconciliation events from daemon logs.

    Pre-scans all lines to detect any relevant reconciliation message before regex parsing.
    Any relevant line that fails the strict pattern, contains a malformed timestamp,
    lacks timezone offset, or arrives out of order invalidates the reconciliation log stream,
    returning an error message that prevents a PASS outcome.

    Returns:
        (matches, error):
            - matches: List of valid reconciliation event dicts (empty if an error occurred).
            - error: Error description string if any relevant line was malformed/unrecognized/out-of-order,
                     or None if all relevant lines parsed cleanly.
    """
    matches: List[Dict[str, Any]] = []
    lines = text.strip().splitlines()

    for line_num, line in enumerate(lines, 1):
        line_clean = line.strip()
        if not line_clean:
            continue

        # Detect all relevant reconciliation messages before regex parsing
        if "Universe reconciled" in line_clean or "reconcil" in line_clean.lower():
            m = RECONCILE_LINE_PATTERN.match(line_clean)
            if not m:
                return [], f"Line {line_num}: Unrecognized or malformed reconciliation event text: \"{line_clean[:80]}\""

            ts_str, sub_c, unsub_c, act_c, atm_s = m.groups()
            try:
                ts = datetime.datetime.fromisoformat(ts_str)
            except Exception as ex:
                return [], f"Line {line_num}: Malformed reconciliation timestamp \"{ts_str}\": {ex}"

            if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
                return [], f"Line {line_num}: Timezone-naive timestamp in reconciliation event: {ts_str}"

            if matches and ts < matches[-1]["ts"]:
                prev_raw = matches[-1]["raw"]
                return [], f"Line {line_num}: Out-of-order reconciliation event: {ts_str} preceded previous {prev_raw}"

            matches.append({
                "ts": ts,
                "sub": int(sub_c),
                "unsub": int(unsub_c),
                "active": int(act_c),
                "atm": Decimal(atm_s),
                "raw": ts_str,
                "line": line_num
            })

    return matches, None


def evaluate_reconciliation_verdict(matches: List[Dict[str, Any]], error: Optional[str]) -> Dict[str, Any]:
    """
    Computes log evidence validity from parsed reconciliation events.

    Strictly prevents PASS whenever error is not None.

    NOTE: A status of 'VALID_LOG_EVENTS' or 'can_pass: True' signifies ONLY that
    the log stream parsed without corruption or chronological anomalies.
    It DOES NOT independently grant an AC-1-L05 acceptance PASS.
    The final acceptance verdict additionally requires:
      - Authoritative transition timing at bar close
      - Desired universe set equality against observed quote tokens
      - Verification of active token count invariants (e.g. 22)
      - Zero lingering extra tokens after the unsubscription grace period.
    """
    if error is not None:
        return {
            "can_pass": False,
            "status": "NOT TESTED (RECONCILIATION_EVIDENCE_INCONCLUSIVE)",
            "evidence": "DATA_CHECK_INCONCLUSIVE",
            "details": f"Reconciliation evidence invalidated: {error}"
        }
    if not matches:
        return {
            "can_pass": False,
            "status": "NOT TESTED (NO_RECONCILIATION_EVENTS)",
            "evidence": "DATA_CHECK_INCONCLUSIVE",
            "details": "Zero reconciliation events found in log"
        }
    return {
        "can_pass": True,
        "status": "VALID_LOG_EVENTS",
        "evidence": "DATA_CHECK_PASS",
        "details": f"{len(matches)} reconciliation events validated"
    }


# ============================================================================
# 3. AC-1-L02: Look-Ahead-Free Completed Spot Bar Timing Convention
# ============================================================================

def get_latest_completed_spot_bar(
    spot_bars: List[Any],
    as_of_time: datetime.datetime,
    bar_duration: datetime.timedelta = datetime.timedelta(minutes=1)
) -> Optional[Any]:
    """
    Selects the latest completed spot bar available at as_of_time without look-ahead bias.

    In OHLCVBar, `timestamp` denotes the bar OPENING time.
    A bar covering [b.timestamp, b.timestamp + bar_duration) is completed and its
    `close` price is formed only at `b.timestamp + bar_duration`.

    Therefore, at evaluation time `as_of_time` (e.g. the start of an option interval slot),
    a spot candle's close is available ONLY if:
        b.timestamp + bar_duration <= as_of_time

    Any bar where `b.timestamp + bar_duration > as_of_time` (including a bar where
    `b.timestamp == as_of_time`, which is currently in-flight) is strictly rejected
    as not yet completed to eliminate look-ahead bias.

    Ordering Guarantee:
    Enforces chronological ordering on `b.timestamp` internally using `max(..., key=lambda b: b.timestamp)`.
    Even if the caller passes an unsorted or reversely-ordered iterable of spot bars,
    the chronologically latest completed bar is guaranteed to be returned.

    Args:
        spot_bars: Iterable/list of spot OHLCVBar instances (need not be pre-sorted).
        as_of_time: The evaluation boundary timestamp (e.g. slot start time).
        bar_duration: The duration of the spot bar (default: 1 minute).

    Returns:
        The latest OHLCVBar whose conclusion was at or prior to as_of_time, or None.
    """
    completed = [b for b in spot_bars if (b.timestamp + bar_duration) <= as_of_time]
    if not completed:
        return None
    return max(completed, key=lambda b: b.timestamp)


DAEMON_ACTIVITY_MARKERS = (
    "[HEARTBEAT]",
    "[SNAPSHOT]",
    "[FNO]",
    "Live ticker streaming active",
    "Connecting to Kite WebSocket",
    "Universe reconciled:",
    "Subscribing to",
)


def extract_verified_disconnect_intervals(
    log_text: str,
    max_duration_sec: float = 5.0,
    expected_subscriptions: Optional[int] = None,
) -> Tuple[List[Tuple[datetime.datetime, datetime.datetime]], bool, str]:
    """
    Extracts verified disconnect intervals using the shared evaluate_watchdog_log parser.
    Ensures that only strictly parsed and chronologically paired events establish intervals.
    Does not guess or mark arbitrary neighboring minutes.
    Does not assume 22 as a universal default subscription count.

    Completeness Rules for Zero-Disconnect Sessions:
    - Empty logs or whitespace-only strings do NOT prove a complete log (returns is_valid=False).
    - Logs lacking watchdog events must contain verified daemon activity markers
      (e.g. [HEARTBEAT], [SNAPSHOT], [FNO], 'Live ticker streaming active') to establish session
      completeness (returns is_valid=True, intervals=[]).
    - Logs without watchdog events and without daemon activity markers cannot establish
      completeness (returns is_valid=False).
    - If disconnect events exist but expected_subscriptions is None, subscription count is
      unverified, so is_valid=False.
    - If disconnect events fail subscription count check, is_valid=False.

    Returns:
        (intervals, is_valid, summary)
    """
    if not log_text or not log_text.strip():
        return [], False, "EMPTY_LOG_FILE (Log text is empty; cannot establish session completeness or network stability)"

    res = evaluate_watchdog_log(
        log_text,
        max_duration_sec=max_duration_sec,
        expected_subscriptions=expected_subscriptions,
    )

    if res["verdict"] == "NOT TESTED (NO_EVENTS)":
        has_daemon_markers = any(m in log_text for m in DAEMON_ACTIVITY_MARKERS)
        if has_daemon_markers:
            return [], True, "VALID_LOGS_ZERO_DISCONNECT_EVENTS (Daemon streaming active with 0 disconnect events)"
        return [], False, "INCONCLUSIVE_LOG_COMPLETENESS (Log contains no watchdog events and no verified daemon activity markers to establish session completeness)"

    if "INCONCLUSIVE" in res["verdict"]:
        return [], False, f"MALFORMED_DISCONNECT_EVIDENCE ({res['details']})"

    if res["verdict"] == "FAIL":
        # Known subscription count mismatch must never establish valid disconnect intervals
        if any("subscriptions" in reason.lower() for reason in res.get("details", "").split(";")):
            return [], False, f"MALFORMED_DISCONNECT_EVIDENCE ({res['details']})"
        intervals = [(p.get("cycle_start", p["init"]["ts"]), p["succ"]["ts"]) for p in res.get("pairs", [])]
        return intervals, True, f"VALID_LOGS_WITH_DISCONNECTS ({len(intervals)} verified disconnect intervals, recovery exceeded duration benchmark)"

    pairs = res.get("pairs", [])
    if pairs:
        intervals = [(p.get("cycle_start", p["init"]["ts"]), p["succ"]["ts"]) for p in pairs]
        return intervals, True, f"VALID_LOGS_WITH_DISCONNECTS ({len(intervals)} verified disconnect intervals, within benchmark)"

    return [], False, f"MALFORMED_DISCONNECT_EVIDENCE ({res.get('details', 'Uncorrelated or invalid watchdog evidence')})"


def is_bar_within_disconnect_interval(
    bar_start_ts: datetime.datetime,
    bar_duration: datetime.timedelta,
    disconnect_intervals: List[Tuple[datetime.datetime, datetime.datetime]]
) -> bool:
    """
    Checks if a bar [bar_start_ts, bar_start_ts + bar_duration) temporally overlaps
    with any verified disconnect interval [d_start, d_end].
    Does NOT mark or infer arbitrary neighboring minutes.
    """
    bar_end_ts = bar_start_ts + bar_duration
    for d_start, d_end in disconnect_intervals:
        if d_start < bar_end_ts and d_end > bar_start_ts:
            return True
    return False


def evaluate_option_bar_coverage_verdict(
    expected_slots_count: int,
    present_expected_slots: int,
    pipeline_drops: List[Any],
    unverified_missing_slots: List[Any],
    uncorrelated_partial_bars: int,
    unverified_partial_bars: int,
    duplicates: int,
    ohlc_errors: int,
    vol_errors: int,
    invalid_oi_count: int,
    disconnect_evidence_valid: bool,
    disconnect_evidence_summary: str,
) -> Dict[str, Any]:
    """
    Computes AC-1-L02 coverage and integrity acceptance verdict with strict precedence.

    Outcome Precedence:
    1. Zero expected slots -> INCONCLUSIVE (awaiting live session data).
    2. Confirmed pipeline drops (snapshots exist for slot, but bar absent) -> FAIL.
       (CRITICAL: Evaluated BEFORE checking whether persisted bars is zero, to prevent
        a total aggregation outage from being masked as 'inconclusive / awaiting data').
    3. Uncorrelated partial bars (partial bar with no verified disconnect) -> FAIL.
    4. Expected universe data integrity errors (duplicates, OHLC, volume, OI status) -> FAIL.
    5. Partial bars present with disconnect evidence unavailable or malformed -> INCONCLUSIVE.
    6. Expected slots missing without tick telemetry -> INCONCLUSIVE (insufficient telemetry).
    7. Disconnect evidence malformed -> INCONCLUSIVE.
    8. 100% expected completed coverage verified with 0 integrity errors -> PASS.
    """
    if expected_slots_count == 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (Awaiting live session data)",
            "evidence": "DATA_CHECK_INCONCLUSIVE (Zero expected slots in window)",
        }

    # Precedence Rule 1: Confirmed pipeline drops MUST fail immediately, even if present_expected_slots is 0
    if len(pipeline_drops) > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({len(pipeline_drops)} pipeline drops: snapshots arrived but completed bar was not persisted)",
        }

    if uncorrelated_partial_bars > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({uncorrelated_partial_bars} partial bars in expected universe could not be correlated with a verified disconnect event)",
        }

    integrity_errors = duplicates + ohlc_errors + vol_errors + invalid_oi_count
    if integrity_errors > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL (Expected universe integrity errors: duplicates={duplicates}, ohlc={ohlc_errors}, vol={vol_errors}, oi_errors={invalid_oi_count})",
        }

    if unverified_partial_bars > 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (PARTIAL_BAR_CORRELATION_UNAVAILABLE)",
            "evidence": f"DATA_CHECK_INCONCLUSIVE ({unverified_partial_bars} partial bars in expected universe cannot be correlated because disconnect log evidence is unavailable or malformed: {disconnect_evidence_summary})",
        }

    if len(unverified_missing_slots) > 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (INSUFFICIENT_TELEMETRY)",
            "evidence": f"DATA_CHECK_INCONCLUSIVE ({len(unverified_missing_slots)} expected slots lack bars and broker tick telemetry cannot confirm inactivity)",
        }

    if not disconnect_evidence_valid:
        if disconnect_evidence_summary.startswith("MALFORMED_DISCONNECT_EVIDENCE"):
            status_tag = "MALFORMED_DISCONNECT_EVIDENCE"
        else:
            status_tag = "DISCONNECT_EVIDENCE_UNAVAILABLE"
        return {
            "verdict": "INCONCLUSIVE",
            "status": f"NOT TESTED ({status_tag})",
            "evidence": f"DATA_CHECK_INCONCLUSIVE (Disconnect log evidence is invalid or unavailable to establish network stability: {disconnect_evidence_summary})",
        }

    if present_expected_slots == expected_slots_count:
        return {
            "verdict": "PASS",
            "status": "PASS",
            "evidence": f"DATA_CHECK_PASS (100% expected completed coverage verified: {present_expected_slots} bars persisted, 0 integrity errors in expected universe)",
        }

    return {
        "verdict": "INCONCLUSIVE",
        "status": "NOT TESTED",
        "evidence": "DATA_CHECK_INCONCLUSIVE",
    }


# ============================================================================
# 5. AC-1-L01: Equity Table Isolation & Bounded Activity Evaluator
# ============================================================================

def evaluate_equity_isolation_verdict(
    fno_quotes: int,
    fno_bars: int,
    contaminated_instruments: int,
    contaminated_bars: int,
    contaminated_contexts: int,
) -> Dict[str, Any]:
    """
    Computes AC-1-L01 equity isolation verdict with strict outcome precedence:

    1. If fno_quotes == 0 and fno_bars == 0:
       No active ingestion was observed within the bounded window [start_window, now].
       Future-dated records (> now) cannot prove ingestion.
       Returns INCONCLUSIVE / NOT TESTED (F&O_INGESTION_INACTIVE).
    2. Contamination detected in equity tables (any count > 0) -> FAIL.
    3. Active ingestion verified (>0 quotes or bars in window) AND zero contamination -> PASS.
    """
    if fno_quotes == 0 and fno_bars == 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (F&O_INGESTION_INACTIVE)",
            "evidence": "DATA_CHECK_INCONCLUSIVE (F&O ingestion inactive in observation window; zero records in OptionQuoteSnapshot and OptionOHLCVBar within bounded window)",
        }

    total_contamination = contaminated_instruments + contaminated_bars + contaminated_contexts
    if total_contamination > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL (Contamination detected in equity tables: instruments={contaminated_instruments}, bars={contaminated_bars}, contexts={contaminated_contexts})",
        }

    return {
        "verdict": "PASS",
        "status": "PASS",
        "evidence": "DATA_CHECK_PASS (Strict equity isolation verified while F&O stream active in bounded window)",
    }


# ============================================================================
# 6. AC-1-L04: Quote Snapshot Freshness & Dynamic ATM Acceptance Evaluator
# ============================================================================

def evaluate_quote_snapshot_integrity(
    snapshot: Any,
    now: datetime.datetime,
    max_age_seconds: float = 3.0,
    max_future_skew_seconds: float = 0.0,
) -> Dict[str, Any]:
    """
    Evaluates a single OptionQuoteSnapshot for timestamp semantics, dynamic freshness at 'now',
    depth validity, order book conditions (locked/crossed), and execution eligibility.

    Explicitly distinguishes:
    - exchange_timestamp_utc: timestamp assigned by exchange matching engine.
    - received_wall_clock_utc: local arrival timestamp at the daemon.
    - dyn_age: (now - exchange_timestamp_utc).total_seconds() at observation time.
    """
    received_wall_clock_utc = getattr(snapshot, "received_wall_clock_utc", None)
    if received_wall_clock_utc and received_wall_clock_utc > now:
        return {
            "is_valid_for_window": False,
            "status": "FUTURE_RECEIPT_EXCLUDED",
            "dyn_age": None,
            "is_fresh": False,
            "is_eligible": False,
            "mismatch": False,
        }

    is_stale_ingest = getattr(snapshot, "is_stale", False)
    quote_status = getattr(snapshot, "quote_status", "VALID")
    exchange_time_status = getattr(snapshot, "exchange_time_status", "VALID")
    exch_ts = getattr(snapshot, "exchange_timestamp_utc", None)
    best_bid = getattr(snapshot, "best_bid", None)
    best_ask = getattr(snapshot, "best_ask", None)
    is_locked = getattr(snapshot, "is_locked", False)
    is_crossed = getattr(snapshot, "is_crossed", False)
    depth = getattr(snapshot, "depth", None)
    stored_eligible = getattr(snapshot, "is_execution_eligible", False)

    is_locked_quote = (
        is_locked
        or (best_bid is not None and best_ask is not None and best_bid == best_ask)
        or (quote_status == "LOCKED")
    )
    is_crossed_quote = (
        is_crossed
        or (best_bid is not None and best_ask is not None and best_bid > best_ask)
        or (quote_status == "CROSSED")
    )
    is_zero_bid = (quote_status == "ZERO_BID") or (best_bid is not None and best_bid <= Decimal("0.0"))
    is_missing_depth = (
        quote_status == "EMPTY_BOOK"
        or best_bid is None
        or best_ask is None
        or not depth
        or not isinstance(depth, dict)
        or not depth.get("buy")
        or not depth.get("sell")
    )

    expected_eligible = (
        exchange_time_status == "VALID"
        and quote_status == "VALID"
        and not is_stale_ingest
        and not is_locked_quote
        and not is_crossed_quote
        and not is_zero_bid
        and not is_missing_depth
        and best_bid is not None and best_bid > Decimal("0.0")
        and best_ask is not None and best_ask > best_bid
        and exch_ts is not None
    )
    mismatch = (stored_eligible != expected_eligible)

    if exchange_time_status != "VALID" or exch_ts is None:
        status_obs = "INVALID_TIME_STATUS"
        dyn_age = None
        is_fresh = False
    else:
        dyn_age = (now - exch_ts).total_seconds()
        if dyn_age < -max_future_skew_seconds:
            status_obs = "FUTURE_SKEW"
            is_fresh = False
        elif dyn_age > max_age_seconds:
            status_obs = "STALE_AT_OBS"
            is_fresh = False
        elif quote_status == "INVALID":
            status_obs = "INVALID_QUOTE_STATUS"
            is_fresh = False
        elif is_stale_ingest:
            status_obs = "STALE_AT_INGESTION"
            is_fresh = False
        elif is_crossed_quote:
            status_obs = "CROSSED_BOOK"
            is_fresh = False
        elif is_locked_quote:
            # Locked book is valid market data (e.g. circuit limit) with fresh age <= 3.0s,
            # but is strictly ineligible for paper execution (is_eligible = False).
            status_obs = "LOCKED_BOOK"
            is_fresh = True
        elif mismatch:
            status_obs = "ELIGIBILITY_MISMATCH"
            is_fresh = True
        elif is_missing_depth:
            status_obs = "MISSING_DEPTH"
            is_fresh = True
        elif is_zero_bid:
            status_obs = "ZERO_BID"
            is_fresh = True
        elif not stored_eligible:
            status_obs = "NOT_EXECUTION_ELIGIBLE"
            is_fresh = True
        else:
            status_obs = "FRESH_AND_ELIGIBLE"
            is_fresh = True

    return {
        "is_valid_for_window": True,
        "status": status_obs,
        "dyn_age": dyn_age,
        "is_fresh": is_fresh,
        "is_eligible": stored_eligible,
        "expected_eligible": expected_eligible,
        "mismatch": mismatch,
    }


def evaluate_quote_freshness_and_universe_verdict(
    expected_tokens_count: int,
    tokens_with_quotes: int,
    fresh_and_eligible: int,
    stale_at_obs: int,
    future_skew: int,
    stale_at_ingestion: int,
    invalid_time_status: int,
    invalid_quote_status: int,
    locked_quotes: int,
    crossed_quotes: int,
    missing_depth_quotes: int,
    zero_bid_quotes: int,
    persisted_eligibility_mismatches: int,
    other_ineligible_quotes: int,
    unfulfilled_subscriptions_count: int,
    total_snapshots: int = 0,
) -> Dict[str, Any]:
    """
    Computes AC-1-L04 quote freshness and dynamic ATM acceptance verdict with strict precedence:

    1. Zero snapshots or unresolvable expected universe -> INCONCLUSIVE (Awaiting live session data).
    2. Any confirmed defect -> FAIL:
       - future_skew > 0 (clock desync / future exchange timestamp)
       - invalid_time_status > 0 (invalid exchange timestamp classification)
       - invalid_quote_status > 0 (corrupt prices)
       - stale_at_ingestion > 0 (persisted as stale at insertion)
       - persisted_eligibility_mismatches > 0 (eligibility flag disagrees with metadata)
       - stale_at_obs > 0 (dynamic age > 3.0s at observation time)
       - crossed_quotes > 0 (best_bid > best_ask)
       - locked_quotes > 0 (best_bid == best_ask)
    3. Missing quotes for quiet strikes -> INCONCLUSIVE (INCOMPLETE_STREAM_DELIVERY_QUIET_STRIKES).
    4. Benign microstructure conditions preventing eligibility (zero bid, missing depth) -> INCONCLUSIVE.
    5. 100% of expected active universe present in stream and fresh_and_eligible -> PASS.
    """
    if total_snapshots == 0 or expected_tokens_count == 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (Awaiting live session data)",
            "evidence": "DATA_CHECK_INCONCLUSIVE (Zero quote snapshots or unresolvable universe)",
        }

    if future_skew > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({future_skew} quotes exhibit negative age / future timestamp skew)",
        }

    if invalid_time_status > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({invalid_time_status} quotes have invalid exchange-time classification or null timestamp)",
        }

    if invalid_quote_status > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({invalid_quote_status} quotes have invalid quote_status classification)",
        }

    if stale_at_ingestion > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({stale_at_ingestion} quotes were persisted with is_stale=True at ingestion)",
        }

    if persisted_eligibility_mismatches > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({persisted_eligibility_mismatches} persisted eligibility metadata mismatches)",
        }

    if stale_at_obs > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({stale_at_obs} tokens exceed 3.0s dynamic age threshold at observation)",
        }

    if crossed_quotes > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({crossed_quotes} quotes exhibit crossed order book: best_bid > best_ask)",
        }

    if locked_quotes > 0:
        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "evidence": f"DATA_CHECK_FAIL ({locked_quotes} quotes exhibit locked order book: best_bid == best_ask)",
        }

    if unfulfilled_subscriptions_count > 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (INCOMPLETE_STREAM_DELIVERY_QUIET_STRIKES)",
            "evidence": f"DATA_CHECK_INCONCLUSIVE (Incomplete stream delivery: {unfulfilled_subscriptions_count} desired tokens absent from snapshot stream; quiet strike vs. unsubscription cannot be proven via database snapshots alone)",
        }

    if zero_bid_quotes > 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (ZERO_BID_QUOTES_PRESENT)",
            "evidence": f"DATA_CHECK_INCONCLUSIVE ({zero_bid_quotes} quotes exhibit zero bid [no active buy orders]; valid microstructure state for quiet strike but prevents execution-eligibility verification)",
        }

    if missing_depth_quotes > 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (MISSING_DEPTH_QUOTES_PRESENT)",
            "evidence": f"DATA_CHECK_INCONCLUSIVE ({missing_depth_quotes} quotes have missing depth or empty order book; prevents execution-eligibility verification)",
        }

    if other_ineligible_quotes > 0:
        return {
            "verdict": "INCONCLUSIVE",
            "status": "NOT TESTED (NON_ELIGIBLE_QUOTES_PRESENT)",
            "evidence": f"DATA_CHECK_INCONCLUSIVE ({other_ineligible_quotes} quotes are not execution eligible)",
        }

    if fresh_and_eligible == expected_tokens_count and tokens_with_quotes == expected_tokens_count:
        return {
            "verdict": "PASS",
            "status": "PASS",
            "evidence": f"DATA_CHECK_PASS (100% of expected active universe [{expected_tokens_count} contracts] present in stream with age <= 3.0s, quote_status=VALID, exchange_time=VALID, positive depth, uncrossed/unlocked books, and 0 metadata mismatches)",
        }

    return {
        "verdict": "INCONCLUSIVE",
        "status": "NOT TESTED",
        "evidence": "DATA_CHECK_INCONCLUSIVE (Quote verification could not establish 100% fresh and eligible universe)",
    }

