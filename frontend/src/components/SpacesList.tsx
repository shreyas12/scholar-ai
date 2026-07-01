import { BookOpen, MoreVertical, Plus, Trash2, Pencil, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { SpaceFormDialog } from "@/components/SpaceFormDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  createSpace,
  deleteSpace,
  listSpaces,
  renameSpace,
  type Space,
} from "@/lib/api";

export function SpacesList({ onOpen }: { onOpen: (space: Space) => void }) {
  const [spaces, setSpaces] = useState<Space[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState<Space | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);

  async function refresh() {
    try {
      setSpaces(await listSpaces());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load spaces");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleDelete(space: Space) {
    if (!confirm(`Delete "${space.name}"? This removes its documents and index.`)) return;
    await deleteSpace(space.id);
    setMenuFor(null);
    refresh();
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Learning spaces</h2>
          <p className="text-sm text-muted-foreground">
            One space per subject. Each is fully isolated.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> New space
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {spaces === null ? (
        <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : spaces.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <BookOpen className="h-8 w-8 text-muted-foreground" />
            <div>
              <p className="font-medium">No learning spaces yet</p>
              <p className="text-sm text-muted-foreground">
                Create your first subject to start adding documents.
              </p>
            </div>
            <Button onClick={() => setCreating(true)} variant="outline">
              <Plus className="h-4 w-4" /> Create a space
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {spaces.map((space) => (
            <Card key={space.id} className="group relative transition-shadow hover:shadow-md">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="cursor-pointer" onClick={() => onOpen(space)}>
                    {space.name}
                  </CardTitle>
                  <div className="relative">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => setMenuFor(menuFor === space.id ? null : space.id)}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                    {menuFor === space.id && (
                      <div className="absolute right-0 z-10 mt-1 w-32 rounded-md border bg-background p-1 shadow-md">
                        <button
                          className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-secondary"
                          onClick={() => {
                            setRenaming(space);
                            setMenuFor(null);
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" /> Rename
                        </button>
                        <button
                          className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-destructive hover:bg-secondary"
                          onClick={() => handleDelete(space)}
                        >
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="cursor-pointer pt-0" onClick={() => onOpen(space)}>
                <p className="text-sm text-muted-foreground">
                  {space.document_count} document{space.document_count === 1 ? "" : "s"}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <SpaceFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="New learning space"
        description="Name the subject you want to study."
        submitLabel="Create"
        onSubmit={async (name) => {
          await createSpace(name);
          await refresh();
        }}
      />

      <SpaceFormDialog
        open={renaming !== null}
        onOpenChange={(o) => !o && setRenaming(null)}
        title="Rename space"
        initialName={renaming?.name}
        submitLabel="Save"
        onSubmit={async (name) => {
          if (renaming) await renameSpace(renaming.id, name);
          await refresh();
        }}
      />
    </div>
  );
}
