import { FileText, Loader2, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  deleteDocument,
  listDocuments,
  uploadDocument,
  type Document,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.md,.markdown,.txt,.docx";

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentsTab({
  spaceId,
  onCountChange,
}: {
  spaceId: string;
  onCountChange?: (n: number) => void;
}) {
  const [docs, setDocs] = useState<Document[] | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    const list = await listDocuments(spaceId);
    setDocs(list);
    onCountChange?.(list.length);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spaceId]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setError(null);
    for (const file of Array.from(files)) {
      setUploading((u) => [...u, file.name]);
      try {
        await uploadDocument(spaceId, file);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : `Failed to upload ${file.name}`);
      } finally {
        setUploading((u) => u.filter((n) => n !== file.name));
      }
    }
  }

  async function handleDelete(doc: Document) {
    if (!confirm(`Remove "${doc.name}" from this space?`)) return;
    await deleteDocument(spaceId, doc.doc_id);
    refresh();
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed py-10 text-center transition-colors",
          dragging ? "border-primary bg-primary/5" : "border-muted-foreground/25"
        )}
      >
        <Upload className="h-6 w-6 text-muted-foreground" />
        <p className="text-sm font-medium">Drop files here, or</p>
        <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
          Browse
        </Button>
        <p className="text-xs text-muted-foreground">PDF, Markdown, TXT, DOCX</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

      {uploading.map((name) => (
        <div
          key={name}
          className="mt-3 flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground"
        >
          <Loader2 className="h-4 w-4 animate-spin" /> Ingesting {name}…
        </div>
      ))}

      <div className="mt-6">
        {docs === null ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : docs.length === 0 && uploading.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No documents yet. Upload notes to make them searchable.
          </p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {docs.map((doc) => (
              <li key={doc.doc_id} className="flex items-center gap-3 px-4 py-3">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.ext.replace(".", "").toUpperCase()} · {fmtSize(doc.size)} ·{" "}
                    {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => handleDelete(doc)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
