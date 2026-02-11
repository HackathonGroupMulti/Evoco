import { Card, CardContent } from "@/components/ui/card";

interface ThinkingOverlayProps {
  reasoning: string | null;
}

const FALLBACK_MESSAGES = [
  "Analyzing your request and identifying the best approach...",
  "Determining which sites to search and what data to extract...",
  "Building an execution plan with parallel branches for speed...",
];

export function ThinkingOverlay({ reasoning }: ThinkingOverlayProps) {
  return (
    <Card className="glass-panel flex h-full flex-col border-border/30 overflow-hidden">
      <CardContent className="flex-1 flex items-center justify-center p-8">
        <div
          className="flex flex-col items-center gap-6 max-w-md text-center"
          style={{ animation: "hero-fade-in 0.4s ease-out" }}
        >
          {/* Animated brain/thinking icon */}
          <div className="relative">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20 border border-neon-cyan/30 flex items-center justify-center">
              <span className="text-2xl">{"\u{1F9E0}"}</span>
            </div>
            {/* Radar sweep */}
            <div className="absolute inset-0 rounded-2xl overflow-hidden">
              <div
                className="absolute inset-0"
                style={{
                  background: "conic-gradient(from 0deg, transparent 0%, var(--neon-cyan) 10%, transparent 20%)",
                  animation: "radar-sweep 2s linear infinite",
                  opacity: 0.15,
                }}
              />
            </div>
            {/* Expanding rings */}
            <div className="absolute inset-0 rounded-2xl" style={{ animation: "ring-expand 2s ease-out infinite" }}>
              <div className="h-full w-full rounded-2xl border border-neon-cyan/30" />
            </div>
            <div className="absolute inset-0 rounded-2xl" style={{ animation: "ring-expand 2s ease-out infinite 0.6s" }}>
              <div className="h-full w-full rounded-2xl border border-neon-cyan/20" />
            </div>
          </div>

          {/* Title */}
          <div>
            <h3 className="text-lg font-semibold bg-gradient-to-r from-neon-cyan to-neon-purple bg-clip-text text-transparent">
              Planning your research
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
              <p className="text-sm text-foreground/80 leading-relaxed italic">
                "{reasoning}"
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {FALLBACK_MESSAGES.map((msg, i) => (
                  <p
                    key={i}
                    className="text-xs text-muted-foreground/60 leading-relaxed"
                    style={{ animation: `float-up 0.4s ease-out ${i * 0.15}s both` }}
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
