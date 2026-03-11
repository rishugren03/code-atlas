/**
 * CodeAtlas API Client
 *
 * Centralized API calls to the FastAPI backend.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

/**
 * Generic fetch wrapper with error handling.
 */
async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  const config = {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: response.statusText,
    }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// ─── Health ────────────────────────────────────────────────

export async function checkHealth() {
  return apiFetch("/api/health");
}

// ─── Repositories ─────────────────────────────────────────

export async function analyzeRepo(url: string) {
  return apiFetch("/api/repos/analyze", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function getRepoStatus(id: string | number) {
  return apiFetch(`/api/repos/${id}/status`);
}

export async function getRepo(id: string | number) {
  return apiFetch(`/api/repos/${id}`);
}

export async function lookupRepo(owner: string, name: string) {
  return apiFetch(`/api/repos/lookup/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`);
}

export async function searchRepos(query: string) {
  return apiFetch(`/api/repos/search?q=${encodeURIComponent(query)}`);
}

export async function getPopularRepos() {
  return apiFetch("/api/repos/popular");
}

// ─── Commits ──────────────────────────────────────────────

export async function getRepoCommits(repoId: string | number, params: any = {}) {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", params.page);
  if (params.per_page) searchParams.set("per_page", params.per_page);
  if (params.author) searchParams.set("author", params.author);
  if (params.date_from) searchParams.set("date_from", params.date_from);
  if (params.date_to) searchParams.set("date_to", params.date_to);

  const qs = searchParams.toString();
  return apiFetch(`/api/repos/${repoId}/commits${qs ? `?${qs}` : ""}`);
}

// ─── Contributors ─────────────────────────────────────────

export async function getRepoContributors(repoId: string | number) {
  return apiFetch(`/api/repos/${repoId}/contributors`);
}

// ─── WebSocket ────────────────────────────────────────────

export function connectRepoWebSocket(repoId: string | number, onMessage: (data: any) => void) {
  const ws = new WebSocket(`${WS_BASE_URL}/api/ws/repos/${repoId}/status`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      // ignore parse errors
    }
  };

  ws.onerror = () => {
    // silently handle — UI will fall back to polling
  };

  return ws;
}

const api = {
  checkHealth,
  analyzeRepo,
  getRepoStatus,
  getRepo,
  lookupRepo,
  searchRepos,
  getPopularRepos,
  getRepoCommits,
  getRepoContributors,
  connectRepoWebSocket,
};

export default api;
