export type OutputFormat = "json" | "csv" | "summary";

export type StepStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type TaskStatus = "queued" | "planning" | "executing" | "completed" | "failed" | "cancelled";

export interface TaskStep {
  id: string;
  action: string;
  target: string;
  description: string;
  status: StepStatus;
  result?: Record<string, unknown>;
  error?: string;
}

export interface TaskPlan {
  task_id: string;
  original_command: string;
  steps: TaskStep[];
}

export interface TaskResult {
  task_id: string;
  status: TaskStatus;
  command: string;
  plan?: TaskPlan;
  output?: unknown;
  output_format: OutputFormat;
  error?: string;
  created_at: string;
  finished_at?: string;
  duration_ms?: number;
}

export interface WSEvent {
  task_id: string;
  event:
    | "planning_started"
    | "plan_ready"
    | "step_started"
    | "step_completed"
    | "step_failed"
    | "task_done";
  data: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  aws_configured: boolean;
  nova_act_configured: boolean;
  mode: "live" | "mock";
}
