import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import type { TaskResult, TaskStep, TaskTrace } from "@/types";
import type { ConnectionState } from "@/hooks/useTaskRunner";

interface ResultsPanelProps {
  result: TaskResult | null;
  connectionState: ConnectionState;
  steps: TaskStep[];
  trace: TaskTrace | null;
}

function buildDiagnosticSnapshot(
  result: TaskResult,
  steps: TaskStep[],
  trace: TaskTrace | null
): string {
  const lines: string[] = [
    `=== EVOCO DIAGNOSTIC SNAPSHOT ===`,
    `Task:     ${result.task_id}`,
    `Command:  ${result.command}`,
    `Status:   ${result.status}`,
  ];

  if (result.error) lines.push(`Error:    ${result.error}`);
  if (result.duration_ms != null) lines.push(`Duration: ${(result.duration_ms / 1000).toFixed(2)}s`);
  if (result.cost_usd != null) lines.push(`Cost:     $${result.cost_usd.toFixed(4)}`);
  if (trace) {
    lines.push(`Planning: ${(trace.planning_ms / 1000).toFixed(2)}s`);
    lines.push(`Execution:${(trace.execution_ms / 1000).toFixed(2)}s`);
  }

  lines.push("", "--- Steps ---");

  const stepSource = trace?.steps ?? [];
  for (const ts of stepSource) {
    const matching = steps.find((s) => s.id === ts.id);
    const target = matching?.target ?? "";
    const desc = matching?.description ?? "";
    const dur = ts.duration_ms != null ? `${(ts.duration_ms / 1000).toFixed(2)}s` : "-";
    const retries = ts.retries > 0 ? ` (${ts.retries} retries)` : "";

    lines.push(`[${ts.status.toUpperCase().padEnd(9)}] ${ts.id}`);
    lines.push(`  action:   ${ts.action} | executor: ${ts.executor} | group: ${ts.group}`);
    if (target) lines.push(`  target:   ${target}`);
    if (desc) lines.push(`  desc:     ${desc}`);
    lines.push(`  duration: ${dur}${retries} | cost: $${ts.cost_usd.toFixed(4)}`);
    if (ts.error) lines.push(`  error:    ${ts.error}`);
  }

  // Fallback: if no trace yet, use live steps
  if (stepSource.length === 0 && steps.length > 0) {
    for (const s of steps) {
      lines.push(`[${s.status.toUpperCase().padEnd(9)}] ${s.id}`);
      lines.push(`  action: ${s.action} | executor: ${s.executor ?? "?"} | target: ${s.target}`);
      if (s.description) lines.push(`  desc:   ${s.description}`);
      if (s.error) lines.push(`  error:  ${s.error}`);
    }
  }

  lines.push("", `Generated: ${new Date().toISOString()}`);
  return lines.join("\n");
}

