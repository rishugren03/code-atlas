import { Folder, FileCode2, ChevronRight, ChevronDown } from "lucide-react";
import { useState } from "react";
import styles from "./FileBrowser.module.css";

interface FileEntry {
  path: string;
  type: string;
  size: number | null;
}

interface FileBrowserProps {
  entries: FileEntry[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

export default function FileBrowser({ entries, selectedPath, onSelect }: FileBrowserProps) {
  // Convert flat list to tree
  const tree: any = {};
  entries.forEach((entry) => {
    const parts = entry.path.split("/");
    let current = tree;
    parts.forEach((part, i) => {
      if (i === parts.length - 1) {
        current[part] = entry;
      } else {
        if (!current[part]) {
          current[part] = { _isDir: true, _children: {} };
        }
        current = current[part]._children;
      }
    });
  });

  const renderTree = (node: any, pathPrefix = "") => {
    return Object.keys(node).sort((a, b) => {
      // Directories first
      const aIsDir = node[a]._isDir || node[a].type === "tree";
      const bIsDir = node[b]._isDir || node[b].type === "tree";
      if (aIsDir && !bIsDir) return -1;
      if (!aIsDir && bIsDir) return 1;
      return a.localeCompare(b);
    }).map((key) => {
      const item = node[key];
      const currentPath = pathPrefix ? `${pathPrefix}/${key}` : key;
      const isDir = item._isDir || item.type === "tree";

      return (
        <TreeNode
          key={currentPath}
          name={key}
          path={currentPath}
          isDir={isDir}
          childrenNode={isDir && item._children ? item._children : null}
          selectedPath={selectedPath}
          onSelect={onSelect}
          renderTree={renderTree}
        />
      );
    });
  };

  if(!entries || entries.length === 0) {
    return <div className={styles.empty}>No files found</div>;
  }

  return <div className={styles.fileBrowser}>{renderTree(tree)}</div>;
}

function TreeNode({
  name,
  path,
  isDir,
  childrenNode,
  selectedPath,
  onSelect,
  renderTree,
}: any) {
  const [isOpen, setIsOpen] = useState(false);
  const isSelected = selectedPath === path;

  const handleClick = () => {
    if (isDir) {
      setIsOpen(!isOpen);
    } else {
      onSelect(path);
    }
  };

  return (
    <div className={styles.treeNode}>
      <div
        className={`${styles.nodeLabel} ${isSelected ? styles.selected : ""}`}
        onClick={handleClick}
        style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
      >
        {isDir ? (
          isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />
        ) : (
          <span style={{ width: 14 }} />
        )}
        {isDir ? <Folder size={14} color="#8ab4f8" /> : <FileCode2 size={14} color="#a8c7fa" />}
        <span>{name}</span>
      </div>
      {isDir && isOpen && childrenNode && (
        <div className={styles.children}>{renderTree(childrenNode, path)}</div>
      )}
    </div>
  );
}
