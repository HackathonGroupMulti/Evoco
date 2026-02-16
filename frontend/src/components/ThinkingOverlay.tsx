import { Card, CardContent } from "@/components/ui/card";

interface ThinkingOverlayProps {
  reasoning: string | null;
}

const FALLBACK_MESSAGES = [
  "Processing your request... forming initial connections...",
  "Mapping the information landscape... identifying key sources...",
  "Synthesizing an approach... preparing to explore...",
];

export function ThinkingOverlay({ reasoning }: ThinkingOverlayProps) {
  return (
    <Card className="glass-panel flex h-full flex-col border-border/30 overflow-hidden">
      <CardContent className="flex-1 flex items-center justify-center p-8">
        <div
          className="flex flex-col items-center gap-6 max-w-md text-center"
          style={{ animation: "hero-fade-in 0.4s ease-out" }}
        >
          {/* Entity orb — active state with neural pulses */}
          <div className="relative flex items-center justify-center">
            <div className="absolute h-20 w-20 rounded-full border border-neon-cyan/20" style={{ animation: "neural-pulse 2s ease-out infinite" }} />
            <div className="absolute h-20 w-20 rounded-full border border-neon-cyan/15" style={{ animation: "neural-pulse 2s ease-out infinite 0.5s" }} />
            <div className="absolute h-20 w-20 rounded-full border border-neon-purple/10" style={{ animation: "neural-pulse 2s ease-out infinite 1s" }} />
            <div className="absolute h-20 w-20 rounded-full border border-neon-purple/8" style={{ animation: "neural-pulse 2s ease-out infinite 1.5s" }} />
            {/* Active core orb */}
            <div className="h-16 w-16 rounded-full entity-orb-active" />
          </div>

          {/* Title */}
          <div>
            <h3 className="text-lg font-semibold bg-gradient-to-r from-neon-cyan to-neon-purple bg-clip-text text-transparent">
              Forming understanding...
            </h3>
            <div className="flex items-center justify-center gap-1 mt-2">
              <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-neon-cyan" />
              <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-neon-cyan" />
              <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-neon-cyan" />
            </div>
          </div>

          {/* Reasoning text or fallback */}
          <div className="rounded-xl bg-neon-cyan/[0.05] border border-neon-cyan/10 p-4 w-full">
            {reasoning ? (
              <p className="text-sm text-foreground/80 leading-relaxed" style={{ animation: "typewriter-fade 0.5s ease-out" }}>
                {reasoning}
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {FALLBACK_MESSAGES.map((msg, i) => (
                  <p
                    key={i}
                    className="text-xs text-muted-foreground/60 leading-relaxed"
                    style={{ animation: `typewriter-fade 0.6s ease-out ${i * 0.2}s both` }}
                  >
                    {msg}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
