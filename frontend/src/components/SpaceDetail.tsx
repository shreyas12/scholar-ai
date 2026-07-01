import { ArrowLeft, FileText, MessageSquare, BarChart3 } from "lucide-react";
import { useState } from "react";

import { ChatTab } from "@/components/ChatTab";
import { DashboardTab } from "@/components/DashboardTab";
import { DocumentsTab } from "@/components/DocumentsTab";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Space } from "@/lib/api";

type Tab = "documents" | "chat" | "dashboard";

const TABS: { key: Tab; label: string; icon: typeof FileText }[] = [
  { key: "documents", label: "Documents", icon: FileText },
  { key: "chat", label: "Chat", icon: MessageSquare },
  { key: "dashboard", label: "Dashboard", icon: BarChart3 },
];

export function SpaceDetail({ space, onBack }: { space: Space; onBack: () => void }) {
  const [tab, setTab] = useState<Tab>("documents");
  const [docCount, setDocCount] = useState(space.document_count);

  return (
    <div>
      <Button variant="ghost" size="sm" onClick={onBack} className="mb-4 -ml-2">
        <ArrowLeft className="h-4 w-4" /> All spaces
      </Button>

      <h2 className="text-2xl font-bold tracking-tight">{space.name}</h2>
      <p className="text-sm text-muted-foreground">
        {docCount} document{docCount === 1 ? "" : "s"}
      </p>

      <div className="mt-6 flex gap-1 border-b">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              "flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              tab === key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === "documents" && (
          <DocumentsTab spaceId={space.id} onCountChange={setDocCount} />
        )}
        {tab === "chat" && <ChatTab spaceId={space.id} />}
        {tab === "dashboard" && <DashboardTab spaceId={space.id} />}
      </div>
    </div>
  );
}
