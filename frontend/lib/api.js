/**
 * CodeAtlas API Client
 *
 * Centralized API calls to the FastAPI backend.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Generic fetch wrapper with error handling.
 */
async function apiFetch(endpoint, options = {}) {
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

// ─── Repositories (Phase 2+) ──────────────────────────────

export async function analyzeRepo(url) {
  return apiFetch("/api/repos/analyze", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function getRepoStatus(id) {
  return apiFetch(`/api/repos/${id}/status`);
}

export async function getRepo(id) {
  return apiFetch(`/api/repos/${id}`);
}

export async function searchRepos(query) {
  return apiFetch(`/api/repos/search?q=${encodeURIComponent(query)}`);
}

export async function getPopularRepos() {
  return apiFetch("/api/repos/popular");
}

const api = {
  checkHealth,
  analyzeRepo,
  getRepoStatus,
  getRepo,
  searchRepos,
  getPopularRepos,
};

export default api;
