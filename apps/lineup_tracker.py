"""Ottoneu Lineup Change Tracker

Streamlit app to monitor automated lineup changes across all leagues.
Reads from output/lineup_log.json and output/schedule.json.
"""

import html
import json
from collections import Counter, defaultdict
from datetime import date as date_type, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import base64

import streamlit as st

# CSS for change cards (used with st.html which renders in iframes)
CARD_CSS = """
<style>
    @import url('https://use.typekit.net/ocz7eof.css');
    * { font-family: 'sofia-pro', 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
    body { background: transparent; }
    .change-card {
        background: rgba(28,35,51,0.8);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 10px;
        border-left: 3px solid #83bdc0;
        transition: all 0.2s ease;
    }
    .change-card:hover { border-color: rgba(255,255,255,0.12); transform: translateX(3px); }
    .change-card.optimal { border-left-color: #5a9f76; }
    .change-card.dry-run { border-left-color: #f8cf8b; }
    .change-card.error { border-left-color: #d05950; }
    .change-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        gap: 12px;
        flex-wrap: wrap;
    }
    .league-name { font-size: 1rem; font-weight: 600; color: #FFF; letter-spacing: -0.01em; }
    .timestamp { font-size: 0.8rem; color: rgba(255,255,255,0.55); }
    .status-badge {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 10px; border-radius: 14px;
        font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .moves-container { background: rgba(0,0,0,0.15); border-radius: 8px; padding: 10px 14px; }
    .move-row {
        display: grid;
        grid-template-columns: minmax(140px, 1fr) auto auto auto;
        align-items: center; gap: 10px; padding: 7px 0;
        font-size: 0.9rem; color: rgba(255,255,255,0.7);
        border-bottom: 1px solid rgba(255,255,255,0.04);
    }
    .move-row:last-child { border-bottom: none; }
    .player-name { color: #FFF; font-weight: 600; letter-spacing: -0.01em; overflow-wrap: break-word; }
    .arrow { color: rgba(255,255,255,0.2); font-size: 1.1rem; }
    .pos-from {
        color: #e68b5e; font-weight: 600; font-size: 0.82rem;
        text-transform: uppercase; letter-spacing: 0.02em;
        padding: 3px 9px; background: rgba(230,139,94,0.1); border-radius: 5px;
        text-align: center; min-width: 52px;
    }
    .pos-to {
        color: #83bdc0; font-weight: 600; font-size: 0.82rem;
        text-transform: uppercase; letter-spacing: 0.02em;
        padding: 3px 9px; background: rgba(131,189,192,0.1); border-radius: 5px;
        text-align: center; min-width: 52px;
    }
    .no-changes { color: #5a9f76; font-size: 0.9rem; padding: 6px 0; }
    .section-divider { display: flex; align-items: center; gap: 8px; margin: 12px 0 6px 0; }
    .section-divider:first-child { margin-top: 4px; }
    .section-label {
        font-size: 0.65rem; font-weight: 600; letter-spacing: 0.08em;
        text-transform: uppercase; color: rgba(131, 189, 192, 0.7); white-space: nowrap;
    }
    .section-divider .line {
        flex: 1; height: 1px;
        background: linear-gradient(to right, rgba(131, 189, 192, 0.25), transparent);
    }
    .rec-container {
        margin-top: 8px; padding: 10px 14px;
        background: rgba(245, 187, 91, 0.04); border-radius: 8px;
        border: 1px solid rgba(245, 187, 91, 0.1);
    }
    .rec-header {
        font-size: 0.65rem; font-weight: 600; letter-spacing: 0.08em;
        text-transform: uppercase; color: rgba(245, 187, 91, 0.7); margin-bottom: 6px;
    }
    .rec-row {
        display: grid;
        grid-template-columns: minmax(120px, 1fr) auto auto auto;
        align-items: center; gap: 8px; padding: 5px 0;
        font-size: 0.82rem; color: rgba(255,255,255,0.5);
        border-bottom: 1px solid rgba(255,255,255,0.03);
    }
    .rec-row:last-child { border-bottom: none; }
    .rec-name { color: rgba(255,255,255,0.7); font-weight: 500; }
    .rec-matchup { font-size: 0.75rem; color: rgba(255,255,255,0.55); }
    .rec-reason {
        font-size: 0.72rem; color: rgba(245, 187, 91, 0.6);
        padding: 2px 7px; background: rgba(245, 187, 91, 0.08);
        border-radius: 4px; white-space: nowrap;
    }
    .overnight-badge {
        background: rgba(156, 120, 255, 0.15); color: #B39DFF;
        font-size: 0.55rem; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase; padding: 2px 8px; border-radius: 4px; margin-left: 6px;
    }
    .game-date-badge {
        background: rgba(131,189,192,0.12); color: #83bdc0;
        font-size: 0.68rem; font-weight: 600; letter-spacing: 0.02em;
        padding: 3px 10px; border-radius: 5px; margin-left: 8px;
        display: inline-flex; align-items: center; gap: 4px;
    }
    @media (max-width: 768px) {
        .change-card { padding: 12px 14px; border-radius: 10px; }
        .change-header { flex-direction: column; align-items: flex-start; gap: 6px; }
        .league-name { font-size: 0.9rem; }
        .timestamp { font-size: 0.72rem; }
        .status-badge { font-size: 0.65rem; }
        .move-row { grid-template-columns: minmax(100px, 1fr) auto auto auto; gap: 6px; font-size: 0.82rem; }
        .player-name { font-size: 0.82rem; overflow-wrap: break-word; }
        .pos-from, .pos-to { font-size: 0.72rem; padding: 2px 6px; min-width: 40px; }
        .moves-container { padding: 8px 10px; }
        .rec-container { padding: 8px 10px; }
        .rec-row { grid-template-columns: 1fr auto; gap: 4px; font-size: 0.75rem; }
        .rec-header { font-size: 0.6rem; }
        .rec-matchup { font-size: 0.68rem; }
        .rec-reason { font-size: 0.65rem; }
        .overnight-badge { font-size: 0.5rem; }
        .game-date-badge { font-size: 0.6rem; padding: 2px 6px; }
    }
</style>
"""

LOGO_SVG_PATH = Path(__file__).parent / "logo.svg"
LOGO_SVG = LOGO_SVG_PATH.read_text()
LOGO_B64 = base64.b64encode(LOGO_SVG.encode()).decode()
LOGO_DATA_URI = f"data:image/svg+xml;base64,{LOGO_B64}"

st.set_page_config(
    page_title="Ottoneu Lineup Tracker",
    page_icon=LOGO_DATA_URI,
    layout="wide",
)

LOG_PATH = Path(__file__).parent.parent / "output" / "lineup_log.json"
SCHEDULE_PATH = Path(__file__).parent.parent / "output" / "schedule.json"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "lineup_priorities.json"
ROSTER_CACHE_PATH = Path(__file__).parent.parent / "output" / "roster_cache.json"

POSITION_SLOTS = ["C", "1B", "2B", "SS", "MI", "3B", "OF", "Util", "SP", "RP"]

LEAGUES = {
    100: "CaNtZ",
    301: "SABRmagician",
    530: "SABRmagician",
    649: "SABRmagician",
    663: "SabrCatz",
    757: "SabrWhiskeyCatzo",
    791: "SabrKurtz",
    836: "SabrCatz",
    1487: "SabrWarKurtz",
    1940: "Duran Duran",
}

STATUS_COLORS = {
    "applied": "#f5bb5b",
    "optimal": "#5a9f76",
    "dry_run": "#f8cf8b",
    "error": "#d05950",
}

STATUS_ICONS = {
    "applied": "&#10003;",
    "optimal": "&#10003;",
    "dry_run": "&#8635;",
    "error": "&#9888;",
}


# --- Data loading ---
@st.cache_data(ttl=60)
def load_log():
    if not LOG_PATH.exists():
        return []
    try:
        return json.loads(LOG_PATH.read_text())
    except (json.JSONDecodeError, ValueError):
        return []


@st.cache_data(ttl=60)
def load_schedule():
    if not SCHEDULE_PATH.exists():
        return None
    try:
        return json.loads(SCHEDULE_PATH.read_text())
    except (json.JSONDecodeError, ValueError):
        return None


ET = ZoneInfo("America/New_York")

def load_config():
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, ValueError):
        return {}


def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=4))


