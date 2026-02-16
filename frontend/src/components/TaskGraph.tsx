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
    glow: "shadow-[0_0_30px_rgba(6,182,212,0.3),0_0_60px_rgba(6,182,212,0.1)]",
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

// Site-specific icons instead of generic action icons
const SITE_ICONS: Record<string, string> = {
  "amazon.com": "\u{1F4E6}",
  "bestbuy.com": "\u{1F3F7}",
  "newegg.com": "\u{1F5A5}",
  "walmart.com": "\u{1F6D2}",
  "ebay.com": "\u{1F4B0}",
  "google.com": "\u{1F50D}",
};

const ACTION_ICONS: Record<string, string> = {
  navigate: "\u{1F310}",
  search: "\u{1F50D}",
  extract: "\u{1F4E6}",
  compare: "\u{2696}\u{FE0F}",
  summarize: "\u{1F4CB}",
  analyze: "\u{1F9E0}",
  rank: "\u{1F3C6}",
};

const EXECUTOR_BADGE: Record<string, { label: string; color: string }> = {
  browser: { label: "BROWSER", color: "text-neon-cyan/50 bg-neon-cyan/[0.08] border-neon-cyan/20" },
  llm: { label: "AI", color: "text-neon-purple/60 bg-neon-purple/[0.08] border-neon-purple/20" },
};

function getSiteIcon(target: string): string | null {
  for (const [domain, icon] of Object.entries(SITE_ICONS)) {
    if (target.includes(domain)) return icon;
  }
  return null;
}

