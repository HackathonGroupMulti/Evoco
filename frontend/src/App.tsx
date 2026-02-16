import { useCallback, useEffect, useState } from "react";
import { CommandPanel } from "@/components/CommandPanel";
import { TaskGraph } from "@/components/TaskGraph";
import { ResultsPanel } from "@/components/ResultsPanel";
import { StatusBar } from "@/components/StatusBar";
import { LandingHero } from "@/components/LandingHero";
import { ThinkingOverlay } from "@/components/ThinkingOverlay";
import { WaterfallView } from "@/components/WaterfallView";
import { LogPanel } from "@/components/LogPanel";
import { useTaskRunner } from "@/hooks/useTaskRunner";
import type { HealthResponse, OutputFormat, TaskResult } from "@/types";

export default function App() {
  const { connectionState, steps, result, completedCount, reasoning, trace, runTask } =
    useTaskRunner();
  const [history, setHistory] = useState<TaskResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<TaskResult | null>(null);
  const [mode, setMode] = useState<"live" | "mock" | "unknown">("unknown");
  const [hasStarted, setHasStarted] = useState(false);
  const [showWaterfall, setShowWaterfall] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((data: HealthResponse) => setMode(data.mode))
      .catch(() => setMode("unknown"));
  }, []);

  useEffect(() => {
    if (result && result.status === "completed") {
      setHistory((prev) => {
        if (prev.some((t) => t.task_id === result.task_id)) return prev;
        return [result, ...prev];
      });
      setSelectedResult(null);
    }
  }, [result]);

  const handleSubmit = useCallback(
    (command: string, format: OutputFormat) => {
      setSelectedResult(null);
      setHasStarted(true);
      setShowWaterfall(false);
      runTask(command, format);
    },
    [runTask]
  );

  const handleSelectHistory = useCallback((task: TaskResult) => {
    setSelectedResult(task);
    setHasStarted(true);
  }, []);

  const displayResult = selectedResult ?? result;
  const isRunning = connectionState === "connecting" || connectionState === "running";
  const showThinking = isRunning && steps.length === 0;

  // Landing page when no task has started
  if (!hasStarted) {
    return (
      <div className="dark flex h-screen flex-col bg-background text-foreground overflow-hidden">
        {/* Ambient background glow */}
        <div className="pointer-events-none fixed inset-0 overflow-hidden">
          <div className="absolute -top-[40%] -left-[20%] h-[80%] w-[60%] rounded-full bg-neon-cyan/[0.03] blur-[120px]" />
          <div className="absolute -bottom-[30%] -right-[20%] h-[70%] w-[50%] rounded-full bg-neon-purple/[0.04] blur-[120px]" />
          <div className="absolute top-[20%] right-[10%] h-[40%] w-[30%] rounded-full bg-neon-emerald/[0.02] blur-[100px]" />
        </div>

        <LandingHero onSubmit={handleSubmit} mode={mode} />
      </div>
    );
  }

  // Active task view
  return (
    <div className="dark flex h-screen flex-col bg-background text-foreground overflow-hidden">
      {/* Ambient background glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-[40%] -left-[20%] h-[80%] w-[60%] rounded-full bg-neon-cyan/[0.03] blur-[120px]" />
        <div className="absolute -bottom-[30%] -right-[20%] h-[70%] w-[50%] rounded-full bg-neon-purple/[0.04] blur-[120px]" />
      </div>

      {/* Header */}
      <header className="relative flex h-12 shrink-0 items-center justify-between border-b border-border/50 px-5">
        <div className="absolute inset-0 bg-gradient-to-r from-neon-cyan/[0.06] via-transparent to-neon-purple/[0.06]" />
        <div className="relative flex items-center gap-3">
          {/* Entity mark */}
          <button
            onClick={() => setHasStarted(false)}
            className="flex h-6 w-6 items-center justify-center rounded-full entity-orb-mini hover:shadow-[0_0_16px_rgba(6,182,212,0.4)] transition-all"
          />
          <h1 className="text-sm font-semibold tracking-wider lowercase">
            <span className="bg-gradient-to-r from-neon-cyan to-neon-purple bg-clip-text text-transparent">
              evoco
            </span>
          </h1>
        </div>

        {/* Graph/Waterfall toggle */}
        {(steps.length > 0 || trace) && (
          <div className="relative flex items-center gap-1 rounded-lg bg-secondary/30 p-0.5">
            <button
              onClick={() => setShowWaterfall(false)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                !showWaterfall
                  ? "bg-gradient-to-r from-neon-cyan/20 to-neon-purple/20 text-neon-cyan"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Neural Map
            </button>
            <button
              onClick={() => setShowWaterfall(true)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                showWaterfall
                  ? "bg-gradient-to-r from-neon-cyan/20 to-neon-purple/20 text-neon-cyan"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Timeline
            </button>
          </div>
        )}

        {/* Awareness indicator */}
        {steps.length > 0 && (
          <div className="relative flex items-center gap-1.5">
            <span className="text-[9px] text-muted-foreground/40 uppercase tracking-wider">Awareness</span>
            <div className="h-1 w-12 rounded-full bg-secondary/30 overflow-hidden">
              <div
                className="h-full rounded-full consciousness-bar transition-all duration-700"
                style={{ width: `${steps.length > 0 ? (completedCount / steps.length) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}

        {/* Consciousness toggle */}
        <button
          onClick={() => setShowLogs((v) => !v)}
          className={`relative rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
            showLogs
              ? "bg-gradient-to-r from-neon-amber/20 to-neon-rose/20 text-neon-amber"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Consciousness
        </button>

        {/* Shimmer line */}
        <div className="absolute bottom-0 left-0 h-px w-full bg-gradient-to-r from-transparent via-neon-cyan/40 to-transparent" />
      </header>

      {/* Main 3-panel layout */}
      <main className="relative flex flex-1 gap-3 overflow-hidden p-3">
        <div className="w-72 shrink-0">
          <CommandPanel
            onSubmit={handleSubmit}
            connectionState={connectionState}
            history={history}
            onSelectHistory={handleSelectHistory}
          />
        </div>

        <div className="flex-1 min-w-0 relative">
          {/* Thinking overlay during planning */}
          {showThinking && <ThinkingOverlay reasoning={reasoning} />}

          {/* Graph or Waterfall */}
          {!showThinking && (
            showWaterfall && trace ? (
              <WaterfallView trace={trace} />
            ) : (
              <TaskGraph steps={selectedResult?.plan?.steps ?? steps} />
            )
          )}
        </div>

        <div className="w-80 shrink-0">
          <ResultsPanel result={displayResult} connectionState={connectionState} steps={steps} trace={trace} />
        </div>
      </main>

      {/* Log drawer */}
      {showLogs && (
        <div className="shrink-0 h-56 border-t border-border/30 px-3 pb-1">
          <LogPanel />
        </div>
      )}

      {/* Status Bar */}
      <StatusBar
        connectionState={connectionState}
        stepsTotal={steps.length}
        stepsCompleted={completedCount}
        durationMs={result?.duration_ms ?? undefined}
        costUsd={result?.cost_usd ?? undefined}
        mode={mode}
      />
    </div>
  );
}
