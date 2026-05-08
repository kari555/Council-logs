# Streamlit Community Cloud deploy

## 1. Prepare GitHub

```bash
cd /Users/karolkaminski/Claude/przemielimy-logs
git init
git add .
git status
git commit -m "Prepare Council raid dashboard for Streamlit Cloud"
```

Create an empty repository on GitHub, then follow GitHub's commands for adding
the remote and pushing `main`.

## 2. Add Streamlit secrets

In Streamlit Community Cloud, open the app settings and paste:

```toml
WCL_CLIENT_ID = "..."
WCL_CLIENT_SECRET = "..."

GUILD_NAME = "Council"
GUILD_SERVER = "burning-legion"
GUILD_REGION = "EU"

GOOGLE_SHEETS_ID = ""
```

Do not commit `.env` or `.streamlit/secrets.toml`.

## 3. Deploy

Use:

- Repository: your GitHub repo
- Branch: `main`
- Main file path: `app.py`

The committed `cache/*.json` files are used as the initial data snapshot.

## 4. Refreshing data

For now, refresh data locally and commit the updated cache:

```bash
cd /Users/karolkaminski/Claude/przemielimy-logs
venv/bin/python fetch.py --reports 20
git add cache app.py fetch.py config.py
git commit -m "Refresh raid cache"
git push
```

Later we can add an admin-only refresh button or a GitHub Actions scheduled job.
