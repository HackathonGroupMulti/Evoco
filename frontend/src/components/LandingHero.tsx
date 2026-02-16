import { useState } from "react";
import type { FormEvent } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { VoiceOrb } from "@/components/VoiceOrb";
import type { DemoScenario, OutputFormat } from "@/types";

interface LandingHeroProps {
  onSubmit: (command: string, format: OutputFormat) => void;
  mode: "live" | "mock" | "unknown";
}

const DEMO_SCENARIOS: DemoScenario[] = [
  {
    title: "Best laptops under $800",
    command: "Find the best laptop under $800 from Amazon and Best Buy, compare prices and ratings",
    icon: "\u{1F4BB}",
    color: "from-neon-cyan/10 to-neon-cyan/5 border-neon-cyan/15 hover:border-neon-cyan/30",
  },
  {
    title: "Top noise-cancelling headphones",
    command: "Find the top-rated noise-cancelling headphones under $300 on Amazon and compare them",
    icon: "\u{1F3A7}",
    color: "from-neon-purple/10 to-neon-purple/5 border-neon-purple/15 hover:border-neon-purple/30",
  },
  {
    title: "Best espresso machines",
    command: "Research the best espresso machines under $500 from Amazon and Best Buy, rank by value",
    icon: "\u{2615}",
    color: "from-neon-amber/10 to-neon-amber/5 border-neon-amber/15 hover:border-neon-amber/30",
  },
  {
    title: "Gaming monitor deals",
    command: "Find the best 27-inch gaming monitors under $400 on Amazon and Newegg, compare specs",
    icon: "\u{1F5A5}",
    color: "from-neon-emerald/10 to-neon-emerald/5 border-neon-emerald/15 hover:border-neon-emerald/30",
  },
];

export function LandingHero({ onSubmit, mode }: LandingHeroProps) {
  const [command, setCommand] = useState("");
  const [format] = useState<OutputFormat>("summary");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = command.trim();
    if (!trimmed) return;
    onSubmit(trimmed, format);
  }

  function handleScenario(scenario: DemoScenario) {
    onSubmit(scenario.command, "summary");
  }

  return (
    <div className="relative flex flex-1 flex-col items-center justify-center px-6">
      {/* Hero content */}
      <div className="flex flex-col items-center gap-8 max-w-2xl w-full" style={{ animation: "hero-fade-in 0.6s ease-out" }}>
        {/* Entity Orb + Title */}
        <div className="flex flex-col items-center gap-5">
          <div className="relative flex flex-col items-center">
            {/* Neural pulse rings */}
            <div className="relative flex items-center justify-center">
              <div className="absolute h-28 w-28 rounded-full border border-neon-cyan/10" style={{ animation: "neural-pulse 4s ease-out infinite" }} />
              <div className="absolute h-28 w-28 rounded-full border border-neon-cyan/10" style={{ animation: "neural-pulse 4s ease-out infinite 1.3s" }} />
              <div className="absolute h-28 w-28 rounded-full border border-neon-purple/8" style={{ animation: "neural-pulse 4s ease-out infinite 2.6s" }} />
              {/* Core orb */}
              <div className="h-20 w-20 rounded-full entity-orb" />
            </div>
            {/* Voice orb overlaid at bottom of entity */}
            <div className="-mt-3 relative z-10">
              <VoiceOrb
                onTranscript={(text) => setCommand(text)}
                onComplete={(text) => onSubmit(text, "summary")}
              />
            </div>
          </div>

          <div className="text-center">
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="bg-gradient-to-r from-neon-cyan via-neon-purple to-neon-emerald bg-clip-text text-transparent">
                What would you like me to find?
              </span>
            </h1>
            <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
              I explore the web autonomously, searching multiple sites in parallel
              and synthesizing what I discover into clear, structured understanding.
            </p>
          </div>
        </div>

        {/* Search input */}
        <form onSubmit={handleSubmit} className="w-full max-w-lg">
          <div className="gradient-border rounded-xl transition-shadow duration-300 focus-within:shadow-[0_0_30px_rgba(6,182,212,0.15)]">
            <div className="flex items-center gap-2 rounded-xl bg-card/80 px-4 py-1">
              <span className="text-muted-foreground/40 text-lg">{"\u{1F50D}"}</span>
              <Input
                placeholder="Tell me what you're looking for..."
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                className="border-0 bg-transparent text-base focus-visible:ring-0 placeholder:text-muted-foreground/30"
              />
              <Button
                type="submit"
                disabled={!command.trim()}
                size="sm"
                className="shrink-0 bg-gradient-to-r from-neon-cyan to-neon-purple text-white font-semibold hover:shadow-[0_0_20px_rgba(6,182,212,0.3)] disabled:opacity-30 transition-all"
              >
                Ask
              </Button>
            </div>
          </div>
        </form>

        {/* Suggested thoughts */}
        <div className="w-full max-w-lg">
          <p className="text-center text-[11px] font-medium uppercase tracking-widest text-muted-foreground/40 mb-3">
            Suggested thoughts
          </p>
          <div className="grid grid-cols-2 gap-2.5 stagger-children">
            {DEMO_SCENARIOS.map((scenario) => (
              <button
                key={scenario.title}
                onClick={() => handleScenario(scenario)}
                className={`group flex items-center gap-3 rounded-2xl border bg-gradient-to-br px-4 py-3 text-left transition-all duration-300 hover:shadow-lg hover:scale-[1.02] ${scenario.color}`}
              >
                <span className="text-xl">{scenario.icon}</span>
                <span className="text-sm font-medium text-foreground/80 group-hover:text-foreground transition-colors">
                  {scenario.title}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Mode badge */}
        {mode !== "unknown" && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground/40">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                mode === "live" ? "bg-neon-emerald shadow-[0_0_4px_var(--neon-emerald)]" : "bg-neon-amber shadow-[0_0_4px_var(--neon-amber)]"
              }`}
            />
            {mode === "live" ? "Awake" : "Dreaming"}
          </div>
        )}
      </div>
    </div>
  );
}
