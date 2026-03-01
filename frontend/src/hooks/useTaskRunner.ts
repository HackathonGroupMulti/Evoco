import { useCallback, useRef, useState } from "react";
import type { OutputFormat, TaskResult, TaskStep, TaskTrace, WSEvent } from "@/types";

export type ConnectionState = "idle" | "connecting" | "running" | "done" | "error" | "disconnected";

interface UseTaskRunnerReturn {
  connectionState: ConnectionState;
  taskId: string | null;
  steps: TaskStep[];
  result: TaskResult | null;
  error: string | null;
  completedCount: number;
  reasoning: string | null;
  trace: TaskTrace | null;
  runTask: (command: string, outputFormat: OutputFormat) => void;
  cancelTask: () => Promise<void>;
}

export function useTaskRunner(): UseTaskRunnerReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [steps, setSteps] = useState<TaskStep[]>([]);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completedCount, setCompletedCount] = useState(0);
  const [reasoning, setReasoning] = useState<string | null>(null);
  const [trace, setTrace] = useState<TaskTrace | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const taskIdRef = useRef<string | null>(null);
  // Track whether the socket was closed on purpose so onclose can tell
  // an intentional close apart from an unexpected network disconnect.
  const intentionalCloseRef = useRef(false);
  // Keep connectionState accessible in the ws.onclose closure without
  // re-creating the runTask callback on every state change.
  const connectionStateRef = useRef<ConnectionState>("idle");

  const handleEvent = useCallback((event: WSEvent) => {
    // Capture task_id from the first incoming event
    if (event.task_id && !taskIdRef.current) {
      taskIdRef.current = event.task_id;
      setTaskId(event.task_id);
    }

    switch (event.event) {
      case "planning_reasoning":
        setReasoning(event.data.text as string);
        break;
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
      case "task_done":
        if (event.data.trace) {
          setTrace(event.data.trace as TaskTrace);
        }
        break;
    }
  }, []);

  const cancelTask = useCallback(async () => {
    intentionalCloseRef.current = true;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    // Best-effort REST cancel so the pipeline shuts down server-side
    const tid = taskIdRef.current;
    if (tid) {
      try {
        await fetch(`/api/tasks/${tid}/cancel`, { method: "POST" });
      } catch {
        // Ignore — the pipeline will time out on its own
      }
    }
    setConnectionState("idle");
    connectionStateRef.current = "idle";
    setError(null);
  }, []);

  const runTask = useCallback((command: string, outputFormat: OutputFormat) => {
    // Reset all state
    setSteps([]);
    setResult(null);
    setError(null);
    setCompletedCount(0);
    setReasoning(null);
    setTrace(null);
    setTaskId(null);
    taskIdRef.current = null;

    // Close any existing connection intentionally before opening a new one
    intentionalCloseRef.current = true;
    if (wsRef.current) {
      wsRef.current.close();
    }
    intentionalCloseRef.current = false;

    setConnectionState("connecting");
    connectionStateRef.current = "connecting";

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionState("running");
      connectionStateRef.current = "running";
      ws.send(JSON.stringify({ command, output_format: outputFormat }));
    };

    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data) as Record<string, unknown>;

      // Server-side error frame (e.g. timeout, bad command)
      if ("error" in data && !("task_id" in data)) {
        setError(data.error as string);
        setConnectionState("error");
        connectionStateRef.current = "error";
        return;
      }

      if ("event" in data) {
        handleEvent(data as unknown as WSEvent);
      } else if ("task_id" in data && "status" in data) {
        // Final TaskResult
        const taskResult = data as unknown as TaskResult;
        taskIdRef.current = taskResult.task_id;
        setTaskId(taskResult.task_id);
        setResult(taskResult);
        setConnectionState("done");
        connectionStateRef.current = "done";
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection failed");
      setConnectionState("error");
      connectionStateRef.current = "error";
    };

    ws.onclose = (ev) => {
      wsRef.current = null;
      // Only surface a disconnect warning when the task was actively running
      // and we didn't close the socket ourselves.
      if (
        !intentionalCloseRef.current &&
        connectionStateRef.current === "running"
      ) {
        setError(
          `Connection lost (code ${ev.code}). The task may still be running in the background.`
        );
        setConnectionState("disconnected");
        connectionStateRef.current = "disconnected";
      }
    };
  }, [handleEvent]);

  return {
    connectionState,
    taskId,
    steps,
    result,
    error,
    completedCount,
    reasoning,
    trace,
    runTask,
    cancelTask,
  };
}
