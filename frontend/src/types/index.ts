export type TaskStatus = 'pending' | 'running' | 'complete' | 'error';

export interface PlanStep {
  id: string;
  action: 'navigate' | 'extract' | 'compare' | 'summarize';
  target: string;
  description: string;
  dependsOn: string[];
  status: TaskStatus;
  result?: unknown;
  error?: string;
}

export interface ExecutionPlan {
  taskSummary: string;
  steps: PlanStep[];
}

export interface Product {
  name: string;
  price: number;
  url: string;
  source: string;
  imageUrl?: string;
  rating?: number;
}

export interface AgentState {
  status: 'idle' | 'listening' | 'thinking' | 'planning' | 'executing' | 'complete' | 'error';
  message: string;
  plan: ExecutionPlan | null;
  results: Product[];
  currentStep: string | null;
}

export interface WebSocketMessage {
  event: 'command' | 'plan' | 'step_start' | 'step_complete' | 'step_error' | 'results' | 'voice_response' | 'status';
  data: unknown;
}
