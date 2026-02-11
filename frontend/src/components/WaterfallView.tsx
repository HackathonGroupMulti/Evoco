import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { TaskTrace, TraceStep } from "@/types";

interface WaterfallViewProps {
  trace: TaskTrace;
}

const GROUP_COLORS: Record<string, string> = {
  amazon: "bg-neon-amber",
  bestbuy: "bg-neon-cyan",
  newegg: "bg-neon-emerald",
  walmart: "bg-neon-purple",
  ebay: "bg-neon-rose",
  google: "bg-neon-cyan",
  analysis: "bg-gradient-to-r from-neon-purple to-neon-cyan",
};

const STATUS_COLORS: Record<string, string> = {
  completed: "text-neon-emerald",
  failed: "text-neon-rose",
  skipped: "text-muted-foreground/40",
};

const ACTION_ICONS: Record<string, string> = {
  navigate: "\u{1F310}",
  search: "\u{1F50D}",
  extract: "\u{1F4E6}",
  compare: "\u{2696}",
  summarize: "\u{1F4CB}",
};

export function WaterfallView({ trace }: WaterfallViewProps) {
  const { totalMs, bars } = useMemo(() => {
    if (!trace.steps.length) return { totalMs: 0, bars: [] };

    // Find the earliest start and latest end to compute timeline bounds
    const stepsWithTime = trace.steps.filter((s) => s.started_at && s.duration_ms);
    if (stepsWithTime.length === 0) {
      // Fall back to sequential layout using durations
      let offset = trace.planning_ms;
      const total = trace.planning_ms + trace.execution_ms;
      const bars = trace.steps.map((step) => {
        const dur = step.duration_ms ?? 0;
        const bar = {
          step,
          startPct: (offset / total) * 100,
          widthPct: Math.max((dur / total) * 100, 1),
        };
        offset += dur;
        return bar;
      });
      return { totalMs: total, bars };
    }

    const starts = stepsWithTime.map((s) => new Date(s.started_at!).getTime());
    const ends = stepsWithTime.map((s) => new Date(s.started_at!).getTime() + (s.duration_ms ?? 0));
    const minStart = Math.min(...starts);
    const maxEnd = Math.max(...ends);
    const totalMs = maxEnd - minStart;

    const bars = trace.steps.map((step) => {
      if (!step.started_at || !step.duration_ms) {
        return { step, startPct: 0, widthPct: 0 };
      }
      const start = new Date(step.started_at).getTime() - minStart;
      return {
        step,
        startPct: (start / totalMs) * 100,
        widthPct: Math.max((step.duration_ms / totalMs) * 100, 1),
      };
    });

    return { totalMs, bars };
  }, [trace]);

  return (
    <Card className="glass-panel flex h-full flex-col border-border/30 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-neon-purple animate-glow-pulse" />
            <span className="bg-gradient-to-r from-neon-purple to-neon-cyan bg-clip-text text-transparent">
              Execution Timeline
            </span>
          </CardTitle>
          <div className="flex items-center gap-3">
            {trace.total_cost_usd > 0 && (
              <Badge variant="outline" className="text-[10px] border-neon-amber/30 text-neon-amber/80">
                ${trace.total_cost_usd.toFixed(4)}
              </Badge>
            )}
            <Badge variant="outline" className="text-[10px] border-neon-cyan/30 text-neon-cyan/80">
              {(totalMs / 1000).toFixed(1)}s total
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0 px-4 pb-4">
        <ScrollArea className="h-full">
          {/* Planning bar */}
          <div className="flex items-center gap-3 mb-1 py-1.5">
            <div className="w-28 shrink-0 flex items-center gap-2">
              <span className="text-sm">{"\u{1F9E0}"}</span>
              <span className="text-[11px] font-medium text-muted-foreground truncate">Planning</span>
            </div>
            <div className="flex-1 h-6 rounded bg-secondary/20 relative overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 rounded bg-gradient-to-r from-neon-purple/60 to-neon-cyan/60 waterfall-bar flex items-center px-2"
                style={{ width: `${Math.max((trace.planning_ms / totalMs) * 100, 3)}%` }}
              >
                <span className="text-[9px] font-mono text-white/80 whitespace-nowrap">
                  {trace.planning_ms}ms
                </span>
              </div>
            </div>
          </div>

          {/* Step bars */}
          {bars.map(({ step, startPct, widthPct }, i) => (
            <div
              key={step.id}
              className="flex items-center gap-3 py-1.5 group"
              style={{ animation: `float-up 0.3s ease-out ${i * 0.05}s both` }}
            >
              {/* Label */}
              <div className="w-28 shrink-0 flex items-center gap-2">
                <span className="text-sm">{ACTION_ICONS[step.action] ?? "\u{2699}"}</span>
                <div className="flex flex-col min-w-0">
                  <span className={`text-[11px] font-medium truncate ${STATUS_COLORS[step.status] ?? "text-foreground"}`}>
                    {step.action}
                  </span>
                  <span className="text-[9px] text-muted-foreground/40 truncate">{step.group}</span>
                </div>
              </div>

              {/* Bar */}
              <div className="flex-1 h-6 rounded bg-secondary/20 relative overflow-hidden">
                {widthPct > 0 && (
                  <div
                    className={`absolute inset-y-0 rounded waterfall-bar flex items-center px-2 ${
                      GROUP_COLORS[step.group] ?? "bg-neon-cyan/60"
                    } ${step.status === "failed" ? "!bg-neon-rose/60" : ""}`}
                    style={{
                      left: `${startPct}%`,
                      width: `${Math.max(widthPct, 3)}%`,
                      animationDelay: `${i * 0.05}s`,
                      opacity: step.status === "skipped" ? 0.3 : 0.7,
                    }}
                  >
                    <span className="text-[9px] font-mono text-white/90 whitespace-nowrap">
                      {step.duration_ms ? `${step.duration_ms}ms` : ""}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Legend */}
          <div className="flex flex-wrap gap-3 mt-4 pt-3 border-t border-border/20">
            {Object.entries(GROUP_COLORS).map(([group, color]) => {
              if (!bars.some((b) => b.step.group === group)) return null;
              return (
                <div key={group} className="flex items-center gap-1.5">
                  <div className={`h-2 w-2 rounded-sm ${color}`} />
                  <span className="text-[10px] text-muted-foreground/60 capitalize">{group}</span>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
