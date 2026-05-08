"""
Przemielimy Raid Analyzer
Fetches raid data from Warcraft Logs and exports to Google Sheets.

Usage:
    python main.py                    # Analyze last 5 reports
    python main.py --reports 10       # Analyze last 10 reports
    python main.py --code ABC123      # Analyze a specific report
"""

import argparse
import sys

from config import (
    GUILD_NAME, GUILD_SERVER, GUILD_REGION,
    CONSUMABLES_CONFIG_SHEET, DEFENSIVES_CONFIG_SHEET,
    CONFIG_HEADERS, DEFAULT_CONSUMABLES, DEFAULT_DEFENSIVES,
    COMBAT_RES_IDS,
)
from wcl_client import WCLClient
from sheets_client import SheetsClient
from data_processor import (
    build_actor_map, build_config_lookup,
    process_performance, process_consumables,
    process_utility_table, process_defensives, process_deaths,
    process_timeline, process_attendance, get_consumable_headers,
    PERFORMANCE_HEADERS, UTILITY_HEADERS,
    DEFENSIVES_HEADERS, DEATHS_HEADERS, TIMELINE_HEADERS,
    ATTENDANCE_HEADERS,
)


def load_config_from_sheets(sheets):
    """Load consumable and defensive configs from Google Sheets.

    Creates config sheets with defaults if they don't exist.
    Returns (consumable_config, defensive_config) as lists of dicts.
    """
    # Consumables config
    created = sheets.init_config_sheet(
        CONSUMABLES_CONFIG_SHEET, CONFIG_HEADERS, DEFAULT_CONSUMABLES
    )
    if created:
        print(f"  Created '{CONSUMABLES_CONFIG_SHEET}' sheet with default data.")
    consumable_config = sheets.read_config_sheet(CONSUMABLES_CONFIG_SHEET)
    print(f"  Loaded {len(consumable_config)} consumable definitions.")

    # Defensives config
    created = sheets.init_config_sheet(
        DEFENSIVES_CONFIG_SHEET, CONFIG_HEADERS, DEFAULT_DEFENSIVES
    )
    if created:
        print(f"  Created '{DEFENSIVES_CONFIG_SHEET}' sheet with default data.")
    defensive_config = sheets.read_config_sheet(DEFENSIVES_CONFIG_SHEET)
    print(f"  Loaded {len(defensive_config)} defensive definitions.")

    return consumable_config, defensive_config


def load_default_config():
    """Load default configs from config.py (for --no-sheets mode)."""
    consumable_config = [
        {"Spell ID": row[0], "Name": row[1], "Category": row[2]}
        for row in DEFAULT_CONSUMABLES
    ]
    defensive_config = [
        {"Spell ID": row[0], "Name": row[1], "Category": row[2]}
        for row in DEFAULT_DEFENSIVES
    ]
    return consumable_config, defensive_config


