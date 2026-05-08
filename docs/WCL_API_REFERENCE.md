# Warcraft Logs API v2 - Complete Reference

This document contains practical knowledge about the Warcraft Logs API v2 (GraphQL) gathered from building a raid analyzer. Use it as a quick reference when working with WCL data.

## 1. Authentication (OAuth2 Client Credentials)

**Endpoints:**
- Token endpoint: `https://www.warcraftlogs.com/oauth/token`
- GraphQL endpoint: `https://www.warcraftlogs.com/api/v2/client`

**Steps:**
1. Register an API client at `https://www.warcraftlogs.com/api/clients` - get `client_id` and `client_secret`.
2. Do NOT check "Public Client" - we need a client secret.
3. Redirect URL is required but not used for client_credentials - just set `http://localhost`.
4. POST to token endpoint with HTTP Basic Auth:

```python
import requests
resp = requests.post(
    "https://www.warcraftlogs.com/oauth/token",
    auth=(client_id, client_secret),
    data={"grant_type": "client_credentials"},
)
# Response: {"access_token": "...", "token_type": "Bearer", "expires_in": 86400}
```

5. Tokens are valid 24h. Refresh when needed.

**Headers for GraphQL requests:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
Accept: application/json
```

**Gotcha:** Always use `www.` in hostname - omitting it causes "site not found" errors.

---

## 2. Rate Limits

- **3600 points per hour** - resets every hour
- Simple queries (list reports) cost ~1 point
- Table/events queries cost ~1-3 points each
- Check current usage: `{ rateLimitData { limitPerHour, pointsSpentThisHour, pointsResetIn } }`

---

## 3. GraphQL Schema Root

Top-level query fields:
- `reportData` - access reports by code
- `guildData` - access guilds by name/server/region
- `characterData` - access characters
- `gameData` - static game data (abilities, classes, zones, encounters)
- `worldData` - world/zone/encounter data
- `rateLimitData` - check rate limit status

---

## 4. Guild Reports (list recent reports)

```graphql
query GuildReports($guildName: String!, $serverSlug: String!, $serverRegion: String!, $page: Int) {
  reportData {
    reports(
      guildName: $guildName
      guildServerSlug: $serverSlug
      guildServerRegion: $serverRegion
      page: $page
      limit: 25
    ) {
      last_page
      current_page
      has_more_pages
      data {
        code
        title
        startTime
        endTime
        zone { id name }
      }
    }
  }
}
```

**Server slug format:** lowercase, dashes instead of spaces. E.g. "Burning Legion" -> `burning-legion`
**Region:** lowercase (eu, us, kr, tw)

---

## 5. Report Fights

```graphql
query ReportFights($code: String!) {
  reportData {
    report(code: $code) {
      code
      title
      startTime       # epoch ms, absolute
      endTime
      fights(killType: Encounters) {
        id            # fight id (int, used in other queries)
        encounterID   # encounter id (same across reports)
        name          # boss name
        kill          # boolean
        difficulty    # 3=Normal, 4=Heroic, 5=Mythic, 10=LFR, (Raid Finder)
        startTime     # ms RELATIVE to report start
        endTime       # ms RELATIVE to report start
        fightPercentage    # boss HP % at end (for wipes)
        bossPercentage
        friendlyPlayers    # array of actor IDs
      }
      masterData(translate: true) {
        actors(type: "Player") {
          id        # actor id (int)
          name      # character name
          type      # ALWAYS "Player" for player actors
          subType   # CLASS NAME (e.g. "Monk", "DeathKnight") - this is the class!
          server    # server name
        }
      }
    }
  }
}
```

**Critical:**
- `fights.startTime`/`endTime` are ms relative to report start, NOT epoch.
- `masterData.actors.type` is always "Player" - use `subType` for class name.
- `difficulty: 5` = Mythic, `4` = Heroic, `3` = Normal.

---

## 6. Table Data (aggregated)

For DPS, HPS, Deaths, Interrupts, Dispels, etc.

```graphql
query TableData($code: String!, $dataType: TableDataType!, $fightIDs: [Int],
                $startTime: Float!, $endTime: Float!, $filter: String) {
  reportData {
    report(code: $code) {
      table(
        dataType: $dataType
        fightIDs: $fightIDs
        startTime: $startTime
        endTime: $endTime
        viewBy: Source
        filterExpression: $filter
      )
    }
  }
}
```

**Returns:** JSON scalar (not typed). Parse `data.reportData.report.table` as JSON.
Structure: `{data: {totalTime, entries: [...]}}`

**`dataType` enum values (TableDataType):**
- `DamageDone` - DPS per source
- `Healing` - HPS per source
- `DamageTaken`
- `Casts`
- `Buffs`, `Debuffs`
- `Deaths`
- `Interrupts`
- `Dispels`
- `Summons`
- `Resources`
- `Summary`, `Survivability`, `Threat`

**Important arguments:**
- `startTime`, `endTime` - REQUIRED, must form a non-zero range. Both in ms relative to report start.
- `viewBy`: `Source`, `Target`, `Ability`, `Fight`
- `filterExpression` - WCL filter syntax
- `hostilityType`: `Friendlies` (default) or `Enemies`
- `killType`: `Encounters`, `Trash`, `All`
- `sourceID` - filter by specific player actor ID

### Table entry structures (examples)

**DPS/Healing table entry:**
```json
{
  "name": "PlayerName",
  "id": 5,
  "type": "Mage",         // CLASS name
  "icon": "Mage-Frost",   // class-spec
  "total": 52340000,      // total damage/healing
  "activeTime": 240000,   // ms active
  "abilities": [...],
  "gear": [...],
  "talents": [...]
}
```
- DPS calculation: `entry.total / (totalTime_ms / 1000)`
- Active %: `entry.activeTime / totalTime * 100`

**Deaths table entry:**
```json
{
  "name": "PlayerName",
  "type": "Monk",
  "timestamp": 721880,     // ms RELATIVE TO REPORT START (not fight!)
  "fight": 4,
  "killingBlow": {"name": "Umbral Collapse", "guid": 1249262},
  "damage": {...},
  "events": [...],
  "deathWindow": 5570,
  "overkill": 69871
}
```
- Convert to fight-relative time: `entry.timestamp - fight.startTime`

**Interrupts/Dispels table - NESTED structure:**
```json
{
  "entries": [
    {
      "entries": [      // nested! ability being interrupted/dispelled
        {
          "name": "Black Miasma",       // ability being interrupted
          "spellsBegun": 5,
          "spellsInterrupted": 2,
          "details": [                   // players who performed it
            {"name": "Player1", "type": "DeathKnight", "total": 1, "abilities": [...]},
            {"name": "Player2", "type": "Warrior", "total": 1, "abilities": [...]}
          ]
        }
      ]
    }
  ]
}
```
To aggregate per player, recurse into nested `entries` and extract `details[]`.

---

## 7. Events (raw event stream)

```graphql
query Events($code: String!, $dataType: EventDataType!, $startTime: Float!,
             $endTime: Float!, $fightIDs: [Int], $filter: String,
             $abilityID: Float, $limit: Int) {
  reportData {
    report(code: $code) {
      events(
        dataType: $dataType
        startTime: $startTime
        endTime: $endTime
        fightIDs: $fightIDs
        filterExpression: $filter
        abilityID: $abilityID
        limit: $limit
      ) {
        data               # array of event objects
        nextPageTimestamp  # pagination - if not null, fetch next page
      }
    }
  }
}
```

**EventDataType enum:**
- `Casts` - ability casts
- `Buffs`, `Debuffs` - buff/debuff applications
- `DamageDone`, `DamageTaken`, `HealingDone`
- `Deaths`
- `Dispels`, `Interrupts`
- `Resources`
- `Summons`
- `CombatantInfo`

**Event object structure:**
```json
{
  "timestamp": 721859,       // ms RELATIVE TO REPORT START
  "type": "cast",
  "sourceID": 5,
  "sourceIsFriendly": true,
  "targetID": 2,
  "targetIsFriendly": true,
  "abilityGameID": 6262,
  "ability": {"name": "...", "guid": ..., "abilityIcon": "..."},
  "fight": 4
}
```

**Pagination:** Check `nextPageTimestamp`. If not null, make another request with `startTime` set to that value. Loop until null.

---

## 8. Filter Expressions

WCL filter syntax for `filterExpression`:
- `ability.id = 6262` - single ability
- `ability.id IN (6262, 431416, 431418)` - multiple abilities
- `source.name = "PlayerName"`
- `target.id = 5`
- `type = "cast"`
- Logical: `AND`, `OR`, `NOT`

**Example - filter events to specific consumables:**
```
ability.id IN (1236616, 1236994, 1238443, 1236998)
```

---

## 9. Guild Attendance

```graphql
query GuildAttendance($name: String!, $server: String!, $region: String!,
                      $zoneID: Int, $page: Int) {
  guildData {
    guild(name: $name, serverSlug: $server, serverRegion: $region) {
      id
      name
      attendance(zoneID: $zoneID, page: $page, limit: 25) {
        current_page
        has_more_pages
        data {
          code
          startTime
          zone { id name }
          players {
            name
            type          # class
            presence      # 0-1 or other scale
          }
        }
      }
    }
  }
}
```

---

## 10. Key Data Gotchas

### Timestamps
- **`report.startTime`, `report.endTime`** - absolute epoch milliseconds
- **`fight.startTime`, `fight.endTime`** - ms RELATIVE to report start
- **`table` entries (Deaths etc) `.timestamp`** - ms RELATIVE to REPORT start (not fight!)
- **`events[].timestamp`** - ms RELATIVE to REPORT start
- **`table` arguments `startTime`, `endTime`** - ms RELATIVE to report start
- Convert event to fight-relative: `event.timestamp - fight.startTime`

### Classes
- `masterData.actors.type` is ALWAYS "Player" - useless for class
- Use `masterData.actors.subType` for class ("Mage", "Monk", etc.)
- In DPS/HPS table entries, `type` IS the class (e.g. "Mage")
- `icon` in DPS table entries is `"Class-Spec"` format (e.g. "Mage-Frost")

### Augmented Damage (Aug Evoker)
- Default WCL API `DamageDone` returns **reattributed** damage
- Aug Evoker damage includes bonus given to allies
- Allies have that bonus subtracted from their DPS
- **No API parameter** to toggle this - UI-only feature
- If no Aug Evoker in raid, data matches in-game meters
- Power Infusion, Bloodlust - these are NOT reattributed, buffed player keeps full credit

### Archived Reports
- Reports older than ~6 months may require a WCL subscription for event/table access
- Basic report info (fights, masterData) usually still works

---

## 11. Common Ability IDs (Midnight 12.0 / WoW Retail)

### Combat Potions (buff/effect spell IDs - what's in combat logs)
```
1236616 - Light's Potential
1236994 - Potion of Recklessness
1238443 - Potion of Zealotry
1236998 - Draught of Rampant Abandon
```

### Healing Potions
```
1234768 - Silvermoon Health Potion
1263074 - Amani Extract
1235568 - Light's Preservation
1236590 - Refreshing Serum
6262    - Healthstone (unchanged since Classic)
```

### Mana Potions
```
1236648 - Lightfused Mana Potion
1239479 - Potion of Devoured Dreams
```

### Combat Resurrection
```
20484   - Rebirth (Druid)
20707   - Soulstone (Warlock)
61999   - Raise Ally (Death Knight)
391054  - Intercession (Paladin)
```

### External Defensive Cooldowns (common)
```
33206   - Pain Suppression
47788   - Guardian Spirit
102342  - Ironbark
116849  - Life Cocoon
6940    - Blessing of Sacrifice
204018  - Blessing of Spellwarding
1022    - Blessing of Protection
```

**Note:** In Midnight 12.0, crafted potions have 2 quality tiers (T1/T2) but both share the same spell ID. Recipe spell IDs are different from buff spell IDs - always use buff IDs for combat log filtering.

---

## 12. Python Minimal Client Example

```python
import requests, time

