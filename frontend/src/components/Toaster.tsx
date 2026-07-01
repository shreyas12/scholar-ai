import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import { dismiss, subscribe, type Toast } from "@/lib/toast";

const STYLE: Record<Toast["kind"], { border: string; icon: typeof Info }> = {
  error: { border: "border-l-red-500", icon: AlertCircle },
  success: { border: "border-l-emerald-500", icon: CheckCircle2 },
  info: { border: "border-l-blue-500", icon: Info },
};

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  useEffect(() => subscribe(setToasts), []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((t) => {
        const { border, icon: Icon } = STYLE[t.kind];
        return (
          <div
            key={t.id}
            role="status"
            className={cn(
              "flex items-start gap-2 rounded-md border border-l-4 bg-background px-3 py-2.5 text-sm shadow-md",
              border
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="flex-1">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="text-muted-foreground hover:text-foreground"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