def analyze_report(wcl, report_code, consumable_config, defensive_config):
    """Analyze a single report. Returns dict of sheet_name -> rows."""
    print(f"  Fetching fights for report {report_code}...")
    report = wcl.get_report_fights(report_code)
    all_fights = report.get("fights", [])

    # Breakdown by difficulty for diagnostics
    from collections import Counter
    DIFF_NAMES = {3: "Normal", 4: "Heroic", 5: "Mythic", 10: "LFR"}
    diff_breakdown = {}
    for f in all_fights:
        diff = f.get("difficulty")
        diff_breakdown.setdefault(diff, []).append(f["name"])
    if diff_breakdown:
        print(f"  All fights in report by difficulty:")
        for diff, names in sorted(diff_breakdown.items(), key=lambda x: -(x[0] or 0)):
            label = DIFF_NAMES.get(diff, f"diff={diff}")
            counts = Counter(names)
            bosses = ", ".join(f"{n} x{c}" for n, c in counts.items())
            print(f"    {label}: {len(names)} pulls - {bosses}")

    # Filter to Mythic only (difficulty 5)
    fights = [f for f in all_fights if f.get("difficulty") == 5]
    if not fights:
        print(f"  No Mythic fights found in this report, skipping.")
        actor_map = {}
    else:
        print(f"  Found {len(fights)} Mythic fights (skipped {len(all_fights) - len(fights)} non-Mythic).")
    actor_map = build_actor_map(report.get("masterData", {}))

    report_info = {
        "code": report["code"],
        "title": report.get("title", ""),
        "startTime": report["startTime"],
        "endTime": report["endTime"],
    }

    # Build ID lists from config
    consumable_lookup = build_config_lookup(consumable_config)
    defensive_lookup = build_config_lookup(defensive_config)
    consumable_ids = list(consumable_lookup[0].keys())  # id_to_category keys
    defensive_ids = list(defensive_lookup[0].keys())

    perf_rows = []
    consumable_rows = []
    interrupt_rows = []
    dispel_rows = []
    defensive_rows = []
    death_rows = []
    timeline_rows = []

    # Calculate pull number per boss
    boss_pull_counter = {}
    for fight in fights:
        boss = fight["name"]
        boss_pull_counter[boss] = boss_pull_counter.get(boss, 0) + 1
        fight["pull_number"] = boss_pull_counter[boss]

    for fight in fights:
        fight_id = fight["id"]
        boss = fight["name"]
        pull = fight["pull_number"]
        print(f"    Processing: {boss} Pull #{pull} ({'Kill' if fight['kill'] else 'Wipe'})...")

        # DPS
        try:
            dps_table = wcl.get_table(report_code, "DamageDone", [fight_id],
                                      fight["startTime"], fight["endTime"])
            perf_rows.extend(process_performance(report_info, fight, dps_table, "DPS", actor_map))
        except Exception as e:
            print(f"      Warning: Could not fetch DPS data: {e}")

        # HPS
        try:
            hps_table = wcl.get_table(report_code, "Healing", [fight_id],
                                      fight["startTime"], fight["endTime"])
            perf_rows.extend(process_performance(report_info, fight, hps_table, "HPS", actor_map))
        except Exception as e:
            print(f"      Warning: Could not fetch HPS data: {e}")

        # Interrupts
        try:
            int_table = wcl.get_table(report_code, "Interrupts", [fight_id],
                                      fight["startTime"], fight["endTime"])
            interrupt_rows.extend(
                process_utility_table(report_info, fight, int_table, "Interrupt", actor_map)
            )
        except Exception as e:
            print(f"      Warning: Could not fetch interrupt data: {e}")

        # Dispels
        try:
            disp_table = wcl.get_table(report_code, "Dispels", [fight_id],
                                       fight["startTime"], fight["endTime"])
            dispel_rows.extend(
                process_utility_table(report_info, fight, disp_table, "Dispel", actor_map)
            )
        except Exception as e:
            print(f"      Warning: Could not fetch dispel data: {e}")

        # Deaths
        death_table = {}
        try:
            death_table = wcl.get_table(report_code, "Deaths", [fight_id],
                                        fight["startTime"], fight["endTime"])
            death_rows.extend(process_deaths(report_info, fight, death_table, actor_map))
        except Exception as e:
            print(f"      Warning: Could not fetch death data: {e}")

        # Consumables
        consumable_events_raw = []
        if consumable_ids:
            try:
                id_list = ", ".join(str(i) for i in consumable_ids)
                consumable_events_raw = wcl.get_events(
                    report_code, "Casts",
                    fight["startTime"], fight["endTime"],
                    fight_ids=[fight_id],
                    filter_expression=f"ability.id IN ({id_list})",
                )
                consumable_rows.extend(
                    process_consumables(report_info, fight, consumable_events_raw,
                                        actor_map, consumable_config)
                )
            except Exception as e:
                print(f"      Warning: Could not fetch consumable data: {e}")

        # Defensive Cooldowns
        defensive_events_raw = []
        if defensive_ids:
            try:
                id_list = ", ".join(str(i) for i in defensive_ids)
                defensive_events_raw = wcl.get_events(
                    report_code, "Casts",
                    fight["startTime"], fight["endTime"],
                    fight_ids=[fight_id],
                    filter_expression=f"ability.id IN ({id_list})",
                )
                defensive_rows.extend(
                    process_defensives(report_info, fight, defensive_events_raw,
                                       actor_map, defensive_config)
                )
            except Exception as e:
                print(f"      Warning: Could not fetch defensive data: {e}")

        # Combat Res (for timeline)
        combat_res_events_raw = []
        if COMBAT_RES_IDS:
            try:
                id_list = ", ".join(str(i) for i in COMBAT_RES_IDS)
                combat_res_events_raw = wcl.get_events(
                    report_code, "Casts",
                    fight["startTime"], fight["endTime"],
                    fight_ids=[fight_id],
                    filter_expression=f"ability.id IN ({id_list})",
                )
            except Exception as e:
                print(f"      Warning: Could not fetch combat res data: {e}")

        # Timeline (uses data already fetched above)
        try:
            timeline_rows.extend(
                process_timeline(report_info, fight, death_table,
                                 consumable_events_raw, defensive_events_raw,
                                 combat_res_events_raw,
                                 actor_map, consumable_config, defensive_config)
            )
        except Exception as e:
            print(f"      Warning: Could not build timeline: {e}")

    consumable_headers = get_consumable_headers(consumable_config)

    return {
        "Performance": (PERFORMANCE_HEADERS, perf_rows),
        "Deaths": (DEATHS_HEADERS, death_rows),
        "Timeline": (TIMELINE_HEADERS, timeline_rows),
        "Interrupts": (UTILITY_HEADERS, interrupt_rows),
        "Dispels": (UTILITY_HEADERS, dispel_rows),
        "Consumables": (consumable_headers, consumable_rows),
        "Defensives": (DEFENSIVES_HEADERS, defensive_rows),
    }


