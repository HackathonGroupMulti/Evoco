import { Badge } from "@/components/ui/badge";
import type { ConnectionState } from "@/hooks/useTaskRunner";

interface StatusBarProps {
  connectionState: ConnectionState;
  stepsTotal: number;
  stepsCompleted: number;
  durationMs?: number;
  costUsd?: number;
  mode: "live" | "mock" | "unknown";
}

const STATE_CONFIG: Record<ConnectionState, { label: string; color: string; glow: string }> = {
  idle: { label: "Dormant", color: "bg-muted-foreground/40", glow: "" },
  connecting: {
    label: "Awakening...",
    color: "bg-neon-amber",
    glow: "shadow-[0_0_6px_var(--neon-amber)]",
  },
  running: {
    label: "Thinking",
    color: "bg-neon-cyan animate-pulse",
    glow: "shadow-[0_0_6px_var(--neon-cyan)]",
  },
  done: {
    label: "Complete",
    color: "bg-neon-emerald",
    glow: "shadow-[0_0_6px_var(--neon-emerald)]",
  },
  error: {
    label: "Disrupted",
    color: "bg-neon-rose",
    glow: "shadow-[0_0_6px_var(--neon-rose)]",
  },
};

export function StatusBar({
  connectionState,
  stepsTotal,
  stepsCompleted,
  durationMs,
  costUsd,
  mode,
}: StatusBarProps) {
  const state = STATE_CONFIG[connectionState];

  return (
    <div className="relative flex h-8 shrink-0 items-center gap-4 border-t border-border/30 px-4 text-xs text-muted-foreground">
      {/* Subtle top gradient line */}
      <div className="absolute top-0 left-0 h-px w-full bg-gradient-to-r from-transparent via-neon-purple/30 to-transparent" />

      <span className="flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${state.color} ${state.glow}`} />
        <span>{state.label}</span>
      </span>

      {stepsTotal > 0 && (
        <>
          <span className="text-border/50">{"\u{2502}"}</span>
          <span>
            Pathways:{" "}
            <span className="text-neon-cyan font-medium">{stepsCompleted}</span>
            <span className="text-muted-foreground/40">/{stepsTotal}</span>
          </span>
          {/* Mini progress bar */}
          <div className="h-1 w-16 rounded-full bg-secondary/50 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-neon-cyan to-neon-emerald transition-all duration-500"
              style={{
                width: `${stepsTotal > 0 ? (stepsCompleted / stepsTotal) * 100 : 0}%`,
              }}
            />
          </div>
        </>
      )}

      {durationMs != null && (
        <>
          <span className="text-border/50">{"\u{2502}"}</span>
          <span className="text-neon-emerald/70">{(durationMs / 1000).toFixed(1)}s</span>
        </>
      )}

      {costUsd != null && costUsd > 0 && (
        <>
          <span className="text-border/50">{"\u{2502}"}</span>
          <span className="text-neon-amber/70">${costUsd.toFixed(4)}</span>
        </>
      )}

      <span className="ml-auto">
        <Badge
          variant="outline"
          className={`text-[10px] px-1.5 py-0 ${
            mode === "live"
              ? "border-neon-emerald/30 text-neon-emerald"
              : mode === "mock"
                ? "border-neon-amber/30 text-neon-amber"
                : "border-border text-muted-foreground"
          }`}
        >
          {mode === "live" ? "Awake" : mode === "mock" ? "Dreaming" : "\u{2014}"}
        </Badge>
      </span>
    </div>
  );
}
