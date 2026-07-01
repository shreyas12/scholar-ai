import {
  Brain,
  ChevronDown,
  ChevronRight,
  GitBranch,
  GraduationCap,
  Loader2,
  Sparkles,
  Target,
} from "lucide-react";
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
  type ConceptMastery,
  type Coverage,
  type MasteryReport,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "@/lib/toast";

export function DashboardTab({
  spaceId,
  onStudyConcept,
}: {
  spaceId: string;
  onStudyConcept: (conceptId: string) => void;
}) {
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
      toast.success("Concepts extracted");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Extraction failed";
      setError(msg);
      toast.error(msg);
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
        <MasterySection report={mastery} onStudy={onStudyConcept} />
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
          <p className="mb-2 text-sm text-muted-foreground">
            Every concept in this space — click one to quiz yourself on it.
          </p>
          <div className="flex flex-wrap gap-2">
            {concepts.map((c) => {
              const ready = graph?.nodes.find((n) => n.id === c.id)?.ready;
              return (
                <button
                  key={c.id}
                  onClick={() => onStudyConcept(c.id)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors hover:brightness-95",
                    c.encountered
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : ready
                        ? "border-blue-200 bg-blue-50 text-blue-700"
                        : "bg-background text-muted-foreground"
                  )}
                  title={
                    ready && !c.encountered
                      ? "Ready to learn — prerequisites covered. Click to quiz."
                      : "Click to quiz yourself on this concept"
                  }
                >
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      c.encountered ? "bg-emerald-500" : ready ? "bg-blue-500" : "bg-muted-foreground/40"
                    )}
                  />
                  {c.label}
                </button>
              );
            })}
          </div>

          {graph && graph.edges.length > 0 && <Prerequisites graph={graph} />}
        </>
      )}
    </div>
  );
}

const BUCKET_STYLE: Record<string, { bar: string; text: string; chip: string; label: string }> = {
  mastered: { bar: "bg-emerald-500", text: "text-emerald-700", chip: "bg-emerald-50 text-emerald-700", label: "Mastered" },
  learning: { bar: "bg-blue-500", text: "text-blue-700", chip: "bg-blue-50 text-blue-700", label: "Learning" },
  weak: { bar: "bg-amber-500", text: "text-amber-700", chip: "bg-amber-50 text-amber-700", label: "Weak" },
  unknown: { bar: "bg-muted-foreground/40", text: "text-muted-foreground", chip: "bg-muted text-muted-foreground", label: "Untested" },
};

function fmtDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function MasterySection({
  report,
  onStudy,
}: {
  report: MasteryReport;
  onStudy: (conceptId: string) => void;
}) {
  const { summary } = report;
  const assessed = report.concepts.filter((c) => c.mastery !== null);
  // Study targets: weakest first, plus anything due for review (SA-091).
  const targets = report.concepts
    .filter((c) => c.mastery !== null && (c.bucket === "weak" || c.bucket === "learning" || c.review_due))
    .slice(0, 5);

  return (
    <Card className="mb-4">
      <CardContent className="py-4">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium">Demonstrated mastery</span>
          <span className="text-sm text-muted-foreground">
            Mastered {summary.mastered} of {summary.total_concepts} concepts
            {summary.overall_mastery !== null && ` · ${summary.overall_mastery}% avg`}
          </span>
        </div>

        {/* Bucket counts (SA-090) */}
        <div className="mt-3 flex flex-wrap gap-2">
          {(["mastered", "learning", "weak", "unknown"] as const).map((b) => {
            const count =
              b === "mastered" ? summary.mastered
              : b === "learning" ? summary.learning
              : b === "weak" ? summary.weak
              : summary.unknown;
            return (
              <span
                key={b}
                className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", BUCKET_STYLE[b].chip)}
              >
                {count} {BUCKET_STYLE[b].label}
              </span>
            );
          })}
        </div>

        {/* Next study targets (SA-091) */}
        {targets.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
              <Target className="h-4 w-4" /> Next study targets
            </div>
            <div className="space-y-1.5">
              {targets.map((c) => (
                <div
                  key={c.concept_id}
                  className="flex items-center justify-between rounded-md border bg-background px-3 py-1.5 text-sm"
                >
                  <span className="flex items-center gap-1.5">
                    {c.label}
                    <span className={cn("text-xs", BUCKET_STYLE[c.bucket].text)}>
                      {c.review_due ? "due for review" : `${BUCKET_STYLE[c.bucket].label.toLowerCase()} · ${Math.round(c.mastery ?? 0)}%`}
                    </span>
                  </span>
                  <Button size="sm" variant="outline" onClick={() => onStudy(c.concept_id)}>
                    <GraduationCap className="h-3.5 w-3.5" /> Quiz
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Per-concept mastery, expandable to the full breakdown (SA-092/094) */}
        <div className="mt-4 space-y-2.5">
          {assessed.map((c) => (
            <ConceptRow key={c.concept_id} c={c} onStudy={onStudy} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ConceptRow({
  c,
  onStudy,
}: {
  c: ConceptMastery;
  onStudy: (conceptId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const style = BUCKET_STYLE[c.bucket];
  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left"
        aria-expanded={open}
      >
        <div className="mb-1 flex items-center justify-between text-sm">
          <span className="flex items-center gap-1.5">
            {open ? (
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            {c.label}
            {c.misconceptions > 0 && (
              <span
                className="rounded-full bg-amber-100 px-1.5 text-xs text-amber-700"
                title="Confident but incorrect — a flagged misconception"
              >
                ⚠ {c.misconceptions}
              </span>
            )}
            {c.review_due && (
              <span
                className="rounded-full bg-blue-100 px-1.5 text-xs text-blue-700"
                title={
                  c.retention !== null
                    ? `Retention ~${Math.round(c.retention * 100)}% — time to review`
                    : "Time to review"
                }
              >
                ↻ review
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
      </button>

      {open && <ConceptDetail c={c} onStudy={onStudy} />}
    </div>
  );
}

function ConceptDetail({
  c,
  onStudy,
}: {
  c: ConceptMastery;
  onStudy: (conceptId: string) => void;
}) {
  const signals: [string, number | null][] = [
    ["Recall", c.recall],
    ["Recognition", c.recognition],
    ["Application", c.application],
  ];
  const lastCorrect = fmtDate(c.last_correct);
  const nextReview = fmtDate(c.next_review);

  return (
    <div className="mt-2 rounded-md border bg-muted/30 px-3 py-3 text-xs">
      <div className="grid grid-cols-3 gap-y-2">
        {signals.map(([label, v]) => (
          <div key={label}>
            <div className="text-muted-foreground">{label}</div>
            <div className="font-medium">{v === null ? "—" : `${Math.round(v)}%`}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-y-2 border-t pt-3">
        <Stat label="Evidence" value={`${c.evidence_count}`} />
        <Stat label="Misconceptions" value={`${c.misconceptions}`} />
        <Stat
          label="Retention"
          value={c.retention !== null ? `${Math.round(c.retention * 100)}%` : "—"}
        />
        <Stat
          label="Avg confidence"
          value={c.avg_confidence !== null ? `${c.avg_confidence}/5` : "—"}
        />
        <Stat
          label="Avg grounding"
          value={c.avg_retrieval_confidence !== null ? `${Math.round(c.avg_retrieval_confidence * 100)}%` : "—"}
        />
        <Stat label="Demonstrated" value={c.demonstrated !== null ? `${Math.round(c.demonstrated)}%` : "—"} />
        <Stat label="Last correct" value={lastCorrect ?? "—"} />
        <Stat label="Review by" value={nextReview ?? "—"} />
      </div>

      <div className="mt-3 flex justify-end">
        <Button size="sm" variant="outline" onClick={() => onStudy(c.concept_id)}>
          <GraduationCap className="h-3.5 w-3.5" /> Quiz this concept
        </Button>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
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
