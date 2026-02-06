import { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, Search, GitCompare, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import type { ExecutionPlan, PlanStep, TaskStatus } from '../../types';

interface TaskGraphProps {
  plan: ExecutionPlan | null;
  currentStep: string | null;
}

const actionIcons: Record<string, React.ReactNode> = {
  navigate: <Globe className="w-4 h-4" />,
  extract: <Search className="w-4 h-4" />,
  compare: <GitCompare className="w-4 h-4" />,
  summarize: <FileText className="w-4 h-4" />,
};

const statusColors: Record<TaskStatus, { bg: string; border: string; glow: string }> = {
  pending: {
    bg: 'rgba(55, 65, 81, 0.8)',
    border: 'rgba(75, 85, 99, 0.5)',
    glow: 'none',
  },
  running: {
    bg: 'rgba(30, 64, 175, 0.8)',
    border: 'rgba(59, 130, 246, 0.8)',
    glow: '0 0 20px rgba(59, 130, 246, 0.5)',
  },
  complete: {
    bg: 'rgba(6, 95, 70, 0.8)',
    border: 'rgba(16, 185, 129, 0.8)',
    glow: '0 0 15px rgba(16, 185, 129, 0.3)',
  },
  error: {
    bg: 'rgba(153, 27, 27, 0.8)',
    border: 'rgba(239, 68, 68, 0.8)',
    glow: '0 0 15px rgba(239, 68, 68, 0.3)',
  },
};

function CustomNode({ data }: { data: PlanStep }) {
  const colors = statusColors[data.status];
  const Icon = actionIcons[data.action] || <Globe className="w-4 h-4" />;

  return (
    <motion.div
      className="px-4 py-3 rounded-xl min-w-[180px] max-w-[220px]"
      style={{
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        boxShadow: colors.glow,
        backdropFilter: 'blur(10px)',
      }}
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          className="p-1.5 rounded-lg"
          style={{ background: 'rgba(255, 255, 255, 0.1)' }}
        >
          {Icon}
        </div>
        <span className="text-xs font-medium text-white/60 uppercase tracking-wider">
          {data.action}
        </span>
        <div className="ml-auto">
          {data.status === 'running' && (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            >
              <Loader2 className="w-4 h-4 text-blue-400" />
            </motion.div>
          )}
          {data.status === 'complete' && <CheckCircle className="w-4 h-4 text-green-400" />}
          {data.status === 'error' && <AlertCircle className="w-4 h-4 text-red-400" />}
        </div>
      </div>
      <p className="text-sm text-white/90 leading-snug">{data.description}</p>
      {data.target && (
        <p className="text-xs text-white/40 mt-1 truncate">{data.target}</p>
      )}
    </motion.div>
  );
}

const nodeTypes = {
  taskNode: CustomNode,
};

function convertPlanToGraph(plan: ExecutionPlan): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Group steps by their dependencies to create layers
  const layers: PlanStep[][] = [];
  const assigned = new Set<string>();

  // Find root nodes (no dependencies)
  const rootSteps = plan.steps.filter((s) => s.dependsOn.length === 0);
  if (rootSteps.length > 0) {
    layers.push(rootSteps);
    rootSteps.forEach((s) => assigned.add(s.id));
  }

  // Build remaining layers
  while (assigned.size < plan.steps.length) {
    const nextLayer: PlanStep[] = [];
    for (const step of plan.steps) {
      if (!assigned.has(step.id) && step.dependsOn.every((dep) => assigned.has(dep))) {
        nextLayer.push(step);
      }
    }
    if (nextLayer.length === 0) break;
    layers.push(nextLayer);
    nextLayer.forEach((s) => assigned.add(s.id));
  }

  // Position nodes
  const nodeWidth = 220;
  const nodeHeight = 100;
  const horizontalGap = 60;
  const verticalGap = 80;

  layers.forEach((layer, layerIndex) => {
    const totalWidth = layer.length * nodeWidth + (layer.length - 1) * horizontalGap;
    const startX = -totalWidth / 2 + nodeWidth / 2;

    layer.forEach((step, stepIndex) => {
      nodes.push({
        id: step.id,
        type: 'taskNode',
        position: {
          x: startX + stepIndex * (nodeWidth + horizontalGap),
          y: layerIndex * (nodeHeight + verticalGap),
        },
        data: step,
      });
    });
  });

  // Create edges
  for (const step of plan.steps) {
    for (const dep of step.dependsOn) {
      const sourceStep = plan.steps.find((s) => s.id === dep);
      edges.push({
        id: `${dep}-${step.id}`,
        source: dep,
        target: step.id,
        type: 'smoothstep',
        animated: sourceStep?.status === 'running',
        style: {
          stroke:
            sourceStep?.status === 'complete'
              ? 'rgba(16, 185, 129, 0.6)'
              : sourceStep?.status === 'running'
              ? 'rgba(59, 130, 246, 0.8)'
              : 'rgba(0, 245, 255, 0.3)',
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color:
            sourceStep?.status === 'complete'
              ? 'rgba(16, 185, 129, 0.8)'
              : 'rgba(0, 245, 255, 0.5)',
        },
      });
    }
  }

  return { nodes, edges };
}

export function TaskGraph({ plan, currentStep }: TaskGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Update graph when plan changes
  useEffect(() => {
    if (plan) {
      const { nodes: newNodes, edges: newEdges } = convertPlanToGraph(plan);
      setNodes(newNodes);
      setEdges(newEdges);
    } else {
      setNodes([]);
      setEdges([]);
    }
  }, [plan, setNodes, setEdges]);

  const defaultViewport = useMemo(() => ({ x: 400, y: 50, zoom: 0.9 }), []);

  return (
    <div className="w-full h-full relative">
      <AnimatePresence>
        {!plan ? (
          <motion.div
            className="absolute inset-0 flex flex-col items-center justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="w-24 h-24 rounded-2xl flex items-center justify-center mb-6"
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px dashed rgba(255, 255, 255, 0.1)',
              }}
              animate={{
                borderColor: ['rgba(255, 255, 255, 0.1)', 'rgba(0, 245, 255, 0.3)', 'rgba(255, 255, 255, 0.1)'],
              }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              <GitCompare className="w-10 h-10 text-white/20" />
            </motion.div>
            <p className="text-white/40 text-lg">Task graph will appear here</p>
            <p className="text-white/20 text-sm mt-2">Enter a command to get started</p>
          </motion.div>
        ) : (
          <motion.div
            className="w-full h-full"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              defaultViewport={defaultViewport}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="rgba(255, 255, 255, 0.03)" gap={20} />
              <Controls
                style={{
                  background: 'rgba(18, 18, 26, 0.9)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                }}
              />
            </ReactFlow>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default TaskGraph;
