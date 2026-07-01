import { Brain, CheckCircle2, Loader2, XCircle, AlertTriangle, GraduationCap } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  generateQuiz,
  listConcepts,
  submitAnswer,
  type AnswerFeedback,
  type Concept,
  type Quiz,
  type QuizQuestion,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<QuizQuestion["type"], string> = {
  recall: "Recall",
  recognition: "Recognition",
  application: "Application",
};

export function QuizTab({
  spaceId,
  initialConceptId = null,
}: {
  spaceId: string;
  initialConceptId?: string | null;
}) {
  const [concepts, setConcepts] = useState<Concept[] | null>(null);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoStarted = useRef(false);

  useEffect(() => {
    listConcepts(spaceId)
      .then(setConcepts)
      .catch((e) => setError(e.message));
  }, [spaceId]);

  async function startQuiz(conceptId: string) {
    setLoading(true);
    setError(null);
    try {
      setQuiz(await generateQuiz(spaceId, conceptId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate quiz");
    } finally {
      setLoading(false);
    }
  }

  // Auto-start when the dashboard sent us here to study a specific concept
  // (SA-091). Runs once; manual tab visits clear initialConceptId upstream.
  useEffect(() => {
    if (initialConceptId && !autoStarted.current) {
      autoStarted.current = true;
      startQuiz(initialConceptId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialConceptId]);

  if (quiz) {
    return (
      <QuizRunner
        spaceId={spaceId}
        quiz={quiz}
        onExit={() => setQuiz(null)}
      />
    );
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Generating your quiz…
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <h3 className="font-semibold">Quiz yourself</h3>
        <p className="text-sm text-muted-foreground">
          Pick a concept. We generate recall, recognition, and application
          questions from your material — your answers become mastery evidence.
        </p>
      </div>

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

      {concepts === null ? (
        <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading concepts…
        </div>
      ) : concepts.length === 0 ? (
        <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">
          <Brain className="mx-auto mb-2 h-8 w-8" />
          <p className="font-medium">No concepts yet</p>
          <p>Upload documents and extract concepts (Dashboard tab) first.</p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {concepts.map((c) => (
            <Button
              key={c.id}
              variant="outline"
              size="sm"
              disabled={loading}
              onClick={() => startQuiz(c.id)}
            >
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GraduationCap className="h-3.5 w-3.5" />}
              {c.label}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

function QuizRunner({
  spaceId,
  quiz,
  onExit,
}: {
  spaceId: string;
  quiz: Quiz;
  onExit: () => void;
}) {
  const [index, setIndex] = useState(0);
  const total = quiz.questions.length;
  const question = quiz.questions[index];
  const done = index >= total;

  if (done) {
    return (
      <div className="text-center">
        <CheckCircle2 className="mx-auto mb-2 h-10 w-10 text-emerald-500" />
        <h3 className="font-semibold">Quiz complete</h3>
        <p className="mb-4 text-sm text-muted-foreground">
          Your answers were recorded as evidence for{" "}
          <span className="font-medium">{quiz.concept_label}</span>. Check the
          Dashboard to see mastery update.
        </p>
        <Button variant="outline" size="sm" onClick={onExit}>
          Back to concepts
        </Button>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {quiz.concept_label} · {TYPE_LABEL[question.type]}
          </span>
          <div className="mt-1 text-sm text-muted-foreground">
            Question {index + 1} of {total}
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={onExit}>
          Exit
        </Button>
      </div>

      <QuestionCard
        key={question.id}
        spaceId={spaceId}
        quizId={quiz.quiz_id}
        question={question}
        onNext={() => setIndex((i) => i + 1)}
        isLast={index === total - 1}
      />
    </div>
  );
}

const CONFIDENCE_LABELS = ["Guessing", "Unsure", "Okay", "Confident", "Certain"];

function QuestionCard({
  spaceId,
  quizId,
  question,
  onNext,
  isLast,
}: {
  spaceId: string;
  quizId: string;
  question: QuizQuestion;
  onNext: () => void;
  isLast: boolean;
}) {
  const [answer, setAnswer] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [confidence, setConfidence] = useState(3);
  const [feedback, setFeedback] = useState<AnswerFeedback | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMcq = question.type === "recognition";
  const canSubmit = isMcq ? selected !== null : answer.trim().length > 0;

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const fb = await submitAnswer(spaceId, quizId, {
        question_id: question.id,
        answer: isMcq ? "" : answer,
        selected_index: isMcq ? selected : null,
        confidence,
      });
      setFeedback(fb);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Grading failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-4 py-5">
        <p className="font-medium">{question.question}</p>

        {isMcq ? (
          <div className="space-y-2">
            {question.options?.map((opt, i) => {
              const isCorrect = feedback && feedback.correct_answer === opt;
              const isChosen = selected === i;
              return (
                <button
                  key={i}
                  disabled={!!feedback}
                  onClick={() => setSelected(i)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                    feedback
                      ? isCorrect
                        ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                        : isChosen
                          ? "border-red-300 bg-red-50 text-red-800"
                          : "opacity-60"
                      : isChosen
                        ? "border-primary bg-secondary"
                        : "hover:bg-secondary"
                  )}
                >
                  <span className="font-mono text-xs text-muted-foreground">
                    {String.fromCharCode(65 + i)}
                  </span>
                  {opt}
                </button>
              );
            })}
          </div>
        ) : (
          <textarea
            value={answer}
            disabled={!!feedback}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Explain in your own words…"
            rows={4}
            className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-70"
          />
        )}

        {!feedback && (
          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
              <span>How confident are you?</span>
              <span className="font-medium text-foreground">
                {CONFIDENCE_LABELS[confidence - 1]}
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={5}
              value={confidence}
              onChange={(e) => setConfidence(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {feedback ? (
          <Feedback feedback={feedback} onNext={onNext} isLast={isLast} />
        ) : (
          <Button onClick={handleSubmit} disabled={!canSubmit || submitting} size="sm">
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Submit answer
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function Feedback({
  feedback,
  onNext,
  isLast,
}: {
  feedback: AnswerFeedback;
  onNext: () => void;
  isLast: boolean;
}) {
  return (
    <div className="space-y-3 border-t pt-3">
      <div className="flex items-center gap-2">
        {feedback.correct ? (
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
        ) : (
          <XCircle className="h-5 w-5 text-red-500" />
        )}
        <span className="font-medium">
          {feedback.correct ? "Correct" : "Not quite"}
        </span>
        <span className="ml-auto text-sm text-muted-foreground">
          Score {feedback.score}/100
        </span>
      </div>

      <p className="text-sm text-muted-foreground">{feedback.reasoning}</p>

      {feedback.correct_answer && !feedback.correct && (
        <p className="text-sm">
          <span className="text-muted-foreground">Expected: </span>
          {feedback.correct_answer}
        </p>
      )}

      {feedback.misconception_flag && feedback.misconception && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <span className="font-medium">Misconception flagged: </span>
            {feedback.misconception} — you were confident but incorrect, so this
            is worth revisiting.
          </span>
        </div>
      )}

      <Button onClick={onNext} size="sm">
        {isLast ? "Finish" : "Next question"}
      </Button>
    </div>
  );
}
