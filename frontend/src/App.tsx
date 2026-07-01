import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getHealth, type HealthStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center justify-between border-b py-2 last:border-0">
      <div className="flex items-center gap-2">
        {ok ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        ) : (
          <XCircle className="h-4 w-4 text-amber-500" />
        )}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <span className={cn("text-xs", ok ? "text-muted-foreground" : "text-amber-600")}>
        {detail}
      </span>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setHealth(await getHealth());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-2xl px-4 py-16">
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">ScholarAI</h1>
          <p className="mt-1 text-muted-foreground">
            Local-first, evidence-based learning. Let's check your setup.
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>System status</CardTitle>
            <CardDescription>
              ScholarAI runs entirely on your machine. Everything below should be
              green before you start learning.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading && (
              <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Checking backend…
              </div>
            )}

            {error && (
              <div className="py-6 text-sm text-amber-600">
                Could not reach the backend ({error}). Is it running on port 8000?
              </div>
            )}

            {health && (
              <div className="divide-y">
                <StatusRow label="Backend API" ok detail={`v${health.version}`} />
                <StatusRow
                  label="Ollama"
                  ok={health.ollama.reachable}
                  detail={
                    health.ollama.reachable ? "connected" : "not running — start Ollama"
                  }
                />
                <StatusRow
                  label={`Model (${health.ollama.configured_model})`}
                  ok={health.ollama.model_pulled}
                  detail={
                    health.ollama.model_pulled
                      ? "ready"
                      : `run: ollama pull ${health.ollama.configured_model}`
                  }
                />
                <StatusRow
                  label="Embeddings"
                  ok={health.embeddings.dependency_installed}
                  detail={
                    health.embeddings.dependency_installed
                      ? health.embeddings.model
                      : 'install: pip install -e ".[ml]"'
                  }
                />
              </div>
            )}

            <div className="mt-6">
              <Button onClick={refresh} variant="outline" size="sm" disabled={loading}>
                {loading ? "Checking…" : "Re-check"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Phase 0 skeleton · learning spaces, documents & chat coming next.
        </p>
      </div>
    </div>
  );
}