@st.cache_data(ttl=120)
def load_roster_cache():
    if not ROSTER_CACHE_PATH.exists():
        return {"players": {}, "league_rosters": {}}
    try:
        return json.loads(ROSTER_CACHE_PATH.read_text())
    except (json.JSONDecodeError, ValueError):
        return {"players": {}, "league_rosters": {}}


def player_name(pid, roster_cache, config=None):
    """Get display name for a player ID. Falls back to config annotations, then raw ID."""
    pid_str = str(pid)
    p = roster_cache.get("players", {}).get(pid_str)
    if p:
        return p.get("name", f"ID {pid}")
    # Fallback: parse from config _must_start_names / _rp_fatigue_protected_names
    if config:
        for names_key in ("_must_start_names", "_rp_fatigue_protected_names"):
            for entry in config.get(names_key, []):
                if f"({pid})" in str(entry):
                    return str(entry).split(" (")[0]
    return f"Player {pid}"


def player_league_count(pid, roster_cache):
    """Count how many leagues a player is rostered in."""
    count = 0
    for lid, pids in roster_cache.get("league_rosters", {}).items():
        if str(pid) in [str(p) for p in pids]:
            count += 1
    return count


HITTING_POSITIONS = {"C", "1B", "2B", "SS", "3B", "OF", "MI", "Util"}
PITCHING_POSITIONS = {"SP", "RP"}


def eligible_players_for_position(pos, league_id, roster_cache):
    """Get players eligible for a position in a specific league.

    If a player has positions data, uses strict matching.
    If positions data is empty, falls back to hitter/pitcher classification:
    hitters are eligible for hitting slots, pitchers for pitching slots.
    """
    lid = str(league_id)
    player_ids = roster_cache.get("league_rosters", {}).get(lid, [])
    players = roster_cache.get("players", {})
    eligible = []
    for pid in player_ids:
        p = players.get(str(pid))
        if not p:
            continue
        if p.get("minor_leaguer"):
            continue
        positions = p.get("positions", [])
        is_pitcher = p.get("is_pitcher", False)

        if positions:
            # Strict match when position data is available
            if pos == "Util" and not is_pitcher:
                eligible.append((str(pid), p["name"]))
            elif pos == "MI" and any(x in positions for x in ["2B", "SS"]):
                eligible.append((str(pid), p["name"]))
            elif pos in positions:
                eligible.append((str(pid), p["name"]))
        else:
            # No position data - use hitter/pitcher classification
            if pos in HITTING_POSITIONS and not is_pitcher:
                eligible.append((str(pid), p["name"]))
            elif pos in PITCHING_POSITIONS and is_pitcher:
                eligible.append((str(pid), p["name"]))
    return sorted(eligible, key=lambda x: x[1])


TS_FORMATS = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"]


def parse_ts(ts):
    """Parse a timestamp string into a timezone-aware datetime, or None."""
    if not ts:
        return None
    for fmt in TS_FORMATS:
        try:
            dt = datetime.strptime(ts, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def filter_by_period(entries, period, now_utc=None):
    """Filter log entries by time period: Today, 7d, 30d, YTD."""
    if period == "YTD":
        return entries
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if period == "Today":
        cutoff = date_type.today().isoformat()
        return [r for r in entries if r.get("timestamp", "")[:10] == cutoff]
    days = 7 if period == "7d" else 30
    cutoff = (now_utc - timedelta(days=days)).isoformat()
    return [r for r in entries if r.get("timestamp", "") >= cutoff]


def format_timestamp(ts):
    dt = parse_ts(ts)
    if not dt:
        return "Unknown"
    return dt.astimezone(ET).strftime("%b %d, %I:%M %p ET")


def get_next_run(schedule):
    """Find the next scheduled run from schedule.json."""
    if not schedule:
        return None
    now_utc = datetime.now(timezone.utc)
    for entry in schedule.get("entries", []):
        try:
            parts = entry["cron"].split()
            if len(parts) >= 5:
                d = datetime.strptime(entry["date"], "%Y-%m-%d")
                cron_dt = datetime(
                    d.year, int(parts[3]), int(parts[2]),
                    int(parts[1]), int(parts[0]), tzinfo=timezone.utc
                )
                if cron_dt > now_utc:
                    return cron_dt, entry.get("et_time", "")
        except (ValueError, KeyError, IndexError):
            continue
    return None


def time_ago(ts):
    """Convert timestamp to relative time string."""
    dt = parse_ts(ts)
    if not dt:
        return "Never"
    delta = datetime.now(timezone.utc) - dt
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours}h ago"
    mins = delta.seconds // 60
    return f"{mins}m ago" if mins > 0 else "Just now"


