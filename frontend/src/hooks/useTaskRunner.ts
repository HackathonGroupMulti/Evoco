import { useCallback, useRef, useState } from "react";
import type { OutputFormat, TaskResult, TaskStep, WSEvent } from "@/types";

export type ConnectionState = "idle" | "connecting" | "running" | "done" | "error";

interface UseTaskRunnerReturn {
  connectionState: ConnectionState;
  steps: TaskStep[];
  result: TaskResult | null;
  error: string | null;
  completedCount: number;
  runTask: (command: string, outputFormat: OutputFormat) => void;
}

export function useTaskRunner(): UseTaskRunnerReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [steps, setSteps] = useState<TaskStep[]>([]);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completedCount, setCompletedCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  const runTask = useCallback((command: string, outputFormat: OutputFormat) => {
    // Reset state
    setSteps([]);
    setResult(null);
    setError(null);
    setCompletedCount(0);
    setConnectionState("connecting");

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionState("running");
      ws.send(JSON.stringify({ command, output_format: outputFormat }));
    };

    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data);

      // Check if this is a WSEvent or the final TaskResult
      if ("event" in data) {
        const event = data as WSEvent;
        handleEvent(event);
      } else if ("task_id" in data && "status" in data) {
        // Final TaskResult
        setResult(data as TaskResult);
        setConnectionState("done");
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection failed");
      setConnectionState("error");
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  }, []);

  function handleEvent(event: WSEvent) {
    switch (event.event) {
      case "plan_ready": {
        const planSteps = (event.data.steps as TaskStep[]) ?? [];
        setSteps(planSteps.map((s) => ({ ...s, status: "pending" })));
        break;
      }
      case "step_started":
        setSteps((prev) =>
          prev.map((s) =>
            s.id === event.data.step_id ? { ...s, status: "running" } : s
          )
        );
        break;
      case "step_completed":
        setSteps((prev) =>
          prev.map((s) =>
            s.id === event.data.step_id
              ? { ...s, status: "completed", result: event.data.result as Record<string, unknown> }
              : s
          )
        );
        setCompletedCount((c) => c + 1);
        break;
      case "step_failed":
        setSteps((prev) =>
          prev.map((s) =>
            s.id === event.data.step_id
              ? { ...s, status: "failed", error: event.data.error as string }
              : s
          )
        );
        setCompletedCount((c) => c + 1);
        break;
    }
  }

  return { connectionState, steps, result, error, completedCount, runTask };
}
