# SkyGuard AI — Frontend

Next.js 16 dashboard for the SkyGuard AI anomaly detection system.

## Quick Start

```bash
npm install
npm run dev
Open http://localhost:3000.

Requires the backend API to be running:

bash
# From project root
python api.py
Or use the deployed backend at https://skyguardai-production.up.railway.app.

Pages
/ — Dashboard (metrics, alerts, charts, map)

/network — Station network topology + insights

/parameters — Live T/P/H charts with station filter

/reality-check — Sensor fault vs genuine weather comparison

/test — Fault Injection Lab

/maintenance — Prioritized work queue

/stations — AWS station table with filters

Tech Stack
Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui · Recharts · lucide-react

Full Documentation
See ../docs/README.md for the complete project documentation.

text

**That's it. Nothing else goes in this file.**

---
