"""Processes raw WCL data into structured rows for Google Sheets."""

from datetime import datetime


def build_actor_map(master_data):
    """Build a mapping of actor ID -> player info from report masterData.

    In masterData.actors: type="Player", subType="Monk" (this is the class, not spec).
    We store subType as class since type is always "Player" for player actors.
    """
    actors = {}
    for actor in master_data.get("actors", []):
        actors[actor["id"]] = {
            "name": actor["name"],
            "class": actor.get("subType", "Unknown"),
            "spec": "",
            "server": actor.get("server", ""),
        }
    return actors


def format_timestamp(epoch_ms):
    """Convert epoch milliseconds to readable date string."""
    return datetime.fromtimestamp(epoch_ms / 1000).strftime("%Y-%m-%d %H:%M")


def format_duration(ms):
    """Convert milliseconds to M:SS format."""
    total_seconds = int(ms / 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def fight_duration_seconds(fight):
    """Get fight duration in seconds."""
    return round((fight["endTime"] - fight["startTime"]) / 1000, 1)


def fight_boss_hp(fight):
    """Get boss HP % at end of fight. Kill = 0, Wipe = remaining %."""
    if fight["kill"]:
        return 0
    return fight.get("bossPercentage") or fight.get("fightPercentage") or None


def fight_result(fight):
    """Get fight result as string."""
    if fight["kill"]:
        return "Kill"
    hp = fight_boss_hp(fight)
    if hp is not None:
        return f"Wipe ({hp}%)"
    return "Wipe"


def fight_common_cols(report_info, fight):
    """Return common columns shared by all sheet types."""
    return [
        report_info["code"],
        format_timestamp(report_info["startTime"]),
        fight["name"],
        fight.get("pull_number", 0),
        fight_result(fight),
        fight_boss_hp(fight),
        fight_duration_seconds(fight),
    ]


COMMON_HEADERS = ["Report", "Date", "Boss", "Pull #", "Result", "Boss HP %", "Duration (s)"]


def build_config_lookup(config_records):
    """Build lookup structures from config sheet records.

    Args:
        config_records: list of dicts [{"Spell ID": int, "Name": str, "Category": str}, ...]

    Returns:
        tuple: (id_to_category, id_to_name, categories)
            - id_to_category: {spell_id: category_name}
            - id_to_name: {spell_id: ability_name}
            - categories: sorted list of unique category names
    """
    id_to_category = {}
    id_to_name = {}
    categories_set = set()
    for record in config_records:
        try:
            spell_id = int(record["Spell ID"])
        except (ValueError, KeyError):
            continue
        name = record.get("Name", f"Unknown({spell_id})")
        category = record.get("Category", "Other")
        id_to_category[spell_id] = category
        id_to_name[spell_id] = name
        categories_set.add(category)
    categories = sorted(categories_set)
    return id_to_category, id_to_name, categories


# ---------------------------------------------------------------------------
# Performance (DPS / HPS)
# ---------------------------------------------------------------------------

def process_performance(report_info, fight, table_data, data_type, actor_map):
    """Process DPS or HPS table into rows."""
    rows = []
    total_time_ms = table_data.get("totalTime", 1)
    common = fight_common_cols(report_info, fight)

    for entry in table_data.get("entries", []):
        per_second = round(entry["total"] / (total_time_ms / 1000), 1)
        active_pct = round(entry.get("activeTime", 0) / total_time_ms * 100, 1) if total_time_ms else 0
        rows.append(common + [
            entry["name"],
            entry.get("type", ""),
            entry.get("icon", "").split("-")[-1] if entry.get("icon") else "",
            data_type,
            round(entry["total"]),
            per_second,
            active_pct,
        ])
    return rows


PERFORMANCE_HEADERS = COMMON_HEADERS + [
    "Player", "Class", "Spec", "Type", "Total", "Per Second", "Active %",
]


def process_target_damage(report_info, fight, table_data, actor_map):
    """Process source-view damage table into player -> target damage rows."""
    rows = []
    common = fight_common_cols(report_info, fight)

    for entry in table_data.get("entries", []):
        source_id = entry.get("id")
        if source_id not in actor_map:
            continue

        player = entry.get("name", actor_map[source_id]["name"])
        player_class = entry.get("type", actor_map[source_id].get("class", ""))
        player_total = entry.get("total", 0) or 0

        targets = {}
        for target in entry.get("targets", []):
            target_name = target.get("name") or "Unknown"
            target_type = target.get("type") or ""
            key = (target_name, target_type)
            targets[key] = targets.get(key, 0) + (target.get("total", 0) or 0)

        for (target_name, target_type), damage in sorted(
            targets.items(), key=lambda item: item[1], reverse=True
        ):
            player_pct = round(damage / player_total * 100, 1) if player_total else 0
            rows.append(common + [
                player,
                player_class,
                target_name,
                target_type,
                round(damage),
                round(player_total),
                player_pct,
            ])

    return rows


TARGET_DAMAGE_HEADERS = COMMON_HEADERS + [
    "Player", "Class", "Target", "Target Type", "Damage",
    "Player Total", "% Player Damage",
]


# ---------------------------------------------------------------------------
# Consumables (config-driven)
# ---------------------------------------------------------------------------

def process_consumables(report_info, fight, events, actor_map, consumable_config):
    """Process consumable events into per-player counts."""
    id_to_category, _, categories = build_config_lookup(consumable_config)
    common = fight_common_cols(report_info, fight)

    player_counts = {}
    for event in events:
        source_id = event.get("sourceID")
        ability_id = event.get("abilityGameID")
        if source_id not in actor_map:
            continue
        player_name = actor_map[source_id]["name"]
        category = id_to_category.get(ability_id, "Other")

        if player_name not in player_counts:
            player_counts[player_name] = {cat: 0 for cat in categories}
        player_counts[player_name][category] = player_counts[player_name].get(category, 0) + 1

    rows = []
    for player_name, counts in sorted(player_counts.items()):
        actor_info = next(
            (a for a in actor_map.values() if a["name"] == player_name),
            {"class": "", "spec": ""},
        )
        row = common + [player_name, actor_info["class"]]
        for cat in categories:
            row.append(counts.get(cat, 0))
        rows.append(row)

    return rows


def get_consumable_headers(consumable_config):
    """Generate dynamic headers based on config categories."""
    _, _, categories = build_config_lookup(consumable_config)
    return COMMON_HEADERS + ["Player", "Class"] + categories


# ---------------------------------------------------------------------------
# Interrupts & Dispels
# ---------------------------------------------------------------------------

def process_utility_table(report_info, fight, table_data, data_type, actor_map):
    """Process interrupt/dispel table data into rows.

    WCL interrupt/dispel tables are nested:
      entries[] -> abilities being interrupted (e.g. "Black Miasma")
        entries[] -> same nesting again in some cases
          details[] -> players who performed the interrupt, with total count
    """
    rows = []
    common = fight_common_cols(report_info, fight)

    # Aggregate per player across all abilities
    player_totals = {}

    def extract_players(entries_list):
        for entry in entries_list:
            if "entries" in entry:
                extract_players(entry["entries"])
            for detail in entry.get("details", []):
                name = detail.get("name", "Unknown")
                cls = detail.get("type", "")
                total = detail.get("total", 0)
                if name in player_totals:
                    player_totals[name]["total"] += total
                else:
                    player_totals[name] = {"class": cls, "total": total}

    extract_players(table_data.get("entries", []))

    for player_name, info in sorted(player_totals.items()):
        rows.append(common + [
            player_name,
            info["class"],
            data_type,
            info["total"],
        ])
    return rows


UTILITY_HEADERS = COMMON_HEADERS + ["Player", "Class", "Type", "Count"]


# ---------------------------------------------------------------------------
# Defensive Cooldowns (config-driven)
# ---------------------------------------------------------------------------

def process_defensives(report_info, fight, events, actor_map, defensive_config):
    """Process defensive cooldown events into per-player counts."""
    _, id_to_name, _ = build_config_lookup(defensive_config)
    common = fight_common_cols(report_info, fight)

    player_counts = {}
    for event in events:
        source_id = event.get("sourceID")
        ability_id = event.get("abilityGameID")
        if source_id not in actor_map:
            continue
        player_name = actor_map[source_id]["name"]
        ability_name = id_to_name.get(ability_id, f"Unknown({ability_id})")

        if player_name not in player_counts:
            player_counts[player_name] = {}
        player_counts[player_name][ability_name] = player_counts[player_name].get(ability_name, 0) + 1

    rows = []
    for player_name, abilities in sorted(player_counts.items()):
        actor_info = next(
            (a for a in actor_map.values() if a["name"] == player_name),
            {"class": "", "spec": ""},
        )
        for ability_name, count in sorted(abilities.items()):
            rows.append(common + [
                player_name,
                actor_info["class"],
                ability_name,
                count,
            ])
    return rows


DEFENSIVES_HEADERS = COMMON_HEADERS + ["Player", "Class", "Ability", "Count"]


# ---------------------------------------------------------------------------
# Deaths
# ---------------------------------------------------------------------------

def process_deaths(report_info, fight, table_data, actor_map):
    """Process death table data into rows.

    WCL Deaths table structure:
      entries[] -> each entry is a death event with:
        name: player name
        type: class
        timestamp: ms relative to REPORT start (not fight start!)
        killingBlow: {name, guid, type} - the ability that killed them
        events: list of last damage/heal events before death
    """
    rows = []
    common = fight_common_cols(report_info, fight)
    fight_start = fight["startTime"]

    for entry in table_data.get("entries", []):
        player_name = entry.get("name", "Unknown")
        player_class = entry.get("type", "")

        # timestamp is relative to report start, convert to fight-relative
        death_time_report_ms = entry.get("timestamp", 0)
        death_time_ms = death_time_report_ms - fight_start
        if death_time_ms < 0:
            death_time_ms = 0
        death_time_s = round(death_time_ms / 1000, 1)
        death_time_fmt = format_duration(death_time_ms)

        # Killing blow is a direct field
        killing_blow_obj = entry.get("killingBlow")
        if killing_blow_obj:
            killing_blow = killing_blow_obj.get("name", "Unknown")
        else:
            # Fallback: last event in events list
            events = entry.get("events", [])
            if events and events[0].get("type") == "damage":
                killing_blow = events[0].get("ability", {}).get("name", "Unknown")
            else:
                killing_blow = "Unknown"

        rows.append(common + [
            player_name,
            player_class,
            death_time_s,
            death_time_fmt,
            killing_blow,
        ])
    return rows


DEATHS_HEADERS = COMMON_HEADERS + [
    "Player", "Class", "Death Time (s)", "Death Time", "Killing Blow",
]


# ---------------------------------------------------------------------------
# Timeline (unified event timeline per fight)
# ---------------------------------------------------------------------------

def process_timeline(report_info, fight, death_table, consumable_events,
                     defensive_events, combat_res_events,
                     actor_map, consumable_config, defensive_config):
    """Build a unified timeline of key events during a fight.

    Combines data from deaths, consumables, defensives and combat res into
    a single chronological list. No extra API calls needed - reuses existing data.
    """
    common = fight_common_cols(report_info, fight)
    fight_duration_ms = fight["endTime"] - fight["startTime"]
    fight_start = fight["startTime"]
    rows = []

    # Build player index (stable numbering for scatter plot Y axis)
    # Collect all player names from actor_map, sorted alphabetically
    friendly_ids = fight.get("friendlyPlayers", [])
    player_names = sorted(set(
        actor_map[pid]["name"] for pid in friendly_ids if pid in actor_map
    ))
    # Fallback: use all actors if friendlyPlayers is empty
    if not player_names:
        player_names = sorted(set(a["name"] for a in actor_map.values()))
    player_index = {name: idx + 1 for idx, name in enumerate(player_names)}

    def add_event(time_ms, event_type, player_name, player_class, detail):
        idx = player_index.get(player_name, 0)
        rows.append(common + [
            round(time_ms / 1000, 1),
            format_duration(time_ms),
            event_type,
            player_name,
            player_class,
            idx,
            detail,
        ])

    # Fight Start
    rows.append(common + [0.0, "0:00", "Fight Start", "", "", 0, ""])

    # Deaths (from death table)
    for entry in death_table.get("entries", []):
        death_time_ms = entry.get("timestamp", 0) - fight_start
        if death_time_ms < 0:
            death_time_ms = 0
        killing_blow_obj = entry.get("killingBlow")
        killing_blow = killing_blow_obj.get("name", "Unknown") if killing_blow_obj else ""
        add_event(death_time_ms, "Death",
                  entry.get("name", "Unknown"), entry.get("type", ""), killing_blow)

    # Combat Res (from raw events)
    for event in combat_res_events:
        source_id = event.get("sourceID")
        target_id = event.get("targetID")
        if source_id not in actor_map:
            continue
        event_time_ms = event.get("timestamp", 0) - fight_start
        if event_time_ms < 0:
            continue
        ability_name = event.get("ability", {}).get("name", "Combat Res")
        # Target is the one being resurrected
        target_name = actor_map.get(target_id, {}).get("name", "Unknown")
        source_name = actor_map[source_id]["name"]
        detail = f"{ability_name} on {target_name}" if target_name != "Unknown" else ability_name
        add_event(event_time_ms, "Combat Res",
                  source_name, actor_map[source_id]["class"], detail)

    # Consumables (from raw events)
    consumable_lookup = build_config_lookup(consumable_config)
    id_to_category = consumable_lookup[0]
    id_to_name = consumable_lookup[1]

    for event in consumable_events:
        source_id = event.get("sourceID")
        if source_id not in actor_map:
            continue
        ability_id = event.get("abilityGameID")
        event_time_ms = event.get("timestamp", 0) - fight_start
        if event_time_ms < 0:
            continue
        category = id_to_category.get(ability_id, "Consumable")
        name = id_to_name.get(ability_id, f"Unknown({ability_id})")
        add_event(event_time_ms, category,
                  actor_map[source_id]["name"], actor_map[source_id]["class"], name)

    # Defensives (from raw events)
    defensive_lookup = build_config_lookup(defensive_config)
    def_id_to_name = defensive_lookup[1]
    def_id_to_category = defensive_lookup[0]

    for event in defensive_events:
        source_id = event.get("sourceID")
        if source_id not in actor_map:
            continue
        ability_id = event.get("abilityGameID")
        event_time_ms = event.get("timestamp", 0) - fight_start
        if event_time_ms < 0:
            continue
        ability_name = def_id_to_name.get(ability_id, f"Unknown({ability_id})")
        category = def_id_to_category.get(ability_id, "Defensive")
        event_type = f"Defensive ({category})" if category else "Defensive"
        add_event(event_time_ms, event_type,
                  actor_map[source_id]["name"], actor_map[source_id]["class"], ability_name)

    # Fight End
    rows.append(common + [
        round(fight_duration_ms / 1000, 1),
        format_duration(fight_duration_ms),
        "Fight End", "", "", 0,
        fight_result(fight),
    ])

    # Sort by event time
    rows.sort(key=lambda r: r[len(common)])

    return rows


TIMELINE_HEADERS = COMMON_HEADERS + [
    "Event Time (s)", "Event Time", "Event Type", "Player", "Class",
    "Player Index", "Detail",
]


# ---------------------------------------------------------------------------
# Playground detail events
# ---------------------------------------------------------------------------

def _event_fight_time(fight, event):
    time_ms = event.get("timestamp", 0) - fight["startTime"]
    if time_ms < 0:
        time_ms = 0
    return time_ms, round(time_ms / 1000, 1), format_duration(time_ms)


def process_timed_spell_events(report_info, fight, events, actor_map,
                               config_records, event_group):
    """Process raw player cast events into timestamped rows for Playground."""
    id_to_category, id_to_name, _ = build_config_lookup(config_records)
    common = fight_common_cols(report_info, fight)
    rows = []

    for event in events:
        source_id = event.get("sourceID")
        if source_id not in actor_map:
            continue
        ability_id = event.get("abilityGameID")
        event_ms, event_s, event_label = _event_fight_time(fight, event)
        if event_ms > fight["endTime"] - fight["startTime"]:
            continue
        ability_name = (
            id_to_name.get(ability_id)
            or event.get("ability", {}).get("name")
            or f"Spell {ability_id}"
        )
        rows.append(common + [
            event_s,
            event_label,
            actor_map[source_id]["name"],
            actor_map[source_id].get("class", ""),
            event_group,
            id_to_category.get(ability_id, "Other"),
            ability_name,
            ability_id,
        ])

    return rows


TIMED_SPELL_HEADERS = COMMON_HEADERS + [
    "Event Time (s)", "Event Time", "Player", "Class",
    "Event Group", "Category", "Ability", "Ability ID",
]


def process_enemy_cast_events(report_info, fight, events, actor_map, ability_map=None):
    """Process enemy cast events into named cast rows.

    Source names are best-effort because report masterData is currently loaded for
    players only; ability names remain reliable through masterData abilities or
    inline event ability data.
    """
    common = fight_common_cols(report_info, fight)
    fight_duration_ms = fight["endTime"] - fight["startTime"]
    rows = []

    for event in events:
        if event.get("sourceID") in actor_map:
            continue
        event_ms, event_s, event_label = _event_fight_time(fight, event)
        if event_ms > fight_duration_ms:
            continue
        ability_id = event.get("abilityGameID", 0)
        ability_name = (
            (ability_map.get(ability_id) if ability_map else None)
            or event.get("ability", {}).get("name")
            or f"Spell {ability_id}"
        )
        target_id = event.get("targetID")
        target_name = actor_map.get(target_id, {}).get("name", f"Actor {target_id}" if target_id else "")
        rows.append(common + [
            event_s,
            event_label,
            event.get("sourceID", ""),
            target_name,
            ability_name,
            ability_id,
        ])

    return rows


ENEMY_CAST_HEADERS = COMMON_HEADERS + [
    "Event Time (s)", "Event Time", "Source ID", "Target",
    "Ability", "Ability ID",
]


def process_player_details(report_info, fight, details_raw):
    """Flatten WCL playerDetails into stable player rows.

    WCL returns a JSON scalar with a role/spec-oriented structure that can vary
    between report types. This keeps the stable fields and stores compact talent
    and gear summaries when they exist.
    """
    common = fight_common_cols(report_info, fight)
    rows = []

    def walk(value, role_hint="", spec_hint=""):
        if isinstance(value, list):
            for item in value:
                walk(item, role_hint, spec_hint)
            return
        if not isinstance(value, dict):
            return

        if "name" in value and ("type" in value or "class" in value or "itemLevel" in value):
            gear = value.get("gear") if isinstance(value.get("gear"), list) else []
            talents = value.get("talents") if isinstance(value.get("talents"), list) else []
            trinkets = [
                str(item.get("name") or item.get("id") or "")
                for item in gear
                if isinstance(item, dict) and str(item.get("slot") or "").lower() in {"trinket", "trinket1", "trinket2", "12", "13"}
            ]
            talent_summary = ", ".join(
                str(t.get("name") or t.get("id") or "")
                for t in talents[:8]
                if isinstance(t, dict)
            )
            rows.append(common + [
                value.get("name", ""),
                value.get("type") or value.get("class") or "",
                value.get("spec") or value.get("bestSpec") or spec_hint,
                value.get("role") or role_hint,
                round(float(value.get("itemLevel") or value.get("ilvl") or 0), 1),
                ", ".join([t for t in trinkets if t]),
                talent_summary,
            ])
            return

        for key, child in value.items():
            next_role = role_hint
            next_spec = spec_hint
            if key in {"tanks", "healers", "dps", "melee", "ranged"}:
                next_role = key
            elif isinstance(child, (list, dict)):
                next_spec = spec_hint or key
            walk(child, next_role, next_spec)

    walk(details_raw)

    # Deduplicate in case WCL exposes the same character under several groups.
    deduped = {}
    for row in rows:
        key = (row[0], row[2], row[3], row[len(common)])
        deduped[key] = row
    return list(deduped.values())


PLAYER_DETAILS_HEADERS = COMMON_HEADERS + [
    "Player", "Class", "Spec", "Role", "Item Level",
    "Trinkets", "Talent Summary",
]


# ---------------------------------------------------------------------------
# Damage Taken (avoidable hits for player profile timeline)
# ---------------------------------------------------------------------------

# WCL hitType codes
_HIT_TYPES_LANDED = {1, 2}  # 1 = Normal, 2 = Critical
_MELEE_NAMES = {"melee", "auto attack", "auto-attack", "sinister strike"}


def build_ability_map(master_data):
    """Build {gameID: name} lookup from report masterData abilities."""
    return {
        a["gameID"]: a["name"]
        for a in master_data.get("abilities", [])
        if a.get("name") and a.get("gameID")
    }


def process_damage_taken_events(report_info, fight, events, actor_map,
                                ability_map=None):
    """Process raw DamageTaken events into per-hit rows.

    Keeps only avoidable hits: Normal/Critical from non-player sources,
    excluding melee auto-attacks.  Ability names come from masterData
    ability_map (preferred) → inline event.ability.name → Spell <ID>.
    """
    fight_start = fight["startTime"]
    fight_end = fight["endTime"]
    fight_duration_ms = fight_end - fight_start
    common = fight_common_cols(report_info, fight)
    rows = []

    for event in events:
        target_id = event.get("targetID")
        source_id = event.get("sourceID")

        # Target must be a known player
        if target_id not in actor_map:
            continue

        # Source must NOT be a player (i.e. it's an NPC/enemy)
        if source_id in actor_map:
            continue

        # Only landed hits (Normal=1, Critical=2)
        hit_type = event.get("hitType", 0)
        if hit_type not in _HIT_TYPES_LANDED:
            continue

        time_ms = event.get("timestamp", 0) - fight_start
        if time_ms < 0 or time_ms > fight_duration_ms:
            continue

        ability_id = event.get("abilityGameID", 0)
        ability_name = (
            (ability_map.get(ability_id) if ability_map else None)
            or event.get("ability", {}).get("name")
            or f"Spell {ability_id}"
        )

        # Skip auto-attacks
        if ability_name.lower() in _MELEE_NAMES:
            continue

        player_name = actor_map[target_id]["name"]
        player_class = actor_map[target_id].get("class", "")
        amount = event.get("amount", 0)

        rows.append(common + [
            round(time_ms / 1000, 1),
            format_duration(time_ms),
            player_name,
            player_class,
            ability_name,
            ability_id,
            amount,
            hit_type,
        ])

    return rows


DAMAGE_TAKEN_HEADERS = COMMON_HEADERS + [
    "Event Time (s)", "Event Time", "Player", "Class",
    "Ability", "Ability ID", "Amount", "Hit Type",
]


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

def process_attendance(attendance_data, guild_filter=None, mythic_codes=None):
    """Process guild attendance data into rows."""
    rows = []
    for report in attendance_data.get("data", []):
        if mythic_codes and report["code"] not in mythic_codes:
            continue
        report_date = format_timestamp(report["startTime"])
        zone_name = report.get("zone", {}).get("name", "Unknown")
        for player in report.get("players", []):
            if guild_filter and player["name"] not in guild_filter:
                continue
            presence = player.get("presence", 0)
            rows.append([
                report["code"],
                report_date,
                zone_name,
                player["name"],
                player.get("type", ""),
                presence,
                f"{round(presence * 100)}%" if isinstance(presence, (int, float)) else str(presence),
            ])
    return rows


ATTENDANCE_HEADERS = [
    "Report", "Date", "Zone", "Player", "Class", "Presence", "Presence %",
]


# ---------------------------------------------------------------------------
# Rankings (parse percentile + item level per player per fight)
# ---------------------------------------------------------------------------

def process_rankings(report_info, fight, rankings_raw, metric="Damage"):
    """Extract per-player parse % and item level from WCL fight rankings JSON."""
    rows = []
    common = fight_common_cols(report_info, fight)

    if not rankings_raw:
        return rows

    # WCL returns {"data": [...]} where each list item is one fight's rankings
    inner = rankings_raw if isinstance(rankings_raw, dict) else {}
    data_field = inner.get("data", [])
    if isinstance(data_field, list):
        inner = data_field[0] if data_field else {}
    elif isinstance(data_field, dict):
        inner = data_field

    roles = inner.get("roles", {}) if isinstance(inner, dict) else {}

    for role_key, role_data in roles.items():
        if not isinstance(role_data, dict):
            continue
        role_name = role_data.get("name", role_key)
        for char in role_data.get("characters", []):
            rows.append(common + [
                char.get("name", ""),
                char.get("class", ""),
                char.get("spec", "") or char.get("bestSpec", ""),
                role_name,
                round(float(char.get("rankPercent") or 0), 1),
                round(float(char.get("medianPercent") or 0), 1),
                round(float(char.get("amount") or 0), 1),
                round(float(char.get("itemLevel") or 0), 1),
                round(float(char.get("bracketPercent") or 0), 1),
                round(float(char.get("bracketData") or 0), 1),
                metric,
            ])
    return rows


RANKINGS_HEADERS = COMMON_HEADERS + [
    "Player", "Class", "Spec", "Role",
    "Parse %", "Median Parse %", "Amount", "Item Level",
    "ilvl Parse %", "ilvl Bracket", "Metric",
]
