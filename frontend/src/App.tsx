import { AlertTriangle, CheckCircle2, GraduationCap } from "lucide-react";
import { useEffect, useState } from "react";

import { SetupBanner } from "@/components/SetupBanner";
import { SpaceDetail } from "@/components/SpaceDetail";
import { SpacesList } from "@/components/SpacesList";
import { Toaster } from "@/components/Toaster";
import { getHealth, type HealthStatus, type Space } from "@/lib/api";

function HealthPill({ health }: { health: HealthStatus | null }) {
  if (!health) return null;
  const ready = health.ollama.reachable && health.ollama.model_pulled;

  return (
    <div
      className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground"
      title={
        ready
          ? "Ollama connected and model ready"
          : "Chat needs Ollama running with the model pulled"
      }
    >
      {ready ? (
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
      ) : (
        <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
      )}
      {ready ? "Ready" : "Setup incomplete"}
    </div>
  );
}

export default function App() {
  const [openSpace, setOpenSpace] = useState<Space | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5" />
            <span className="font-semibold">ScholarAI</span>
          </div>
          <HealthPill health={health} />
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-10">
        {health && !openSpace && <SetupBanner health={health} />}
        {openSpace ? (
          <SpaceDetail space={openSpace} onBack={() => setOpenSpace(null)} />
        ) : (
          <SpacesList onOpen={setOpenSpace} />
        )}
      </main>

      <Toaster />
    </div>
  );
}
