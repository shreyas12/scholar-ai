import { Brain, GitBranch, Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  extractConcepts,
  getConceptGraph,
  getCoverage,
  getMastery,
  listConcepts,
  type Concept,
  type ConceptGraph,
  type Coverage,
  type MasteryReport,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export function DashboardTab({ spaceId }: { spaceId: string }) {
  const [concepts, setConcepts] = useState<Concept[] | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [graph, setGraph] = useState<ConceptGraph | null>(null);
  const [mastery, setMastery] = useState<MasteryReport | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [c, cov, g, m] = await Promise.all([
      listConcepts(spaceId),
      getCoverage(spaceId),
      getConceptGraph(spaceId),
      getMastery(spaceId),
    ]);
    setConcepts(c);
    setCoverage(cov);
    setGraph(g);
    setMastery(m);
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
              Coverage means encountered — not yet mastered. Take a quiz to turn
              coverage into demonstrated mastery.
            </p>
          </CardContent>
        </Card>
      )}

      {mastery && mastery.summary.assessed > 0 && (
        <MasterySection report={mastery} />
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
        <>
          <div className="flex flex-wrap gap-2">
            {concepts.map((c) => {
              const ready = graph?.nodes.find((n) => n.id === c.id)?.ready;
              return (
                <span
                  key={c.id}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm",
                    c.encountered
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : ready
                        ? "border-blue-200 bg-blue-50 text-blue-700"
                        : "bg-background text-muted-foreground"
                  )}
                  title={
                    ready && !c.encountered
                      ? "Ready to learn — prerequisites covered"
                      : `${c.source_chunk_count} source section${c.source_chunk_count === 1 ? "" : "s"}`
                  }
                >
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      c.encountered ? "bg-emerald-500" : ready ? "bg-blue-500" : "bg-muted-foreground/40"
                    )}
                  />
                  {c.label}
                </span>
              );
            })}
          </div>

          {graph && graph.edges.length > 0 && <Prerequisites graph={graph} />}
        </>
      )}
    </div>
  );
}

const BUCKET_STYLE: Record<string, { bar: string; text: string; label: string }> = {
  mastered: { bar: "bg-emerald-500", text: "text-emerald-700", label: "Mastered" },
  learning: { bar: "bg-blue-500", text: "text-blue-700", label: "Learning" },
  weak: { bar: "bg-amber-500", text: "text-amber-700", label: "Weak" },
  unknown: { bar: "bg-muted-foreground/40", text: "text-muted-foreground", label: "Untested" },
};

function MasterySection({ report }: { report: MasteryReport }) {
  const assessed = report.concepts.filter((c) => c.mastery !== null);
  return (
    <Card className="mb-4">
      <CardContent className="py-4">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium">Demonstrated mastery</span>
          {report.summary.overall_mastery !== null && (
            <span className="text-sm text-muted-foreground">
              {report.summary.overall_mastery}% overall ·{" "}
              {report.summary.assessed} of {report.summary.total_concepts} assessed
            </span>
          )}
        </div>

        <div className="mt-3 space-y-2.5">
          {assessed.map((c) => {
            const style = BUCKET_STYLE[c.bucket];
            return (
              <div key={c.concept_id}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="flex items-center gap-1.5">
                    {c.label}
                    {c.misconceptions > 0 && (
                      <span
                        className="rounded-full bg-amber-100 px-1.5 text-xs text-amber-700"
                        title="Confident but incorrect — a flagged misconception"
                      >
                        ⚠ {c.misconceptions}
                      </span>
                    )}
                  </span>
                  <span className={cn("text-xs font-medium", style.text)}>
                    {style.label} · {Math.round(c.mastery ?? 0)}%
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full transition-all", style.bar)}
                    style={{ width: `${c.mastery ?? 0}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function Prerequisites({ graph }: { graph: ConceptGraph }) {
  const label = (id: string) => graph.nodes.find((n) => n.id === id)?.label ?? id;
  // group prerequisites by the dependent concept
  const byTarget = new Map<string, string[]>();
  for (const e of graph.edges) {
    byTarget.set(e.target, [...(byTarget.get(e.target) ?? []), label(e.source)]);
  }
  return (
    <div className="mt-6">
      <div className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <GitBranch className="h-4 w-4" /> Prerequisites
      </div>
      <ul className="space-y-1 text-sm">
        {[...byTarget.entries()].map(([target, prereqs]) => (
          <li key={target}>
            <span className="font-medium">{label(target)}</span>
            <span className="text-muted-foreground"> needs </span>
            {prereqs.join(", ")}
          </li>
        ))}
      </ul>
    </div>
  );
}
