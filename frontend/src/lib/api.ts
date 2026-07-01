// Typed client for the ScholarAI backend. Requests are same-origin in dev via the
// Vite proxy (see vite.config.ts).

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  data_dir: string;
  ollama: {
    base_url: string;
    reachable: boolean;
    configured_model: string;
    model_pulled: boolean;
    available_models: string[];
  };
  embeddings: {
    model: string;
    dependency_installed: boolean;
    loaded: boolean;
  };
}

export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch("/health");
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

// --- Spaces ------------------------------------------------------------------

export interface Space {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  document_count: number;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function listSpaces(): Promise<Space[]> {
  return jsonOrThrow(await fetch("/api/spaces"));
}

export async function createSpace(name: string): Promise<Space> {
  return jsonOrThrow(
    await fetch("/api/spaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    })
  );
}

export async function renameSpace(id: string, name: string): Promise<Space> {
  return jsonOrThrow(
    await fetch(`/api/spaces/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    })
  );
}

export async function deleteSpace(id: string): Promise<void> {
  const res = await fetch(`/api/spaces/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`Delete failed: ${res.status}`);
}

// --- Documents ---------------------------------------------------------------

export interface Document {
  doc_id: string;
  name: string;
  ext: string;
  size: number;
  checksum: string;
  uploaded_at: string;
  chunk_count: number;
  status: string;
  reused: boolean;
}

export async function listDocuments(spaceId: string): Promise<Document[]> {
  return jsonOrThrow(await fetch(`/api/spaces/${spaceId}/documents`));
}

export async function uploadDocument(spaceId: string, file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  return jsonOrThrow(
    await fetch(`/api/spaces/${spaceId}/documents`, { method: "POST", body: form })
  );
}

export async function deleteDocument(spaceId: string, docId: string): Promise<void> {
  const res = await fetch(`/api/spaces/${spaceId}/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) throw new Error(`Delete failed: ${res.status}`);
}

// --- Chat --------------------------------------------------------------------

export interface Source {
  index: number;
  chunk_id: string;
  document: string;
  page: number | null;
  score: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  prompt_version?: string;
  ts?: string;
}

export async function getChatHistory(spaceId: string): Promise<ChatMessage[]> {
  return jsonOrThrow(await fetch(`/api/spaces/${spaceId}/chat/history`));
}

export interface StreamHandlers {
  onSources?: (sources: Source[]) => void;
  onToken?: (text: string) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
}

/** POST a question and consume the NDJSON event stream. */
export async function streamChat(
  spaceId: string,
  question: string,
  handlers: StreamHandlers
): Promise<void> {
  const res = await fetch(`/api/spaces/${spaceId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok || !res.body) {
    handlers.onError?.(`Request failed: ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "sources") handlers.onSources?.(event.sources);
      else if (event.type === "token") handlers.onToken?.(event.text);
      else if (event.type === "error") handlers.onError?.(event.message);
      else if (event.type === "done") handlers.onDone?.();
    }
  }
}