def countdown(target_dt):
    """Time until a future datetime."""
    if not target_dt:
        return ""
    delta = target_dt - datetime.now(timezone.utc)
    if delta.total_seconds() < 0:
        return "Now"
    hours = int(delta.total_seconds() // 3600)
    mins = int((delta.total_seconds() % 3600) // 60)
    if hours > 0:
        return f"in {hours}h {mins}m"
    return f"in {mins}m"


# --- CSS ---
st.markdown("""
<style>
    @import url('https://use.typekit.net/ocz7eof.css');
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * { font-family: 'sofia-pro', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    .block-container { padding-top: 1.5rem; max-width: 1400px; }

    /* Hero header */
    .hero-header {
        background: linear-gradient(135deg, #1C2333 0%, #242D3D 100%);
        border-radius: 16px;
        padding: 28px 36px;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(131, 189, 192, 0.1);
    }
    .hero-header::before {
        content: '';
        position: absolute;
        top: 0; right: 0;
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(131, 189, 192, 0.08) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-title {
        font-size: clamp(1.6rem, 4vw, 2.25rem);
        font-weight: 800;
        margin: 0 0 6px 0;
        letter-spacing: -0.03em;
        background: linear-gradient(120deg, #FFFFFF 0%, #f5bb5b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .hero-logo {
        width: clamp(36px, 5vw, 48px);
        height: clamp(36px, 5vw, 48px);
        -webkit-text-fill-color: initial;
        flex-shrink: 0;
        filter: drop-shadow(0 0 8px rgba(131, 189, 192, 0.3));
    }
    .hero-subtitle {
        font-size: 0.95rem;
        color: rgba(255,255,255,0.5);
        font-weight: 400;
    }
    .hero-status-row {
        display: flex;
        gap: 16px;
        margin-top: 18px;
        flex-wrap: wrap;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 24px;
        padding: 7px 16px;
        font-size: 0.85rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .status-pill .label { color: rgba(255,255,255,0.6); font-weight: 400; }
    .status-pill .value { color: #FFFFFF; font-weight: 600; }
    .pill-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
    }
    .pill-group-bracket {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 100%;
    }
    .bracket-arm {
        flex: 1;
        height: 1px;
        background: rgba(131, 189, 192, 0.25);
    }
    .bracket-label {
        font-size: 0.6rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: rgba(131, 189, 192, 0.6);
        white-space: nowrap;
    }
    .pill-group-pills {
        display: flex;
        gap: 8px;
    }
    .status-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #5a9f76;
        box-shadow: 0 0 8px rgba(90,159,118,0.6);
        animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

    /* League health grid */
    .league-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 10px;
        margin-bottom: 24px;
        justify-items: center;
    }
    .league-mini {
        background: rgba(28,35,51,0.7);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 14px;
        transition: all 0.2s ease;
        cursor: default;
        width: 100%;
    }
    .league-mini:hover {
        border-color: rgba(131,189,192,0.2);
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }
    .league-mini-name {
        font-size: 0.8rem;
        font-weight: 600;
        color: #FFF;
        margin-bottom: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .league-mini-id {
        font-size: 0.7rem;
        color: rgba(255,255,255,0.55);
        font-weight: 400;
    }
    .league-mini-stats {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 8px;
    }
    .league-mini-stat {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.5);
    }
    .league-mini-stat strong {
        color: #83bdc0;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .league-status-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 4px;
    }

    /* Metric grid */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }
    .metric-grid-3 {
        grid-template-columns: repeat(3, 1fr);
    }

    /* Metric cards */
    .metric-card {
        background: rgba(28,35,51,0.6);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 22px 18px;
        text-align: center;
        position: relative;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, #83bdc0, transparent);
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    .metric-card:hover { transform: translateY(-3px); border-color: rgba(131,189,192,0.2); box-shadow: 0 8px 24px rgba(131,189,192,0.1); }
    .metric-card:hover::before { opacity: 1; }
    .metric-value {
        font-size: 2.25rem;
        font-weight: 800;
        background: linear-gradient(135deg, #f5bb5b 0%, #e68b5e 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    .metric-label {
        font-size: 0.78rem;
        color: rgba(255,255,255,0.6);
        margin-top: 6px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Change cards, move rows, rec styles rendered via st.html (CARD_CSS) - not needed here */

    /* Schedule */
    .schedule-day {
        background: rgba(28,35,51,0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 14px;
        transition: border-color 0.2s ease;
    }
    .schedule-day:hover { border-color: rgba(131,189,192,0.15); }
    .schedule-day-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #FFF;
        margin-bottom: 12px;
        letter-spacing: -0.02em;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .schedule-day-count {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.55);
        font-weight: 400;
    }
    .schedule-time {
        display: inline-flex;
        align-items: center;
        background: rgba(42,42,62,0.8);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 7px 14px;
        margin: 5px 6px 5px 0;
        font-size: 0.9rem;
        color: #FFF;
        font-weight: 500;
        font-variant-numeric: tabular-nums;
        transition: all 0.2s ease;
    }
    .schedule-time.past {
        opacity: 0.3;
        text-decoration: line-through;
        color: rgba(255,255,255,0.55);
    }
    .schedule-time.next {
        background: rgba(131,189,192,0.12);
        border: 2px solid #83bdc0;
        color: #83bdc0;
        font-weight: 600;
        box-shadow: 0 0 16px rgba(131,189,192,0.25);
        animation: glow 2s ease-in-out infinite;
    }
    @keyframes glow {
        0%,100% { box-shadow: 0 0 16px rgba(131,189,192,0.25); }
        50% { box-shadow: 0 0 24px rgba(131,189,192,0.4); }
    }
    .schedule-meta {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.55);
        margin-top: 18px;
        line-height: 1.6;
        padding: 14px;
        background: rgba(0,0,0,0.12);
        border-radius: 8px;
        border-left: 3px solid rgba(131,189,192,0.3);
    }

    /* Section headers */
    .section-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #FFF;
        margin: 32px 0 16px 0;
        letter-spacing: -0.02em;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .section-header::before {
        content: '';
        width: 3px; height: 20px;
        background: linear-gradient(180deg, #83bdc0, #83bdc0);
        border-radius: 2px;
    }

    .section-rule {
        border: none;
        height: 1px;
        background: linear-gradient(to right, rgba(131,189,192,0.18), rgba(255,255,255,0.04), transparent);
        margin: 32px 0;
    }

    /* Day headers in change feed */
    .day-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin: 36px 0 16px 0;
        padding: 0;
    }
    .day-header:first-child { margin-top: 0; }
    .day-header-label {
        font-size: 1.1rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: rgba(131, 189, 192, 1);
        white-space: nowrap;
    }
    .day-header .line {
        flex: 1;
        height: 2px;
        background: linear-gradient(to right, rgba(131, 189, 192, 0.4), transparent);
    }
    .overnight-badge {
        background: rgba(156, 120, 255, 0.15);
        color: #B39DFF;
        font-size: 0.55rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 2px 8px;
        border-radius: 4px;
        margin-left: 6px;
    }

    /* Empty states */
    .empty-state {
        text-align: center;
        padding: 48px 28px;
        background: rgba(28,35,51,0.4);
        border: 2px dashed rgba(255,255,255,0.08);
        border-radius: 12px;
        margin: 24px 0;
    }
    .empty-state-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.4; }
    .empty-state-title { font-size: 1.05rem; font-weight: 600; color: rgba(255,255,255,0.6); margin-bottom: 6px; }
    .empty-state-text { font-size: 0.9rem; color: rgba(255,255,255,0.55); }

    /* Position breakdown */
    .pos-bar-container { margin-bottom: 6px; }
    .pos-bar-label {
        display: flex; justify-content: space-between;
        font-size: 0.8rem; color: rgba(255,255,255,0.6); margin-bottom: 3px;
    }
    .pos-bar-label strong { color: #FFF; }
    .pos-bar-bg {
        background: rgba(255,255,255,0.06);
        border-radius: 4px; height: 6px; overflow: hidden;
    }
    .pos-bar-fill {
        height: 100%; border-radius: 4px;
        background: linear-gradient(90deg, #83bdc0, #f5bb5b);
        transition: width 0.5s ease;
    }

    /* Mobile */
    @media (max-width: 768px) {
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
        .hero-header { padding: 16px 14px; border-radius: 12px; }
        .hero-title { font-size: clamp(1.2rem, 5vw, 1.5rem); gap: 8px; }
        .hero-logo { width: 32px; height: 32px; }
        .hero-subtitle { font-size: 0.82rem; }
        .hero-status-row { flex-direction: column; gap: 6px; }
        .status-pill { font-size: 0.75rem; padding: 5px 10px; width: 100%; }
        .pill-group-pills { flex-direction: row; gap: 6px; }
        .league-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .league-mini { padding: 10px; }
        .league-mini-name { font-size: 0.75rem; }
        .metric-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .metric-grid-3 { grid-template-columns: repeat(3, 1fr); }
        .metric-card { padding: 12px 8px; }
        .metric-value { font-size: 1.3rem; }
        .metric-label { font-size: 0.62rem; }
        .schedule-day { padding: 14px 16px; }
        .schedule-time { font-size: 0.78rem; padding: 6px 10px; min-height: 44px; }
        .schedule-meta { font-size: 0.75rem; padding: 10px; }
        .section-header { font-size: 1rem; margin: 20px 0 10px 0; }
        .section-rule { margin: 20px 0; }
        .day-header-label { font-size: 0.9rem; }
        .empty-state { padding: 32px 16px; }
        .pos-bar-label { font-size: 0.72rem; }

        /* Streamlit widget mobile overrides */
        div[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
        div[data-testid="stSelectbox"] label { font-size: 0.75rem !important; }
        div[data-testid="stRadio"] label { font-size: 0.8rem !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 0; }
        .stTabs [data-baseweb="tab"] { font-size: 0.8rem !important; padding: 8px 12px !important; min-height: 44px; }
    }

    @media (max-width: 640px) {
        /* Ensure configure tab content doesn't overflow */
        div[data-testid="stVerticalBlock"] { overflow-x: hidden; }
        /* Keep name + X button on same row in configure tab */
        div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
    }

    /* Config section titles */
    .config-section-title {
        font-size: 1rem;
        font-weight: 700;
        color: #FFF;
        padding: 10px 14px;
        background: rgba(28,35,51,0.6);
        border: 1px solid rgba(131,189,192,0.12);
        border-radius: 8px;
        margin-bottom: 4px;
    }
    /* Hide config section dividers on desktop (only show when stacked) */
    .config-section-rule { display: none; }
    @media (max-width: 640px) {
        .config-section-rule { display: block; margin: 24px 0 8px 0; }
    }

    /* Remove Streamlit's default scrollable containers on markdown elements */
    div[data-testid="stMarkdownContainer"] { overflow: visible !important; }
    div[data-testid="element-container"] { overflow: visible !important; }

    /* Skeleton loading */
    .skeleton {
        background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s ease-in-out infinite;
        border-radius: 8px;
    }
    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    .skeleton-card {
        height: 120px;
        margin-bottom: 10px;
    }
    .skeleton-metric {
        height: 90px;
    }
    .skeleton-bar {
        height: 24px;
        margin-bottom: 8px;
    }
    .skeleton-table-row {
        height: 40px;
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)


# --- Load data ---
log = load_log()
schedule = load_schedule()
roster_cache = load_roster_cache()

# --- Hero header ---
total_log_runs = len(log)
latest_ts = log[-1].get("timestamp") if log else None
next_run_info = get_next_run(schedule)

hero_pills = ""
if not log:
    # Skeleton pills while no data has loaded yet
    hero_pills = """
    <div class="skeleton" style="width:140px;height:34px;border-radius:24px;display:inline-block;"></div>
    <div class="skeleton" style="width:120px;height:34px;border-radius:24px;display:inline-block;"></div>
    <div class="skeleton" style="width:100px;height:34px;border-radius:24px;display:inline-block;"></div>"""

if latest_ts:
    hero_pills = ""
    hero_pills += f"""
    <div class="status-pill">
        <span class="status-dot"></span>
        <span class="label">Last run</span>
        <span class="value">{time_ago(latest_ts)}</span>
    </div>"""

if next_run_info:
    next_dt, next_et = next_run_info
    hero_pills += f"""
    <div class="status-pill">
        <span class="label">Next run</span>
        <span class="value">{html.escape(next_et)} ({countdown(next_dt)})</span>
    </div>"""

hero_pills += f"""
<div class="status-pill">
    <span class="label">Leagues</span>
    <span class="value">{len(LEAGUES)}</span>
</div>"""

today_str = date_type.today().isoformat()
seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
runs_today = sum(1 for entry in log if entry.get("timestamp", "")[:10] == today_str)
runs_7d = sum(1 for entry in log if entry.get("timestamp", "") >= seven_days_ago)
runs_ytd = len(log)

hero_pills += f"""
<div class="pill-group">
    <div class="pill-group-bracket">
        <span class="bracket-arm"></span>
        <span class="bracket-label">Script Runs</span>
        <span class="bracket-arm"></span>
    </div>
    <div class="pill-group-pills">
        <div class="status-pill">
            <span class="label">Today</span>
            <span class="value">{runs_today}</span>
        </div>
        <div class="status-pill">
            <span class="label">7d</span>
            <span class="value">{runs_7d}</span>
        </div>
        <div class="status-pill">
            <span class="label">YTD</span>
            <span class="value">{runs_ytd}</span>
        </div>
    </div>
</div>"""

st.markdown(f"""
<div class="hero-header">
    <h1 class="hero-title"><img src="{LOGO_DATA_URI}" class="hero-logo" alt=""/>Ottoneu Lineup Tracker</h1>
    <p class="hero-subtitle">Automated lineup optimization across {len(LEAGUES)} leagues</p>
    <div class="hero-status-row">{hero_pills}</div>
</div>
""", unsafe_allow_html=True)


# --- Tabs ---
tab_insights, tab_changes, tab_schedule, tab_config = st.tabs(["Insights", "Changes", "Schedule", "Configure"])


# ==================== CHANGES TAB ====================
with tab_changes:
    if not log:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">&#9918;</div>
            <div class="empty-state-title">No lineup changes yet</div>
            <div class="empty-state-text">Run <code>python set_lineups.py</code> to start tracking</div>
        </div>""", unsafe_allow_html=True)
    else:
        # League health grid
        st.markdown('<h2 class="section-header">League Status</h2>', unsafe_allow_html=True)
        st.markdown(
            '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:0.75rem;color:rgba(255,255,255,0.5);">'
            '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f5bb5b;margin-right:4px;"></span>Changes Made</span>'
            '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#5a9f76;margin-right:4px;"></span>Lineup Set</span>'
            '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f8cf8b;margin-right:4px;"></span>Dry Run</span>'
            '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#d05950;margin-right:4px;"></span>Error</span>'
            '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,0.2);margin-right:4px;"></span>No Data</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        league_cards_html = '<div class="league-grid">'
        for lid, lname in LEAGUES.items():
            league_runs = [r for r in log if r.get("league_id") == lid]
            last_run = league_runs[-1] if league_runs else None
            last_status = last_run.get("status", "unknown") if last_run else "none"
            last_changes = len(last_run.get("changes", [])) if last_run else 0
            last_ago = time_ago(last_run.get("timestamp")) if last_run else "Never"

            if last_status == "applied":
                dot_color = "#f5bb5b"
            elif last_status == "optimal":
                dot_color = "#5a9f76"
            elif last_status.startswith("error"):
                dot_color = "#d05950"
            elif last_status == "dry_run":
                dot_color = "#f8cf8b"
            else:
                dot_color = "rgba(255,255,255,0.2)"

            lname_safe = html.escape(lname)
            league_cards_html += f"""
            <div class="league-mini">
                <div class="league-mini-name">
                    <span class="league-status-dot" style="background:{dot_color};"></span>
                    {lname_safe}
                </div>
                <div class="league-mini-id">League {lid}</div>
                <div class="league-mini-stats">
                    <span class="league-mini-stat"><strong>{last_changes}</strong> moves</span>
                    <span class="league-mini-stat">{last_ago}</span>
                </div>
            </div>"""
        league_cards_html += '</div>'
        st.markdown(league_cards_html, unsafe_allow_html=True)

        # Filters
        col_f1, col_f2, col_f3 = st.columns(3)
        all_league_ids = sorted(set(r.get("league_id") for r in log if r.get("league_id") is not None))
        league_options = {f"{lid} - {LEAGUES.get(lid, '?')}": lid for lid in all_league_ids}

        with col_f1:
            selected_league = st.selectbox("League", ["All Leagues"] + list(league_options.keys()), key="f_league")
        all_dates = sorted(set(r.get("game_date", "") for r in log if r.get("game_date")), reverse=True)
        with col_f2:
            selected_date = st.selectbox("Game Date", ["All Dates"] + all_dates, key="f_date")
        with col_f3:
            status_display = {"All": "All", "Changes Made": "applied", "Lineup Set": "optimal", "Dry Run": "dry_run", "Error": "error"}
            selected_display = st.selectbox("Status", list(status_display.keys()), key="f_status")
            selected_status = status_display[selected_display]

        filtered = log
        if selected_league != "All Leagues":
            lid = league_options[selected_league]
            filtered = [r for r in filtered if r.get("league_id") == lid]
        if selected_date != "All Dates":
            filtered = [r for r in filtered if r.get("game_date") == selected_date]
        if selected_status != "All":
            filtered = [r for r in filtered if r.get("status", "").startswith(selected_status)]

        # Metrics across all runs (including dry runs)
        total_runs = len(filtered)
        lineups_changed = sum(1 for r in filtered if r.get("changes"))
        total_moves = sum(len(r.get("changes", [])) for r in filtered)
        error_runs = sum(1 for r in filtered if r.get("status", "").startswith("error"))

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card"><div class="metric-value">{total_runs}</div><div class="metric-label">Total Runs</div></div>
            <div class="metric-card"><div class="metric-value">{lineups_changed}</div><div class="metric-label">Lineups Changed</div></div>
            <div class="metric-card"><div class="metric-value">{total_moves}</div><div class="metric-label">Total Moves</div></div>
            <div class="metric-card"><div class="metric-value">{error_runs}</div><div class="metric-label">Errors</div></div>
        </div>""", unsafe_allow_html=True)

        # Change feed - with day headers
        current_day_label = None
        for entry in reversed(filtered):
            # Day header: group by date of the run timestamp
            raw_ts = entry.get("timestamp", "")
            entry_date_label = None
            is_overnight = False
            entry_dt = parse_ts(raw_ts)
            if entry_dt:
                entry_et = entry_dt.astimezone(ET)
                entry_date_label = entry_et.strftime("%A, %B %d")
                is_overnight = entry_et.hour >= 20 or entry_et.hour < 6

            if entry_date_label and entry_date_label != current_day_label:
                current_day_label = entry_date_label
                st.markdown(f"""
                <div class="day-header">
                    <span class="day-header-label">{html.escape(entry_date_label)}</span>
                    <span class="line"></span>
                </div>""", unsafe_allow_html=True)

            league_id = entry.get("league_id", "?")
            league_name = html.escape(str(entry.get("league_name", "Unknown")))
            league_label = f"League {league_id} - {league_name}"
            ts = format_timestamp(entry.get("timestamp"))
            status = entry.get("status", "unknown")
            status_key = status.split(":")[0].strip() if ":" in status else status
            card_class = status_key.replace("_", "-")
            color = STATUS_COLORS.get(status_key, "#888")
            icon = STATUS_ICONS.get(status_key, "")
            game_date = entry.get("game_date", "")
            teams_playing = entry.get("teams_playing", 0)

            changes = entry.get("changes", [])
            if changes:
                pitching_pos = {"SP", "RP"}
                hitting_moves = []
                pitching_moves = []
                for c in changes:
                    p_name = html.escape(c.get("player", "Unknown"))
                    p_from = html.escape(c.get("from", "?"))
                    p_to = html.escape(c.get("to", "?"))
                    row = f"""
                    <div class="move-row">
                        <span class="player-name">{p_name}</span>
                        <span class="pos-from">{p_from}</span>
                        <span class="arrow">&rarr;</span>
                        <span class="pos-to">{p_to}</span>
                    </div>"""
                    if c.get("from", "") in pitching_pos or c.get("to", "") in pitching_pos:
                        pitching_moves.append(row)
                    else:
                        hitting_moves.append(row)
                moves_html = '<div class="moves-container">'
                if hitting_moves:
                    moves_html += '<div class="section-divider"><span class="section-label">Hitting</span><span class="line"></span></div>'
                    moves_html += "".join(hitting_moves)
                if pitching_moves:
                    moves_html += '<div class="section-divider"><span class="section-label">Pitching</span><span class="line"></span></div>'
                    moves_html += "".join(pitching_moves)
                moves_html += '</div>'
            else:
                moves_html = '<div class="moves-container"><div class="no-changes">&#10003; Lineup set - no changes needed</div></div>'

            # Recommendations section
            recs = entry.get("recommendations", [])
            rec_html = ""
            if recs:
                # Split into hitters and pitchers, show hitters only (pitchers less actionable)
                hitter_recs = [r for r in recs if not r.get("is_pitcher")]
                if hitter_recs:
                    rec_html = '<div class="rec-container"><div class="rec-header">Bench - Playing Today</div>'
                    # Sort by FGPts/GS descending (N/A sorts last)
                    for r in sorted(hitter_recs, key=lambda x: -(x.get("fgpts_per_g") or -999))[:8]:
                        r_name = html.escape(r.get("player", ""))
                        r_team = html.escape(r.get("mlb_team", ""))
                        r_vs = html.escape(r.get("vs_pitcher", "TBD"))
                        r_hand = html.escape(r.get("bat_hand", "?"))
                        r_vs_hand = html.escape(r.get("vs_hand", "?"))
                        r_reason = html.escape(r.get("reason", ""))
                        fgpts = r.get("fgpts_per_g")
                        salary = r.get("salary")
                        # Fall back to roster cache P/G if log doesn't have it
                        if fgpts is None:
                            r_pid = str(r.get("player_id", ""))
                            cached_p = roster_cache.get("players", {}).get(r_pid, {})
                            fgpts = cached_p.get("ppg")
                        if fgpts is not None:
                            stat_label = f'<span style="opacity:0.4">{fgpts} P/G</span>'
                        elif salary is not None:
                            stat_label = f'<span style="opacity:0.4">${salary}</span>'
                        else:
                            stat_label = '<span style="opacity:0.4">N/A</span>'
                        rec_html += f"""
                        <div class="rec-row">
                            <span class="rec-name">{r_name} {stat_label}</span>
                            <span class="rec-matchup">{r_hand} vs {r_vs_hand} {r_vs}</span>
                            <span class="rec-reason">{r_reason}</span>
                        </div>"""
                    rec_html += '</div>'

            # IL players who are playing (alert to activate)
            il_players = entry.get("il_playing", [])
            il_html = ""
            if il_players:
                il_html = '<div class="rec-container" style="border-color:rgba(90,159,118,0.2);background:rgba(90,159,118,0.04);margin-top:8px;">'
                il_html += '<div class="rec-header" style="color:rgba(90,159,118,0.8);">IL - Active &amp; Playing</div>'
                for ilp in il_players:
                    il_name = html.escape(ilp.get("player", ""))
                    il_team = html.escape(ilp.get("mlb_team", ""))
                    il_ppg = ilp.get("ppg")
                    il_stat = f'<span style="opacity:0.4">{il_ppg} P/G</span>' if il_ppg else ""
                    il_html += f'<div class="rec-row"><span class="rec-name">{il_name} {il_stat}</span><span class="rec-matchup">{il_team}</span><span class="rec-reason" style="background:rgba(90,159,118,0.12);color:rgba(90,159,118,0.7);">activate?</span></div>'
                il_html += '</div>'

            if is_overnight and game_date:
                try:
                    gd_dt = datetime.strptime(game_date, "%Y-%m-%d")
                    gd_label = gd_dt.strftime("%b %d")
                except Exception:
                    gd_label = game_date
                overnight_html = f'<span class="overnight-badge">Overnight</span><span class="game-date-badge">For {html.escape(gd_label)} games</span>'
            else:
                overnight_html = ""
            # Human-readable status labels
            if status_key == "optimal":
                display_status = "Lineup Set"
                display_icon = "&#10003;"
            elif status_key == "applied":
                display_status = "Changes Made"
                display_icon = "&#10003;"
            elif status_key == "error":
                display_status = "Error"
                display_icon = "&#9888;"
            elif status_key == "dry_run":
                display_status = "Dry Run"
                display_icon = "&#8635;"
            else:
                display_status = status
                display_icon = icon
            st.html(CARD_CSS + f"""
            <div class="change-card {card_class}">
                <div class="change-header">
                    <div>
                        <span class="league-name">{league_label}</span>
                        <span class="status-badge" style="background:{color}22;color:{color};margin-left:10px;">
                            {display_icon} {html.escape(display_status)}
                        </span>
                        {overnight_html}
                    </div>
                    <div>
                        <span class="timestamp">{ts} &middot; {game_date} &middot; {teams_playing} teams</span>
                    </div>
                </div>
                {moves_html}
                {rec_html}
                {il_html}
            </div>""")


# ==================== SCHEDULE TAB ====================
with tab_schedule:
    if not schedule:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">&#128197;</div>
            <div class="empty-state-title">No schedule generated</div>
            <div class="empty-state-text">Run <code>python generate_schedule.py --write</code> to create game-time schedule</div>
        </div>""", unsafe_allow_html=True)
    else:
        generated_at = schedule.get("generated_at", "")
        if generated_at:
            try:
                gen_dt = datetime.fromisoformat(generated_at)
                if gen_dt.tzinfo is None:
                    gen_dt = gen_dt.replace(tzinfo=timezone.utc)
                gen_et = gen_dt.astimezone(ET)
                st.caption(f"Generated {gen_et.strftime('%b %d, %I:%M %p')} ET")
            except ValueError:
                pass

        now_utc = datetime.now(timezone.utc)
        by_date = defaultdict(list)
        for entry in schedule.get("entries", []):
            by_date[entry.get("date", "")].append(entry)

        # Build lookup: for each game_date, collect run timestamps to determine success/fail
        run_results_by_date = defaultdict(list)
        for r in log:
            gd = r.get("game_date", "")
            status = r.get("status", "")
            run_results_by_date[gd].append(status)

        next_found = False
        for date_str in sorted(by_date.keys()):
            if not date_str:
                continue
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                day_label = d.strftime("%A, %B %d")
            except ValueError:
                day_label = date_str

            # Sort entries by ET time for display (parse "HH:MM ET" for sort key)
            def et_sort_key(e):
                t = e.get("et_time", "99:99 ET").replace(" ET", "")
                try:
                    h, m = t.split(":")
                    return (int(h), int(m))
                except ValueError:
                    return (99, 99)
            entries = sorted(by_date[date_str], key=et_sort_key)
            # Check if any runs happened for this date
            date_statuses = run_results_by_date.get(date_str, [])
            had_error = any(s.startswith("error") for s in date_statuses)
            had_success = any(s in ("applied", "optimal") for s in date_statuses)

            time_pills = ""
            for e in entries:
                et_time = html.escape(e.get("et_time", "?"))
                css_class = ""
                status_icon = ""
                try:
                    parts = e["cron"].split()
                    if len(parts) >= 5:
                        cron_dt = datetime(
                            d.year, int(parts[3]), int(parts[2]),
                            int(parts[1]), int(parts[0]), tzinfo=timezone.utc
                        )
                        if cron_dt < now_utc:
                            css_class = "past"
                            # Check if runs exist around this cron time for this date
                            if had_success:
                                status_icon = ' <span style="color:#5a9f76;font-size:0.8em;">&#10003;</span>'
                            elif had_error:
                                status_icon = ' <span style="color:#d05950;font-size:0.8em;">&#10007;</span>'
                        elif not next_found:
                            css_class = "next"
                            next_found = True
                except (ValueError, KeyError, IndexError):
                    pass
                time_pills += f'<span class="schedule-time {css_class}">{et_time}{status_icon}</span>'

            st.markdown(f"""
            <div class="schedule-day">
                <div class="schedule-day-header">
                    <span>{day_label}</span>
                    <span class="schedule-day-count">{len(entries)} runs</span>
                </div>
                {time_pills}
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class="schedule-meta">
            Schedule regenerates nightly at midnight ET. Each run fires ~1 hour before game time,
            clustered within 15-min windows. Max 20 entries per cycle (GitHub Actions limit).
        </div>""", unsafe_allow_html=True)


# ==================== INSIGHTS TAB ====================
with tab_insights:
    @st.fragment
    def insights_fragment():
        if not log:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">&#128200;</div>
                <div class="empty-state-title">No data for insights</div>
                <div class="empty-state-text">Insights appear after the bot has run a few times</div>
            </div>""", unsafe_allow_html=True)
            return

        # Overview metrics with filters
        icol_f1, icol_f2, icol_f3 = st.columns(3)
        i_all_league_ids = sorted(set(r.get("league_id") for r in log if r.get("league_id") is not None))
        i_league_options = {f"{lid} - {LEAGUES.get(lid, '?')}": lid for lid in i_all_league_ids}

        with icol_f1:
            i_selected_league = st.selectbox("League", ["All Leagues"] + list(i_league_options.keys()), key="i_f_league")
        i_all_dates = sorted(set(r.get("game_date", "") for r in log if r.get("game_date")), reverse=True)
        with icol_f2:
            i_selected_date = st.selectbox("Game Date", ["All Dates"] + i_all_dates, key="i_f_date")
        with icol_f3:
            i_status_display = {"All": "All", "Changes Made": "applied", "Lineup Set": "optimal", "Dry Run": "dry_run", "Error": "error"}
            i_selected_display = st.selectbox("Status", list(i_status_display.keys()), key="i_f_status")
            i_selected_status = i_status_display[i_selected_display]

        i_filtered = log
        if i_selected_league != "All Leagues":
            i_lid = i_league_options[i_selected_league]
            i_filtered = [r for r in i_filtered if r.get("league_id") == i_lid]
        if i_selected_date != "All Dates":
            i_filtered = [r for r in i_filtered if r.get("game_date") == i_selected_date]
        if i_selected_status != "All":
            i_filtered = [r for r in i_filtered if r.get("status", "").startswith(i_selected_status)]

        i_total_runs = len(i_filtered)
        i_lineups_changed = sum(1 for r in i_filtered if r.get("changes"))
        i_total_moves = sum(len(r.get("changes", [])) for r in i_filtered)
        i_error_runs = sum(1 for r in i_filtered if r.get("status", "").startswith("error"))

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card"><div class="metric-value">{i_total_runs}</div><div class="metric-label">Total Runs</div></div>
            <div class="metric-card"><div class="metric-value">{i_lineups_changed}</div><div class="metric-label">Lineups Changed</div></div>
            <div class="metric-card"><div class="metric-value">{i_total_moves}</div><div class="metric-label">Total Moves</div></div>
            <div class="metric-card"><div class="metric-value">{i_error_runs}</div><div class="metric-label">Errors</div></div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

        # Daily summary table - deduplicate: last run per league per day
        st.markdown('<h2 class="section-header">Daily Summary</h2>', unsafe_allow_html=True)
        st.caption("Runs, moves, and outcomes per game date across all leagues")

        # Skeleton placeholder while computing
        summary_placeholder = st.empty()
        summary_placeholder.markdown(
            '<div class="skeleton skeleton-table-row"></div>'
            '<div class="skeleton skeleton-table-row"></div>'
            '<div class="skeleton skeleton-table-row"></div>',
            unsafe_allow_html=True,
        )

        # Aggregate daily stats from ALL log entries (runs = total script executions)
        daily = defaultdict(lambda: {"runs": 0, "changes": 0, "errors": 0, "leagues": set()})
        for r in log:
            gd = r.get("game_date", "Unknown")
            daily[gd]["runs"] += 1
            daily[gd]["changes"] += len(r.get("changes", []))
            daily[gd]["leagues"].add(r.get("league_id"))
            if r.get("status", "").startswith("error"):
                daily[gd]["errors"] += 1

        table_css = """<style>
            @import url('https://use.typekit.net/ocz7eof.css');
            * { font-family: 'sofia-pro', 'Inter', -apple-system, sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
            body { background: transparent; }
            .summary-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.85rem; }
            .summary-table th { text-align: left; padding: 10px 12px; color: rgba(255,255,255,0.6); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid rgba(255,255,255,0.08); }
            .summary-table td { padding: 10px 12px; color: rgba(255,255,255,0.75); border-bottom: 1px solid rgba(255,255,255,0.04); }
            .summary-table tr:hover td { background: rgba(131,189,192,0.04); }
            .summary-table .num { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; color: #FFF; }
            .summary-table .err { color: #d05950; font-weight: 600; }
            @media (max-width: 768px) {
                .summary-table { font-size: 0.75rem; }
                .summary-table th { padding: 8px 6px; font-size: 0.65rem; }
                .summary-table td { padding: 8px 6px; }
            }
        </style>"""
        table_html = table_css + """
        <table class="summary-table">
        <tr><th>Date</th><th style="text-align:right">Leagues</th><th style="text-align:right">Runs</th><th style="text-align:right">Moves</th><th style="text-align:right">Errors</th></tr>"""
        for gd in sorted(daily.keys(), reverse=True):
            d = daily[gd]
            err_class = "err" if d["errors"] > 0 else ""
            table_html += f"""
            <tr>
                <td><strong>{gd}</strong></td>
                <td class="num">{len(d['leagues'])}</td>
                <td class="num">{d['runs']}</td>
                <td class="num">{d['changes']}</td>
                <td class="num {err_class}">{d['errors']}</td>
            </tr>"""
        table_html += "</table>"
        summary_placeholder.empty()
        st.html(table_html)

        # Line graph: changes per day
        import plotly.graph_objects as go

        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
        st.markdown('<h2 class="section-header">Lineup Activity</h2>', unsafe_allow_html=True)
        st.caption("Total lineup changes per game day across all leagues")

        thirty_log = filter_by_period(log, "30d")
        changes_by_day = defaultdict(int)
        for r in thirty_log:
            gd = r.get("game_date", "")
            if gd:
                changes_by_day[gd] += len(r.get("changes", []))

        if changes_by_day:
            sorted_dates = sorted(changes_by_day.keys())
            counts = [changes_by_day[d] for d in sorted_dates]
            avg = sum(counts) / len(counts) if counts else 0

            # Summary metrics above chart
            st.markdown(f"""
            <div class="metric-grid metric-grid-3">
                <div class="metric-card"><div class="metric-value">{sum(counts)}</div><div class="metric-label">Total Changes</div></div>
                <div class="metric-card"><div class="metric-value">{avg:.0f}</div><div class="metric-label">Avg / Day</div></div>
                <div class="metric-card"><div class="metric-value">{max(counts)}</div><div class="metric-label">Peak Day</div></div>
            </div>""", unsafe_allow_html=True)

            fig = go.Figure()
            # Average line
            fig.add_trace(go.Scatter(
                x=sorted_dates, y=[avg] * len(sorted_dates),
                mode="lines",
                line=dict(color="rgba(245,187,91,0.3)", width=1, dash="dot"),
                hovertemplate="Avg: %{y:.0f}<extra></extra>",
                showlegend=False,
            ))
            # Main line
            fig.add_trace(go.Scatter(
                x=sorted_dates, y=counts,
                mode="lines+markers",
                line=dict(color="#83bdc0", width=2.5, shape="spline"),
                marker=dict(size=7, color="#83bdc0", line=dict(width=2, color="#0e1117")),
                fill="tozeroy",
                fillcolor="rgba(131,189,192,0.06)",
                hovertemplate="%{x|%b %d}<br><b>%{y} changes</b><extra></extra>",
                showlegend=False,
            ))
            fig.update_layout(
                height=240,
                margin=dict(l=0, r=0, t=8, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    showgrid=False,
                    color="rgba(255,255,255,0.5)",
                    tickformat="%b %d",
                    tickfont=dict(size=12),
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(255,255,255,0.05)",
                    color="rgba(255,255,255,0.5)",
                    title=None,
                    tickfont=dict(size=11),
                ),
                hovermode="x unified",
                hoverlabel=dict(bgcolor="#1c2333", font_color="#fff", font_size=13),
            )
            st.plotly_chart(fig, use_container_width=True, config={
                "displayModeBar": False, "scrollZoom": False,
                "staticPlot": True,
            })

        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

        # Position breakdown + Most Moved Players
        col_pos, col_movers = st.columns(2)

        with col_pos:
            st.markdown('<h2 class="section-header">Position Breakdown</h2>', unsafe_allow_html=True)
            st.caption("Which lineup slots the bot adjusts most often")
            time_filter = st.radio("Period", ["Today", "7d", "30d", "YTD"], horizontal=True, key="pos_period", index=1)
            pos_log = filter_by_period(log, time_filter)

            pos_counts = Counter()
            for r in pos_log:
                for c in r.get("changes", []):
                    pos_to = c.get("to", "")
                    if pos_to and pos_to != "Bench":
                        pos_counts[pos_to] += 1

            if pos_counts:
                max_count = max(pos_counts.values())
                bars_html = ""
                for pos, count in pos_counts.most_common(10):
                    pct = round(100 * count / max(max_count, 1))
                    pos_safe = html.escape(pos)
                    bars_html += f"""
                    <div class="pos-bar-container">
                        <div class="pos-bar-label"><strong>{pos_safe}</strong><span>{count}</span></div>
                        <div class="pos-bar-bg"><div class="pos-bar-fill" style="width:{pct}%"></div></div>
                    </div>"""
                st.markdown(bars_html, unsafe_allow_html=True)
            else:
                st.write("No position data for this period.")

        with col_movers:
            st.markdown('<h2 class="section-header">Most Active Players</h2>', unsafe_allow_html=True)
            st.caption("Players moved in/out of lineup most frequently")
            mover_filter = st.radio("Period", ["Today", "7d", "30d", "YTD"], horizontal=True, key="mover_period", index=1)
            mover_log = filter_by_period(log, mover_filter)

            player_moves = Counter()
            for r in mover_log:
                for c in r.get("changes", []):
                    player_moves[c.get("player", "Unknown")] += 1

            if player_moves:
                max_moves = max(player_moves.values())
                movers_html = ""
                for name, count in player_moves.most_common(10):
                    pct = round(100 * count / max(max_moves, 1))
                    name_safe = html.escape(name)
                    movers_html += f"""
                    <div class="pos-bar-container">
                        <div class="pos-bar-label"><strong>{name_safe}</strong><span>{count}</span></div>
                        <div class="pos-bar-bg"><div class="pos-bar-fill" style="width:{pct}%"></div></div>
                    </div>"""
                st.markdown(movers_html, unsafe_allow_html=True)
            else:
                st.write("No player data for this period.")

        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

        # Automated Lineup Moves by League
        st.markdown('<h2 class="section-header">Automated Lineup Moves by League</h2>', unsafe_allow_html=True)
        st.caption("Total lineup changes per league")
        league_filter = st.radio("Period", ["Today", "7d", "30d", "YTD"], horizontal=True, key="league_period", index=1)
        league_log = filter_by_period(log, league_filter)

        league_moves = Counter()
        for r in league_log:
            changes = r.get("changes", [])
            if changes:
                lid = r.get("league_id", "")
                lname = LEAGUES.get(lid, LEAGUES.get(str(lid), f"League {lid}"))
                league_moves[f"{lid} - {lname}"] += len(changes)

        if league_moves:
            max_lm = max(league_moves.values())
            league_html = ""
            for label, count in league_moves.most_common(10):
                pct = round(100 * count / max(max_lm, 1))
                label_safe = html.escape(label)
                league_html += f"""
                <div class="pos-bar-container">
                    <div class="pos-bar-label"><strong>{label_safe}</strong><span>{count}</span></div>
                    <div class="pos-bar-bg"><div class="pos-bar-fill" style="width:{pct}%"></div></div>
                </div>"""
            st.markdown(league_html, unsafe_allow_html=True)
        else:
            st.write("No league data for this period.")

    insights_fragment()



# ==================== CONFIGURE TAB ====================
with tab_config:
    @st.fragment
    def configure_fragment():
        config = load_config()
        roster_cache = load_roster_cache()
        has_cache = bool(roster_cache.get("players"))
        changed = False

        st.markdown('<h2 class="section-header">Lineup Configuration</h2>', unsafe_allow_html=True)
        st.caption("Manage bot rules, player lists, and per-league position priorities")

        if not has_cache:
            st.info("Player name lookup will be available after the bot runs once and populates the roster cache.")

        # --- Bot Rules (all toggles, core ones locked) ---
        st.markdown('<h3 style="color:#FFF;margin-top:24px;">Bot Rules</h3>', unsafe_allow_html=True)

        rules = config.get("rules", {})

        # Locked core rules first
        st.markdown('<p style="color:rgba(255,255,255,0.5);font-size:0.78rem;font-weight:600;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:8px;">Core Rules (locked)</p>', unsafe_allow_html=True)
        core_col1, core_col2, core_col3 = st.columns(3)
        with core_col1:
            st.toggle("Conservative swaps", value=True, disabled=True, key="rule_core1", help="Only swap red X for green check. Never rearrange active players.")
            st.toggle("Three-pass system", value=True, disabled=True, key="rule_core2", help="Pass 0: must_start. Pass 1: direct swaps. Pass 2: three-way indirect.")
        with core_col2:
            st.toggle("Never touch IL/Minors", value=True, disabled=True, key="rule_core3", help="Injured list and minor league slots are always left alone.")
            st.toggle("SP/RP role boundary", value=True, disabled=True, key="rule_core4", help="Starters can't fill RP slots. Relievers can't fill SP. Followers can fill SP.")
        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

        # Configurable rules
        st.markdown('<p style="color:rgba(255,255,255,0.5);font-size:0.78rem;font-weight:600;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:8px;">Configurable Rules</p>', unsafe_allow_html=True)
        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            lhb_block = st.toggle("LHB vs LHP block", value=rules.get("lhb_vs_lhp_block", True), key="rule_lhb", help="Skip left-handed batters facing a left-handed pitcher.")
            active_roster = st.toggle("Active roster filter", value=rules.get("active_roster_filter", True), key="rule_active", help="Skip bench players not on the MLB 26-man active roster.")
        with cfg_col2:
            rp_freshness = st.toggle("RP freshness priority", value=rules.get("rp_freshness", True), key="rule_freshness", help="Prefer well-rested relievers when filling RP slots. Factors in consecutive days, pitch counts, and rest.")
            flex_optimization = st.toggle("Flex slot optimization", value=rules.get("flex_optimization", True), key="rule_flex", help="Put latest-game-time players in Util/MI flex slots.")
        with cfg_col3:
            salary_tiebreak = st.toggle("Salary tiebreak", value=rules.get("salary_tiebreak", True), key="rule_salary", help="When priority rank is equal, higher-salary players start first.")

        new_rules = {
            "lhb_vs_lhp_block": lhb_block,
            "active_roster_filter": active_roster,
            "rp_freshness": rp_freshness,
            "flex_optimization": flex_optimization,
            "salary_tiebreak": salary_tiebreak,
        }
        if new_rules != rules:
            config["rules"] = new_rules
            changed = True

        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

        # --- Global Player Rules ---
        st.markdown('<h3 style="color:#FFF;margin-top:8px;">Global Player Rules</h3>', unsafe_allow_html=True)

        col_ms, col_dnm, col_rpp = st.columns(3)

        # Must Start
        with col_ms:
            st.markdown(
                '<div class="config-section-title">Must Start</div>',
                unsafe_allow_html=True,
            )
            st.caption("Always activated if playing")
            ms_ids = config.get("must_start", [])
            for pid in ms_ids:
                name = player_name(pid, roster_cache, config)
                col_name, col_rm = st.columns([4, 1])
                col_name.markdown(f"**{name}**")
                if col_rm.button("x", key=f"rm_ms_{pid}"):
                    config["must_start"] = [p for p in ms_ids if p != pid]
                    config["_must_start_names"] = [n for n in config.get("_must_start_names", []) if f"({pid})" not in str(n)]
                    changed = True

            # Add player - name search or ID
            if has_cache:
                all_players = [(pid, p["name"]) for pid, p in roster_cache.get("players", {}).items()]
                all_players.sort(key=lambda x: x[1])
                options = {f"{name} ({pid})": int(pid) for pid, name in all_players}
                ms_add = st.selectbox("Add player", [""] + list(options.keys()), key="add_ms_select")
                if ms_add and st.button("Add Must Start", key="btn_ms"):
                    pid = options[ms_add]
                    if pid not in ms_ids:
                        config.setdefault("must_start", []).append(pid)
                        name = ms_add.split(" (")[0]
                        config.setdefault("_must_start_names", []).append(f"{name} ({pid})")
                        changed = True
            else:
                new_ms_id = st.text_input("Player ID", key="add_ms", placeholder="e.g. 23327")
                new_ms_name = st.text_input("Name", key="add_ms_name", placeholder="e.g. Ronald Acuna Jr.")
                if st.button("Add Must Start", key="btn_ms_id"):
                    if new_ms_id.strip().isdigit():
                        pid = int(new_ms_id.strip())
                        if pid not in ms_ids:
                            config.setdefault("must_start", []).append(pid)
                            label = f"{new_ms_name.strip()} ({pid})" if new_ms_name.strip() else str(pid)
                            config.setdefault("_must_start_names", []).append(label)
                            changed = True

        # Do Not Move
        with col_dnm:
            st.markdown('<hr class="section-rule config-section-rule">', unsafe_allow_html=True)
            st.markdown('<div class="config-section-title">Do Not Move</div>', unsafe_allow_html=True)
            st.caption("Never swapped from current slot")
            dnm_ids = config.get("do_not_move", [])
            for pid in dnm_ids:
                name = player_name(pid, roster_cache, config)
                lc = player_league_count(pid, roster_cache)
                league_note = f" ({lc} league{'s' if lc != 1 else ''})" if lc > 0 else ""
                col_name, col_rm = st.columns([4, 1])
                col_name.markdown(f"**{name}**{league_note}")
                if col_rm.button("x", key=f"rm_dnm_{pid}"):
                    config["do_not_move"] = [p for p in dnm_ids if p != pid]
                    changed = True

            if has_cache:
                all_players = [(pid, p["name"]) for pid, p in roster_cache.get("players", {}).items()]
                all_players.sort(key=lambda x: x[1])
                options_dnm = {f"{name} ({pid})": int(pid) for pid, name in all_players}
                dnm_add = st.selectbox("Add player", [""] + list(options_dnm.keys()), key="add_dnm_select")
                if dnm_add and st.button("Add Do Not Move", key="btn_dnm"):
                    pid = options_dnm[dnm_add]
                    if pid not in dnm_ids:
                        config.setdefault("do_not_move", []).append(pid)
                        changed = True
            else:
                new_dnm_id = st.text_input("Player ID", key="add_dnm", placeholder="e.g. 33600")
                if st.button("Add Do Not Move", key="btn_dnm_id"):
                    if new_dnm_id.strip().isdigit():
                        pid = int(new_dnm_id.strip())
                        if pid not in dnm_ids:
                            config.setdefault("do_not_move", []).append(pid)
                            changed = True

        # RP Fatigue Protected
        with col_rpp:
            st.markdown('<hr class="section-rule config-section-rule">', unsafe_allow_html=True)
            st.markdown('<div class="config-section-title">RP Fatigue Protected</div>', unsafe_allow_html=True)
            st.caption("Exempt from fatigue benching")
            rpp_ids = config.get("rp_fatigue_protected", [])
            for pid in rpp_ids:
                name = player_name(pid, roster_cache, config)
                lc = player_league_count(pid, roster_cache)
                league_note = f" ({lc} league{'s' if lc != 1 else ''})" if lc > 0 else ""
                col_name, col_rm = st.columns([4, 1])
                col_name.markdown(f"**{name}**{league_note}")
                if col_rm.button("x", key=f"rm_rpp_{pid}"):
                    config["rp_fatigue_protected"] = [p for p in rpp_ids if p != pid]
                    config["_rp_fatigue_protected_names"] = [
                        n for n in config.get("_rp_fatigue_protected_names", []) if f"({pid})" not in str(n)
                    ]
                    changed = True

            if has_cache:
                # Only show players with RP eligibility
                rp_players = [
                    (pid, p["name"]) for pid, p in roster_cache.get("players", {}).items()
                    if "RP" in p.get("positions", [])
                ]
                rp_players.sort(key=lambda x: x[1])
                options_rpp = {f"{name} ({pid})": int(pid) for pid, name in rp_players}
                rpp_add = st.selectbox("Add pitcher", [""] + list(options_rpp.keys()), key="add_rpp_select")
                if rpp_add and st.button("Add RP Protected", key="btn_rpp"):
                    pid = options_rpp[rpp_add]
                    if pid not in rpp_ids:
                        config.setdefault("rp_fatigue_protected", []).append(pid)
                        name = rpp_add.split(" (")[0]
                        config.setdefault("_rp_fatigue_protected_names", []).append(f"{name} ({pid})")
                        changed = True
            else:
                new_rpp_id = st.text_input("Player ID", key="add_rpp", placeholder="e.g. 23601")
                if st.button("Add RP Protected", key="btn_rpp_id"):
                    if new_rpp_id.strip().isdigit():
                        pid = int(new_rpp_id.strip())
                        if pid not in rpp_ids:
                            config.setdefault("rp_fatigue_protected", []).append(pid)
                            changed = True

        # --- Per-League Position Priority ---
        st.markdown('<h3 style="color:#FFF;margin-top:32px;">League Position Priorities</h3>', unsafe_allow_html=True)
        st.caption("Ranked order per position. Use actions to reorder or remove. A player can appear under multiple positions but not twice in the same one.")

        league_options = [f"{lid} - {name}" for lid, name in LEAGUES.items()]
        default_idx = next((i for i, o in enumerate(league_options) if o.startswith("791")), 0)
        league_select = st.selectbox("League", league_options, index=default_idx, key="cfg_league")
        sel_lid = str(league_select.split(" - ")[0])
        sel_lid_int = int(sel_lid)

        league_cfg = config.get(sel_lid, {})

        # Show positions in 5x2 grid with spacing between rows
        row1_cols = st.columns(5)

        for i, slot in enumerate(POSITION_SLOTS):
            # Insert spacing and second row after first 5
            if i == 5:
                st.markdown("<br>", unsafe_allow_html=True)
                row2_cols = st.columns(5)

            col = row1_cols[i] if i < 5 else row2_cols[i - 5]

            with col:
                current_ids = league_cfg.get(slot, [])
                st.markdown(f"**{slot}**")

                if has_cache:
                    eligible = eligible_players_for_position(slot, sel_lid_int, roster_cache)
                    eligible_map = {pid: name for pid, name in eligible}

                    # Player list with remove button
                    for rank, pid in enumerate(current_ids):
                        name = eligible_map.get(str(pid), player_name(pid, roster_cache, config))
                        ppg_val = roster_cache.get("players", {}).get(str(pid), {}).get("ppg")
                        ppg_label = f" *{ppg_val} P/G*" if ppg_val else ""
                        c_name, c_rm = st.columns([5, 1])
                        c_name.markdown(f"`{rank+1}.` {name}{ppg_label}")
                        if c_rm.button("\u2715", key=f"rm_{sel_lid}_{slot}_{pid}"):
                            config.setdefault(sel_lid, {})[slot] = [p for p in current_ids if p != pid]
                            changed = True

                    if not current_ids:
                        st.caption("No custom order set")

                    # Always show add dropdown (filtered to players not already in this slot)
                    not_in_list = [(pid, name) for pid, name in eligible if int(pid) not in current_ids]
                    if not_in_list:
                        # Show P/G next to names in dropdown
                        add_options = {}
                        for apid, aname in not_in_list:
                            appg = roster_cache.get("players", {}).get(str(apid), {}).get("ppg")
                            label = f"{aname} ({appg} P/G)" if appg else aname
                            add_options[label] = int(apid)
                        add_sel = st.selectbox("Add", [""] + list(add_options.keys()), key=f"add_{sel_lid}_{slot}", label_visibility="collapsed")
                        if add_sel:
                            new_pid = add_options[add_sel]
                            if new_pid not in current_ids:
                                # Check rank conflict: find this player's highest rank in other positions
                                highest_rank = 0
                                for other_slot, other_ids in league_cfg.items():
                                    if other_slot != slot and isinstance(other_ids, list) and new_pid in other_ids:
                                        rank = other_ids.index(new_pid)
                                        highest_rank = max(highest_rank, rank + 1)
                                slot_list = config.setdefault(sel_lid, {}).setdefault(slot, [])
                                # Insert after the highest conflicting rank (or append if no conflict)
                                insert_pos = max(highest_rank, len(slot_list))
                                slot_list.insert(insert_pos, new_pid)
                                changed = True
                else:
                    new_val = st.text_area(
                        f"{slot} IDs",
                        value="\n".join(str(x) for x in current_ids),
                        height=150,
                        key=f"cfg_{sel_lid}_{slot}",
                        label_visibility="collapsed",
                    )
                    parsed = []
                    for line in new_val.strip().split("\n"):
                        line = line.strip()
                        if line.isdigit():
                            parsed.append(int(line))
                    if parsed != current_ids:
                        config.setdefault(sel_lid, {})[slot] = parsed
                        changed = True

        # --- Save ---
        if changed:
            save_config(config)
            st.success("Configuration saved. Changes take effect on next bot run.")
            st.rerun()

    configure_fragment()

# Signature
st.markdown(
    '<div style="text-align:right;padding:40px 12px 12px;color:rgba(131,189,192,0.18);font-size:0.72rem;'
    'font-weight:600;letter-spacing:0.06em;">@sabrmagician</div>',
    unsafe_allow_html=True,
)
