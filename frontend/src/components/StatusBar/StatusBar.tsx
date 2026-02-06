import { motion } from 'framer-motion';
import { Bot, Wifi, WifiOff, Zap } from 'lucide-react';
import type { AgentState } from '../../types';

interface StatusBarProps {
  agentState: AgentState;
  isConnected: boolean;
}

export function StatusBar({ agentState, isConnected }: StatusBarProps) {
  const statusConfig = {
    idle: { color: 'text-white/40', bg: 'bg-white/10', label: 'Ready' },
    listening: { color: 'text-red-400', bg: 'bg-red-500/20', label: 'Listening' },
    thinking: { color: 'text-yellow-400', bg: 'bg-yellow-500/20', label: 'Thinking' },
    planning: { color: 'text-purple-400', bg: 'bg-purple-500/20', label: 'Planning' },
    executing: { color: 'text-accent-cyan', bg: 'bg-accent-cyan/20', label: 'Executing' },
    complete: { color: 'text-green-400', bg: 'bg-green-500/20', label: 'Complete' },
    error: { color: 'text-red-400', bg: 'bg-red-500/20', label: 'Error' },
  };

  const config = statusConfig[agentState.status];

  return (
    <motion.header
      className="flex items-center justify-between px-6 py-3 glass"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      style={{
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <motion.div
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{
            background: 'linear-gradient(135deg, rgba(0, 245, 255, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%)',
            border: '1px solid rgba(0, 245, 255, 0.3)',
          }}
          whileHover={{ scale: 1.05 }}
        >
          <Bot className="w-5 h-5 text-accent-cyan" />
        </motion.div>
        <div>
          <h1 className="text-lg font-semibold gradient-text">Nova Agent</h1>
        </div>
      </div>

      {/* Status indicators */}
      <div className="flex items-center gap-4">
        {/* Agent status */}
        <motion.div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${config.bg}`}
          animate={{
            scale: agentState.status === 'executing' ? [1, 1.02, 1] : 1,
          }}
          transition={{ duration: 0.5, repeat: agentState.status === 'executing' ? Infinity : 0 }}
        >
          {agentState.status !== 'idle' && agentState.status !== 'complete' && (
            <motion.div
              animate={{
                opacity: [1, 0.5, 1],
              }}
              transition={{ duration: 1, repeat: Infinity }}
            >
              <Zap className={`w-3.5 h-3.5 ${config.color}`} />
            </motion.div>
          )}
          <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
        </motion.div>

        {/* Connection status */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
            isConnected ? 'bg-green-500/10' : 'bg-red-500/10'
          }`}
        >
          {isConnected ? (
            <>
              <Wifi className="w-3.5 h-3.5 text-green-400" />
              <span className="text-sm text-green-400">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-red-400" />
              <span className="text-sm text-red-400">Disconnected</span>
            </>
          )}
        </div>
      </div>
    </motion.header>
  );
}

export default StatusBar;
