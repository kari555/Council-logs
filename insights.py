"""Shared raid insight aggregations for experimental and production views."""

import numpy as np
import pandas as pd


def _empty() -> pd.DataFrame:
    return pd.DataFrame()


def target_priority(targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if targets.empty:
        return _empty(), _empty()
    t = targets.copy()
    t = t[
        t["Target"].notna()
        & ~t["Target"].astype(str).str.lower().isin(["", "none", "nan", "undefined", "unknown"])
    ].copy()
    if t.empty:
        return _empty(), _empty()

    player_target = (
        t.groupby(["Player", "Class", "Target", "Target Type"], as_index=False)
        .agg(Damage=("Damage", "sum"))
    )
    per_player = (
        player_target.groupby(["Player", "Class"], as_index=False)
        .agg(Total=("Damage", "sum"))
    )
    boss_damage = (
        player_target[player_target["Target Type"].eq("Boss")]
        .groupby("Player")["Damage"].sum()
    )
    per_player["Boss Damage"] = per_player["Player"].map(boss_damage).fillna(0)
    per_player["Non Boss Damage"] = per_player["Total"] - per_player["Boss Damage"]
    per_player["Boss Share %"] = np.where(
        per_player["Total"] > 0,
        per_player["Boss Damage"] / per_player["Total"] * 100,
        0,
    )
    per_player = per_player.sort_values("Boss Damage", ascending=False)
    target_totals = (
        player_target.groupby(["Target", "Target Type"], as_index=False)
        .agg(Damage=("Damage", "sum"))
        .sort_values("Damage", ascending=True)
    )
    return per_player, target_totals


def death_quality(deaths: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if deaths.empty:
        return _empty(), _empty(), _empty()
    d = deaths.copy()
    d["Early Death"] = d["Death Time (s)"].fillna(9999) <= 90
    by_player = (
        d.groupby(["Player", "Class"], as_index=False)
        .agg(
            Deaths=("Player", "count"),
            Early=("Early Death", "sum"),
            Avg_Time=("Death Time (s)", "mean"),
        )
        .sort_values("Deaths", ascending=False)
    )
    by_ability = (
        d.groupby("Killing Blow", as_index=False)
        .agg(Deaths=("Player", "count"))
        .sort_values("Deaths", ascending=True)
    )
    return by_player, by_ability, d


def defensive_quality(
    perf: pd.DataFrame,
    deaths: pd.DataFrame,
    defensives: pd.DataFrame,
    defensive_events: pd.DataFrame,
) -> pd.DataFrame:
    d_count = deaths.groupby("Player").size().rename("Deaths") if not deaths.empty else pd.Series(dtype=float)
    def_count = defensives.groupby("Player")["Count"].sum().rename("Defensives") if not defensives.empty else pd.Series(dtype=float)
    pulls_count = perf.groupby("Player")["Fight ID"].nunique().rename("Pulls") if not perf.empty else pd.Series(dtype=float)
    out = pd.concat([pulls_count, d_count, def_count], axis=1).fillna(0).reset_index()
    if out.empty:
        return out
    out["Defensives / Pull"] = np.where(out["Pulls"] > 0, out["Defensives"] / out["Pulls"], 0)
    out["Defensives / Death"] = np.where(out["Deaths"] > 0, out["Defensives"] / out["Deaths"], np.nan)

    if not deaths.empty and not defensive_events.empty:
        death_pairs = deaths[["Report", "Fight ID", "Player", "Death Time (s)"]].dropna()
        event_pairs = defensive_events[["Report", "Fight ID", "Player", "Event Time (s)"]].dropna()
        before_count = {}
        for _, death in death_pairs.iterrows():
            mask = (
                (event_pairs["Report"] == death["Report"])
                & (event_pairs["Fight ID"] == death["Fight ID"])
                & (event_pairs["Player"] == death["Player"])
                & (event_pairs["Event Time (s)"] >= death["Death Time (s)"] - 15)
                & (event_pairs["Event Time (s)"] <= death["Death Time (s)"])
            )
            if mask.any():
                before_count[death["Player"]] = before_count.get(death["Player"], 0) + 1
        out["Deaths With Defensive 15s"] = out["Player"].map(before_count).fillna(0).astype(int)
        out["Defensive Before Death %"] = np.where(
            out["Deaths"] > 0,
            out["Deaths With Defensive 15s"] / out["Deaths"] * 100,
            np.nan,
        )
    return out.sort_values(["Deaths", "Defensives"], ascending=[False, True])


def consumable_compliance(consumables: pd.DataFrame) -> pd.DataFrame:
    if consumables.empty:
        return _empty()
    cons = consumables.copy()
    skip = {
        "Report", "Date", "Boss", "Pull #", "Result", "Boss HP %", "Duration (s)",
        "Player", "Class", "Fight ID", "Kill",
    }
    cons_cols = [col for col in cons.columns if col not in skip]
    if not cons_cols:
        return _empty()
    for col in cons_cols:
        cons[col] = pd.to_numeric(cons[col], errors="coerce").fillna(0)
    cons["Total Consumables"] = cons[cons_cols].sum(axis=1)
    out = (
        cons.groupby(["Player", "Class"], as_index=False)
        .agg(
            Pulls=("Player", "count"),
            Pulls_With_Any=("Total Consumables", lambda s: int((s > 0).sum())),
            Avg_Consumables=("Total Consumables", "mean"),
        )
    )
    out["Compliance %"] = np.where(out["Pulls"] > 0, out["Pulls_With_Any"] / out["Pulls"] * 100, 0)
    return out.sort_values("Compliance %", ascending=True)


def active_time(performance: pd.DataFrame) -> pd.DataFrame:
    if performance.empty or "Type" not in performance.columns:
        return _empty()
    p = performance[performance["Type"].eq("DPS")].copy()
    if p.empty:
        return _empty()
    out = (
        p.groupby(["Player", "Class"], as_index=False)
        .agg(
            Pulls=("Player", "count"),
            Avg_Active=("Active %", "mean"),
            Low_Active=("Active %", lambda s: int((s < 80).sum())),
        )
        .sort_values("Avg_Active", ascending=True)
    )
    return out


def utility_coverage(interrupts: pd.DataFrame, dispels: pd.DataFrame,
                     enemy_casts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    int_count = interrupts.groupby("Player")["Count"].sum().rename("Interrupts") if not interrupts.empty else pd.Series(dtype=float)
    disp_count = dispels.groupby("Player")["Count"].sum().rename("Dispels") if not dispels.empty else pd.Series(dtype=float)
    utility = pd.concat([int_count, disp_count], axis=1).fillna(0).reset_index()
    if not utility.empty:
        utility["Total"] = utility["Interrupts"] + utility["Dispels"]
        utility = utility.sort_values("Total", ascending=False)

    if enemy_casts.empty:
        return utility, _empty()
    casts = (
        enemy_casts.groupby("Ability", as_index=False)
        .agg(Casts=("Ability", "count"), Targets=("Target", "nunique"))
        .sort_values("Casts", ascending=False)
    )
    return utility, casts


def gear_parse_summary(rankings: pd.DataFrame, boss_rankings: pd.DataFrame,
                       player_details: pd.DataFrame) -> pd.DataFrame:
    if rankings.empty:
        return _empty()
    r = rankings.copy()
    out = (
        r.groupby(["Player", "Class", "Spec"], as_index=False)
        .agg(
            Avg_Parse=("Parse %", "mean"),
            Best_Parse=("Parse %", "max"),
            Avg_Ilvl=("Item Level", "mean"),
            Avg_Ilvl_Parse=("ilvl Parse %", "mean"),
            Rows=("Player", "count"),
        )
    )
    if not boss_rankings.empty:
        boss = (
            boss_rankings.groupby("Player", as_index=False)
            .agg(Avg_Boss_Parse=("Parse %", "mean"), Best_Boss_Parse=("Parse %", "max"))
        )
        out = out.merge(boss, on="Player", how="left")
    if not player_details.empty:
        details = (
            player_details.sort_values("Date")
            .groupby("Player", as_index=False)
            .agg(Role=("Role", "last"), Trinkets=("Trinkets", "last"), Talent_Summary=("Talent Summary", "last"))
        )
        out = out.merge(details, on="Player", how="left")
    return out.sort_values("Avg_Parse", ascending=False)


def raid_composition(performance: pd.DataFrame, player_details: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = performance[performance["Type"].eq("DPS")].copy() if not performance.empty and "Type" in performance.columns else performance.copy()
    if p.empty:
        return _empty(), _empty()
    class_totals = (
        p.groupby(["Report", "Boss", "Pull #", "Class"], as_index=False)
        .agg(Players=("Player", "nunique"))
        .groupby("Class", as_index=False)["Players"].sum()
        .sort_values("Players", ascending=True)
    )
    fight_size = (
        p.groupby(["Report", "Boss", "Pull #", "Result"], as_index=False)
        .agg(Players=("Player", "nunique"), Classes=("Class", "nunique"))
        .sort_values(["Report", "Boss", "Pull #"])
    )
    if not player_details.empty and "Role" in player_details.columns:
        role_counts = (
            player_details[player_details["Role"].astype(str).ne("")]
            .groupby(["Report", "Boss", "Pull #", "Role"], as_index=False)
            .agg(Players=("Player", "nunique"))
        )
        if not role_counts.empty:
            fight_size = fight_size.merge(
                role_counts.pivot_table(
                    index=["Report", "Boss", "Pull #"],
                    columns="Role",
                    values="Players",
                    fill_value=0,
                    aggfunc="sum",
                ).reset_index(),
                on=["Report", "Boss", "Pull #"],
                how="left",
            )
    return class_totals, fight_size


def build_playground_insights(frames: dict[str, pd.DataFrame]) -> dict[str, object]:
    return {
        "target_priority": target_priority(frames.get("targets", _empty())),
        "death_quality": death_quality(frames.get("deaths", _empty())),
        "defensive_quality": defensive_quality(
            frames.get("performance", _empty()),
            frames.get("deaths", _empty()),
            frames.get("defensives", _empty()),
            frames.get("defensive_events", _empty()),
        ),
        "consumable_compliance": consumable_compliance(frames.get("consumables", _empty())),
        "active_time": active_time(frames.get("performance", _empty())),
        "utility_coverage": utility_coverage(
            frames.get("interrupts", _empty()),
            frames.get("dispels", _empty()),
            frames.get("enemy_casts", _empty()),
        ),
        "gear_parse_summary": gear_parse_summary(
            frames.get("rankings", _empty()),
            frames.get("boss_rankings", _empty()),
            frames.get("player_details", _empty()),
        ),
        "raid_composition": raid_composition(
            frames.get("performance", _empty()),
            frames.get("player_details", _empty()),
        ),
    }
