---
trigger: always_on
---

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
- [ ] **Contributor network graph:** D3 force-directed graph showing collaborations 