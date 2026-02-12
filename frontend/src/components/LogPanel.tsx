import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { useLogStream, type LogEntry } from "@/hooks/useLogStream";

const LEVEL_STYLE: Record<string, string> = {
  DEBUG: "text-muted-foreground/60",
  INFO: "text-neon-cyan",
  WARNING: "text-neon-amber",
  ERROR: "text-neon-rose",
  CRITICAL: "text-neon-rose font-bold",
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour12: false, fractionalSecondDigits: 3 } as Intl.DateTimeFormatOptions);
  } catch {
    return iso;
  }
}

export function LogPanel() {
  const { entries, connected, clear } = useLogStream();
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const filtered = filter
    ? entries.filter((e) => e.level === filter)
    : entries;

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [filtered.length, autoScroll]);

  return (
    <Card className="glass-panel flex h-full flex-col border-border/30">
      <CardHeader className="pb-2 pt-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                connected
                  ? "bg-neon-emerald animate-glow-pulse"
                  : "bg-muted-foreground/40"
              }`}
            />
            <span className="bg-gradient-to-r from-neon-amber to-neon-rose bg-clip-text text-transparent">
              Logs
            </span>
          </CardTitle>
          <div className="flex items-center gap-1.5">
            {["INFO", "WARNING", "ERROR"].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setFilter(filter === lvl ? null : lvl)}
                className={`rounded px-1.5 py-0.5 text-[9px] font-medium transition-all ${
                  filter === lvl
                    ? "bg-neon-cyan/20 text-neon-cyan"
                    : "text-muted-foreground/50 hover:text-muted-foreground"
                }`}
              >
                {lvl}
              </button>
            ))}
            <button
              onClick={() => setAutoScroll((v) => !v)}
              className={`rounded px-1.5 py-0.5 text-[9px] font-medium transition-all ${
                autoScroll
                  ? "bg-neon-emerald/20 text-neon-emerald"
                  : "text-muted-foreground/50 hover:text-muted-foreground"
              }`}
              title="Auto-scroll"
            >
              {"\u{2193}"}
            </button>
            <button
              onClick={clear}
              className="rounded px-1.5 py-0.5 text-[9px] font-medium text-muted-foreground/50 hover:text-neon-rose transition-colors"
              title="Clear logs"
            >
              Clear
            </button>
            <Badge
              variant="outline"
              className={`text-[9px] px-1.5 py-0 ${
                connected
                  ? "border-neon-emerald/30 text-neon-emerald"
                  : "border-neon-rose/30 text-neon-rose"
              }`}
            >
              {connected ? "Live" : "Disconnected"}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden pt-0">
        <ScrollArea className="h-full">
          <div className="font-mono text-[11px] leading-5 space-y-px p-1">
            {filtered.length === 0 && (
              <p className="text-muted-foreground/30 italic text-xs py-6 text-center">
                {connected
                  ? "No log entries yet"
                  : "Connecting to log stream..."}
              </p>
            )}
            {filtered.map((entry, i) => (
              <LogLine key={i} entry={entry} />
            ))}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const levelCls = LEVEL_STYLE[entry.level] ?? "text-foreground";
  const hasTrace = !!entry.traceback;

  return (
    <div>
      <div
        className={`flex gap-2 py-0.5 rounded px-1 transition-colors group ${
          hasTrace
            ? "cursor-pointer hover:bg-neon-rose/[0.06]"
            : "hover:bg-neon-cyan/[0.03]"
        }`}
        onClick={hasTrace ? () => setExpanded((v) => !v) : undefined}
      >
        <span className="text-muted-foreground/30 shrink-0 w-[72px]">
          {formatTime(entry.ts)}
        </span>
        <span className={`shrink-0 w-[52px] font-semibold ${levelCls}`}>
          {entry.level}
        </span>
        <span className="text-neon-purple/50 shrink-0 max-w-[120px] truncate">
          {entry.logger}
        </span>
        <span className="text-foreground/80 break-all flex-1">
          {entry.message}
          {hasTrace && !expanded && (
            <span className="ml-1 text-neon-rose/40 text-[9px]">[+trace]</span>
          )}
        </span>
      </div>
      {expanded && entry.traceback && (
        <pre className="ml-[128px] text-[10px] leading-4 text-neon-rose/70 bg-neon-rose/[0.04] rounded p-2 my-0.5 whitespace-pre-wrap border border-neon-rose/10">
          {entry.traceback}
        </pre>
      )}
    </div>
  );
}
