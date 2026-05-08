"""Google Sheets client using OAuth2 user credentials."""

import os
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import CREDENTIALS_FILE, TOKEN_FILE, GOOGLE_SCOPES, GOOGLE_SHEETS_ID


def get_google_creds():
    """Authenticate with Google using OAuth2 (browser flow on first run)."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


class SheetsClient:
    def __init__(self, spreadsheet_id=None):
        creds = get_google_creds()
        self.gc = gspread.authorize(creds)
        self.spreadsheet_id = spreadsheet_id or GOOGLE_SHEETS_ID
        self._spreadsheet = None

    @property
    def spreadsheet(self):
        if self._spreadsheet is None:
            self._spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def get_or_create_worksheet(self, title, rows=1000, cols=30):
        """Get existing worksheet or create a new one."""
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def clear_and_write(self, worksheet_title, headers, rows):
        """Clear a worksheet and write headers + data rows."""
        ws = self.get_or_create_worksheet(worksheet_title)
        ws.clear()
        if not rows:
            ws.update("A1", [headers])
            return ws

        all_data = [headers] + rows
        ws.update(f"A1:{_col_letter(len(headers))}{len(all_data)}", all_data)
        return ws

    def get_existing_report_codes(self, worksheet_title):
        """Get set of report codes already in a worksheet (column A, skipping header)."""
        try:
            ws = self.spreadsheet.worksheet(worksheet_title)
            col_a = ws.col_values(1)
            return set(col_a[1:])  # skip header
        except gspread.exceptions.WorksheetNotFound:
            return set()

    def append_rows(self, worksheet_title, headers, rows):
        """Append rows to an existing worksheet, adding headers if sheet is new."""
        ws = self.get_or_create_worksheet(worksheet_title)
        existing = ws.get_all_values()
        if not existing or not existing[0]:
            # Sheet is empty - write headers first
            ws.update(f"A1:{_col_letter(len(headers))}1", [headers])
        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")
        return ws


    def read_config_sheet(self, title):
        """Read a config sheet and return all rows (excluding header) as list of dicts.

        Expected columns: Spell ID | Name | Category
        Returns list of dicts: [{"spell_id": int, "name": str, "category": str}, ...]
        """
        try:
            ws = self.spreadsheet.worksheet(title)
            records = ws.get_all_records()
            return records
        except gspread.exceptions.WorksheetNotFound:
            return []

    def init_config_sheet(self, title, headers, rows):
        """Create a config sheet with initial data if it doesn't exist.

        Returns True if sheet was created, False if it already existed.
        """
        try:
            self.spreadsheet.worksheet(title)
            return False  # already exists
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=title, rows=500, cols=len(headers))
            all_data = [headers] + rows
            ws.update(f"A1:{_col_letter(len(headers))}{len(all_data)}", all_data)
            return True


def _col_letter(n):
    """Convert column number (1-based) to letter(s): 1->A, 26->Z, 27->AA."""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result