function StepNode({ data }: NodeProps) {
  const step = data.step as TaskStep;
  const style = STATUS_STYLES[step.status] ?? STATUS_STYLES.pending;
  const siteIcon = getSiteIcon(step.target);
  const actionIcon = ACTION_ICONS[step.action] ?? "\u{2699}\u{FE0F}";
  const executor = step.executor ? EXECUTOR_BADGE[step.executor] : null;

  // Extract result preview
  const resultPreview = step.status === "completed" && step.result
    ? getResultPreview(step.result)
    : null;

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-neon-cyan/40 !border-0 !w-2 !h-2"
      />
      <div
        className={`node-enter rounded-2xl border px-3 py-3 min-w-[180px] max-w-[200px] transition-all duration-700 ${style.border} ${style.bg} ${style.glow}`}
      >
        <div className="flex items-center gap-2 mb-1.5">
          {/* Icon: site-specific or action-based */}
          <span className="text-base">{siteIcon ?? actionIcon}</span>
          <span
            className={`text-[11px] font-bold uppercase tracking-wider ${style.icon}`}
          >
            {step.action}
          </span>

          {/* Executor badge */}
          {executor && (
            <span className={`ml-auto text-[8px] font-bold px-1.5 py-0.5 rounded border ${executor.color}`}>
              {executor.label}
            </span>
          )}

          {/* Status indicator */}
          <span className={executor ? "" : "ml-auto"}>
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

        {/* Result preview badge */}
        {resultPreview && (
          <div className="mt-2 rounded-md bg-neon-emerald/[0.08] border border-neon-emerald/15 px-2 py-1">
            <p className="text-[9px] text-neon-emerald/70 font-medium truncate">
              {resultPreview}
            </p>
          </div>
        )}

        {/* Error detail badge */}
        {step.status === "failed" && step.error && (
          <div className="mt-2 rounded-md bg-neon-rose/[0.08] border border-neon-rose/15 px-2 py-1">
            <p className="text-[9px] text-neon-rose/70 font-medium line-clamp-2">
              {step.error}
            </p>
          </div>
        )}

        {/* Skipped detail badge */}
        {step.status === "skipped" && (
          <div className="mt-2 rounded-md bg-muted/20 border border-border/20 px-2 py-1">
            <p className="text-[9px] text-muted-foreground/50 font-medium">
              {step.error ?? "skipped"}
            </p>
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-neon-cyan/40 !border-0 !w-2 !h-2"
      />
    </>
  );
}

function getResultPreview(result: Record<string, unknown>): string | null {
  // Try to extract a meaningful preview from step results
  if (Array.isArray(result)) {
    return `Found ${result.length} items`;
  }
  if (result.products && Array.isArray(result.products)) {
    return `Found ${result.products.length} products`;
  }
  if (result.count != null) {
    return `${result.count} results`;
  }
  if (result.summary && typeof result.summary === "string") {
    return result.summary.slice(0, 40) + "...";
  }
  return null;
}

const nodeTypes = { step: StepNode as FC<NodeProps> };

export function TaskGraph({ steps }: TaskGraphProps) {
  const { nodes, edges } = useMemo(() => {
    if (steps.length === 0) return { nodes: [], edges: [] };

    // Build a proper DAG layout using groups and dependencies
    const groups = new Map<string, TaskStep[]>();
    for (const step of steps) {
      const group = step.group || "default";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group)!.push(step);
    }

    const VERTICAL_GAP = 100;
    const HORIZONTAL_GAP = 270;
    const START_Y = 30;

    // Separate browser groups from analysis group
    const browserGroups: string[] = [];
    let analysisGroup: string | null = null;

    for (const [name] of groups) {
      if (name === "analysis" || name === "default") {
        analysisGroup = name;
      } else {
        browserGroups.push(name);
      }
    }

    const totalBrowserCols = browserGroups.length;
    const totalWidth = totalBrowserCols * HORIZONTAL_GAP;
    const startX = totalBrowserCols > 1 ? -totalWidth / 2 + HORIZONTAL_GAP / 2 : 0;

    const nodeMap = new Map<string, { x: number; y: number }>();
    let maxBrowserY = START_Y;

    // Layout browser groups as parallel columns
    browserGroups.forEach((groupName, colIdx) => {
      const groupSteps = groups.get(groupName) ?? [];
      const x = startX + colIdx * HORIZONTAL_GAP;

      groupSteps.forEach((step, rowIdx) => {
        const y = START_Y + rowIdx * VERTICAL_GAP;
        nodeMap.set(step.id, { x, y });
        maxBrowserY = Math.max(maxBrowserY, y);
      });
    });

    // Layout analysis group below all browser groups, centered
    if (analysisGroup) {
      const analysisSteps = groups.get(analysisGroup) ?? [];
      analysisSteps.forEach((step, rowIdx) => {
        const y = maxBrowserY + VERTICAL_GAP + rowIdx * VERTICAL_GAP;
        nodeMap.set(step.id, { x: 0, y });
      });
    }

    // Handle any steps that didn't get placed (fallback)
    let fallbackY = maxBrowserY + VERTICAL_GAP * 3;
    for (const step of steps) {
      if (!nodeMap.has(step.id)) {
        nodeMap.set(step.id, { x: 0, y: fallbackY });
        fallbackY += VERTICAL_GAP;
      }
    }

    const nodes: Node[] = steps.map((step) => {
      const pos = nodeMap.get(step.id) ?? { x: 0, y: 0 };
      return {
        id: step.id,
        type: "step",
        position: pos,
        data: { step },
      };
    });

    // Build edges from depends_on
    const edges: Edge[] = [];
    const stepById = new Map(steps.map((s) => [s.id, s]));

    for (const step of steps) {
      if (step.depends_on && step.depends_on.length > 0) {
        for (const depId of step.depends_on) {
          const dep = stepById.get(depId);
          if (!dep) continue;

          const isActive = dep.status === "completed" || step.status === "running";
          const isCompleted = dep.status === "completed" && step.status === "completed";

          edges.push({
            id: `e-${depId}-${step.id}`,
            source: depId,
            target: step.id,
            animated: step.status === "running",
            style: {
              stroke: isCompleted
                ? "var(--neon-amber)"
                : isActive
                  ? "var(--neon-cyan)"
                  : "oklch(0.4 0 0 / 30%)",
              strokeWidth: isActive ? 2.5 : 1.5,
              opacity: isActive ? 1 : 0.4,
            },
          });
        }
      }
    }

    // Fallback: if no edges were created from depends_on, create sequential edges
    if (edges.length === 0 && steps.length > 1) {
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
    }

    return { nodes, edges };
  }, [steps]);

  const runningCount = steps.filter((s) => s.status === "running").length;
  const completedCount = steps.filter((s) => s.status === "completed").length;

  return (
    <Card className="glass-panel flex h-full flex-col border-border/30 overflow-hidden">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase">
          <span className="h-1.5 w-1.5 rounded-full bg-neon-purple animate-glow-pulse" />
          <span className="bg-gradient-to-r from-neon-purple to-neon-cyan bg-clip-text text-transparent">
            Neural Map
          </span>
          {steps.length > 0 && (
            <span className="ml-2 text-[10px] font-normal text-muted-foreground/50">
              {completedCount}/{steps.length} steps
              {runningCount > 0 && (
                <span className="ml-1 text-neon-cyan">
                  ({runningCount} firing)
                </span>
              )}
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
                Neural pathways will form here
              </p>
            </div>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.4 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            panOnDrag
            zoomOnScroll
            className="bg-transparent"
          >
            <Background
              variant={BackgroundVariant.Cross}
              gap={30}
              size={1}
              color="var(--neon-cyan)"
              className="opacity-[0.05]"
            />
          </ReactFlow>
        )}
      </CardContent>
    </Card>
  );
}
