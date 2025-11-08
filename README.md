# MacroTracker (Lite)

A minimal, ready-to-run Flask app to track daily calories/macros with multi-user accounts, **admin approval**, products, meals, and consumptions.

## Features
- User signup/login, **admin approval** for new accounts
- Per-user data isolation
- Products (per-100g macros), Meals, Consumptions (grams)
- Dashboard (today's totals) + History (last 14 days)

## Quick start

```bash
# 1) Create & activate a virtual env
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) (optional) Set secrets/admin via env
# export FLASK_SECRET_KEY="change-me"
# export ADMIN_EMAIL="admin@example.com"
# export ADMIN_USERNAME="admin"
# export ADMIN_PASSWORD="strong-password"

# 4) Run
python app.py
```

On first run, the database is created and a default admin is ensured (from env vars, or `admin@example.com / admin123`).  
Open http://127.0.0.1:5000/

## Basic flow
1. Visit **/signup** to create a user.  
2. Log in as admin → **Admin Pending** → approve the user.  
3. Log in as the approved user:
   - Create **Products** (kcal/protein/carbs/fat per 100g).
   - Create **Meals** (date + name).
   - **Add Consumption** (meal + product + quantity in grams).
4. See **Dashboard** for today's totals; **History** for recent days.

## Notes
- SQLite DB file: `macrotracker.db` in project root.
- Change the default admin credentials ASAP for any real usage.
- This is an educational, minimal baseline you can extend with editing, charts, goals, etc.
