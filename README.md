# 🌌 CodeAtlas — Open Source Evolution Explorer

> **A platform that visualizes the full evolution, relationships, and influence of software projects and programming languages across the open-source ecosystem.**

Users paste a repository URL and explore:

- 📈 Commit timeline & code replay
- 🧑‍💻 Contributor network
- 🔗 Ecosystem dependency graph
- 🧬 Programming language family tree
- 🐛 Bug origin detection

---

## Table of Contents

1. [Vision](#-vision)
2. [Architecture Overview](#-architecture-overview)
3. [Tech Stack](#-tech-stack)
4. [Data Models](#-data-models)
5. [Implementation Phases](#-implementation-phases)
6. [Directory Structure](#-directory-structure)
7. [API Design](#-api-design)
8. [Scaling & Performance Strategy](#-scaling--performance-strategy)
9. [Security](#-security)

---

## 🎯 Vision

Create the **"Google Maps for Software History"** — a platform where developers can explore how any open-source project evolved, discover hidden relationships between projects, and watch code history unfold like a movie.

### Target Users

| Audience | Use Case |
|---|---|
| **Developers** | Explore open-source project evolution |
| **Students** | Learn large codebases visually |
| **Researchers** | Study software evolution patterns |
| **Coding Clubs** | Learn debugging, refactoring, and commit practices |

---

## 🏗 Architecture Overview

```
                    ┌──────────┐
                    │  Users   │
                    └────┬─────┘
                         │
                ┌────────▼────────┐
                │  CDN / Edge     │  ← Static graph datasets (graph.json, timeline.json)
                │  (Cloudflare)   │
                └────────┬────────┘
                         │
                ┌────────▼────────┐
                │  Next.js        │  ← React + D3.js + Monaco Editor
                │  Frontend       │
                └────────┬────────┘
                         │
                ┌────────▼────────┐
                │  API Gateway    │  ← FastAPI (Python)
                │  (REST + WS)    │
                └───┬─────────┬───┘
                    │         │
          ┌─────────▼──┐  ┌──▼──────────┐
          │  Query     │  │  Job Queue  │  ← Redis + Celery
          │  Services  │  │  (async)    │
          └─────┬──────┘  └──┬──────────┘
                │            │
       ┌────────▼──┐   ┌────▼──────────┐
       │PostgreSQL │   │ Worker        │  ← PyDriller, GitPython
       │ + Neo4j   │   │ Cluster       │
       └───────────┘   └────┬──────────┘
                            │
                    ┌───────▼─────────┐
                    │ Object Storage  │  ← S3 / Cloudflare R2
                    │ (repo datasets) │
                    └─────────────────┘
```

### Data Flow

```
User enters repo URL
       │
       ▼
API checks cache (PostgreSQL)
       │
  ┌────┴────┐
  │ Cached? │
  └────┬────┘
   Yes │  No
   │   │
   │   ▼
   │  Queue job → Worker clones repo → Parse commits
   │                                     → Extract deps
   │                                     → Build graph
   │                                     → Store results
   │                                        │
   ▼                                        ▼
 Serve instantly              Store in DB + Object Storage
```

---

## ⚙ Tech Stack

### Frontend

| Tool | Purpose |
|---|---|
| **Next.js 14+** (App Router) | Framework, SSR, routing |
| **React 18+** | UI components |
| **D3.js** | 2D graphs, timelines, ecosystem maps |
| **Three.js** | 3D "Code Universe" galaxy visualization |
| **Monaco Editor** | Code replay with syntax highlighting |
| **Framer Motion** | Smooth animations & transitions |

### Backend

| Tool | Purpose |
|---|---|
| **FastAPI** (Python) | REST API + WebSocket for live updates |
| **Celery** | Distributed task queue for repo processing |
| **Redis** | Job queue broker + caching layer |
| **PyDriller** | Git commit history extraction & analysis |
| **GitPython** | Git operations (clone, log, diff) |

### Databases

| Database | Purpose |
|---|---|
| **PostgreSQL** | Repositories, commits, contributors, stats |
| **Neo4j** | Ecosystem graph (dependencies, forks, influence) |

### Infrastructure

| Tool | Purpose |
|---|---|
| **Docker + Docker Compose** | Local dev & deployment |
| **Cloudflare R2 / AWS S3** | Object storage for precomputed datasets |
| **Cloudflare CDN** | Edge delivery of static graph data |

---

## 📊 Data Models

### 1. Repository Model (PostgreSQL)

```sql
CREATE TABLE repositories (
    id              SERIAL PRIMARY KEY,
    owner           VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    full_name       VARCHAR(512) UNIQUE NOT NULL,  -- "owner/name"
    url             TEXT NOT NULL,
    description     TEXT,
    primary_language VARCHAR(100),
    stars           INTEGER DEFAULT 0,
    forks           INTEGER DEFAULT 0,
    created_at      TIMESTAMP,
    last_commit_sha VARCHAR(40),
    processing_status VARCHAR(20) DEFAULT 'pending',
        -- pending | queued | processing | processed | failed
    processed_at    TIMESTAMP,
    total_commits   INTEGER DEFAULT 0,
    total_contributors INTEGER DEFAULT 0,
    created_in_db   TIMESTAMP DEFAULT NOW(),
    updated_in_db   TIMESTAMP DEFAULT NOW()
);
```

### 2. Commit Model (PostgreSQL)

```sql
CREATE TABLE commits (
    id              SERIAL PRIMARY KEY,
    repo_id         INTEGER REFERENCES repositories(id),
    commit_hash     VARCHAR(40) NOT NULL,
    author_name     VARCHAR(255),
    author_email    VARCHAR(255),
    committed_at    TIMESTAMP,
    message         TEXT,
    files_changed   INTEGER DEFAULT 0,
    additions       INTEGER DEFAULT 0,
    deletions       INTEGER DEFAULT 0,
    parent_hash     VARCHAR(40),
    UNIQUE(repo_id, commit_hash)
);

CREATE INDEX idx_commits_repo_date ON commits(repo_id, committed_at);
```

### 3. Contributor Model (PostgreSQL)

```sql
CREATE TABLE contributors (
    id              SERIAL PRIMARY KEY,
    repo_id         INTEGER REFERENCES repositories(id),
    name            VARCHAR(255),
    email           VARCHAR(255),
    total_commits   INTEGER DEFAULT 0,
    total_additions INTEGER DEFAULT 0,
    total_deletions INTEGER DEFAULT 0,
    first_commit_at TIMESTAMP,
    last_commit_at  TIMESTAMP,
    UNIQUE(repo_id, email)
);
```

### 4. File Evolution Model (PostgreSQL)

```sql
CREATE TABLE file_changes (
    id              SERIAL PRIMARY KEY,
    commit_id       INTEGER REFERENCES commits(id),
    repo_id         INTEGER REFERENCES repositories(id),
    file_path       TEXT NOT NULL,
    change_type     VARCHAR(20), -- added | modified | deleted | renamed
    additions       INTEGER DEFAULT 0,
    deletions       INTEGER DEFAULT 0
);

CREATE INDEX idx_file_changes_path ON file_changes(repo_id, file_path);
```

### 5. Graph Relationships (Neo4j)

```cypher
// Nodes
(:Repository {name, owner, language, stars, url})
(:Language {name, year_created, paradigm})
(:Developer {name, email})

// Relationships
(:Repository)-[:DEPENDS_ON]->(:Repository)
(:Repository)-[:FORKED_FROM]->(:Repository)
(:Repository)-[:WRITTEN_IN]->(:Language)
(:Language)-[:INFLUENCED]->(:Language)
(:Developer)-[:CONTRIBUTED_TO {commits: N}]->(:Repository)
```

---

## 🚀 Implementation Phases

Each phase is a self-contained milestone. Complete one before moving to the next.

---

### Phase 1 — Project Foundation & Skeleton

> **Goal:** Set up the monorepo, dev environment, and basic project scaffolding.

#### Tasks

- [ ] Initialize Next.js frontend app (`/frontend`)
- [ ] Initialize FastAPI backend app (`/backend`)
- [ ] Create `docker-compose.yml` with services:
  - PostgreSQL
  - Redis
  - Neo4j
  - Backend (FastAPI)
  - Frontend (Next.js)
- [ ] Configure environment variables (`.env.example`)
- [ ] Set up database migrations (Alembic for SQLAlchemy)
- [ ] Create seed data scripts
- [ ] Set up ESLint, Prettier (frontend) and Ruff (backend)
- [ ] Create basic health-check endpoints

#### Deliverables

```
GET /api/health → { "status": "ok" }
Frontend renders at localhost:3000
All Docker services boot successfully
```

---

### Phase 2 — Repository Ingestion Pipeline

> **Goal:** Accept a repo URL, clone it, parse commits, and store the data.

#### Tasks

- [ ] **API endpoint:** `POST /api/repos/analyze` — accepts `{ url: "https://github.com/owner/repo" }`
- [ ] **URL parser:** Extract `owner` and `repo` from GitHub URL
- [ ] **Celery worker task:** `analyze_repository`
  - Clone repo (shallow first, then full if needed)
  - Parse commits using PyDriller
  - Extract: hash, author, date, message, files changed, additions, deletions
  - Store in PostgreSQL
- [ ] **Processing status:** Track `pending → queued → processing → processed → failed`
- [ ] **API endpoint:** `GET /api/repos/{id}/status` — poll processing state
- [ ] **WebSocket:** Push real-time processing updates to frontend
- [ ] **Incremental updates:** Store `last_commit_sha`, only process new commits on re-analysis
- [ ] **Limits:** Max repo size (2GB), max commits (500K), rate limiting

#### Deliverables

```
POST /api/repos/analyze { "url": "https://github.com/facebook/react" }
→ { "id": 1, "status": "queued" }

GET /api/repos/1/status
→ { "status": "processing", "progress": "45%" }

GET /api/repos/1
→ { full repo metadata + stats }
```

---

### Phase 3 — Commit Timeline & Repository Explorer UI

> **Goal:** Build the core frontend — repo input, commit timeline, and basic stats.

#### Tasks

- [ ] **Landing page:** Hero section with repo URL input field
- [ ] **Repo submission flow:** Submit URL → show processing status → redirect to explorer
- [ ] **Repository dashboard page** (`/repo/{owner}/{name}`):
  - Repo header (name, stars, forks, language)
  - Key stats cards (total commits, contributors, files)
  - Commit timeline (scrollable, interactive)
- [ ] **Commit timeline component:**
  - Vertical timeline with date markers
  - Each commit node shows: author, message, files changed
  - Click a commit → expand to show diff summary
  - Filter by date range, author, file
- [ ] **Pagination:** Lazy-load commits as user scrolls
- [ ] **Responsive design** — works on desktop and tablet

#### Deliverables

```
User pastes: https://github.com/microsoft/vscode
→ Processing screen with live progress
→ Interactive timeline of all commits
→ Click any commit to see details
```

---

### Phase 4 — Code Replay Mode

> **Goal:** A slider that scrubs through time, showing code evolving commit-by-commit.

#### Tasks

- [ ] **API endpoint:** `GET /api/repos/{id}/file/{path}/history` — returns list of versions for a file
- [ ] **API endpoint:** `GET /api/repos/{id}/file/{path}/at/{commit_hash}` — returns file content at a specific commit
- [ ] **Backend:** Extract file content at each commit using `git show {hash}:{path}`
- [ ] **Code Replay component:**
  - Monaco Editor showing file content
  - Timeline slider at the bottom
  - Drag slider → code updates with diff highlighting
  - Play/pause button for auto-replay
  - Speed control (1x, 2x, 5x)
- [ ] **Diff highlighting:** Green lines = added, Red lines = removed
- [ ] **File browser sidebar:** Navigate files at any point in time

#### Deliverables

```
Select a file → scrub through its history
See code appear and disappear in real time
Play button auto-advances through commits
```

---

### Phase 5 — Contributor Map & Stats

> **Goal:** Visualize who contributed what and when.

#### Tasks

- [ ] **API endpoint:** `GET /api/repos/{id}/contributors` — sorted by commits
- [ ] **API endpoint:** `GET /api/repos/{id}/contributors/{email}/activity` — contribution heatmap data
- [ ] **Contributor leaderboard component:** Ranked list with avatars, commit counts, LOC added/removed
- [ ] **Contribution heatmap:** GitHub-style activity grid per contributor
- [ ] **File ownership graph:** D3 treemap showing which developer "owns" which files/directories
- [ ] **Contributor network graph:** D3 force-directed graph showing collaborations (devs who edit same files)

#### Deliverables

```
Contributor leaderboard with drill-down
File ownership treemap
Network graph of collaborations
```

---

### Phase 6 — Ecosystem Dependency Graph

> **Goal:** Parse dependency files and build an interactive ecosystem map.

#### Tasks

- [ ] **Dependency parser:** Extract dependencies from:
  - `package.json` (npm)
  - `requirements.txt` / `pyproject.toml` (Python)
  - `Cargo.toml` (Rust)
  - `go.mod` (Go)
  - `pom.xml` / `build.gradle` (Java)
  - `Gemfile` (Ruby)
- [ ] **Neo4j integration:** Store dependency relationships as graph edges
- [ ] **API endpoint:** `GET /api/repos/{id}/dependencies` — list of dependencies
- [ ] **API endpoint:** `GET /api/ecosystem/{repo_name}` — full ecosystem graph
- [ ] **Ecosystem graph UI:**
  - D3 force-directed graph
  - Nodes = repositories/packages
  - Edges = dependency relationships
  - Click a node → see its details, drill into its own graph
  - Zoom, pan, search within graph
- [ ] **Pre-populate:** Process popular repos (React, Vue, Next.js, Express, Django, Flask, etc.)

#### Deliverables

```
Search "react" → see full ecosystem:
React → Next.js, Gatsby, React Native, Remix, etc.
Interactive graph with zoom, click, and drill-down
```

---

### Phase 7 — Programming Language Family Tree

> **Goal:** A visual genealogy of programming languages.

#### Tasks

- [ ] **Curated dataset:** Build a JSON/YAML dataset of language relationships:
  - Name, year created, paradigm, creator
  - Influenced by / influenced (edges)
  - Implementation language
- [ ] **Neo4j seed:** Load language genealogy into graph DB
- [ ] **API endpoint:** `GET /api/languages/tree` — returns the full family tree
- [ ] **API endpoint:** `GET /api/languages/{name}` — details + relationships for one language
- [ ] **Language tree UI:**
  - D3 hierarchical tree or force graph
  - Time axis (1950s → 2020s)
  - Color-coded by paradigm (OOP, functional, systems, scripting)
  - Click a language → see details, repos written in it, influenced languages
- [ ] **Connect to repos:** Link languages to analyzed repositories

#### Deliverables

```
Visual tree: C → C++ → Rust, C → Go, C → Python
Click "Python" → see top repos, influenced languages
Time slider shows languages appearing decade by decade
```

---

### Phase 8 — Bug Origin Finder (Visual Git Blame)

> **Goal:** Input a file + line → trace back to the commit that introduced it.

#### Tasks

- [ ] **API endpoint:** `GET /api/repos/{id}/blame/{path}` — full file blame
- [ ] **API endpoint:** `GET /api/repos/{id}/blame/{path}?line={N}` — blame for specific line
- [ ] **Backend:** Run `git blame` and parse output
- [ ] **Bug Detective UI:**
  - Monaco Editor showing the file
  - Click any line → see when it was written, by whom, and the commit message
  - Highlight "suspicious" lines (old code that was patched multiple times)
  - Timeline of the selected line's history
- [ ] **"Bug Hotspot" detection:** Identify files/functions with most churn (frequent edits = likely buggy)

#### Deliverables

```
Click line 240 of scheduler.c →
"Introduced in commit 4f2a1c (2008) by John Doe"
"Message: Scheduler optimization"
See full history of that line
```

---

### Phase 9 — Code Universe (3D Galaxy View) 🌌

> **Goal:** A 3D visualization where repositories are stars in a galaxy, connected by dependencies and influence.

#### Tasks

- [ ] **Three.js scene:** 3D space with camera controls (orbit, zoom, pan)
- [ ] **Nodes as stars:** Each analyzed repo = a glowing star, size = stars/popularity
- [ ] **Edges as light trails:** Dependencies and influence shown as glowing lines
- [ ] **Clustering:** Group related repos (React ecosystem, Python ML ecosystem, etc.)
- [ ] **Time slider:** Slide through years → watch the universe grow
- [ ] **Search:** Type a project name → camera flies to that star
- [ ] **Click a star:** Opens side panel with repo details
- [ ] **Performance:** Use instanced rendering, LOD, and culling for 10K+ nodes

#### Deliverables

```
3D galaxy of open-source repos
Navigate, zoom, search, click
Time slider shows ecosystem growing since 2008+
```

---

### Phase 10 — AI Explain Button & Feature Birth Tracker

> **Goal:** Use AI to explain commits and detect when features were introduced.

#### Tasks

- [ ] **AI integration:** OpenAI API or local model (Ollama)
- [ ] **"Explain this commit" button:**
  - Sends commit message + diff to AI
  - Returns plain-English explanation
  - Example: "This commit adds password hashing to prevent storing plaintext passwords"
- [ ] **Feature Birth Tracker:**
  - AI analyzes commit messages to detect feature introductions
  - Build a "feature timeline" showing when major features appeared
  - Example: VS Code → "2016: Debugger", "2017: Extensions", "2020: Remote Dev"
- [ ] **Smart commit clustering:** Group related commits into logical changes
- [ ] **Cache AI responses** to avoid redundant API calls

#### Deliverables

```
Click "Explain" on any commit → AI-generated summary
Feature timeline auto-detected from commit history
Clustered commit groups for easier navigation
```

---

### Phase 11 — Pre-loaded Famous Repos & Polish

> **Goal:** Pre-compute data for viral-ready famous repos, final polish.

#### Tasks

- [ ] **Pre-process famous repos:**
  - Linux kernel (`torvalds/linux`)
  - VS Code (`microsoft/vscode`)
  - React (`facebook/react`)
  - Node.js (`nodejs/node`)
  - Rust (`rust-lang/rust`)
  - Go (`golang/go`)
  - Python (`python/cpython`)
  - TensorFlow (`tensorflow/tensorflow`)
- [ ] **Landing page showcase:** Feature these repos as "Explore Now" cards
- [ ] **Shareable links:** `/repo/facebook/react` generates an OG image for social sharing
- [ ] **Dark/Light mode** with smooth transitions
- [ ] **Onboarding tour** for first-time users
- [ ] **Performance optimization:** Lighthouse score > 90
- [ ] **SEO:** Meta tags, OG images, sitemap
- [ ] **Analytics:** Track repos analyzed, page views, feature usage

#### Deliverables

```
Landing page with 8+ famous repos ready to explore
Social sharing with OG preview images
Polished UI with dark mode, animations, onboarding
```

---

## 📁 Directory Structure

```
open-dev-verse/
│
├── README.md                    ← This file
├── docker-compose.yml           ← All services
├── .env.example                 ← Environment variables template
│
├── frontend/                    ← Next.js application
│   ├── app/
│   │   ├── layout.js
│   │   ├── page.js              ← Landing page
│   │   ├── repo/
│   │   │   └── [owner]/
│   │   │       └── [name]/
│   │   │           ├── page.js          ← Repo dashboard
│   │   │           ├── replay/page.js   ← Code replay
│   │   │           ├── contributors/page.js
│   │   │           ├── blame/page.js    ← Bug detective
│   │   │           └── ecosystem/page.js
│   │   ├── universe/page.js     ← 3D Code Universe
│   │   └── languages/page.js   ← Language family tree
│   ├── components/
│   │   ├── ui/                  ← Buttons, cards, inputs
│   │   ├── timeline/            ← Commit timeline
│   │   ├── replay/              ← Code replay slider + editor
│   │   ├── graphs/              ← D3 ecosystem & contributor graphs
│   │   ├── universe/            ← Three.js 3D galaxy
│   │   └── layout/              ← Header, footer, sidebar
│   ├── lib/
│   │   ├── api.js               ← API client
│   │   └── utils.js
│   ├── styles/
│   │   └── globals.css
│   ├── public/
│   └── package.json
│
├── backend/                     ← FastAPI application
│   ├── app/
│   │   ├── main.py              ← FastAPI app + routers
│   │   ├── config.py            ← Settings & env vars
│   │   ├── models/              ← SQLAlchemy models
│   │   │   ├── repository.py
│   │   │   ├── commit.py
│   │   │   ├── contributor.py
│   │   │   └── file_change.py
│   │   ├── schemas/             ← Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── repos.py
│   │   │   ├── commits.py
│   │   │   ├── contributors.py
│   │   │   ├── ecosystem.py
│   │   │   ├── languages.py
│   │   │   └── blame.py
│   │   ├── services/            ← Business logic
│   │   │   ├── git_analyzer.py      ← PyDriller integration
│   │   │   ├── dependency_parser.py ← Parse package.json, etc.
│   │   │   ├── graph_service.py     ← Neo4j operations
│   │   │   └── ai_service.py       ← AI explain integration
│   │   ├── workers/             ← Celery tasks
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py
│   │   ├── db/
│   │   │   ├── database.py      ← DB session & engine
│   │   │   └── migrations/      ← Alembic
│   │   └── utils/
│   ├── requirements.txt
│   └── Dockerfile
│
├── data/                        ← Curated datasets
│   ├── languages.json           ← Programming language genealogy
│   └── famous_repos.json        ← Pre-loaded repo list
│
└── scripts/
    ├── seed_languages.py        ← Seed Neo4j with language data
    ├── preload_repos.py         ← Pre-process famous repos
    └── setup.sh                 ← One-command setup
```

---

## 🔌 API Design

### Repositories

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/repos/analyze` | Submit a repo URL for analysis |
| `GET` | `/api/repos/{id}` | Get repo metadata & stats |
| `GET` | `/api/repos/{id}/status` | Get processing status |
| `GET` | `/api/repos/search?q=react` | Search analyzed repos |
| `GET` | `/api/repos/popular` | List pre-loaded famous repos |

### Commits

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/repos/{id}/commits` | Paginated commit list |
| `GET` | `/api/repos/{id}/commits/{hash}` | Single commit details + diff |
| `GET` | `/api/repos/{id}/commits/stats` | Commit frequency stats |

### Files & Replay

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/repos/{id}/files` | File tree at latest commit |
| `GET` | `/api/repos/{id}/files/{path}/history` | File version list |
| `GET` | `/api/repos/{id}/files/{path}/at/{hash}` | File content at commit |
| `GET` | `/api/repos/{id}/blame/{path}` | Git blame for file |

### Contributors

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/repos/{id}/contributors` | Contributor leaderboard |
| `GET` | `/api/repos/{id}/contributors/{email}/activity` | Activity heatmap |

### Ecosystem

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/repos/{id}/dependencies` | Parsed dependencies |
| `GET` | `/api/ecosystem/{name}` | Full ecosystem graph |

### Languages

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/languages/tree` | Full language family tree |
| `GET` | `/api/languages/{name}` | Language details + relationships |

### AI

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/explain` | AI explanation of a commit |
| `GET` | `/api/repos/{id}/features` | Auto-detected feature timeline |

---

## 📈 Scaling & Performance Strategy

### Processing Pipeline

| Strategy | Detail |
|---|---|
| **Async processing** | All repo analysis runs via Celery workers, never in API request cycle |
| **Incremental updates** | Store `last_commit_sha`, only process new commits on re-analysis |
| **Shallow clones** | Use `git clone --depth` for initial quick analysis |
| **Batch commits** | Process commits in chunks of 1000 |
| **Result caching** | Redis cache for popular repo queries (TTL: 1 hour) |

### Frontend Performance

| Strategy | Detail |
|---|---|
| **Virtual scrolling** | Timeline renders only visible commits |
| **Lazy loading** | Graphs load on-demand when user navigates to them |
| **Precomputed datasets** | Graph JSON stored in object storage, served via CDN |
| **Code splitting** | Three.js and D3 loaded only on pages that need them |
| **Instanced rendering** | Three.js galaxy uses instanced meshes for 10K+ nodes |

### Database Performance

| Strategy | Detail |
|---|---|
| **Indexed queries** | Composite indexes on `(repo_id, committed_at)` |
| **Connection pooling** | SQLAlchemy pool for PostgreSQL |
| **Graph query optimization** | Neo4j indexes on `:Repository(name)`, `:Language(name)` |

### Limits & Rate Limiting

| Resource | Limit |
|---|---|
| Max repo size | 2 GB |
| Max commits per repo | 500,000 |
| API rate limit | 60 requests/min per IP |
| Concurrent processing jobs | 10 per user |
| Max repos in queue | 100 globally |

---

## 🔒 Security

- **Input validation:** Sanitize repo URLs, reject non-GitHub URLs (initially)
- **Rate limiting:** Per-IP and per-user limits on analysis requests
- **Resource limits:** Max clone size, max processing time (30 min timeout)
- **No arbitrary code execution:** Never run code from cloned repos
- **API keys:** GitHub API token for higher rate limits (stored in env vars)
- **CORS:** Restrict to frontend domain in production

---

## 🏁 Getting Started (After Phase 1)

```bash
# Clone and setup
git clone https://github.com/your-org/open-dev-verse.git
cd open-dev-verse
cp .env.example .env

# Start all services
docker-compose up -d

# Run database migrations
cd backend && alembic upgrade head

# Seed language data
python scripts/seed_languages.py

# Open frontend
open http://localhost:3000

# API docs
open http://localhost:8000/docs
```

---

## 📋 Phase Checklist Summary

| Phase | Feature | Status |
|---|---|---|
| 1 | Project foundation & skeleton | ⬜ Not started |
| 2 | Repository ingestion pipeline | ⬜ Not started |
| 3 | Commit timeline & repo explorer UI | ⬜ Not started |
| 4 | Code replay mode | ⬜ Not started |
| 5 | Contributor map & stats | ⬜ Not started |
| 6 | Ecosystem dependency graph | ⬜ Not started |
| 7 | Programming language family tree | ⬜ Not started |
| 8 | Bug origin finder | ⬜ Not started |
| 9 | Code Universe (3D galaxy) | ⬜ Not started |
| 10 | AI explain & feature tracker | ⬜ Not started |
| 11 | Pre-loaded repos & polish | ⬜ Not started |

---

> **Start with Phase 1. Each phase is designed to be independently demoable. Ship early, iterate fast.** 🚀
