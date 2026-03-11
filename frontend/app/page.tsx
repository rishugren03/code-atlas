"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { analyzeRepo } from "../lib/api";
import styles from "./page.module.css";

const FEATURES = [
  {
    icon: "📈",
    title: "Commit Timeline",
    description:
      "Watch code evolve through an interactive timeline. Scrub through history and see every change unfold.",
  },
  {
    icon: "🧑‍💻",
    title: "Contributor Network",
    description:
      "Discover who built what. Explore contributor graphs, ownership maps, and collaboration patterns.",
  },
  {
    icon: "🔗",
    title: "Dependency Graph",
    description:
      "Visualize the entire ecosystem. See how packages connect, influence, and depend on each other.",
  },
  {
    icon: "🧬",
    title: "Language Family Tree",
    description:
      "Explore the genealogy of programming languages from the 1950s to today.",
  },
  {
    icon: "🐛",
    title: "Bug Detective",
    description:
      "Trace any line of code back to its origin. Find who wrote it, when, and why.",
  },
  {
    icon: "🌌",
    title: "Code Universe",
    description:
      "A 3D galaxy of open-source projects. Navigate the cosmos of code.",
  },
];

const FAMOUS_REPOS = [
  { name: "React", owner: "facebook", lang: "JavaScript", stars: "228k" },
  { name: "VS Code", owner: "microsoft", lang: "TypeScript", stars: "165k" },
  { name: "Linux", owner: "torvalds", lang: "C", stars: "185k" },
  { name: "Python", owner: "python", lang: "Python", stars: "64k" },
  { name: "Rust", owner: "rust-lang", lang: "Rust", stars: "100k" },
  { name: "Node.js", owner: "nodejs", lang: "JavaScript", stars: "108k" },
];

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("");
  const [isHovered, setIsHovered] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      // Basic github url parsing
      const urlPattern = /github\.com\/([^/]+)\/([^/]+)/i;
      const match = repoUrl.match(urlPattern);
      
      if (!match) {
        alert("Please enter a valid GitHub URL (e.g., https://github.com/facebook/react).");
        setIsSubmitting(false);
        return;
      }
      
      const owner = match[1];
      let name = match[2];
      if (name.endsWith(".git")) {
        name = name.slice(0, -4);
      }

      // Start analysis process
      await analyzeRepo(repoUrl);
      
      // Navigate to repository dashboard
      router.push(`/repo/${owner}/${name}`);
    } catch (error: any) {
      console.error("Analysis Error:", error);
      alert(error.message || "Failed to analyze repository. Please try again.");
      setIsSubmitting(false);
    }
  };

  return (
    <main className={styles.main}>
      {/* Background Effects */}
      <div className={styles.bgOrbs}>
        <div className={styles.orb1} />
        <div className={styles.orb2} />
        <div className={styles.orb3} />
      </div>

      {/* Hero Section */}
      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.badge}>
            <span className={styles.badgeDot} />
            Open Source Evolution Explorer
          </div>

          <h1 className={styles.title}>
            Explore How
            <span className="gradient-text"> Software </span>
            Evolves
          </h1>

          <p className={styles.subtitle}>
            The Google Maps for Software History. Paste any repository URL and
            watch its entire evolution unfold — commits, contributors,
            dependencies, and beyond.
          </p>

          {/* Search Bar */}
          <form className={styles.searchForm} onSubmit={handleSubmit}>
            <div
              className={`${styles.searchWrapper} ${isHovered ? styles.searchWrapperActive : ""}`}
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
            >
              <div className={styles.searchIcon}>
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="M21 21l-4.35-4.35" />
                </svg>
              </div>
              <input
                id="repo-url-input"
                type="text"
                className={styles.searchInput}
                placeholder="https://github.com/facebook/react"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                aria-label="Repository URL"
              />
              <button id="analyze-btn" type="submit" className={styles.searchBtn} disabled={isSubmitting}>
                {isSubmitting ? "Processing..." : "Explore"}
                {!isSubmitting && (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                )}
              </button>
            </div>
          </form>

          <p className={styles.hint}>
            Try one of the famous repos below, or paste any GitHub URL
          </p>
        </div>
      </section>

      {/* Famous Repos */}
      <section className={styles.famousSection}>
        <h2 className={styles.sectionTitle}>Popular Repositories</h2>
        <div className={styles.repoGrid}>
          {FAMOUS_REPOS.map((repo) => (
            <button
              key={repo.name}
              className={styles.repoCard}
              onClick={() =>
                setRepoUrl(`https://github.com/${repo.owner}/${repo.name.toLowerCase().replace(/\s/g, "")}`)
              }
            >
              <div className={styles.repoName}>{repo.name}</div>
              <div className={styles.repoMeta}>
                <span className={styles.repoOwner}>{repo.owner}</span>
                <span className={styles.repoDot}>·</span>
                <span className={styles.repoLang}>{repo.lang}</span>
                <span className={styles.repoDot}>·</span>
                <span className={styles.repoStars}>⭐ {repo.stars}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className={styles.featuresSection}>
        <h2 className={styles.sectionTitle}>
          Everything You Need to Understand Code
        </h2>
        <p className={styles.sectionSubtitle}>
          Six powerful tools to explore any open-source project
        </p>
        <div className={styles.featuresGrid}>
          {FEATURES.map((feature, idx) => (
            <div
              key={feature.title}
              className={styles.featureCard}
              style={{ animationDelay: `${idx * 100}ms` }}
            >
              <div className={styles.featureIcon}>{feature.icon}</div>
              <h3 className={styles.featureTitle}>{feature.title}</h3>
              <p className={styles.featureDesc}>{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className={styles.footerContent}>
          <div className={styles.footerBrand}>
            <span className="gradient-text">🌌 CodeAtlas</span>
            <p>Open Source Evolution Explorer</p>
          </div>
          <div className={styles.footerLinks}>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
            <a href="/docs">API Docs</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