def main():
    parser = argparse.ArgumentParser(description="Przemielimy Raid Analyzer")
    parser.add_argument("--reports", type=int, default=5,
                        help="Number of recent reports to analyze (default: 5)")
    parser.add_argument("--code", type=str, default=None,
                        help="Analyze a specific report by code")
    parser.add_argument("--no-sheets", action="store_true",
                        help="Skip writing to Google Sheets (dry run)")
    parser.add_argument("--attendance", action="store_true",
                        help="Also fetch guild attendance data")
    parser.add_argument("--list", action="store_true",
                        help="List recent reports with fight counts and exit")
    parser.add_argument("--smart", action="store_true",
                        help="Smart mode: group reports by raid night, pick the one with "
                             "the most Mythic pulls per night. Ignores duplicate/partial logs.")
    args = parser.parse_args()

    # Initialize WCL client
    print("Connecting to Warcraft Logs API...")
    wcl = WCLClient()

    # List mode: show recent reports and exit
    if args.list:
        server_slug = GUILD_SERVER.lower().replace(" ", "-")
        print(f"Fetching reports for {GUILD_NAME} ({GUILD_SERVER}, {GUILD_REGION})...\n")
        reports_data = wcl.get_guild_reports(
            GUILD_NAME, server_slug, GUILD_REGION.lower(), limit=args.reports
        )
        from data_processor import format_timestamp
        print(f"{'Code':<20} {'Date':<18} {'Mythic':<8} {'HC':<5} {'Other':<6} {'Title / Bosses'}")
        print("-" * 120)
        for r in reports_data["data"]:
            fights_data = wcl.get_report_fights(r["code"])
            all_fights = fights_data.get("fights", [])
            from collections import Counter
            mythic = [f for f in all_fights if f.get("difficulty") == 5]
            heroic = [f for f in all_fights if f.get("difficulty") == 4]
            other = [f for f in all_fights if f.get("difficulty") not in (4, 5)]
            mythic_bosses = Counter(f["name"] for f in mythic)
            mythic_str = ", ".join(f"{n}x{c}" for n, c in mythic_bosses.items()) or "-"
            print(f"{r['code']:<20} {format_timestamp(r['startTime']):<18} "
                  f"{len(mythic):<8} {len(heroic):<5} {len(other):<6} "
                  f"{r.get('title', '')[:40]} | Mythic: {mythic_str}")
        print("\nUse: python main.py --code <CODE>  to process a specific report")
        return

    # Determine which reports to analyze
    if args.code:
        report_codes = [args.code]
    elif args.smart:
        server_slug = GUILD_SERVER.lower().replace(" ", "-")
        print(f"Fetching reports for {GUILD_NAME} ({GUILD_SERVER}, {GUILD_REGION})...")
        reports_data = wcl.get_guild_reports(
            GUILD_NAME, server_slug, GUILD_REGION.lower(), limit=args.reports
        )
        raw_reports = reports_data["data"]
        print(f"  Inspecting {len(raw_reports)} candidate reports for Mythic content...")

        # Fetch fight info for each report, count Mythic pulls
        from datetime import datetime
        from collections import defaultdict
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

        # Group by raid date, pick best log per night
        by_date = defaultdict(list)
        for r in scored:
            by_date[r["date"]].append(r)

        picks = []
        for date, candidates in sorted(by_date.items(), reverse=True):
            # Sort: most Mythic pulls first, then earliest startTime (logger who was there from start)
            candidates.sort(key=lambda r: (-r["mythic_count"], r["startTime"]))
            winner = candidates[0]
            picks.append(winner)
            print(f"  [{date}] Picked {winner['code']} ({winner['mythic_count']} Mythic pulls, "
                  f"{winner['unique_bosses']} bosses) - '{winner['title'][:40]}'")
            for loser in candidates[1:]:
                print(f"           Skipped {loser['code']} ({loser['mythic_count']} Mythic pulls)")

        report_codes = [p["code"] for p in picks]
        print(f"Smart mode: selected {len(report_codes)} best log(s) from {len(raw_reports)} reports.")
    else:
        server_slug = GUILD_SERVER.lower().replace(" ", "-")
        print(f"Fetching reports for {GUILD_NAME} ({GUILD_SERVER}, {GUILD_REGION})...")
        reports_data = wcl.get_guild_reports(
            GUILD_NAME, server_slug, GUILD_REGION.lower(), limit=args.reports
        )
        report_codes = [r["code"] for r in reports_data["data"]]
        print(f"Found {len(report_codes)} reports.")

    # Load config and check deduplication
    if not args.no_sheets:
        print("Connecting to Google Sheets...")
        sheets = SheetsClient()

        # Load config from sheets (creates defaults if first run)
        print("Loading config from sheets...")
        consumable_config, defensive_config = load_config_from_sheets(sheets)

        # Deduplication
        existing_codes = sheets.get_existing_report_codes("Performance")
        if existing_codes:
            print(f"  Found {len(existing_codes)} existing report(s) in spreadsheet.")
    else:
        consumable_config, defensive_config = load_default_config()
        existing_codes = set()

    # Filter out already-processed reports
    new_codes = [c for c in report_codes if c not in existing_codes]
    skipped = len(report_codes) - len(new_codes)
    if skipped:
        print(f"  Skipping {skipped} already-processed report(s).")
    if not new_codes:
        print("No new reports to analyze.")
        return

    # Analyze each report
    consumable_headers = get_consumable_headers(consumable_config)
    all_results = {
        "Performance": (PERFORMANCE_HEADERS, []),
        "Deaths": (DEATHS_HEADERS, []),
        "Timeline": (TIMELINE_HEADERS, []),
        "Interrupts": (UTILITY_HEADERS, []),
        "Dispels": (UTILITY_HEADERS, []),
        "Consumables": (consumable_headers, []),
        "Defensives": (DEFENSIVES_HEADERS, []),
    }

    for code in new_codes:
        print(f"\nAnalyzing report: {code}")
        try:
            results = analyze_report(wcl, code, consumable_config, defensive_config)
            for sheet_name, (headers, rows) in results.items():
                all_results[sheet_name] = (headers, all_results[sheet_name][1] + rows)
        except Exception as e:
            print(f"  Error analyzing report {code}: {e}")
            continue

    # Attendance
    if args.attendance:
        print("\nFetching attendance data...")
        try:
            server_slug = GUILD_SERVER.lower().replace(" ", "-")
            att_data = wcl.get_guild_attendance(
                GUILD_NAME, server_slug, GUILD_REGION.lower()
            )
            att_rows = process_attendance(att_data)
            all_results["Attendance"] = (ATTENDANCE_HEADERS, att_rows)
        except Exception as e:
            print(f"  Error fetching attendance: {e}")

    # Print summary
    print("\n--- Summary ---")
    for sheet_name, (headers, rows) in all_results.items():
        print(f"  {sheet_name}: {len(rows)} rows")

    # Write to Google Sheets (append, not overwrite)
    if not args.no_sheets:
        print("\nWriting to Google Sheets...")
        for sheet_name, (headers, rows) in all_results.items():
            if rows:
                print(f"  Appending {sheet_name} ({len(rows)} rows)...")
                sheets.append_rows(sheet_name, headers, rows)
        print("Done! Check your Google Sheets spreadsheet.")
    else:
        print("\nDry run - skipping Google Sheets write.")


if __name__ == "__main__":
    main()
