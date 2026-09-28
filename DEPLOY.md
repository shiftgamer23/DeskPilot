# Deploying

Split deploy: **frontend on Vercel** (static Vite build), **backend on Hugging Face Spaces** (a real
persistent FastAPI process in a Docker container - required for the in-memory SSE relay and the local
Chroma/BM25 index; see the architecture note in the project README/plan for why Vercel's serverless
model doesn't fit the backend, and step 4 below for why Render specifically didn't work out).

Two pieces need a one-time manual step I can't do for you (no account access from here): uploading the
prebuilt index as a GitHub Release asset, and creating the Neon/HF Spaces/Vercel accounts.

## 1. Upload the index/data bundle to a GitHub Release

The Chroma index (~97MB) and raw dataset (~30MB) are gitignored and too large to commit. They're
zipped up already at `scratch/index_data_v1.zip` (~59MB).

1. Go to https://github.com/shiftgamer23/Ticket_triage_agent/releases/new
2. Tag: `index-data-v1`, title: anything (e.g. "Retrieval index + raw dataset")
3. Drag `scratch/index_data_v1.zip` into the assets area, publish the release
4. Copy the asset's direct download URL - right-click the uploaded file link, "Copy link address".
   It looks like:
   `https://github.com/shiftgamer23/Ticket_triage_agent/releases/download/index-data-v1/index_data_v1.zip`
5. Keep that URL - it's the `INDEX_DATA_URL` variable the Space needs in step 4.

## 2. Postgres (ticket history) - Neon

Render's own free Postgres expires after 30 days; Neon's free tier doesn't.

1. https://neon.tech -> sign up -> create a project (any region)
2. Copy the connection string it gives you (starts `postgresql://...`) - this is `DATABASE_URL`

## 3. Redis (cache) - Upstash

1. https://upstash.com -> sign up -> create a Redis database (any region, free tier)
2. Copy the "ioredis"/`rediss://` connection string - this is `REDIS_URL`
   (note the double-`s` scheme, `rediss://` - it's TLS; `redis.from_url()` already handles it)

## 4. Backend - Hugging Face Spaces

Originally planned for Render, but Render's free tier is capped at 512MB RAM, and torch +
sentence-transformers + chromadb all loaded in one process blow well past that at startup (confirmed -
it OOM'd before ever opening a port). HF Spaces' free CPU tier gives 16GB RAM instead - built for
exactly this kind of ML workload - so we moved the backend there. `render.yaml` is left in the repo but
unused; Neon/Upstash/GitHub-Release steps above are unaffected, this only changes where the FastAPI
process itself runs.

1. https://huggingface.co/new-space -> pick a name, SDK = **Docker**, visibility = public (simplest,
   no paid tier needed), hardware = **CPU basic** (free)
2. In the new Space's **Settings** tab:
   - Under **Variables** (not Secrets - it's a public URL, not sensitive): add `INDEX_DATA_URL` =
     the release asset URL from step 1 above. This one needs to be a Variable specifically, since the
     Dockerfile consumes it as a build-arg (see `ARG INDEX_DATA_URL` in the `Dockerfile`).
   - Under **Repository secrets**: add `GROQ_API_KEY`, `GEMINI_API_KEY`, `DATABASE_URL` (from Neon),
     and `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_BASE_URL` - same values as your
     local `.env`. These are only needed at runtime, so no Dockerfile changes needed for them.
   - `REDIS_URL` - skip it, same as the Render plan; caching just stays disabled.
3. Generate a Hugging Face access token (with write access) at
   https://huggingface.co/settings/tokens - you'll need it as the password for the next step.
4. Locally, add the Space as a second git remote and push:
   ```
   git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
   git push space main:main
   ```
   When git prompts for a password, paste the access token from step 3 (not your HF account password).
5. HF builds the image (installs deps, then runs `scripts/fetch_index_data.py` as a build step -
   downloads+extracts the release asset instead of rebuilding the index from scratch). Watch progress
   in the Space's **Logs** tab.
6. Once it's live, the Space's URL is `https://<your-username>-<space-name>.hf.space` - that's what
   the frontend needs next (in place of the Render URL below).

**Cold starts:** free Spaces also sleep after a period of inactivity and take a bit to wake on the next
request, same tradeoff as Render's free tier - just without the 512MB ceiling.

## 5. Frontend - Vercel

1. https://vercel.com -> sign up -> New Project -> import the same GitHub repo
2. **Root Directory**: set to `frontend` (the repo root isn't the Vite project)
3. Framework preset should auto-detect as Vite (build `npm run build`, output `dist`)
4. Add env var `VITE_API_BASE_URL` = the Space URL from step 4.6, **no trailing slash**
   (e.g. `https://your-username-space-name.hf.space`)
5. Deploy.

## 6. Verify

- Open the Vercel URL, submit a ticket, confirm it streams through Processing -> a queue column.
- If it hangs on "Reasoning" forever: check the Space's Logs tab (cold start can take a bit - give
  it a minute before assuming it's broken).
- If tickets never persist across a Space restart: check the Space's secrets actually have
  `DATABASE_URL` set and check the Space logs for a `Postgres unavailable` warning from
  `app/infra/db.py`.

## What's NOT handled here

- CORS is wide open (`allow_origins=["*"]` in `app/main.py`) - fine for a demo, tighten to the exact
  Vercel domain later if this ever needs to be more locked down.
- No auth on the API - anyone with the Space URL can submit tickets. Acceptable for a portfolio demo,
  not for anything real.
- `render.yaml` is left in the repo from the original plan but is no longer used.
