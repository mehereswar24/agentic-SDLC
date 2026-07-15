// Server-only helper for calling the Lovable AI Gateway (OpenAI-compatible).
// Never import this from client code.

const GATEWAY_URL = "https://ai.gateway.lovable.dev/v1/chat/completions";
const LOCAL_URL = process.env.LOCAL_AI_URL || "http://localhost:11434/v1/chat/completions";


export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ModelResult {
  content: string;
  tokensIn: number;
  tokensOut: number;
}

export async function callModel(
  messages: ChatMessage[],
  opts: { json?: boolean; model?: string; provider?: "local" | "gemini" } = {},
): Promise<ModelResult> {
  const isLocal = opts.provider === "local";
  
  if (!isLocal) {
    const apiKey = process.env.LOVABLE_API_KEY;
    if (!apiKey) throw new Error("Missing LOVABLE_API_KEY");
  }

  const model = opts.model ?? (isLocal ? (process.env.LOCAL_AI_MODEL || "llama3") : "google/gemini-3-flash-preview");

  const body: Record<string, unknown> = {
    model,
    messages,
  };
  if (opts.json) {
    body.response_format = { type: "json_object" };
  }

  const res = await fetch(isLocal ? LOCAL_URL : GATEWAY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(isLocal ? {} : { "Lovable-API-Key": process.env.LOVABLE_API_KEY! }),
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    if (res.status === 429) {
      throw new Error("AI rate limit reached. Please wait a moment and try again.");
    }
    if (res.status === 402) {
      throw new Error("AI credits exhausted. Add credits in your workspace to continue.");
    }
    throw new Error(`AI gateway error (${res.status}): ${text.slice(0, 300)}`);
  }

  const data = await res.json();
  const content: string = data?.choices?.[0]?.message?.content ?? "";
  const tokensIn: number = data?.usage?.prompt_tokens ?? 0;
  const tokensOut: number = data?.usage?.completion_tokens ?? 0;

  return { content, tokensIn, tokensOut };
}

// Robustly extract a JSON object from a model response.
export function parseJson<T>(raw: string): T {
  let text = raw.trim();

  // Strip markdown code fences if present.
  const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenceMatch) text = fenceMatch[1].trim();

  try {
    return JSON.parse(text) as T;
  } catch {
    // Fallback: grab the outermost braces.
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start !== -1 && end !== -1 && end > start) {
      return JSON.parse(text.slice(start, end + 1)) as T;
    }
    throw new Error("Failed to parse AI response as JSON");
  }
}
