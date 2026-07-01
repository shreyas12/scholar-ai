import { AlertTriangle, FileText, Gauge, Loader2, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getChatHistory,
  streamChat,
  type ChatMessage,
  type Confidence,
  type Source,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function ConfidenceBadge({ c }: { c: Confidence }) {
  const tone =
    c.confidence >= 70
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : c.confidence >= 40
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-red-200 bg-red-50 text-red-700";
  return (
    <div
      className={cn(
        "mt-2 inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs",
        tone
      )}
      title={c.reason}
    >
      <Gauge className="h-3 w-3" />
      {c.confidence}% grounded · {c.relevant_chunks} relevant · avg sim{" "}
      {c.avg_similarity.toFixed(2)}
    </div>
  );
}

function SourceChips({ sources }: { sources: Source[] }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {sources.map((s) => (
        <span
          key={s.chunk_id}
          className="inline-flex items-center gap-1 rounded-full border bg-background px-2 py-0.5 text-xs text-muted-foreground"
          title={`similarity ${s.score}`}
        >
          <FileText className="h-3 w-3" />
          {s.document}
          {s.page ? `, p.${s.page}` : ""}
        </span>
      ))}
    </div>
  );
}

function Bubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-4 py-2.5 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "border bg-background"
        )}
      >
        <p className="whitespace-pre-wrap">{msg.content || "…"}</p>
        {!isUser && msg.confidence && <ConfidenceBadge c={msg.confidence} />}
        {!isUser && msg.sources && <SourceChips sources={msg.sources} />}
      </div>
    </div>
  );
}

export function ChatTab({ spaceId }: { spaceId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatHistory(spaceId).then(setMessages).catch(() => {});
  }, [spaceId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setError(null);
    setBusy(true);

    setMessages((m) => [
      ...m,
      { role: "user", content: question },
      { role: "assistant", content: "", sources: [] },
    ]);

    const patchAssistant = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((msgs) => {
        const copy = [...msgs];
        copy[copy.length - 1] = fn(copy[copy.length - 1]);
        return copy;
      });

    await streamChat(spaceId, question, {
      onSources: (sources) => patchAssistant((m) => ({ ...m, sources })),
      onConfidence: (confidence) => patchAssistant((m) => ({ ...m, confidence })),
      onToken: (text) => patchAssistant((m) => ({ ...m, content: m.content + text })),
      onError: (message) => setError(message),
      onDone: () => {},
    });
    setBusy(false);
  }

  return (
    <div className="flex h-[60vh] flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted-foreground">
            <p className="font-medium">Ask anything about your notes</p>
            <p>Answers are grounded in this space's documents, with citations.</p>
          </div>
        ) : (
          messages.map((m, i) => <Bubble key={i} msg={m} />)
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <div className="mt-2 flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <div className="mt-3 flex gap-2">
        <Input
          value={input}
          placeholder="What is HNSW?"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={busy}
        />
        <Button onClick={send} disabled={busy || !input.trim()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
