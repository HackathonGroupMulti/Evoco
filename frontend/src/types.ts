export type OutputFormat = "json" | "csv" | "summary";

export type StepStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type TaskStatus = "queued" | "planning" | "executing" | "completed" | "failed" | "cancelled";

export interface TaskStep {
  id: string;
  action: string;
  target: string;
  description: string;
  status: StepStatus;
  executor?: "browser" | "llm";
  group?: string;
  depends_on?: string[];
  result?: Record<string, unknown>;
  error?: string;
}

export interface TaskPlan {
  task_id: string;
  original_command: string;
  steps: TaskStep[];
}

export interface TraceStep {
  id: string;
  action: string;
  group: string;
  executor: string;
  status: string;
  cost_usd: number;
  retries: number;
  duration_ms?: number;
  started_at?: string;
  finished_at?: string;
  error?: string;
}

export interface TaskTrace {
  planning_ms: number;
  execution_ms: number;
  total_cost_usd: number;
  steps: TraceStep[];
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
  cost_usd?: number;
  trace?: TaskTrace;
}

export interface WSEvent {
  task_id: string;
  event:
    | "planning_started"
    | "planning_reasoning"
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

export interface DemoScenario {
  title: string;
  command: string;
  icon: string;
  color: string;
}
