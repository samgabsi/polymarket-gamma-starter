# Polymarket Gamma Starter

> Local-first, human-in-the-loop Polymarket research, paper trading, risk review, execution-readiness, and audit platform.

## Overview

Polymarket Gamma Starter is a local-first operator console designed to help traders, researchers, developers, and system architects build disciplined prediction-market workflows before risking real capital.

The platform emphasizes:

- Research-first decision making
- Evidence collection and scoring
- Paper trading and simulation
- Risk management and preflight validation
- Auditability and operational accountability
- Human approval workflows
- Staged live-readiness evaluation
- Fail-closed execution controls

This project intentionally prioritizes operator visibility, process discipline, and safety over automation.

Version 1.0.1-real ships with extensive safeguards that keep live execution disabled by default and require deliberate operator action before any live trading workflow can occur.

---

# Philosophy

Most trading systems focus on execution.

Polymarket Gamma Starter focuses on decision quality.

The goal is not to automate trading.

The goal is to create a structured environment where operators can:

1. Research markets
2. Gather evidence
3. Evaluate risk
4. Simulate outcomes
5. Review approvals
6. Audit decisions
7. Progress through controlled execution stages

Every stage is visible.

Every stage is reviewable.

Every stage can be audited.

---

# Key Features

## Research Workflow

- Market discovery
- Opportunity scanning
- Watchlists
- Evidence collection
- Evidence scoring
- Market notes
- Research source management
- Thesis and counter-thesis tracking

## Paper Trading

- Paper buy/sell workflows
- Position management
- Settlement tracking
- Portfolio analytics
- Trade ticket management
- Exit planning
- Risk budgeting

## Risk Controls

- Exposure limits
- Position limits
- Liquidity requirements
- Volume requirements
- Price-bound protections
- Preflight validation
- Approval workflows

## Market Data Intelligence

- Market snapshots
- Order book analysis
- Liquidity visibility
- Spread analysis
- Execution quality simulation

## Audit & Compliance

- Trade history
- Review reports
- Audit logs
- CSV exports
- Decision tracking
- Reconciliation workflows

## Live Readiness Framework

The platform includes a staged live-readiness architecture that allows operators to evaluate execution pathways without immediately enabling live trading.

Stages include:

- Configuration readiness
- Order intent creation
- Preflight validation
- Authorization review
- Execution packet generation
- Dry-run validation
- Adapter request review
- Manual execution review

Live execution remains disabled by default.

---

# Safety Model

This project follows a fail-closed design philosophy.

Default behavior includes:

- Live trading disabled
- Real network access disabled
- Submit disabled
- Cancel disabled
- Autonomous live trading disabled
- Scheduler disabled
- Kill switch enabled

The safest state is the default state.

The software is intentionally designed to block unsafe actions until operators deliberately enable and validate every required gate.

---

# System Architecture

```text
Research
    ↓
Evidence Collection
    ↓
Trade Ticket
    ↓
Preflight Validation
    ↓
Risk Review
    ↓
Approval Workflow
    ↓
Paper Execution
    ↓
Position Management
    ↓
Audit & Review
    ↓
Live Readiness (Optional)
```

The architecture is designed to maintain clear separation between:

- Research
- Paper operations
- Simulation
- Readiness review
- Manual execution workflows

---

# Installation

## Clone

```bash
git clone https://github.com/samgabsi/polymarket-gamma-starter.git

cd polymarket-gamma-starter
```

## Create Virtual Environment

```bash
python -m venv .venv
```

Activate:

### Linux/macOS

```bash
source .venv/bin/activate
```

### Windows

```powershell
.venv\Scripts\activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

Optional:

```bash
pip install -r requirements-live-optional.txt
```

## Configure Environment

```bash
cp .env.example .env
```

Edit locally.

Never commit credentials, wallet keys, API keys, passphrases, or generated state.

## Run

```bash
python run.py
```

or

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

# First Run

1. Open the application.
2. Visit `/setup`.
3. Create an administrator account.
4. Log in.
5. Review runtime configuration.
6. Verify health status.
7. Confirm:

```text
LIVE DISABLED
REAL NETWORK DISABLED
SUBMIT DISABLED
CANCEL DISABLED
KILL SWITCH ACTIVE
```

These are expected defaults.

---

# Operational Workflow

A typical workflow:

```text
Research Market
      ↓
Collect Evidence
      ↓
Create Ticket
      ↓
Run Preflight
      ↓
Risk Review
      ↓
Approval
      ↓
Paper Trade
      ↓
Manage Position
      ↓
Settlement
      ↓
Audit
```

---

# Autonomous Trading

Autonomous live trading is NOT enabled in Version 1.0.1-real.

The platform supports:

- Signal recording
- Strategy evaluation
- Dry-run workflows
- Fake adapter workflows

It does not enable unrestricted autonomous live execution.

---

# Security

Never commit:

```text
.env
data/users.json
data/session_secret.txt
data/live/*
data/paper/*
.venv/
__pycache__/
```

Always:

- Use strong passwords
- Restrict network access
- Back up encrypted data
- Keep credentials local
- Review logs before sharing

---

# Disclaimer

This software is provided for educational, research, operational, and experimental purposes.

This project is NOT financial advice.

This project does NOT guarantee profitability, market accuracy, or trading success.

Prediction markets involve substantial risk.

The author(s), contributors, and distributors of this software are not responsible for:

- Trading losses
- Financial losses
- Regulatory consequences
- Account restrictions
- Data loss
- Infrastructure failures
- User mistakes
- Misconfiguration
- Third-party service failures

Users assume all responsibility for use of this software.

Always verify information independently and comply with all applicable laws, regulations, exchange rules, and platform terms of service.

---

# License

Released under the MIT License.

See [LICENSE](LICENSE) for details.

---

# Author

Created and maintained by Sam Gabsi.

Community contributions, improvements, audits, testing, and feedback are welcome.
