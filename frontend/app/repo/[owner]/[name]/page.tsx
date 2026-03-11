"use client";

import { useEffect, useState, use } from "react";
import { formatDistanceToNow, format } from "date-fns";
import Navbar from "../../../components/Navbar";
import {
  lookupRepo,
  getRepoCommits,
  connectRepoWebSocket,
} from "../../../../lib/api";
import styles from "./page.module.css";
import { Calendar, GitCommit, Users, FileCode2, Search } from "lucide-react";

export default function RepoDashboard({ params }: { params: Promise<{ owner: string; name: string }> }) {
  const unwrappedParams = use(params);
  const { owner, name } = unwrappedParams;
  
  const [repo, setRepo] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Dashboard Data
  const [commits, setCommits] = useState<any[]>([]);
  const [commitsTotal, setCommitsTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [authorFilter, setAuthorFilter] = useState("");
  const [expandedCommit, setExpandedCommit] = useState<string | null>(null);

  // 1. Initial Lookup
  useEffect(() => {
    async function init() {
      try {
        const data = await lookupRepo(owner, name);
        setRepo(data);
        setStatus({
          status: data.processing_status,
          progress: data.processing_status === "processed" ? 100 : 0,
          commits_processed: data.total_commits,
          message:
            data.processing_status === "processed"
              ? "Analysis Complete."
              : "Initializing...",
        });
      } catch (err: any) {
        setError(err.message || "Repository not found or failed to load.");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [owner, name]);

  // 2. WebSocket for live processing updates
  useEffect(() => {
    if (!repo || repo.processing_status === "processed" || repo.processing_status === "failed") {
      return;
    }

    const ws = connectRepoWebSocket(repo.id, (data) => {
      setStatus((prev: any) => ({ ...prev, ...data }));
      
      if (data.status === "processed") {
        setRepo((prev: any) => ({ ...prev, processing_status: "processed" }));
      }
    });

    return () => {
      ws.close();
    };
  }, [repo]);

  // 3. Load Dashboard Data once processed
  useEffect(() => {
    if (repo?.processing_status === "processed") {
      loadCommits(1, true);
    }
  }, [repo?.processing_status, authorFilter]);

  async function loadCommits(pageNum: number, reset = false) {
    if (!repo) return;
    try {
      const res = await getRepoCommits(repo.id, {
        page: pageNum,
        per_page: 50,
        author: authorFilter || undefined,
      });
      if (reset) {
        setCommits(res.items);
      } else {
        setCommits((prev) => [...prev, ...res.items]);
      }
      setCommitsTotal(res.total);
      setPage(pageNum);
    } catch (err) {
      console.error("Failed to load commits:", err);
    }
  }

  // Render Loading
  if (loading) {
    return (
      <div className={styles.pageContainer}>
        <Navbar />
        <div className={styles.processingOverlay}>
          <div className={styles.processingOrb} />
          <h2 className={styles.processingStatus}>Loading Repository...</h2>
        </div>
      </div>
    );
  }

  // Render Error
  if (error) {
    return (
      <div className={styles.pageContainer}>
        <Navbar />
        <div className={styles.processingOverlay}>
          <h2 className={styles.processingStatus} style={{ color: "var(--accent-tertiary)" }}>
            Error
          </h2>
          <p className={styles.processingMessage}>{error}</p>
        </div>
      </div>
    );
  }

  // Render Processing State
  if (status?.status === "pending" || status?.status === "queued" || status?.status === "processing") {
    return (
      <div className={styles.pageContainer}>
        <Navbar />
        <div className={styles.processingOverlay}>
          <div className={styles.processingOrb} />
          <h2 className={styles.processingStatus}>
            Analyzing {owner}/{name}
          </h2>
          <p className={styles.processingMessage}>{status.message}</p>
          
          <div className={styles.progressBar}>
            <div
              className={styles.progressFill}
              style={{ width: `${Math.max(5, status.progress || 0)}%` }}
            />
          </div>
          <p style={{ marginTop: "1rem", color: "var(--text-muted)", fontSize: "0.875rem" }}>
            {status.commits_processed} commits processed...
          </p>
        </div>
      </div>
    );
  }

  // Render Dashboard
  return (
    <div className={styles.pageContainer}>
      <Navbar />
      
      <main className={styles.mainContent}>
        <div className="container">
          
          {/* Header */}
          <header className={styles.dashboardHeader}>
            <h1 className={styles.repoTitle}>
              <span className={styles.repoOwner}>{owner}</span> / {name}
            </h1>
            <div className={styles.repoBadges}>
              {repo.primary_language && (
                <span className={`${styles.badge} ${styles.lang}`}>
                  <FileCode2 size={14} /> {repo.primary_language}
                </span>
              )}
              <span className={`${styles.badge} ${styles.stars}`}>
                ⭐ {Intl.NumberFormat("en-US", { notation: "compact" }).format(repo.stars)}
              </span>
              <span className={styles.badge}>
                🍴 {Intl.NumberFormat("en-US", { notation: "compact" }).format(repo.forks)}
              </span>
            </div>
            {repo.description && (
              <p style={{ color: "var(--text-secondary)", maxWidth: "800px" }}>
                {repo.description}
              </p>
            )}
          </header>

          {/* Stats Grid */}
          <section className={styles.statsGrid}>
            <div className={styles.statCard}>
              <div className={styles.statValue}>
                {Intl.NumberFormat("en-US").format(repo.total_commits)}
              </div>
              <div className={styles.statLabel}>
                <GitCommit size={14} style={{ display: 'inline', marginRight: '4px' }} />
                Total Commits
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>
                {Intl.NumberFormat("en-US").format(repo.total_contributors || 0)}
              </div>
              <div className={styles.statLabel}>
                <Users size={14} style={{ display: 'inline', marginRight: '4px' }} />
                Contributors
              </div>
            </div>
          </section>

          {/* Timeline Section */}
          <section className={styles.timelineSection}>
            <div className={styles.timelineHeader}>
              <h2 className={styles.timelineTitle}>Commit Timeline</h2>
              
              <div className={styles.filters}>
                <div style={{ position: "relative" }}>
                  <Search size={16} style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                  <input
                    type="text"
                    placeholder="Search author..."
                    className={styles.filterInput}
                    style={{ paddingLeft: "32px" }}
                    value={authorFilter}
                    onChange={(e) => setAuthorFilter(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className={styles.timeline}>
              {commits.map((commit: any) => (
                <div 
                  key={commit.commit_hash} 
                  className={styles.commitNode}
                  onClick={() => setExpandedCommit(expandedCommit === commit.commit_hash ? null : commit.commit_hash)}
                >
                  <div className={styles.commitDot} />
                  
                  <div className={styles.commitHeader}>
                    <div style={{ flex: 1 }}>
                      <div className={styles.commitMessage}>
                        {commit.message.split("\n")[0]}
                      </div>
                      <div className={styles.commitMeta}>
                        <span style={{ color: "var(--accent-primary-light)", fontWeight: 500 }}>
                          {commit.author_name}
                        </span>
                        <span>•</span>
                        <span>
                          {commit.committed_at 
                            ? formatDistanceToNow(new Date(commit.committed_at), { addSuffix: true })
                            : "Unknown Date"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className={styles.commitStats}>
                    <span className={styles.added}>+{commit.additions}</span>
                    <span className={styles.deleted}>-{commit.deletions}</span>
                    <span className={styles.files}>({commit.files_changed} files)</span>
                    <span style={{ marginLeft: "auto", color: "var(--text-muted)" }}>
                      {commit.commit_hash.substring(0, 7)}
                    </span>
                  </div>

                  {expandedCommit === commit.commit_hash && (
                    <div className={styles.commitExpanded}>
                      <strong>Full Message:</strong>
                      <br />
                      {commit.message}
                      
                      {commit.committed_at && (
                        <div style={{ marginTop: "12px", color: "var(--text-muted)" }}>
                          <Calendar size={12} style={{ display: "inline", marginRight: "4px" }} />
                          {format(new Date(commit.committed_at), "PPpp")}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {commits.length < commitsTotal && (
                <button 
                  className={styles.loadMore}
                  onClick={() => loadCommits(page + 1)}
                >
                  Load Older Commits
                </button>
              )}
            </div>
          </section>

        </div>
      </main>
    </div>
  );
}