export function ResultsPanel({ result, connectionState, steps, trace }: ResultsPanelProps) {
  const isRunning = connectionState === "connecting" || connectionState === "running";
  const [copied, setCopied] = useState(false);

  const handleCopyDiagnostics = () => {
    if (!result) return;
    const snapshot = buildDiagnosticSnapshot(result, steps, trace);
    navigator.clipboard.writeText(snapshot).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <Card className="glass-panel flex h-full flex-col border-border/30">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-neon-emerald animate-glow-pulse" />
            <span className="bg-gradient-to-r from-neon-emerald to-neon-cyan bg-clip-text text-transparent">
              Response
            </span>
          </CardTitle>
          <div className="flex items-center gap-2">
            {result && (
              <button
                onClick={handleCopyDiagnostics}
                className="rounded-md px-2 py-0.5 text-[10px] font-medium border transition-all duration-200 border-border/40 text-muted-foreground hover:text-neon-cyan hover:border-neon-cyan/40"
                title="Copy diagnostic snapshot to clipboard"
              >
                {copied ? "Copied!" : "Copy Diagnostics"}
              </button>
            )}
            {result?.cost_usd != null && result.cost_usd > 0 && (
              <Badge
                variant="outline"
                className="text-[10px] border-neon-amber/30 text-neon-amber/80"
              >
                ${result.cost_usd.toFixed(4)}
              </Badge>
            )}
            {result?.duration_ms != null && (
              <Badge
                variant="outline"
                className="text-[10px] border-neon-emerald/30 text-neon-emerald/80"
              >
                {(result.duration_ms / 1000).toFixed(1)}s
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden">
        {!result && !isRunning && (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-neon-emerald/10 to-neon-cyan/10 border border-neon-emerald/20 flex items-center justify-center">
                <span className="text-lg text-neon-emerald/40">{"\u{1F4CA}"}</span>
              </div>
              <p className="text-sm text-muted-foreground/40 italic text-center">
                I'll share my findings here
              </p>
            </div>
          </div>
        )}

        {isRunning && !result && (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-4">
              <div className="h-10 w-10 rounded-full entity-orb-active" />
              <p className="text-sm text-neon-cyan/60" style={{ animation: "breathe 2s ease-in-out infinite" }}>
                Gathering understanding...
              </p>
            </div>
          </div>
        )}

        {result && <ResultContent result={result} />}
      </CardContent>
    </Card>
  );
}

function ResultContent({ result }: { result: TaskResult }) {
  if (result.status === "failed") {
    return (
      <div className="rounded-lg bg-gradient-to-br from-neon-rose/10 to-neon-amber/5 border border-neon-rose/30 p-4 glow-rose">
        <p className="text-sm font-semibold text-neon-rose">I encountered a disruption</p>
        <p className="mt-1.5 text-xs text-muted-foreground">{result.error}</p>
      </div>
    );
  }

  return (
    <Tabs defaultValue="formatted" className="flex h-full flex-col">
      <TabsList className="w-full shrink-0 bg-secondary/30">
        <TabsTrigger
          value="formatted"
          className="flex-1 data-[state=active]:bg-gradient-to-r data-[state=active]:from-neon-cyan/10 data-[state=active]:to-neon-purple/10 data-[state=active]:text-foreground"
        >
          Understanding
        </TabsTrigger>
        <TabsTrigger
          value="raw"
          className="flex-1 data-[state=active]:bg-gradient-to-r data-[state=active]:from-neon-cyan/10 data-[state=active]:to-neon-purple/10 data-[state=active]:text-foreground"
        >
          Raw Memory
        </TabsTrigger>
      </TabsList>
      <TabsContent value="formatted" className="flex-1 overflow-hidden mt-3">
        <ScrollArea className="h-full">
          <FormattedOutput result={result} />
        </ScrollArea>
      </TabsContent>
      <TabsContent value="raw" className="flex-1 overflow-hidden mt-3">
        <ScrollArea className="h-full">
          <pre className="whitespace-pre-wrap text-xs font-mono text-neon-cyan/60 leading-relaxed p-3 rounded-lg bg-background/50 border border-border/30">
            {typeof result.output === "string"
              ? result.output
              : JSON.stringify(result.output, null, 2)}
          </pre>
        </ScrollArea>
      </TabsContent>
    </Tabs>
  );
}

function formatSummary(raw: unknown): string | null {
  if (!raw) return null;
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) return raw.join(" ");
  return String(raw);
}

function FormattedOutput({ result }: { result: TaskResult }) {
  const output = result.output as Record<string, unknown> | string | null;

  if (typeof output === "string") {
    return (
      <div className="flex flex-col gap-3 pr-3">
        <div className="rounded-lg bg-gradient-to-br from-neon-cyan/[0.08] to-neon-purple/[0.06] border border-neon-cyan/20 p-4 glow-cyan">
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">{output}</p>
        </div>
      </div>
    );
  }

  if (!output || typeof output !== "object") {
    return <p className="text-sm text-muted-foreground">No output</p>;
  }

  const products = (output.results ?? output.ranked ?? []) as Array<{
    name?: string;
    price?: number;
    rating?: number;
    source?: string;
    url?: string;
  }>;

  const summary = formatSummary(output.summary);
  const validProducts = products.filter((p) => p.name);
  const topPick = validProducts[0];
  const maxPrice = Math.max(...validProducts.map((p) => p.price ?? 0), 1);

  return (
    <div className="flex flex-col gap-3 pr-3">
      {/* Conversational summary */}
      {summary && (
        <div className="rounded-lg bg-gradient-to-br from-neon-cyan/[0.08] to-neon-purple/[0.06] border border-neon-cyan/20 p-4 glow-cyan">
          <div className="flex items-start gap-2.5">
            <span className="text-base mt-0.5 shrink-0">{"\u{1F4AC}"}</span>
            <p className="text-sm text-foreground leading-relaxed">{summary}</p>
          </div>
        </div>
      )}

      {/* Hero card for #1 pick */}
      {topPick && (
        <div className="hero-card-border rounded-xl">
          <div className="rounded-xl bg-gradient-to-br from-neon-amber/[0.12] to-neon-cyan/[0.08] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Badge className="bg-neon-amber/20 text-neon-amber border-neon-amber/30 text-[10px] font-bold">
                {"\u{1F3C6}"} MY RECOMMENDATION
              </Badge>
              {topPick.source && (
                <span className="text-[10px] text-muted-foreground/50">{topPick.source}</span>
              )}
            </div>
            <p className="text-sm font-semibold text-foreground mb-2">{topPick.name}</p>
            <div className="flex items-center gap-3">
              {topPick.price != null && (
                <span className="text-xl font-bold bg-gradient-to-r from-neon-emerald to-neon-cyan bg-clip-text text-transparent">
                  ${topPick.price}
                </span>
              )}
              {topPick.rating != null && topPick.rating > 0 && (
                <div className="flex items-center gap-1">
                  <StarRating rating={topPick.rating} />
                  <span className="text-xs text-neon-amber font-medium">{topPick.rating}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Price comparison bar chart for remaining products */}
      {validProducts.length > 1 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground/50 mb-1">
            All Results
          </p>
          {validProducts.slice(1).map((p, i) => {
            const price = p.price ?? 0;
            const barWidth = maxPrice > 0 ? (price / maxPrice) * 100 : 50;

            return (
              <div
                key={`${p.name}-${i}`}
                className="group rounded-lg border border-border/20 bg-card/30 px-3 py-2.5 transition-all duration-200 hover:bg-neon-cyan/[0.04] hover:border-neon-cyan/20"
                style={{ animation: `float-up 0.3s ease-out ${(i + 1) * 0.08}s both` }}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[10px] font-bold text-muted-foreground/30 w-4">
                      {i + 2}
                    </span>
                    <p className="text-xs font-medium text-foreground truncate group-hover:text-neon-cyan transition-colors">
                      {p.name}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {price > 0 && (
                      <span className="text-sm font-bold text-foreground">${price}</span>
                    )}
                    {p.rating != null && p.rating > 0 && (
                      <Badge
                        variant="secondary"
                        className="text-[9px] bg-neon-amber/10 text-neon-amber border-neon-amber/20 px-1.5"
                      >
                        {p.rating}{"\u2605"}
                      </Badge>
                    )}
                  </div>
                </div>
                {/* Price bar */}
                {price > 0 && (
                  <div className="h-1 rounded-full bg-secondary/30 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-neon-cyan/40 to-neon-purple/40 transition-all duration-500"
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                )}
                {p.source && (
                  <p className="text-[10px] text-muted-foreground/40 mt-1">{p.source}</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Fallback if no structured data */}
      {validProducts.length === 0 && !summary && (
        <pre className="whitespace-pre-wrap text-xs font-mono text-muted-foreground">
          {JSON.stringify(output, null, 2)}
        </pre>
      )}
    </div>
  );
}

function StarRating({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const hasHalf = rating - full >= 0.3;
  const stars = [];

  for (let i = 0; i < 5; i++) {
    if (i < full) {
      stars.push(
        <span key={i} className="text-neon-amber text-xs">{"\u2605"}</span>
      );
    } else if (i === full && hasHalf) {
      stars.push(
        <span key={i} className="text-neon-amber/50 text-xs">{"\u2605"}</span>
      );
    } else {
      stars.push(
        <span key={i} className="text-muted-foreground/20 text-xs">{"\u2605"}</span>
      );
    }
  }

  return <span className="flex items-center">{stars}</span>;
}
