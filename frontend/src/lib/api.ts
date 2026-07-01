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
