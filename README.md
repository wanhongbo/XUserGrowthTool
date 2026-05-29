# X Circle Operator

Compliance-first Web App for discovering active users in Privacy, Signal, Proton, and Cybersecurity circles on X. The system automates discovery, scoring, prioritization, suggestions, and drafting, while every public interaction and DM remains human-reviewed and manually sent.

## What It Does

- Pulls recent public posts through the official X API.
- Scores users by relevance, activity, influence, intent, and risk.
- Generates public interaction tasks and DM drafts.
- Enforces strict DM eligibility before any DM draft can enter the queue.
- Records human review actions in an audit trail.

## What It Does Not Do

- No browser scraping.
- No cookie automation.
- No automated likes, follows, replies, or DMs.
- No bulk unsolicited DM workflow.

## Quick Start

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Configuration

The backend defaults to SQLite at `backend/usergrowth.db`.

For live X API discovery, set:

```bash
X_BEARER_TOKEN=...
DISCOVERY_MODE=x_api
```

Without an X token, the app uses seeded sample data so the workflow can be tested locally.

