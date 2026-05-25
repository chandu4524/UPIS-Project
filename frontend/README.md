# Government Person Intelligence Platform — Frontend

React + Vite + React Router + Axios + plain CSS.

## Run

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/login (dev) or http://127.0.0.1:8000/login (combined)

Axios uses `/api` — proxied to the backend in dev via `vite.config.js`.

## Pages

- `/login` — authentication
- `/dashboard` — welcome & officer info
- `/upload` — CSV upload & JSON preview
- `/citizens` — searchable citizen table
