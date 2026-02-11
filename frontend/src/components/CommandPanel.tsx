import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import type { OutputFormat, TaskResult } from "@/types";
import type { ConnectionState } from "@/hooks/useTaskRunner";

interface CommandPanelProps {
  onSubmit: (command: string, format: OutputFormat) => void;
  connectionState: ConnectionState;
  history: TaskResult[];
  onSelectHistory: (task: TaskResult) => void;
}

const FORMAT_OPTIONS: { value: OutputFormat; label: string }[] = [
  { value: "json", label: "JSON" },
  { value: "csv", label: "CSV" },
  { value: "summary", label: "Summary" },
];

export function CommandPanel({
  onSubmit,
  connectionState,
  history,
  onSelectHistory,
}: CommandPanelProps) {
  const [command, setCommand] = useState("");
  const [format, setFormat] = useState<OutputFormat>("json");

  const isRunning = connectionState === "connecting" || connectionState === "running";

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = command.trim();
    if (!trimmed || isRunning) return;
    onSubmit(trimmed, format);
    setCommand("");
  }

  return (
    <Card className="glass-panel flex h-full flex-col border-border/30">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase">
          <span className="h-1.5 w-1.5 rounded-full bg-neon-cyan animate-glow-pulse" />
          <span className="bg-gradient-to-r from-neon-cyan to-neon-emerald bg-clip-text text-transparent">
            Command
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4 overflow-hidden">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="gradient-border rounded-lg">
            <Input
              placeholder="e.g. Find the best laptop under $800…"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              disabled={isRunning}
              className="border-0 bg-background/50 focus-visible:ring-neon-cyan/30"
            />
          </div>
          <div className="flex gap-1.5">
            {FORMAT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFormat(opt.value)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all duration-200 ${
                  format === opt.value
                    ? "bg-gradient-to-r from-neon-cyan/20 to-neon-purple/20 text-neon-cyan border border-neon-cyan/30 glow-cyan"
                    : "bg-secondary/50 text-muted-foreground hover:text-foreground hover:bg-secondary"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Button
            type="submit"
            disabled={isRunning || !command.trim()}
            className="w-full bg-gradient-to-r from-neon-cyan to-neon-purple text-white font-semibold hover:from-neon-cyan/90 hover:to-neon-purple/90 transition-all duration-300 hover:shadow-[0_0_20px_rgba(34,211,238,0.3)] disabled:opacity-40 disabled:hover:shadow-none"
          >
            {isRunning ? (
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/70 border-t-transparent" />
                Running…
              </span>
            ) : (
              "Execute"
            )}
          </Button>
        </form>

        <Separator className="bg-gradient-to-r from-transparent via-border to-transparent" />

        <div className="flex-1 overflow-hidden">
          <p className="mb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground/60">
            History
          </p>
          <ScrollArea className="h-full">
            <div className="flex flex-col gap-1 pr-3">
              {history.length === 0 && (
                <p className="text-xs text-muted-foreground/40 italic">No tasks yet</p>
              )}
              {history.map((task) => (
                <button
                  key={task.task_id}
                  onClick={() => onSelectHistory(task)}
                  className="group flex items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-all duration-200 hover:bg-neon-cyan/[0.06] hover:border-neon-cyan/10 border border-transparent"
                >
                  <StatusDot status={task.status} />
                  <span className="flex-1 truncate text-muted-foreground group-hover:text-foreground transition-colors">
                    {task.command}
                  </span>
                  {task.duration_ms != null && (
                    <Badge variant="secondary" className="text-[10px] shrink-0 bg-secondary/50">
                      {(task.duration_ms / 1000).toFixed(1)}s
                    </Badge>
                  )}
                </button>
              ))}
            </div>
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}

function StatusDot({ status }: { status: string }) {
  const styles =
    status === "completed"
      ? "bg-neon-emerald shadow-[0_0_6px_var(--neon-emerald)]"
      : status === "failed"
        ? "bg-neon-rose shadow-[0_0_6px_var(--neon-rose)]"
        : status === "executing" || status === "planning"
          ? "bg-neon-cyan shadow-[0_0_6px_var(--neon-cyan)] animate-pulse"
          : "bg-muted-foreground/30";
  return <span className={`h-2 w-2 shrink-0 rounded-full ${styles}`} />;
}
