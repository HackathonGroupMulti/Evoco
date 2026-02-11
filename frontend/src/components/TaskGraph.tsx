import { useMemo, type FC } from "react";
import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
  Position,
  Handle,
  type NodeProps,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TaskStep, StepStatus } from "@/types";

interface TaskGraphProps {
  steps: TaskStep[];
}

const STATUS_STYLES: Record<
  StepStatus,
  { border: string; bg: string; glow: string; icon: string }
> = {
  pending: {
    border: "border-muted-foreground/20",
    bg: "bg-card/60",
    glow: "",
    icon: "text-muted-foreground/40",
  },
  running: {
    border: "border-neon-cyan",
    bg: "bg-gradient-to-br from-neon-cyan/15 to-neon-purple/10",
    glow: "shadow-[0_0_20px_rgba(34,211,238,0.3),0_0_40px_rgba(34,211,238,0.1)]",
    icon: "text-neon-cyan",
  },
  completed: {
    border: "border-neon-emerald/60",
    bg: "bg-gradient-to-br from-neon-emerald/10 to-neon-cyan/5",
    glow: "shadow-[0_0_12px_rgba(52,211,153,0.2)]",
    icon: "text-neon-emerald",
  },
  failed: {
    border: "border-neon-rose/60",
    bg: "bg-gradient-to-br from-neon-rose/10 to-neon-amber/5",
    glow: "shadow-[0_0_12px_rgba(251,113,133,0.2)]",
    icon: "text-neon-rose",
  },
  skipped: {
    border: "border-muted-foreground/15",
    bg: "bg-muted/30",
    glow: "",
    icon: "text-muted-foreground/30",
  },
};

const ACTION_ICONS: Record<string, string> = {
  navigate: "\u{1F310}",
  search: "\u{1F50D}",
  extract: "\u{1F4E6}",
  compare: "\u{2696}",
  summarize: "\u{1F4CB}",
};

function StepNode({ data }: NodeProps) {
  const step = data.step as TaskStep;
  const style = STATUS_STYLES[step.status] ?? STATUS_STYLES.pending;
  const icon = ACTION_ICONS[step.action] ?? "\u{2699}";

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-neon-cyan/40 !border-0 !w-2 !h-2"
      />
      <div
        className={`rounded-xl border px-4 py-3 min-w-[190px] max-w-[230px] transition-all duration-500 ${style.border} ${style.bg} ${style.glow}`}
      >
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-base">{icon}</span>
          <span
            className={`text-[11px] font-bold uppercase tracking-wider ${style.icon}`}
          >
            {step.action}
          </span>
          <span className="ml-auto">
            {step.status === "running" && (
              <span className="flex h-4 w-4 items-center justify-center">
                <span className="absolute h-3 w-3 rounded-full bg-neon-cyan/30 animate-ping" />
                <span className="h-2 w-2 rounded-full bg-neon-cyan" />
              </span>
            )}
            {step.status === "completed" && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-neon-emerald/20 text-neon-emerald text-[10px] font-bold">
                {"\u2713"}
              </span>
            )}
            {step.status === "failed" && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-neon-rose/20 text-neon-rose text-[10px] font-bold">
                {"\u2717"}
              </span>
            )}
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground leading-snug line-clamp-2">
          {step.description}
        </p>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-neon-cyan/40 !border-0 !w-2 !h-2"
      />
    </>
  );
}

const nodeTypes = { step: StepNode as FC<NodeProps> };

export function TaskGraph({ steps }: TaskGraphProps) {
  const { nodes, edges } = useMemo(() => {
    if (steps.length === 0) return { nodes: [], edges: [] };

    const VERTICAL_GAP = 95;
    const START_Y = 30;
    const CENTER_X = 200;

    const nodes: Node[] = steps.map((step, i) => ({
      id: step.id,
      type: "step",
      position: { x: CENTER_X, y: START_Y + i * VERTICAL_GAP },
      data: { step },
    }));

    const edges: Edge[] = [];
    for (let i = 1; i < steps.length; i++) {
      const prevStatus = steps[i - 1].status;
      const curStatus = steps[i].status;
      const isActive = prevStatus === "completed" || curStatus === "running";
      const isCompleted = prevStatus === "completed" && curStatus === "completed";

      edges.push({
        id: `e-${steps[i - 1].id}-${steps[i].id}`,
        source: steps[i - 1].id,
        target: steps[i].id,
        animated: curStatus === "running",
        style: {
          stroke: isCompleted
            ? "var(--neon-emerald)"
            : isActive
              ? "var(--neon-cyan)"
              : "oklch(0.4 0 0 / 30%)",
          strokeWidth: isActive ? 2.5 : 1.5,
          opacity: isActive ? 1 : 0.4,
        },
      });
    }

    return { nodes, edges };
  }, [steps]);

  return (
    <Card className="glass-panel flex h-full flex-col border-border/30 overflow-hidden">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase">
          <span className="h-1.5 w-1.5 rounded-full bg-neon-purple animate-glow-pulse" />
          <span className="bg-gradient-to-r from-neon-purple to-neon-cyan bg-clip-text text-transparent">
            Task Graph
          </span>
          {steps.length > 0 && (
            <span className="ml-2 text-[10px] font-normal text-muted-foreground/50">
              {steps.filter((s) => s.status === "completed").length}/{steps.length} steps
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        {steps.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-neon-purple/10 to-neon-cyan/10 border border-neon-purple/20 flex items-center justify-center">
                <span className="text-lg text-neon-purple/40">{"\u{1F4CA}"}</span>
              </div>
              <p className="text-sm text-muted-foreground/40 italic">
                Submit a command to see the plan
              </p>
            </div>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.3 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            panOnDrag
            zoomOnScroll
            className="bg-transparent"
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={24}
              size={1}
              color="var(--neon-cyan)"
              className="opacity-[0.08]"
            />
          </ReactFlow>
        )}
      </CardContent>
    </Card>
  );
}
