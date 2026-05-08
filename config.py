import os
from dotenv import load_dotenv

load_dotenv()


def _secret(name, default=None):
    """Read config from Streamlit secrets when available, otherwise env."""
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


# Warcraft Logs API
WCL_CLIENT_ID = _secret("WCL_CLIENT_ID")
WCL_CLIENT_SECRET = _secret("WCL_CLIENT_SECRET")
WCL_TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
WCL_API_URL = "https://www.warcraftlogs.com/api/v2/client"

# Guild
GUILD_NAME = _secret("GUILD_NAME", "Council")
GUILD_SERVER = _secret("GUILD_SERVER", "burning-legion")
GUILD_REGION = _secret("GUILD_REGION", "EU")

# Google Sheets
GOOGLE_SHEETS_ID = _secret("GOOGLE_SHEETS_ID")
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")

# Scopes for Google Sheets
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Config sheet names
CONSUMABLES_CONFIG_SHEET = "Config: Consumables"
DEFENSIVES_CONFIG_SHEET = "Config: Defensives"

CONFIG_HEADERS = ["Spell ID", "Name", "Category"]

# Default consumable data (Midnight 12.0) - used to populate config sheet on first run
# Buff/effect spell IDs (what appears in Warcraft Logs combat logs)
DEFAULT_CONSUMABLES = [
    [6262, "Healthstone", "Healthstone"],
    [1236616, "Light's Potential", "Combat Pot"],
    [1236994, "Potion of Recklessness", "Combat Pot"],
    [1238443, "Potion of Zealotry", "Combat Pot"],
    [1236998, "Draught of Rampant Abandon", "Combat Pot"],
    [1234768, "Silvermoon Health Potion", "Health Pot"],
    [1263074, "Amani Extract", "Health Pot"],
    [1235568, "Light's Preservation", "Health Pot"],
    [1236590, "Refreshing Serum", "Health Pot"],
    [1236648, "Lightfused Mana Potion", "Mana Pot"],
    [1239479, "Potion of Devoured Dreams", "Mana Pot"],
]

# Default defensive cooldowns - used to populate config sheet on first run
DEFAULT_DEFENSIVES = [
    # External defensives
    [33206, "Pain Suppression", "External"],
    [47788, "Guardian Spirit", "External"],
    [102342, "Ironbark", "External"],
    [116849, "Life Cocoon", "External"],
    [6940, "Blessing of Sacrifice", "External"],
    [204018, "Blessing of Spellwarding", "External"],
    [1022, "Blessing of Protection", "External"],
    # Personal defensives
    [48792, "Icebound Fortitude", "Personal"],
    [48707, "Anti-Magic Shell", "Personal"],
    [97462, "Rallying Cry", "Personal"],
    [118038, "Die by the Sword", "Personal"],
    [198589, "Blur", "Personal"],
    [196555, "Netherwalk", "Personal"],
    [22812, "Barkskin", "Personal"],
    [61336, "Survival Instincts", "Personal"],
    [186265, "Aspect of the Turtle", "Personal"],
    [109304, "Exhilaration", "Personal"],
    [45438, "Ice Block", "Personal"],
    [55342, "Mirror Image", "Personal"],
    [115203, "Fortifying Brew", "Personal"],
    [122783, "Diffuse Magic", "Personal"],
    [642, "Divine Shield", "Personal"],
    [31850, "Ardent Defender", "Personal"],
    [19236, "Desperate Prayer", "Personal"],
    [47585, "Dispersion", "Personal"],
    [31224, "Cloak of Shadows", "Personal"],
    [5277, "Evasion", "Personal"],
    [108271, "Astral Shift", "Personal"],
    [104773, "Unending Resolve", "Personal"],
    [363916, "Obsidian Scales", "Personal"],
    [374348, "Renewing Blaze", "Personal"],
]

# Combat Resurrection spell IDs
COMBAT_RES_IDS = [
    20484,   # Rebirth (Druid)
    20707,   # Soulstone (Warlock)
    61999,   # Raise Ally (Death Knight)
    391054,  # Intercession (Paladin)
    265116,  # Unstable Temporal Time Shifter (Engineering)
]
