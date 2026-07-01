import { Brain, Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  extractConcepts,
  getCoverage,
  listConcepts,
  type Concept,
  type Coverage,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export function DashboardTab({ spaceId }: { spaceId: string }) {
  const [concepts, setConcepts] = useState<Concept[] | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [c, cov] = await Promise.all([listConcepts(spaceId), getCoverage(spaceId)]);
    setConcepts(c);
    setCoverage(cov);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spaceId]);

  async function handleExtract() {
    setExtracting(true);
    setError(null);
    try {
      await extractConcepts(spaceId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setExtracting(false);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="font-semibold">Concept mastery</h3>
          <p className="text-sm text-muted-foreground">
            We track understanding of concepts, not documents read.
          </p>
        </div>
        <Button onClick={handleExtract} disabled={extracting} variant="outline" size="sm">
          {extracting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {concepts && concepts.length > 0 ? "Re-extract concepts" : "Extract concepts"}
        </Button>
      </div>

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

      {coverage && coverage.total > 0 && (
        <Card className="mb-4">
          <CardContent className="py-4">
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-muted-foreground">Coverage</span>
              <span className="text-sm font-medium">
                {coverage.encountered} of {coverage.total} concepts encountered
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${coverage.coverage_pct}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Coverage means encountered — not yet mastered. Quizzes (coming next)
              turn coverage into real evidence.
            </p>
          </CardContent>
        </Card>
      )}

      {concepts === null ? (
        <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : concepts.length === 0 ? (
        <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">
          <Brain className="mx-auto mb-2 h-8 w-8" />
          <p className="font-medium">No concepts yet</p>
          <p>Upload documents, then extract concepts to map this subject.</p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {concepts.map((c) => (
            <span
              key={c.id}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm",
                c.encountered
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "bg-background text-muted-foreground"
              )}
              title={`${c.source_chunk_count} source chunk${
                c.source_chunk_count === 1 ? "" : "s"
              }`}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  c.encountered ? "bg-emerald-500" : "bg-muted-foreground/40"
                )}
              />
              {c.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
