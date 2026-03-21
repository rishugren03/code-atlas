import { useState, useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import { Play, Pause, ChevronLeft, ChevronRight, FastForward } from "lucide-react";
import styles from "./CodeReplay.module.css";
import { getFileHistory, getFileContentAtCommit } from "../lib/api";
import { format } from "date-fns";

interface CodeReplayProps {
  repoId: number | string;
  filePath: string;
}

export default function CodeReplay({ repoId, filePath }: CodeReplayProps) {
  const [history, setHistory] = useState<any[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const playTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Detect language from file extension
  const getLanguage = (path: string) => {
    const ext = path.split('.').pop()?.toLowerCase();
    const map: Record<string, string> = {
      'js': 'javascript', 'jsx': 'javascript',
      'ts': 'typescript', 'tsx': 'typescript',
      'py': 'python', 'html': 'html', 'css': 'css',
      'json': 'json', 'md': 'markdown', 'rs': 'rust',
      'go': 'go', 'java': 'java', 'c': 'c', 'cpp': 'cpp',
    };
    return map[ext || ''] || 'plaintext';
  };

  useEffect(() => {
    async function fetchHistory() {
      setLoading(true);
      try {
        const res = await getFileHistory(repoId, filePath);
        // Reverse history so it's oldest to newest for replay
        const chronologicalHistory = res.history.slice().reverse();
        setHistory(chronologicalHistory);
        setCurrentIndex(chronologicalHistory.length - 1);
      } catch (e) {
        console.error("Failed to load history", e);
      } finally {
        setLoading(false);
      }
    }
    fetchHistory();
    setIsPlaying(false);
  }, [repoId, filePath]);

  useEffect(() => {
    async function fetchContent() {
      if (history.length === 0 || currentIndex < 0 || currentIndex >= history.length) return;
      
      const commit = history[currentIndex];
      setLoading(true);
      try {
        const targetPath = commit.path || filePath;
        const res = await getFileContentAtCommit(repoId, targetPath, commit.commit_hash);
        setContent(res.content || "");
      } catch (e) {
        console.error("Failed to load file content", e);
        setContent("// Error loading content for this commit");
      } finally {
        setLoading(false);
      }
    }
    
    // Debounce fetching if rapid scrubbing
    const timer = setTimeout(() => {
      fetchContent();
    }, isPlaying ? 0 : 200);
    
    return () => clearTimeout(timer);
  }, [currentIndex, history, repoId, filePath, isPlaying]);

  useEffect(() => {
    if (isPlaying) {
      if (currentIndex >= history.length - 1) {
        setIsPlaying(false);
        return;
      }
      playTimerRef.current = setTimeout(() => {
        setCurrentIndex(prev => prev + 1);
      }, 1500 / speed);
    } else {
      if (playTimerRef.current) clearTimeout(playTimerRef.current);
    }
    
    return () => {
      if (playTimerRef.current) clearTimeout(playTimerRef.current);
    };
  }, [isPlaying, currentIndex, history.length, speed]);
  
  const togglePlay = () => setIsPlaying(!isPlaying);
  
  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setIsPlaying(false);
    setCurrentIndex(parseInt(e.target.value, 10));
  };

  const currentCommit = history[currentIndex] || null;

  if (history.length === 0 && !loading) {
    return (
      <div className={styles.emptyState}>
        No history available for <strong>{filePath}</strong>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Editor Header */}
      <div className={styles.header}>
        <div className={styles.fileName}>{filePath}</div>
        {currentCommit && (
          <div className={styles.commitInfo}>
            <span className={styles.commitDate}>
              {currentCommit.date && format(new Date(currentCommit.date), "PPpp")}
            </span>
            <span className={styles.commitAuthor}>by {currentCommit.author_name}</span>
            <span className={styles.commitHash}>{currentCommit.commit_hash.substring(0, 7)}</span>
          </div>
        )}
      </div>

      {/* Monaco Editor */}
      <div className={styles.editorContainer}>
        <Editor
          height="100%"
          language={getLanguage(filePath)}
          theme="vs-dark"
          value={content}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            wordWrap: "on",
            padding: { top: 16, bottom: 16 },
            fontSize: 14,
          }}
          loading={<div className={styles.editorLoading}>Loading editor...</div>}
        />
        {loading && <div className={styles.loadingOverlay}>Loading...</div>}
      </div>

      {/* Replay Controls & Timeline */}
      <div className={styles.controls}>
        <button className={styles.iconBtn} onClick={togglePlay} aria-label={isPlaying ? "Pause" : "Play"}>
          {isPlaying ? <Pause size={20} /> : <Play size={20} />}
        </button>
        
        <button 
          className={styles.iconBtn} 
          onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
          disabled={currentIndex === 0}
        >
          <ChevronLeft size={18} />
        </button>
        
        <input 
          type="range" 
          min="0" 
          max={Math.max(0, history.length - 1)} 
          value={currentIndex} 
          onChange={handleSliderChange}
          className={styles.slider}
        />
        
        <button 
          className={styles.iconBtn} 
          onClick={() => setCurrentIndex(Math.min(history.length - 1, currentIndex + 1))}
          disabled={currentIndex >= history.length - 1}
        >
          <ChevronRight size={18} />
        </button>

        <button 
          className={`${styles.speedBtn} ${speed === 1 ? '' : styles.speedBtnActive}`}
          onClick={() => setSpeed(speed === 1 ? 2 : speed === 2 ? 5 : 1)}
          title="Playback speed"
        >
          <FastForward size={14} style={{ marginRight: 4 }}/>
          {speed}x
        </button>
      </div>

      {/* Commit Message Box */}
      {currentCommit && (
        <div className={styles.messageBox}>
          {currentCommit.message.split("\n")[0]}
        </div>
      )}
    </div>
  );
}
