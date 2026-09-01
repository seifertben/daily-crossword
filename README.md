# Daily Crossword

A new daily 10×10 crossword, filled purely from a scored word bank and clued
by Google Gemini, served as a single-page NYT-style interactive grid. Every
puzzle is identical for all visitors on a given day, and **every clue is
freshly authored each run** (no clue cache) so puzzles are unique daily. At
10×10 with short words and Standard-difficulty clues, each puzzle is
calibrated to solve in about 10 minutes.

## Architecture

Two runtimes, one immutable puzzle per day:

```
Cloud Scheduler (cron 02:00 UTC)
        │  POST  jobs:run
        ▼
┌─────────────────────┐   Gemini API (theme + all clues, fresh daily)
│  Cloud Run JOB      │   Peter Broda wordlist (vendored, fill answers)
│  daily-crossword-   │   Secret Manager (GEMINI_API_KEY)
│  gen                │
└──────────┬──────────┘
           │  writes puzzles/YYYY-MM-DD.json  (immutable)
           ▼
┌─────────────────────┐   Cloud Storage (public/SA read)
│  Cloud Run SERVICE  │   serves SPA + /api/puzzle/:date
│  daily-crossword-   │   no API key, scales to zero, CDN-cacheable
│  web                │
└─────────────────────┘
```

- **Generation job** (off the request path): builds a 180°-symmetric 10×10
  skeleton (no theme), fills the grid with a backtracking CSP over the Broda
  wordlist (words ≤ 9 letters), then batches **all** clues to Gemini at
  Standard difficulty (target ~10-minute solve). Unclueable words are
  blacklisted for the run and the grid is
  re-filled. Result JSON is written to storage.
- **Web service** (always-on, cheap): reads the stored JSON and serves it plus
  the SPA. Never calls Gemini. The solution ships in the payload so
  Check/Reveal run client-side.

## Local development

Prereqs: [uv](https://docs.astral.sh/uv/) (provisions Python 3.12) and Node 20+.

```bash
make install          # uv sync (Python deps)
cd web && npm install && cd ..   # frontend deps (first time only)

# 1) generate a puzzle to disk (no API key needed — stub mode)
make gen-stub                     # today
make gen-stub DATE=2026-08-28     # a specific date

# 2) run the API + the Vite dev server (two terminals)
make dev        # terminal 1: FastAPI on :8000
make web-dev    # terminal 2: Vite on :5173 (HMR, proxies /api -> :8000)
# open http://localhost:5173
```

To serve the built SPA from FastAPI instead (production-like, single port):
```bash
make build-web      # vite build -> web/dist
make dev            # http://localhost:8000 serves the app + API
```

The dev-only `POST /api/dev/generate` endpoint (enabled when `APP_ENV=dev`)
regenerates a puzzle from the browser's dev panel without restarting the job.

### Using a real Gemini key
```bash
cp .env.example .env
# set GEMINI_API_KEY=... and GEMINI_MODE=live
make gen DATE=2026-08-28
```

## Configuration

| Env var            | Required | Default             | Notes                                  |
| ------------------ | -------- | ------------------- | -------------------------------------- |
| `GEMINI_API_KEY`   | live only| —                   | Google Gemini key; omit for stub mode  |
| `GEMINI_MODEL`     | no       | `gemini-3.7-flash`  | Any Gemini model id                    |
| `GEMINI_MODE`      | no       | stub (no key)       | `live` \| `stub` \| `replay`           |
| `GEMINI_MIN_SCORE` | no       | `75`                | Word-bank quality floor; junk fill below this score is dropped before it reaches the clue provider |
| `GEMINI_MIN_ZIPF`  | no       | `1.1`               | Frequency floor for genuine dictionary words: those this rare in ordinary-text corpora (Zipf `data/word_frequency.txt`, e.g. AOUDAD ≈ 0, ADYTUM ≈ 1.01) are deprioritized and used only when no commoner word fits. Phrases ("cuff 'em"), names, and words at or above the floor are exempt |
| `GEMINI_NAME_CAP`  | no       | `5`                 | Preferred max proper names per puzzle; the fill stays under it, exceeding only as a last resort |
| `PUZZLE_STORE`     | no       | `local`             | `local` (scratch disk) \| `static` (Vite public dir) \| `gcs` |
| `STATIC_PUZZLE_DIR`| static only | `./web/public`   | Root dir for the static store; puzzles land in its `puzzles/` subdir |
| `PUZZLE_BUCKET`    | gcs only | —                   | Cloud Storage bucket name              |
| `LOCAL_DATA_DIR`   | no       | `./local-data`      | On-disk puzzle root (local store)      |
| `APP_ENV`          | no       | `dev`               | `dev` enables `/api/dev/generate`      |

## Testing

```bash
make test        # Python unit + integration tests (offline, no key/cloud)
make web-test    # frontend logic (vitest)
make lint        # ruff
make typecheck   # mypy
cd web && npm run build   # type-check + build the SPA
```

## Project layout

```
daily-crossword/
├── generator/      # skeleton, CSP filler, wordbank, gemini, pipeline, store, serialize
├── api/            # FastAPI serving app
├── web/            # React + Vite + TypeScript SPA
├── data/           # vendored Peter Broda scored wordlist (~527k words) + Zipf frequency map
├── infra/          # deploy.sh (GCP)
├── Dockerfile.web  # SPA + API image
├── Dockerfile.gen  # generation job image
└── Makefile
```

## Deploy to GCP

Prereqs: `gcloud` authed with a project, Docker, and a Gemini API key.

```bash
# one-time setup
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com \
  storage.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create daily-crossword --repository-format=docker --region=us-central1
gsutil mb -l us-central1 gs://YOUR_BUCKET
gsutil defacl set public-read gs://YOUR_BUCKET          # puzzles become publicly readable
echo -n "YOUR_GEMINI_KEY" | gcloud secrets create gemini-api-key --data-file=-
gcloud iam service-accounts create daily-crossword-gen
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member serviceAccount:daily-crossword-gen@PROJECT_ID.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member serviceAccount:daily-crossword-gen@PROJECT_ID.iam.gserviceaccount.com \
  --role roles/run.invoker
gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET \
  --member serviceAccount:daily-crossword-gen@PROJECT_ID.iam.gserviceaccount.com \
  --role roles/storage.objectAdmin

# build, push, deploy service + job, schedule daily 02:00 UTC
PROJECT_ID=YOUR_PROJECT BUCKET=YOUR_BUCKET ./infra/deploy.sh

# generate tomorrow's puzzle immediately
gcloud run jobs execute daily-crossword-gen --region us-central1
```

The web service can be made public with `gcloud run services add-iam-policy-binding
daily-crossword-web --member allUsers --role roles/run.invoker` (or front it with
Cloud CDN / a load balancer).

## Static hosting (free, no server)

The web app only *reads* pre-generated puzzle blobs, so the same SPA can be
built as a fully static site — no FastAPI, no store, no cold starts. The build
mode is a Vite build-time flag:

- **Dynamic (default)** — `make build-web` then `make dev`; FastAPI serves the
  SPA and `/api/puzzle/:date` exactly as above.
- **Static** — `make static` runs the generator into `web/public/puzzles/`
  (`PUZZLE_STORE=static`) and builds the SPA with `VITE_PUZZLE_MODE=static`;
  the client then fetches `puzzles/YYYY-MM-DD.json` directly. `web/dist` is a
  plain static site deployable to GitHub Pages / Cloudflare Pages / any file
  host, with no backend.

Because each day's puzzle is an immutable file, a scheduled CI job (e.g. a
GitHub Actions cron at 02:00 UTC) can generate the next puzzle with
`PUZZLE_STORE=static GEMINI_MODE=live` (key as an Actions secret), commit
`web/public/puzzles/YYYY-MM-DD.json`, and push — the static host redeploys
automatically. There's nothing stopping you from switching back to the dynamic
mode later (e.g. to add accounts, submissions, or server-side scoring): the
client respects `VITE_PUZZLE_MODE` either way, or you just build with the
default and deploy the Cloud Run service again.

