// Thin typed wrapper around the backend REST API.
// Reads VITE_API_URL at build/runtime; falls back to localhost:8000.

import type {
  ArtifactKind,
  ArtifactView,
  ChatRequest,
  ChatResponse,
  CreateRunRequest,
  DecisionRequest,
  RunDetail,
  RunSummary,
  Stats,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

function authHeaders(): Record<string, string> {
  return API_KEY ? { authorization: `Bearer ${API_KEY}` } : {};
}

interface ApiErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(
    message: string,
    status: number,
    code?: string,
  ) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let envelope: ApiErrorEnvelope = {};
    try {
      envelope = (await res.json()) as ApiErrorEnvelope;
    } catch {
      /* non-JSON error body */
    }
    const msg = envelope.error?.message ?? res.statusText ?? "Request failed";
    throw new ApiError(msg, res.status, envelope.error?.code);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  createRun: (body: CreateRunRequest) =>
    request<RunSummary>("/api/runs", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listRuns: (limit = 20) =>
    request<{ runs: RunSummary[]; total_returned: number }>(
      `/api/runs?limit=${limit}`,
    ),

  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),

  stats: () => request<Stats>("/api/stats"),

  chat: (id: string, body: ChatRequest) =>
    request<ChatResponse>(`/api/runs/${id}/chat`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  decideRun: (id: string, body: DecisionRequest) =>
    request<RunSummary>(`/api/runs/${id}/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  deleteRun: (id: string) =>
    request<void>(`/api/runs/${id}`, {
      method: "DELETE",
    }),

  deleteAllRuns: () =>
    request<void>("/api/runs", {
      method: "DELETE",
    }),

  updateArtifact: (runId: string, kind: string, content: any) =>
    request<ArtifactView>(`/api/runs/${runId}/artifacts/${kind}`, {
      method: "PUT",
      body: JSON.stringify(content),
    }),

  parseArtifact: (runId: string, kind: string, text: string) =>
    request<ArtifactView>(`/api/runs/${runId}/artifacts/${kind}/parse`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  retryRun: (runId: string) =>
    request<RunSummary>(`/api/runs/${runId}/retry`, {
      method: "POST",
    }),

  submitClarifications: (runId: string, answers: Record<string, string>) =>
    request<RunSummary>(`/api/runs/${runId}/clarifications`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  listArtifactVersions: (runId: string, kind: ArtifactKind) =>
    request<{
      kind: ArtifactKind;
      versions: Array<{ id: string; version: number; created_at: string }>;
      total: number;
    }>(`/api/runs/${runId}/artifacts/${kind}/versions`),

  getArtifactVersion: (runId: string, kind: ArtifactKind, version: number) =>
    request<ArtifactView>(
      `/api/runs/${runId}/artifacts/${kind}/versions/${version}`,
    ),
};

export const apiUrl = API_URL;
export const apiKey = API_KEY;

/**
 * Fetch the generated code bundle for a run as a ZIP and trigger a browser
 * download. Kept separate from `request()` because it returns a binary blob,
 * not JSON.
 */
export async function downloadCodeZip(runId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/runs/${runId}/code.zip`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    let envelope: ApiErrorEnvelope = {};
    try {
      envelope = (await res.json()) as ApiErrorEnvelope;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(
      envelope.error?.message ?? res.statusText ?? "Download failed",
      res.status,
      envelope.error?.code,
    );
  }

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? `${runId}.zip`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
