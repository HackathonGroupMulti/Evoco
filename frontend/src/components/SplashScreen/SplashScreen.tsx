import { motion } from 'framer-motion';
import { Bot } from 'lucide-react';

interface SplashScreenProps {
  onComplete: () => void;
}

export function SplashScreen({ onComplete }: SplashScreenProps) {
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center mesh-gradient"
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5, delay: 2.5 }}
      onAnimationComplete={(definition) => {
        if (definition === 'exit' || (typeof definition === 'object' && 'opacity' in definition && definition.opacity === 0)) {
          onComplete();
        }
      }}
    >
      {/* Animated grid background */}
      <div className="absolute inset-0 grid-pattern opacity-50" />

      {/* Floating orbs */}
      <motion.div
        className="absolute w-96 h-96 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(0, 245, 255, 0.2) 0%, transparent 70%)',
          filter: 'blur(40px)',
        }}
        animate={{
          x: [0, 100, 0],
          y: [0, -50, 0],
          scale: [1, 1.2, 1],
        }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />
      <motion.div
        className="absolute w-80 h-80 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(168, 85, 247, 0.2) 0%, transparent 70%)',
          filter: 'blur(40px)',
          right: '20%',
          top: '20%',
        }}
        animate={{
          x: [0, -80, 0],
          y: [0, 60, 0],
          scale: [1, 1.3, 1],
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Main content */}
      <div className="relative flex flex-col items-center">
        {/* Logo with pulse rings */}
        <div className="relative mb-8">
          {/* Pulse rings */}
          <motion.div
            className="absolute inset-0 rounded-full border-2 border-accent-cyan/30"
            initial={{ scale: 0.8, opacity: 1 }}
            animate={{ scale: 2, opacity: 0 }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'easeOut',
            }}
            style={{ width: 120, height: 120, margin: '-20px' }}
          />
          <motion.div
            className="absolute inset-0 rounded-full border-2 border-accent-purple/30"
            initial={{ scale: 0.8, opacity: 1 }}
            animate={{ scale: 2, opacity: 0 }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'easeOut',
              delay: 0.5,
            }}
            style={{ width: 120, height: 120, margin: '-20px' }}
          />

          {/* Logo container */}
          <motion.div
            className="relative w-20 h-20 rounded-2xl flex items-center justify-center glow-cyan"
            style={{
              background: 'linear-gradient(135deg, rgba(0, 245, 255, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%)',
              border: '1px solid rgba(0, 245, 255, 0.3)',
            }}
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{
              type: 'spring',
              stiffness: 200,
              damping: 20,
              delay: 0.2,
            }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.5, duration: 0.3 }}
            >
              <Bot className="w-10 h-10 text-accent-cyan" />
            </motion.div>
          </motion.div>
        </div>

        {/* Title */}
        <motion.h1
          className="text-5xl font-bold mb-3 gradient-text"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.5 }}
        >
          Nova Agent
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          className="text-lg text-white/60 mb-12"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.5 }}
        >
          Autonomous Web Intelligence
        </motion.p>

        {/* Loading bar */}
        <motion.div
          className="w-64 h-1 rounded-full overflow-hidden"
          style={{ background: 'rgba(255, 255, 255, 0.1)' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
        >
          <motion.div
            className="h-full rounded-full"
            style={{
              background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-purple), var(--accent-pink))',
            }}
            initial={{ width: '0%' }}
            animate={{ width: '100%' }}
            transition={{
              delay: 1.2,
              duration: 1.5,
              ease: 'easeInOut',
            }}
            onAnimationComplete={() => {
              setTimeout(onComplete, 300);
            }}
          />
        </motion.div>

        {/* Loading text */}
        <motion.p
          className="mt-4 text-sm text-white/40"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2 }}
        >
          Initializing agent systems...
        </motion.p>
      </div>
    </motion.div>
  );
}

export default SplashScreen;
