import { useCallback, useEffect, useState } from "react";
import { CommandPanel } from "@/components/CommandPanel";
import { TaskGraph } from "@/components/TaskGraph";
import { ResultsPanel } from "@/components/ResultsPanel";
import { StatusBar } from "@/components/StatusBar";
import { useTaskRunner } from "@/hooks/useTaskRunner";
import type { HealthResponse, OutputFormat, TaskResult } from "@/types";

export default function App() {
  const { connectionState, steps, result, completedCount, runTask } = useTaskRunner();
  const [history, setHistory] = useState<TaskResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<TaskResult | null>(null);
  const [mode, setMode] = useState<"live" | "mock" | "unknown">("unknown");

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
      runTask(command, format);
    },
    [runTask]
  );

  const handleSelectHistory = useCallback((task: TaskResult) => {
    setSelectedResult(task);
  }, []);

  const displayResult = selectedResult ?? result;

  return (
    <div className="dark flex h-screen flex-col bg-background text-foreground overflow-hidden">
      {/* Ambient background glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-[40%] -left-[20%] h-[80%] w-[60%] rounded-full bg-neon-cyan/[0.03] blur-[120px]" />
        <div className="absolute -bottom-[30%] -right-[20%] h-[70%] w-[50%] rounded-full bg-neon-purple/[0.04] blur-[120px]" />
      </div>

      {/* Header */}
      <header className="relative flex h-12 shrink-0 items-center border-b border-border/50 px-5">
        <div className="absolute inset-0 bg-gradient-to-r from-neon-cyan/[0.06] via-transparent to-neon-purple/[0.06]" />
        <div className="relative flex items-center gap-3">
          {/* Logo mark */}
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-neon-cyan to-neon-purple">
            <span className="text-xs font-black text-white">E</span>
          </div>
          <h1 className="text-sm font-bold tracking-widest uppercase">
            <span className="bg-gradient-to-r from-neon-cyan to-neon-purple bg-clip-text text-transparent">
              Evoco
            </span>
            <span className="ml-1.5 font-normal text-muted-foreground">Control Panel</span>
          </h1>
        </div>
        {/* Shimmer line at bottom of header */}
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

        <div className="flex-1 min-w-0">
          <TaskGraph steps={selectedResult?.plan?.steps ?? steps} />
        </div>

        <div className="w-80 shrink-0">
          <ResultsPanel result={displayResult} connectionState={connectionState} />
        </div>
      </main>

      {/* Status Bar */}
      <StatusBar
        connectionState={connectionState}
        stepsTotal={steps.length}
        stepsCompleted={completedCount}
        durationMs={result?.duration_ms ?? undefined}
        mode={mode}
      />
    </div>
  );
}
