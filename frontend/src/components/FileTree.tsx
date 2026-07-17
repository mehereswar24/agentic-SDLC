import { useMemo, useState } from "react";
import { ChevronRight, File as FileIcon, Folder, FolderOpen } from "lucide-react";

import { cn } from "@/lib/utils";
import { buildTree, type TreeNode } from "@/lib/file-tree";

export function FileTree({
  files,
  activeIndex,
  onSelect,
}: {
  files: Array<{ path: string }>;
  activeIndex: number;
  onSelect: (fileIndex: number) => void;
}) {
  const tree = useMemo(() => buildTree(files), [files]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggle = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  const renderNodes = (nodes: TreeNode[], depth: number) =>
    nodes.map((node) => {
      const pad = { paddingLeft: `${depth * 14 + 8}px` };
      if (node.children) {
        const isCollapsed = collapsed.has(node.path);
        return (
          <div key={node.path}>
            <button
              onClick={() => toggle(node.path)}
              style={pad}
              className="flex w-full items-center gap-1.5 rounded-lg py-1.5 pr-2 text-left text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <ChevronRight
                className={cn(
                  "h-3 w-3 shrink-0 transition-transform",
                  !isCollapsed && "rotate-90",
                )}
              />
              {isCollapsed ? (
                <Folder className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <FolderOpen className="h-3.5 w-3.5 shrink-0" />
              )}
              <span className="truncate font-medium">{node.name}</span>
            </button>
            {!isCollapsed && renderNodes(node.children, depth + 1)}
          </div>
        );
      }
      const isActive = node.fileIndex === activeIndex;
      return (
        <button
          key={node.path}
          onClick={() => onSelect(node.fileIndex!)}
          style={pad}
          className={cn(
            "flex w-full items-center gap-1.5 rounded-lg py-1.5 pr-2 text-left text-xs transition-colors",
            isActive
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
        >
          <span className="w-3 shrink-0" />
          <FileIcon className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate font-mono">{node.name}</span>
        </button>
      );
    });

  return <div className="space-y-px">{renderNodes(tree, 0)}</div>;
}
