"""
Fetch raid data from Warcraft Logs and save to local JSON cache.

Usage:
    python fetch.py                    # Smart mode: best log per raid night (last 20 reports)
    python fetch.py --reports 30       # Look back further
    python fetch.py --code ABC123      # Fetch one specific report
    python fetch.py --force            # Re-fetch even if already cached
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime

import cache
from config import (
    GUILD_NAME, GUILD_SERVER, GUILD_REGION,
    DEFAULT_CONSUMABLES, DEFAULT_DEFENSIVES, COMBAT_RES_IDS,
)
from data_processor import (
    build_actor_map, build_ability_map, build_config_lookup,
    process_performance, process_consumables,
    process_utility_table, process_defensives, process_deaths,
    process_timeline, process_damage_taken_events, process_rankings,
    process_attendance, get_consumable_headers,
    PERFORMANCE_HEADERS, UTILITY_HEADERS,
    DEFENSIVES_HEADERS, DEATHS_HEADERS, TIMELINE_HEADERS, DAMAGE_TAKEN_HEADERS,
    RANKINGS_HEADERS, ATTENDANCE_HEADERS,
    fight_boss_hp, fight_duration_seconds, fight_result,
)
from wcl_client import WCLClient

DIFF_NAMES = {3: "Normal", 4: "Heroic", 5: "Mythic", 10: "LFR"}


def build_config():
    """Build consumable and defensive config from config.py defaults."""
    consumable_config = [
        {"Spell ID": row[0], "Name": row[1], "Category": row[2]}
        for row in DEFAULT_CONSUMABLES
    ]
    defensive_config = [
        {"Spell ID": row[0], "Name": row[1], "Category": row[2]}
        for row in DEFAULT_DEFENSIVES
    ]
    return consumable_config, defensive_config


def rows_to_dicts(headers, rows):
    return [dict(zip(headers, row)) for row in rows]


def fetch_fight(wcl, report_code, fight, report_info, actor_map, ability_map,
                consumable_config, defensive_config):
    """Fetch all data for a single fight. Returns dict with all sections."""
    fight_id = fight["id"]
    boss = fight["name"]
    pull = fight["pull_number"]
    t0, t1 = fight["startTime"], fight["endTime"]

    consumable_lookup = build_config_lookup(consumable_config)
    defensive_lookup = build_config_lookup(defensive_config)
    consumable_ids = list(consumable_lookup[0].keys())
    defensive_ids = list(defensive_lookup[0].keys())
    consumable_headers = get_consumable_headers(consumable_config)

    perf_rows, death_rows, interrupt_rows = [], [], []
    dispel_rows, consumable_rows, defensive_rows, timeline_rows, dt_rows, ranking_rows = [], [], [], [], [], []
    death_table, consumable_events_raw, defensive_events_raw, combat_res_events_raw = {}, [], [], []

    # DPS
    try:
        dps_table = wcl.get_table(report_code, "DamageDone", [fight_id], t0, t1)
        perf_rows.extend(process_performance(report_info, fight, dps_table, "DPS", actor_map))
    except Exception as e:
        print(f"      Warning: DPS: {e}")

    # HPS
    try:
        hps_table = wcl.get_table(report_code, "Healing", [fight_id], t0, t1)
        perf_rows.extend(process_performance(report_info, fight, hps_table, "HPS", actor_map))
    except Exception as e:
        print(f"      Warning: HPS: {e}")

    # Interrupts
    try:
        int_table = wcl.get_table(report_code, "Interrupts", [fight_id], t0, t1)
        interrupt_rows.extend(process_utility_table(report_info, fight, int_table, "Interrupt", actor_map))
    except Exception as e:
        print(f"      Warning: Interrupts: {e}")

    # Dispels
    try:
        disp_table = wcl.get_table(report_code, "Dispels", [fight_id], t0, t1)
        dispel_rows.extend(process_utility_table(report_info, fight, disp_table, "Dispel", actor_map))
    except Exception as e:
        print(f"      Warning: Dispels: {e}")

    # Deaths
    try:
        death_table = wcl.get_table(report_code, "Deaths", [fight_id], t0, t1)
        death_rows.extend(process_deaths(report_info, fight, death_table, actor_map))
    except Exception as e:
        print(f"      Warning: Deaths: {e}")

    # Consumables
    if consumable_ids:
        try:
            id_list = ", ".join(str(i) for i in consumable_ids)
            consumable_events_raw = wcl.get_events(
                report_code, "Casts", t0, t1,
                fight_ids=[fight_id],
                filter_expression=f"ability.id IN ({id_list})",
            )
            consumable_rows.extend(
                process_consumables(report_info, fight, consumable_events_raw,
                                    actor_map, consumable_config)
            )
        except Exception as e:
            print(f"      Warning: Consumables: {e}")

    # Defensives
    if defensive_ids:
        try:
            id_list = ", ".join(str(i) for i in defensive_ids)
            defensive_events_raw = wcl.get_events(
                report_code, "Casts", t0, t1,
                fight_ids=[fight_id],
                filter_expression=f"ability.id IN ({id_list})",
            )
            defensive_rows.extend(
                process_defensives(report_info, fight, defensive_events_raw,
                                   actor_map, defensive_config)
            )
        except Exception as e:
            print(f"      Warning: Defensives: {e}")

    # Combat Res
    if COMBAT_RES_IDS:
        try:
            id_list = ", ".join(str(i) for i in COMBAT_RES_IDS)
            combat_res_events_raw = wcl.get_events(
                report_code, "Casts", t0, t1,
                fight_ids=[fight_id],
                filter_expression=f"ability.id IN ({id_list})",
            )
        except Exception as e:
            print(f"      Warning: Combat Res: {e}")

    # Timeline
    try:
        timeline_rows.extend(
            process_timeline(report_info, fight, death_table,
                             consumable_events_raw, defensive_events_raw,
                             combat_res_events_raw,
                             actor_map, consumable_config, defensive_config)
        )
    except Exception as e:
        print(f"      Warning: Timeline: {e}")

    # Damage Taken (avoidable hits for player profile timeline)
    try:
        dt_events_raw = wcl.get_events(
            report_code, "DamageTaken", t0, t1,
            fight_ids=[fight_id],
        )
        dt_rows.extend(
            process_damage_taken_events(report_info, fight, dt_events_raw,
                                        actor_map, ability_map)
        )
    except Exception as e:
        print(f"      Warning: DamageTaken: {e}")

    # Rankings (parse %, item level)
    try:
        rankings_raw = wcl.get_report_rankings(report_code, fight_ids=[fight_id])
        ranking_rows.extend(process_rankings(report_info, fight, rankings_raw))
    except Exception as e:
        print(f"      Warning: Rankings: {e}")

    return {
        "meta": {
            "report": report_code,
            "fight_id": fight_id,
            "boss": boss,
            "pull": pull,
            "kill": fight["kill"],
            "boss_hp": fight_boss_hp(fight),
            "duration_s": fight_duration_seconds(fight),
            "result": fight_result(fight),
            "date": datetime.fromtimestamp(report_info["startTime"] / 1000).strftime("%Y-%m-%d"),
            "title": report_info.get("title", ""),
        },
        "performance": rows_to_dicts(PERFORMANCE_HEADERS, perf_rows),
        "deaths": rows_to_dicts(DEATHS_HEADERS, death_rows),
        "timeline": rows_to_dicts(TIMELINE_HEADERS, timeline_rows),
        "interrupts": rows_to_dicts(UTILITY_HEADERS, interrupt_rows),
        "dispels": rows_to_dicts(UTILITY_HEADERS, dispel_rows),
        "consumables": rows_to_dicts(consumable_headers, consumable_rows),
        "defensives": rows_to_dicts(DEFENSIVES_HEADERS, defensive_rows),
        "damage_taken": rows_to_dicts(DAMAGE_TAKEN_HEADERS, dt_rows),
        "rankings": rows_to_dicts(RANKINGS_HEADERS, ranking_rows),
    }


def fetch_report(wcl, report_code, consumable_config, defensive_config, force=False):
    """Fetch all Mythic fights for a report. Saves per-fight JSON files.
    Returns list of fight metadata dicts for updating the index."""
    print(f"  Fetching fights for {report_code}...")
    report = wcl.get_report_fights(report_code)
    all_fights = report.get("fights", [])

    # Breakdown by difficulty
    diff_breakdown = {}
    for f in all_fights:
        diff_breakdown.setdefault(f.get("difficulty"), []).append(f["name"])
    for diff, names in sorted(diff_breakdown.items(), key=lambda x: -(x[0] or 0)):
        label = DIFF_NAMES.get(diff, f"diff={diff}")
        counts = Counter(names)
        bosses = ", ".join(f"{n} x{c}" for n, c in counts.items())
        print(f"    {label}: {len(names)} pulls — {bosses}")

    mythic_fights = [f for f in all_fights if f.get("difficulty") == 5]
    if not mythic_fights:
        print(f"  No Mythic fights found, skipping.")
        return []

    actor_map   = build_actor_map(report.get("masterData", {}))
    ability_map = build_ability_map(report.get("masterData", {}))
    report_info = {
        "code": report["code"],
        "title": report.get("title", ""),
        "startTime": report["startTime"],
        "endTime": report["endTime"],
    }

    # Assign pull numbers per boss
    boss_pull_counter = {}
    for fight in mythic_fights:
        boss = fight["name"]
        boss_pull_counter[boss] = boss_pull_counter.get(boss, 0) + 1
        fight["pull_number"] = boss_pull_counter[boss]

    fights_meta = []
    for fight in mythic_fights:
        key = cache.fight_key(report_code, fight["id"])
        if cache.exists(key) and not force:
            print(f"    Skipping {fight['name']} pull #{fight['pull_number']} (cached)")
            # Still need meta for index
            existing = cache.get(key)
            if existing:
                fights_meta.append(existing["meta"])
            continue

        print(f"    Fetching {fight['name']} Pull #{fight['pull_number']} "
              f"({'Kill' if fight['kill'] else 'Wipe'})...")
        try:
            fight_data = fetch_fight(wcl, report_code, fight, report_info,
                                     actor_map, ability_map, consumable_config, defensive_config)
            cache.set(key, fight_data)
            fights_meta.append(fight_data["meta"])
            print(f"      Saved: {key}.json")
        except Exception as e:
            print(f"      Error: {e}")

    _update_parses_index(report_code, fights_meta)
    return fights_meta


def _update_parses_index(report_code, fights_meta):
    """Rebuild parses_index from on-disk fight cache files for this report."""
    existing = cache.load_parses_index()
    # Remove old rows for this report (full re-build per report)
    existing = [r for r in existing if r.get("Report") != report_code]

    for meta in fights_meta:
        fight_data = cache.get(cache.fight_key(report_code, meta["fight_id"]))
        if not fight_data:
            continue
        for row in fight_data.get("rankings", []):
            existing.append(row)

    cache.save_parses_index(existing)


def fetch_guild_members(wcl):
    """Fetch guild member roster from WCL and save to cache."""
    server_slug = GUILD_SERVER.lower().replace(" ", "-")
    print(f"  Fetching guild roster for {GUILD_NAME}...")
    members = wcl.get_guild_members(GUILD_NAME, server_slug, GUILD_REGION.lower())
    cache.save_guild_members(members)
    print(f"  Guild members: {len(members)} saved.")
    return members


def _detect_current_zone_id(wcl):
    """Return zone_id of the most recent guild raid report."""
    server_slug = GUILD_SERVER.lower().replace(" ", "-")
    try:
        reports = wcl.get_guild_reports(GUILD_NAME, server_slug, GUILD_REGION.lower(), limit=1)
        data = reports.get("data", [])
        if data:
            return data[0].get("zone", {}).get("id")
    except Exception:
        pass
    return None


def fetch_attendance(wcl, zone_id=None):
    """Build guild attendance from cached fight files (reports_index + fight_*.json)."""
    import glob as _glob
    from pathlib import Path as _Path

    reports = cache.load_index()
    if not reports:
        print("  No reports in index – run fetch first.")
        return

    members = cache.load_guild_members()
    if not members:
        members = fetch_guild_members(wcl)
    guild_names = {m["name"] for m in members}
    print(f"  Guild roster: {len(guild_names)} members")

    print(f"Building attendance for {GUILD_NAME} from fight cache...")
    all_rows = []
    for report in reports:
        code = report["report_code"]
        date = report["date"]
        title = report.get("title", "Mythic Raid")

        fight_files = sorted(_glob.glob(str(cache.CACHE_DIR / f"fight_{code}_*.json")))
        if not fight_files:
            continue

        players_per_fight = {}
        player_class = {}
        for ff in fight_files:
            fdata = json.loads(_Path(ff).read_text(encoding="utf-8"))
            fight_id = fdata["meta"]["fight_id"]
            present = set()
            for row in fdata.get("performance", []):
                name = row["Player"]
                if name in guild_names:
                    present.add(name)
                    player_class[name] = row.get("Class", "")
            players_per_fight[fight_id] = present

        total_fights = len(players_per_fight)
        player_count = {}
        for p_set in players_per_fight.values():
            for name in p_set:
                player_count[name] = player_count.get(name, 0) + 1

        for name, count in player_count.items():
            presence = round(count / total_fights, 4)
            all_rows.append({
                "Report": code,
                "Date": date,
                "Zone": title,
                "Player": name,
                "Class": player_class.get(name, ""),
                "Presence": presence,
                "Presence %": f"{round(presence * 100)}%",
            })

        print(f"  {code} ({date}): {len(player_count)} players, {total_fights} fights")

    cache.save_attendance(all_rows)
    print(f"  Attendance saved: {len(all_rows)} rows total.")


def pick_best_reports(wcl, limit=20):
    """Smart mode: return every recent report that contains Mythic pulls.

    Some raid nights have multiple groups, each with a separate WCL report. Keep
    them as separate report sessions so the dashboard can analyze them apart.
    """
    server_slug = GUILD_SERVER.lower().replace(" ", "-")
    print(f"Fetching last {limit} reports for {GUILD_NAME}...")
    reports_data = wcl.get_guild_reports(GUILD_NAME, server_slug, GUILD_REGION.lower(), limit=limit)
    raw_reports = reports_data["data"]
    print(f"  Inspecting {len(raw_reports)} candidate reports...")

    scored = []
    for r in raw_reports:
        try:
            fights_data = wcl.get_report_fights(r["code"])
            all_fights = fights_data.get("fights", [])
            mythic_fights = [f for f in all_fights if f.get("difficulty") == 5]
            if not mythic_fights:
                continue
            raid_date = datetime.fromtimestamp(r["startTime"] / 1000).strftime("%Y-%m-%d")
            scored.append({
                "code": r["code"],
                "title": r.get("title", ""),
                "startTime": r["startTime"],
                "date": raid_date,
                "mythic_count": len(mythic_fights),
                "unique_bosses": len(set(f["name"] for f in mythic_fights)),
            })
        except Exception as e:
            print(f"    Warning: could not inspect {r['code']}: {e}")

    # Group only for readable logging; keep every report as a separate session.
    by_date = defaultdict(list)
    for r in scored:
        by_date[r["date"]].append(r)

    picks = []
    for date, candidates in sorted(by_date.items(), reverse=True):
        candidates.sort(key=lambda r: r["startTime"])
        print(f"  [{date}] Found {len(candidates)} Mythic report(s):")
        for report in candidates:
            picks.append(report)
            print(f"           Keeping {report['code']} "
                  f"({report['mythic_count']} Mythic pulls, {report['unique_bosses']} bosses) "
                  f"— '{report['title'][:40]}'")

    return [p["code"] for p in picks]


def update_index(report_code, report_info, fights_meta):
    """Add or update a report entry in reports_index.json."""
    index = cache.load_index()

    # Remove existing entry for this report (will re-add updated)
    index = [e for e in index if e["report_code"] != report_code]

    if fights_meta:
        date = fights_meta[0]["date"]
        index.append({
            "date": date,
            "report_code": report_code,
            "title": report_info.get("title", ""),
            "startTime": report_info.get("startTime", 0),
            "fights": [
                {
                    "fight_id": m["fight_id"],
                    "boss": m["boss"],
                    "pull": m["pull"],
                    "kill": m["kill"],
                    "boss_hp": m["boss_hp"],
                    "duration_s": m["duration_s"],
                    "result": m["result"],
                }
                for m in fights_meta
            ],
        })

    # Sort newest first
    index.sort(key=lambda e: (e["date"], e.get("startTime", 0)), reverse=True)
    cache.save_index(index)
    print(f"  Index updated: {len(index)} report session(s) total.")


def main():
    parser = argparse.ArgumentParser(description="Fetch WCL data to local JSON cache")
    parser.add_argument("--reports", type=int, default=20,
                        help="How many recent reports to scan in smart mode (default: 20)")
    parser.add_argument("--code", type=str, default=None,
                        help="Fetch a specific report by code")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch even if already cached")
    parser.add_argument("--no-attendance", action="store_true",
                        help="Skip fetching guild attendance data")
    args = parser.parse_args()

    print("Connecting to Warcraft Logs API...")
    wcl = WCLClient()
    consumable_config, defensive_config = build_config()

    if args.code:
        report_codes = [args.code]
    else:
        report_codes = pick_best_reports(wcl, limit=args.reports)

    if not report_codes:
        print("No reports with Mythic content found.")
        return

    print(f"\nFetching {len(report_codes)} report(s)...")
    for code in report_codes:
        print(f"\n{'='*60}")
        print(f"Report: {code}")
        print(f"{'='*60}")
        try:
            # Get report info for index
            report_raw = wcl.get_report_fights(code)
            report_info = {
                "code": code,
                "title": report_raw.get("title", ""),
                "startTime": report_raw["startTime"],
            }
            fights_meta = fetch_report(wcl, code, consumable_config, defensive_config, force=args.force)
            update_index(code, report_info, fights_meta)
        except Exception as e:
            print(f"  Error processing {code}: {e}")

    if not args.no_attendance:
        print("\nFetching attendance...")
        try:
            fetch_attendance(wcl)
        except Exception as e:
            print(f"  Error fetching attendance: {e}")

    print(f"\nDone. Cache saved to: cache/")
    print(f"Run: streamlit run app.py")


if __name__ == "__main__":
    main()
