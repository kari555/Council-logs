"""Warcraft Logs API v2 client using OAuth2 client credentials + GraphQL."""

import time
import requests
from config import WCL_CLIENT_ID, WCL_CLIENT_SECRET, WCL_TOKEN_URL, WCL_API_URL


class WCLClient:
    def __init__(self):
        self._token = None
        self._token_expires_at = 0

    def _get_token(self):
        """Obtain or refresh OAuth2 token via client credentials flow."""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        resp = requests.post(
            WCL_TOKEN_URL,
            auth=(WCL_CLIENT_ID, WCL_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"]
        return self._token

    def query(self, graphql_query, variables=None):
        """Execute a GraphQL query against the WCL API v2."""
        token = self._get_token()
        resp = requests.post(
            WCL_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"query": graphql_query, "variables": variables or {}},
        )
        resp.raise_for_status()
        result = resp.json()
        if "errors" in result:
            raise Exception(f"WCL GraphQL errors: {result['errors']}")
        return result["data"]

    def get_guild_reports(self, guild_name, server_slug, region, page=1, limit=25):
        """Fetch recent reports for a guild."""
        q = """
        query GuildReports($name: String!, $server: String!, $region: String!, $page: Int, $limit: Int) {
            reportData {
                reports(
                    guildName: $name
                    guildServerSlug: $server
                    guildServerRegion: $region
                    page: $page
                    limit: $limit
                ) {
                    current_page
                    last_page
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
        """
        data = self.query(q, {
            "name": guild_name,
            "server": server_slug,
            "region": region,
            "page": page,
            "limit": limit,
        })
        return data["reportData"]["reports"]

    def get_report_fights(self, report_code):
        """Fetch fights and player roster for a report."""
        q = """
        query ReportFights($code: String!) {
            reportData {
                report(code: $code) {
                    code
                    title
                    startTime
                    endTime
                    fights(killType: Encounters) {
                        id
                        encounterID
                        name
                        kill
                        difficulty
                        startTime
                        endTime
                        fightPercentage
                        bossPercentage
                        friendlyPlayers
                    }
                    masterData(translate: true) {
                        actors(type: "Player") {
                            id
                            name
                            type
                            subType
                            server
                        }
                        abilities {
                            gameID
                            name
                            type
                        }
                    }
                }
            }
        }
        """
        data = self.query(q, {"code": report_code})
        return data["reportData"]["report"]

    def get_table(self, report_code, data_type, fight_ids, start_time=0,
                  end_time=999999999, filter_expression=None):
        """Fetch aggregated table data (DPS, HPS, Interrupts, etc.)."""
        q = """
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
        """
        variables = {
            "code": report_code,
            "dataType": data_type,
            "fightIDs": fight_ids,
            "startTime": start_time,
            "endTime": end_time,
        }
        if filter_expression:
            variables["filter"] = filter_expression
        data = self.query(q, variables)
        return data["reportData"]["report"]["table"]["data"]

    def get_events(self, report_code, data_type, start_time, end_time,
                   fight_ids=None, filter_expression=None, ability_id=None):
        """Fetch raw events with pagination support."""
        q = """
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
                        data
                        nextPageTimestamp
                    }
                }
            }
        }
        """
        all_events = []
        current_start = start_time

        while True:
            variables = {
                "code": report_code,
                "dataType": data_type,
                "startTime": current_start,
                "endTime": end_time,
                "limit": 10000,
            }
            if fight_ids:
                variables["fightIDs"] = fight_ids
            if filter_expression:
                variables["filter"] = filter_expression
            if ability_id:
                variables["abilityID"] = ability_id

            data = self.query(q, variables)
            events = data["reportData"]["report"]["events"]
            all_events.extend(events["data"])

            if events["nextPageTimestamp"] is None:
                break
            current_start = events["nextPageTimestamp"]

        return all_events

    def get_report_rankings(self, report_code, fight_ids=None):
        """Fetch per-player parse percentile and item level for given fights."""
        q = """
        query ReportRankings($code: String!, $fightIDs: [Int]) {
            reportData {
                report(code: $code) {
                    rankings(fightIDs: $fightIDs)
                }
            }
        }
        """
        data = self.query(q, {"code": report_code, "fightIDs": fight_ids or []})
        return data["reportData"]["report"]["rankings"]

    def get_guild_members(self, guild_name, server_slug, region):
        """Fetch guild member roster."""
        q = """
        query GuildMembers($name: String!, $server: String!, $region: String!,
                           $page: Int, $limit: Int) {
            guildData {
                guild(name: $name, serverSlug: $server, serverRegion: $region) {
                    members(page: $page, limit: $limit) {
                        current_page
                        has_more_pages
                        data {
                            name
                        }
                    }
                }
            }
        }
        """
        all_members = []
        page = 1
        while True:
            data = self.query(q, {
                "name": guild_name,
                "server": server_slug,
                "region": region,
                "page": page,
                "limit": 100,
            })
            members = data["guildData"]["guild"]["members"]
            all_members.extend(members["data"])
            if not members.get("has_more_pages"):
                break
            page += 1
        return all_members

    def get_guild_attendance(self, guild_name, server_slug, region, zone_id=None, page=1):
        """Fetch guild attendance data."""
        q = """
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
                                type
                                presence
                            }
                        }
                    }
                }
            }
        }
        """
        variables = {
            "name": guild_name,
            "server": server_slug,
            "region": region,
            "page": page,
        }
        if zone_id:
            variables["zoneID"] = zone_id
        data = self.query(q, variables)
        return data["guildData"]["guild"]["attendance"]
