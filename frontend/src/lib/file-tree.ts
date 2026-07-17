export interface TreeNode {
  name: string;
  path: string;
  children?: TreeNode[];
  /** Index into the source files array; present only on leaf (file) nodes. */
  fileIndex?: number;
}

/** Build a nested tree from flat file paths — folders first, alphabetical. */
export function buildTree(files: Array<{ path: string }>): TreeNode[] {
  const root: TreeNode[] = [];

  files.forEach((file, fileIndex) => {
    const parts = file.path.split("/").filter(Boolean);
    let level = root;
    let prefix = "";

    parts.forEach((part, i) => {
      prefix = prefix ? `${prefix}/${part}` : part;
      const isFile = i === parts.length - 1;
      let node = level.find((n) => n.name === part && !!n.children !== isFile);
      if (!node) {
        node = isFile
          ? { name: part, path: prefix, fileIndex }
          : { name: part, path: prefix, children: [] };
        level.push(node);
      }
      if (!isFile) level = node.children!;
    });
  });

  const sortLevel = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      const aDir = a.children ? 0 : 1;
      const bDir = b.children ? 0 : 1;
      return aDir - bDir || a.name.localeCompare(b.name);
    });
    for (const n of nodes) if (n.children) sortLevel(n.children);
  };
  sortLevel(root);
  return root;
}

const EXT_LANG: Record<string, string> = {
  ts: "typescript",
  tsx: "tsx",
  js: "javascript",
  jsx: "jsx",
  mjs: "javascript",
  cjs: "javascript",
  json: "json",
  py: "python",
  html: "html",
  htm: "html",
  css: "css",
  md: "markdown",
  yml: "yaml",
  yaml: "yaml",
  sh: "bash",
  bash: "bash",
  sql: "sql",
  toml: "toml",
};

/** Infer a Shiki language id from a file path (undefined → plain text). */
export function langForPath(path: string): string | undefined {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return EXT_LANG[ext];
}
