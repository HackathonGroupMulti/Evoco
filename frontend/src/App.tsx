import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { SplashScreen } from './components/SplashScreen';
import { StatusBar } from './components/StatusBar';
import { InputPanel } from './components/InputPanel';
import { TaskGraph } from './components/TaskGraph';
import { ResultsPanel } from './components/ResultsPanel';
import type { AgentState, ExecutionPlan, Product, PlanStep } from './types';

// Mock data for demo purposes
const createMockPlan = (command: string): ExecutionPlan => ({
  taskSummary: `Searching for: ${command}`,
  steps: [
    {
      id: 'nav-amazon',
      action: 'navigate',
      target: 'https://amazon.com',
      description: 'Search Amazon',
      dependsOn: [],
      status: 'pending',
    },
    {
      id: 'nav-bestbuy',
      action: 'navigate',
      target: 'https://bestbuy.com',
      description: 'Search Best Buy',
      dependsOn: [],
      status: 'pending',
    },
    {
      id: 'nav-newegg',
      action: 'navigate',
      target: 'https://newegg.com',
      description: 'Search Newegg',
      dependsOn: [],
      status: 'pending',
    },
    {
      id: 'extract-amazon',
      action: 'extract',
      target: 'product-list',
      description: 'Extract Amazon products',
      dependsOn: ['nav-amazon'],
      status: 'pending',
    },
    {
      id: 'extract-bestbuy',
      action: 'extract',
      target: 'product-list',
      description: 'Extract Best Buy products',
      dependsOn: ['nav-bestbuy'],
      status: 'pending',
    },
    {
      id: 'extract-newegg',
      action: 'extract',
      target: 'product-list',
      description: 'Extract Newegg products',
      dependsOn: ['nav-newegg'],
      status: 'pending',
    },
    {
      id: 'compare',
      action: 'compare',
      target: 'all-products',
      description: 'Compare prices & ratings',
      dependsOn: ['extract-amazon', 'extract-bestbuy', 'extract-newegg'],
      status: 'pending',
    },
    {
      id: 'summarize',
      action: 'summarize',
      target: 'comparison-result',
      description: 'Generate recommendation',
      dependsOn: ['compare'],
      status: 'pending',
    },
  ],
});

const mockProducts: Product[] = [
  { name: 'Lenovo IdeaPad 3 15.6" Laptop', price: 549.99, rating: 4.5, source: 'amazon', url: '#' },
  { name: 'HP Pavilion 15.6" Touch Laptop', price: 629.99, rating: 4.3, source: 'bestbuy', url: '#' },
  { name: 'ASUS VivoBook 15 Laptop', price: 479.99, rating: 4.4, source: 'newegg', url: '#' },
  { name: 'Acer Aspire 5 Slim Laptop', price: 599.99, rating: 4.6, source: 'amazon', url: '#' },
  { name: 'Dell Inspiron 15 3000', price: 699.99, rating: 4.2, source: 'bestbuy', url: '#' },
  { name: 'HP 15.6" Laptop', price: 449.99, rating: 4.1, source: 'newegg', url: '#' },
];

function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [showApp, setShowApp] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isConnected] = useState(true); // Simulated connection

  const [agentState, setAgentState] = useState<AgentState>({
    status: 'idle',
    message: '',
    plan: null,
    results: [],
    currentStep: null,
  });

  // Handle splash screen completion
  const handleSplashComplete = useCallback(() => {
    setShowSplash(false);
    // Small delay before showing app with animation
    setTimeout(() => setShowApp(true), 100);
  }, []);

  // Simulate command execution
  const handleSubmit = useCallback((command: string) => {
    const plan = createMockPlan(command);

    setAgentState({
      status: 'planning',
      message: 'Generating execution plan...',
      plan: null,
      results: [],
      currentStep: null,
    });

    // Simulate planning phase
    setTimeout(() => {
      setAgentState((prev) => ({
        ...prev,
        status: 'executing',
        message: 'Executing plan...',
        plan,
      }));

      // Simulate step execution
      let stepIndex = 0;
      const executeNextStep = () => {
        if (stepIndex >= plan.steps.length) {
          setAgentState((prev) => ({
            ...prev,
            status: 'complete',
            message: 'Task completed successfully!',
            results: mockProducts,
            currentStep: null,
          }));
          return;
        }

        const currentStepId = plan.steps[stepIndex].id;

        // Mark current step as running
        setAgentState((prev) => ({
          ...prev,
          currentStep: currentStepId,
          plan: prev.plan
            ? {
                ...prev.plan,
                steps: prev.plan.steps.map((s) =>
                  s.id === currentStepId ? { ...s, status: 'running' as const } : s
                ),
              }
            : null,
        }));

        // Complete step after delay
        setTimeout(() => {
          setAgentState((prev) => ({
            ...prev,
            plan: prev.plan
              ? {
                  ...prev.plan,
                  steps: prev.plan.steps.map((s) =>
                    s.id === currentStepId ? { ...s, status: 'complete' as const } : s
                  ),
                }
              : null,
          }));

          stepIndex++;
          setTimeout(executeNextStep, 300);
        }, 800 + Math.random() * 400);
      };

      setTimeout(executeNextStep, 500);
    }, 1500);
  }, []);

  // Voice handlers
  const handleVoiceStart = useCallback(() => {
    setIsListening(true);
    setAgentState((prev) => ({
      ...prev,
      status: 'listening',
      message: 'Listening...',
    }));
  }, []);

  const handleVoiceEnd = useCallback(() => {
    setIsListening(false);
    // Simulate voice transcription
    setAgentState((prev) => ({
      ...prev,
      status: 'thinking',
      message: 'Processing voice input...',
    }));

    setTimeout(() => {
      handleSubmit('Find laptops under $800');
    }, 1000);
  }, [handleSubmit]);

  return (
    <div className="h-screen w-screen overflow-hidden mesh-gradient">
      {/* Splash Screen */}
      <AnimatePresence>
        {showSplash && <SplashScreen onComplete={handleSplashComplete} />}
      </AnimatePresence>

      {/* Main App */}
      <AnimatePresence>
        {showApp && (
          <motion.div
            className="h-full flex flex-col"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            {/* Status Bar */}
            <StatusBar agentState={agentState} isConnected={isConnected} />

            {/* Main Content */}
            <div className="flex-1 flex overflow-hidden">
              {/* Left Panel - Task Graph */}
              <motion.div
                className="flex-1 p-6 overflow-hidden"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2, duration: 0.5 }}
              >
                <TaskGraph plan={agentState.plan} currentStep={agentState.currentStep} />
              </motion.div>

              {/* Right Panel - Results */}
              <motion.div
                className="w-[450px] p-6 border-l border-white/5 overflow-hidden"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3, duration: 0.5 }}
              >
                <ResultsPanel
                  results={agentState.results}
                  isLoading={agentState.status === 'executing'}
                />
              </motion.div>
            </div>

            {/* Bottom Input Panel */}
            <motion.div
              className="p-6 pt-4"
              style={{
                borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                background: 'rgba(10, 10, 15, 0.8)',
              }}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              <InputPanel
                agentState={agentState}
                onSubmit={handleSubmit}
                onVoiceStart={handleVoiceStart}
                onVoiceEnd={handleVoiceEnd}
                isListening={isListening}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
