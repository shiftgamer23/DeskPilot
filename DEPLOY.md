# Deploying

Split deploy: **frontend on Vercel** (static Vite build), **backend on Render** (a real persistent
FastAPI process - required for the in-memory SSE relay and the local Chroma/BM25 index; see the
architecture note in the project README/plan for why Vercel's serverless model doesn't fit the backend).

Two pieces need a one-time manual step I can't do for you (no account access from here): uploading the
prebuilt index as a GitHub Release asset, and creating the Neon/Upstash/Render/Vercel accounts.

## 1. Upload the index/data bundle to a GitHub Release

The Chroma index (~97MB) and raw dataset (~30MB) are gitignored and too large to commit. They're
zipped up already at `scratch/index_data_v1.zip` (~59MB).

1. Go to https://github.com/shiftgamer23/Ticket_triage_agent/releases/new
2. Tag: `index-data-v1`, title: anything (e.g. "Retrieval index + raw dataset")
3. Drag `scratch/index_data_v1.zip` into the assets area, publish the release
4. Copy the asset's direct download URL - right-click the uploaded file link, "Copy link address".
   It looks like:
   `https://github.com/shiftgamer23/Ticket_triage_agent/releases/download/index-data-v1/index_data_v1.zip`
5. Keep that URL - it's the `INDEX_DATA_URL` env var Render needs in step 4.

## 2. Postgres (ticket history) - Neon

Render's own free Postgres expires after 30 days; Neon's free tier doesn't.

1. https://neon.tech -> sign up -> create a project (any region)
2. Copy the connection string it gives you (starts `postgresql://...`) - this is `DATABASE_URL`

## 3. Redis (cache) - Upstash

1. https://upstash.com -> sign up -> create a Redis database (any region, free tier)
2. Copy the "ioredis"/`rediss://` connection string - this is `REDIS_URL`
   (note the double-`s` scheme, `rediss://` - it's TLS; `redis.from_url()` already handles it)

## 4. Backend - Render

1. https://dashboard.render.com -> New -> Blueprint -> connect the `Ticket_triage_agent` repo
   Render will read `render.yaml` at the repo root and propose one web service.
2. On the env var prompts, fill in:
   - `GROQ_API_KEY`, `GEMINI_API_KEY` - same values as your local `.env`
   - `INDEX_DATA_URL` - the release asset URL from step 1
   - `DATABASE_URL` - from step 2 (Neon)
   - `REDIS_URL` - from step 3 (Upstash)
   - `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL` - same as local `.env`
3. Deploy. First build downloads+extracts the index bundle (step 1) instead of rebuilding it, so it
   should finish in a few minutes, not the 20-60+ minutes a from-scratch re-embed of ~28K tickets
   would risk on free-tier resources.
4. Once live, note the service URL, e.g. `https://ticket-triage-agent.onrender.com` - that's what
   the frontend needs next.

**If the free instance runs out of memory at startup** (chromadb + sentence-transformers + torch all
loaded in one process is genuinely heavy, and Render doesn't publish exact free-tier RAM) - upgrade
that one service to the Starter plan (~$7/mo) in Render's dashboard. Nothing else about this guide
changes.

**Cold starts:** the free plan spins the service down after 15 minutes with no traffic, and the next
request pays a ~1 minute cold start on top of the model/index load. Fine for a portfolio demo people
click into occasionally; if you want it always warm, that also needs the paid plan.

## 5. Frontend - Vercel

1. https://vercel.com -> sign up -> New Project -> import the same GitHub repo
2. **Root Directory**: set to `frontend` (the repo root isn't the Vite project)
3. Framework preset should auto-detect as Vite (build `npm run build`, output `dist`)
4. Add env var `VITE_API_BASE_URL` = the Render URL from step 4.4, **no trailing slash**
   (e.g. `https://ticket-triage-agent.onrender.com`)
5. Deploy.

## 6. Verify

- Open the Vercel URL, submit a ticket, confirm it streams through Processing -> a queue column.
- If it hangs on "Reasoning" forever: check the Render service logs (cold start can take ~1 min - give
  it a minute before assuming it's broken).
- If tickets never persist across a Render restart: check Render's env vars actually have
  `DATABASE_URL` set and check the Render logs for a `Postgres unavailable` warning from
  `app/infra/db.py`.

## What's NOT handled here

- CORS is wide open (`allow_origins=["*"]` in `app/main.py`) - fine for a demo, tighten to the exact
  Vercel domain later if this ever needs to be more locked down.
- No auth on the API - anyone with the Render URL can submit tickets. Acceptable for a portfolio demo,
  not for anything real.
