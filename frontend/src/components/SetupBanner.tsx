import { AlertTriangle, Terminal } from "lucide-react";

import type { HealthStatus } from "@/lib/api";

/** A blocking-issue with a copy-pasteable fix. */
interface Issue {
  title: string;
  detail: string;
  commands: string[];
}

function issuesFor(health: HealthStatus): Issue[] {
  const issues: Issue[] = [];
  if (!health.embeddings.dependency_installed) {
    issues.push({
      title: "Embedding dependencies aren't installed",
      detail: "Document ingestion and retrieval need the ML extras.",
      commands: ['cd backend && pip install -e ".[ml]"'],
    });
  }
  if (!health.ollama.reachable) {
    issues.push({
      title: "Ollama isn't running",
      detail: `Chat, quizzes, and concept extraction call a local model at ${health.ollama.base_url}.`,
      commands: ["# install from https://ollama.com, then:", "ollama serve"],
    });
  } else if (!health.ollama.model_pulled) {
    issues.push({
      title: `The model “${health.ollama.configured_model}” isn't pulled yet`,
      detail: "Pull it once; it then runs fully offline.",
      commands: [`ollama pull ${health.ollama.configured_model}`],
    });
  }
  return issues;
}

export function SetupBanner({ health }: { health: HealthStatus }) {
  const issues = issuesFor(health);
  if (issues.length === 0) return null;

  return (
    <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-center gap-2 font-medium text-amber-800">
        <AlertTriangle className="h-4 w-4" />
        Setup incomplete — you can browse spaces, but the AI features are offline
      </div>
      <div className="mt-3 space-y-3">
        {issues.map((issue) => (
          <div key={issue.title} className="text-sm">
            <p className="font-medium text-amber-900">{issue.title}</p>
            <p className="text-amber-800">{issue.detail}</p>
            <pre className="mt-1.5 overflow-x-auto rounded-md bg-amber-900/90 px-3 py-2 text-xs text-amber-50">
              <code className="flex flex-col gap-0.5">
                {issue.commands.map((cmd, i) => (
                  <span key={i} className="flex items-center gap-1.5">
                    <Terminal className="h-3 w-3 shrink-0 opacity-60" />
                    {cmd}
                  </span>
                ))}
              </code>
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