class WCLClient:
    def __init__(self, client_id, client_secret):
        self.cid, self.secret = client_id, client_secret
        self._token, self._exp = None, 0

    def _token(self):
        if self._token and time.time() < self._exp - 60:
            return self._token
        r = requests.post("https://www.warcraftlogs.com/oauth/token",
                          auth=(self.cid, self.secret),
                          data={"grant_type": "client_credentials"})
        r.raise_for_status()
        d = r.json()
        self._token = d["access_token"]
        self._exp = time.time() + d["expires_in"]
        return self._token

    def query(self, q, variables=None):
        r = requests.post("https://www.warcraftlogs.com/api/v2/client",
            headers={"Authorization": f"Bearer {self._token()}",
                     "Content-Type": "application/json"},
            json={"query": q, "variables": variables or {}})
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise Exception(data["errors"])
        return data["data"]
```

---

## 13. Useful Resources

- Official docs: https://www.warcraftlogs.com/api/docs
- GraphQL playground (requires auth): https://www.warcraftlogs.com/v2-api-docs/warcraft/
- Client registration: https://www.warcraftlogs.com/api/clients
- WCL Discord #api-help channel - best for undocumented questions
- Wowhead spell lookup: `https://www.wowhead.com/spell={id}`

---

## 14. Schema Introspection

To discover new fields, run a GraphQL introspection query against the live API:

```graphql
{
  __schema {
    types {
      name
      fields { name type { name kind ofType { name } } }
    }
  }
}
```

Or use tools like Altair GraphQL Client / Insomnia with your Bearer token pointed at `https://www.warcraftlogs.com/api/v2/client`.
