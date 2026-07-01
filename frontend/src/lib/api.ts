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
