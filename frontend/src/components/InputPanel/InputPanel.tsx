import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Send, Sparkles, Loader2 } from 'lucide-react';
import type { AgentState } from '../../types';

interface InputPanelProps {
  agentState: AgentState;
  onSubmit: (command: string) => void;
  onVoiceStart: () => void;
  onVoiceEnd: () => void;
  isListening: boolean;
}

export function InputPanel({
  agentState,
  onSubmit,
  onVoiceStart,
  onVoiceEnd,
  isListening,
}: InputPanelProps) {
  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const isDisabled = agentState.status !== 'idle' && agentState.status !== 'complete' && agentState.status !== 'error';

  const handleSubmit = () => {
    if (inputValue.trim() && !isDisabled) {
      onSubmit(inputValue.trim());
      setInputValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleVoiceToggle = () => {
    if (isListening) {
      onVoiceEnd();
    } else {
      onVoiceStart();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px';
    }
  }, [inputValue]);

  const suggestedCommands = [
    "Find laptops under $800",
    "Compare iPhone prices across stores",
    "Search for best gaming monitors",
  ];

  return (
    <motion.div
      className="w-full max-w-2xl mx-auto"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Suggested commands */}
      <AnimatePresence>
        {agentState.status === 'idle' && !inputValue && (
          <motion.div
            className="flex flex-wrap gap-2 mb-4 justify-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            {suggestedCommands.map((cmd, index) => (
              <motion.button
                key={cmd}
                className="px-4 py-2 rounded-full text-sm text-white/60 hover:text-white/90 transition-all duration-300"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }}
                whileHover={{
                  scale: 1.05,
                  background: 'rgba(0, 245, 255, 0.1)',
                  borderColor: 'rgba(0, 245, 255, 0.3)',
                }}
                whileTap={{ scale: 0.95 }}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                onClick={() => setInputValue(cmd)}
              >
                <Sparkles className="w-3 h-3 inline-block mr-2 opacity-50" />
                {cmd}
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main input container */}
      <motion.div
        className={`relative rounded-2xl transition-all duration-300 ${
          isFocused ? 'glow-cyan' : ''
        }`}
        style={{
          background: 'rgba(18, 18, 26, 0.9)',
          border: `1px solid ${isFocused ? 'rgba(0, 245, 255, 0.5)' : 'rgba(255, 255, 255, 0.1)'}`,
        }}
        animate={{
          boxShadow: isFocused
            ? '0 0 30px rgba(0, 245, 255, 0.2), 0 0 60px rgba(0, 245, 255, 0.1)'
            : '0 0 0px rgba(0, 245, 255, 0)',
        }}
      >
        {/* Animated gradient border */}
        <AnimatePresence>
          {isFocused && (
            <motion.div
              className="absolute inset-0 rounded-2xl pointer-events-none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                background: 'linear-gradient(135deg, rgba(0, 245, 255, 0.1), rgba(168, 85, 247, 0.1), rgba(236, 72, 153, 0.1))',
              }}
            />
          )}
        </AnimatePresence>

        <div className="relative flex items-end p-2 gap-2">
          {/* Voice button */}
          <motion.button
            className={`relative flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${
              isListening
                ? 'bg-red-500/20 text-red-400'
                : 'bg-white/5 text-white/60 hover:text-white hover:bg-white/10'
            }`}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleVoiceToggle}
            disabled={isDisabled}
          >
            {/* Pulse animation when listening */}
            <AnimatePresence>
              {isListening && (
                <>
                  <motion.div
                    className="absolute inset-0 rounded-xl bg-red-500/30"
                    initial={{ scale: 1, opacity: 1 }}
                    animate={{ scale: 1.5, opacity: 0 }}
                    transition={{ duration: 1, repeat: Infinity }}
                  />
                  <motion.div
                    className="absolute inset-0 rounded-xl bg-red-500/20"
                    initial={{ scale: 1, opacity: 1 }}
                    animate={{ scale: 1.8, opacity: 0 }}
                    transition={{ duration: 1, repeat: Infinity, delay: 0.3 }}
                  />
                </>
              )}
            </AnimatePresence>
            {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </motion.button>

          {/* Text input */}
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? "Listening..." : "What would you like me to find?"}
            disabled={isDisabled}
            className="flex-1 bg-transparent text-white placeholder-white/40 outline-none resize-none py-3 px-2 text-base min-h-[48px] max-h-[120px] disabled:opacity-50"
            rows={1}
          />

          {/* Submit button */}
          <motion.button
            className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${
              inputValue.trim() && !isDisabled
                ? 'text-white'
                : 'bg-white/5 text-white/30 cursor-not-allowed'
            }`}
            style={{
              background: inputValue.trim() && !isDisabled
                ? 'linear-gradient(135deg, var(--accent-cyan), var(--accent-purple))'
                : undefined,
            }}
            whileHover={inputValue.trim() && !isDisabled ? { scale: 1.05 } : {}}
            whileTap={inputValue.trim() && !isDisabled ? { scale: 0.95 } : {}}
            onClick={handleSubmit}
            disabled={!inputValue.trim() || isDisabled}
          >
            {isDisabled && agentState.status !== 'complete' && agentState.status !== 'error' ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </motion.button>
        </div>
      </motion.div>

      {/* Status indicator */}
      <AnimatePresence>
        {agentState.status !== 'idle' && (
          <motion.div
            className="mt-4 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <motion.div
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full"
              style={{
                background: 'rgba(0, 245, 255, 0.1)',
                border: '1px solid rgba(0, 245, 255, 0.2)',
              }}
            >
              {agentState.status === 'complete' ? (
                <div className="w-2 h-2 rounded-full bg-green-400" />
              ) : agentState.status === 'error' ? (
                <div className="w-2 h-2 rounded-full bg-red-400" />
              ) : (
                <motion.div
                  className="w-2 h-2 rounded-full bg-accent-cyan"
                  animate={{ scale: [1, 1.2, 1], opacity: [1, 0.7, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                />
              )}
              <span className="text-sm text-white/70">{agentState.message}</span>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default InputPanel;
