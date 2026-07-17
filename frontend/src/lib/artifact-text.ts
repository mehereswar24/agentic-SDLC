/**
 * Serialize a structured artifact into a readable indented-text document.
 * Used by the artifact editor (edit → LLM re-parse) and by the diff view so
 * PRD/design diffs read like documents, not JSON noise.
 */
export function jsonToText(obj: any, indent = 0): string {
  if (obj === null || obj === undefined) return "";
  if (typeof obj !== "object") return String(obj);

  let result = "";
  const spaces = "  ".repeat(indent);

  if (Array.isArray(obj)) {
    for (const item of obj) {
      if (typeof item === "object" && item !== null) {
        result += `${spaces}- ${jsonToText(item, indent + 1).trimStart()}`;
      } else {
        result += `${spaces}- ${item}\n`;
      }
    }
  } else {
    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === "object" && value !== null) {
        result += `${spaces}${key}:\n${jsonToText(value, indent + 1)}`;
      } else {
        result += `${spaces}${key}: ${value}\n`;
      }
    }
  }
  return result;
}