### GitHub Pages (free, no server)

Three workflows in `.github/workflows/` make this repo a self-updating static
site with no backend:

- `pages.yml` — builds `web/dist` (`VITE_PUZZLE_MODE=static`) and deploys it to
  GitHub Pages. Runs on every push to `main`, on demand, and after the daily
  generator finishes.
- `gen-daily.yml` — cron at **02:00 UTC** generates *tomorrow's* puzzle with
  live Gemini, commits it, and pushes (which redeploys). Falls back to stub
  mode if the key is missing so a puzzle always ships.
- `ci.yml` — ruff + mypy + pytest + vitest on every push/PR.

One-time setup in the GitHub UI:

1. **Enable Pages:** Settings → Pages → Source → **GitHub Actions**.
2. **Add the secret:** Settings → Secrets and variables → Actions →
   `GEMINI_API_KEY` = your Gemini key. Until you add it, the cron generates
   stub puzzles (no real clues).
3. Confirm the `Generate Daily Puzzle` workflow is enabled for the repo
   (scheduled workflows are disabled by default on forks).

The Vite build uses a relative `base`, so it works under any Pages subpath
(`https://USER.github.io/REPO/`) without editing config.

## How generation works

1. **Skeleton** — several 10×10 block patterns (180° symmetry, runs 3–9, no
   2×2 blocks, connected) are tried in turn until one fills completely.
2. **Fill** — a backtracking CSP fills the grid from the Broda bank (≤9-letter
   words, no theme).
   - **Solver** (`generator/filler.py`): most-constrained-variable selection
     (pick the unfilled slot with the fewest remaining candidates first),
     forward checking (refresh the crossing slots' domains on every placement;
     prune immediately if any goes empty), and randomized restarts (a fresh
     seed each attempt diversifies tie-breaks / candidate order). Both a node
     budget and a *total* time budget (shared across all restarts, not
     per-restart) bound the search; the deepest partial fill reached is kept.
   - **Produce** (`generator/pipeline.py`): the first skeleton whose fill
     completes is clued and shipped. A partial fill is never accepted — the
     pipeline simply tries the next skeleton.
3. **Clues** — all fill words batched to Gemini at Standard difficulty
   (~10-minute solve); any word the first pass skips is bumped alone a second
   time, so only words unclueable in both passes are blacklisted and the grid
   is re-filled (bounded retries). Only a fully-clued, complete grid is saved.
   The `--difficulty 1-5` flag (and `difficulty` dev-generate field)
   shifts the clue brief from Beginner (~5 min) up to Expert (~25 min).
4. **Number & store** — standard crossword numbering → immutable JSON to storage.
   If generation exhausts its time/skeleton budget and cannot produce a fresh
   puzzle, the day recycles a random existing puzzle from another date
   (restamped to today's date) so the site never serves an empty day.

Wordlist: Peter Broda's scored list (free for any use incl. commercial).
