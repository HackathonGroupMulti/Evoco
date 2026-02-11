import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import type { TaskResult } from "@/types";
import type { ConnectionState } from "@/hooks/useTaskRunner";

interface ResultsPanelProps {
  result: TaskResult | null;
  connectionState: ConnectionState;
}

export function ResultsPanel({ result, connectionState }: ResultsPanelProps) {
  const isRunning = connectionState === "connecting" || connectionState === "running";

  return (
    <Card className="glass-panel flex h-full flex-col border-border/30">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-neon-emerald animate-glow-pulse" />
            <span className="bg-gradient-to-r from-neon-emerald to-neon-cyan bg-clip-text text-transparent">
              Results
            </span>
          </CardTitle>
          {result?.duration_ms != null && (
            <Badge
              variant="outline"
              className="text-[10px] border-neon-emerald/30 text-neon-emerald/80"
            >
              {(result.duration_ms / 1000).toFixed(1)}s
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden">
        {!result && !isRunning && (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-neon-emerald/10 to-neon-cyan/10 border border-neon-emerald/20 flex items-center justify-center">
                <span className="text-lg text-neon-emerald/40">{"\u{1F4C4}"}</span>
              </div>
              <p className="text-sm text-muted-foreground/40 italic">
                Results will appear here
              </p>
            </div>
          </div>
        )}

        {isRunning && !result && (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-4">
              <div className="relative h-10 w-10">
                <span className="absolute inset-0 rounded-full border-2 border-neon-cyan/20" />
                <span className="absolute inset-0 rounded-full border-2 border-neon-cyan border-t-transparent animate-spin" />
              </div>
              <p className="text-sm text-neon-cyan/60">Processing…</p>
            </div>
          </div>
        )}

        {result && <ResultContent result={result} />}
      </CardContent>
    </Card>
  );
}

function ResultContent({ result }: { result: TaskResult }) {
  if (result.status === "failed") {
    return (
      <div className="rounded-lg bg-gradient-to-br from-neon-rose/10 to-neon-amber/5 border border-neon-rose/30 p-4 glow-rose">
        <p className="text-sm font-semibold text-neon-rose">Task failed</p>
        <p className="mt-1.5 text-xs text-muted-foreground">{result.error}</p>
      </div>
    );
  }

  return (
    <Tabs defaultValue="formatted" className="flex h-full flex-col">
      <TabsList className="w-full shrink-0 bg-secondary/30">
        <TabsTrigger
          value="formatted"
          className="flex-1 data-[state=active]:bg-gradient-to-r data-[state=active]:from-neon-cyan/10 data-[state=active]:to-neon-purple/10 data-[state=active]:text-foreground"
        >
          Formatted
        </TabsTrigger>
        <TabsTrigger
          value="raw"
          className="flex-1 data-[state=active]:bg-gradient-to-r data-[state=active]:from-neon-cyan/10 data-[state=active]:to-neon-purple/10 data-[state=active]:text-foreground"
        >
          Raw
        </TabsTrigger>
      </TabsList>
      <TabsContent value="formatted" className="flex-1 overflow-hidden mt-3">
        <ScrollArea className="h-full">
          <FormattedOutput result={result} />
        </ScrollArea>
      </TabsContent>
      <TabsContent value="raw" className="flex-1 overflow-hidden mt-3">
        <ScrollArea className="h-full">
          <pre className="whitespace-pre-wrap text-xs font-mono text-neon-cyan/60 leading-relaxed p-3 rounded-lg bg-background/50 border border-border/30">
            {typeof result.output === "string"
              ? result.output
              : JSON.stringify(result.output, null, 2)}
          </pre>
        </ScrollArea>
      </TabsContent>
    </Tabs>
  );
}

function FormattedOutput({ result }: { result: TaskResult }) {
  const output = result.output as Record<string, unknown> | string | null;

  if (typeof output === "string") {
    return (
      <pre className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        {output}
      </pre>
    );
  }

  if (!output || typeof output !== "object") {
    return <p className="text-sm text-muted-foreground">No output</p>;
  }

  const products = (output.results ?? output.ranked ?? []) as Array<{
    name: string;
    price: number;
    rating: number;
    source: string;
  }>;

  const summary = output.summary as string | undefined;

  return (
    <div className="flex flex-col gap-3 pr-3">
      {summary && (
        <div className="rounded-lg bg-gradient-to-br from-neon-cyan/[0.08] to-neon-purple/[0.06] border border-neon-cyan/20 p-3.5 glow-cyan">
          <p className="text-sm text-foreground leading-relaxed">{summary}</p>
        </div>
      )}

      {products.length > 0 && (
        <div className="flex flex-col gap-2">
          {products.map((p, i) => (
            <div
              key={`${p.name}-${i}`}
              className="group flex items-center justify-between gap-3 rounded-lg border border-border/30 bg-card/40 px-3 py-2.5 transition-all duration-200 hover:bg-neon-cyan/[0.04] hover:border-neon-cyan/20"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-neon-cyan/50 w-4">
                    {i + 1}
                  </span>
                  <p className="text-sm font-medium text-foreground truncate group-hover:text-neon-cyan transition-colors">
                    {p.name}
                  </p>
                </div>
                <p className="text-[11px] text-muted-foreground/60 ml-6">{p.source}</p>
              </div>
              <div className="flex items-center gap-2.5 shrink-0">
                <span className="text-sm font-bold bg-gradient-to-r from-neon-emerald to-neon-cyan bg-clip-text text-transparent">
                  ${p.price}
                </span>
                <Badge
                  variant="secondary"
                  className="text-[10px] bg-neon-amber/10 text-neon-amber border-neon-amber/20"
                >
                  {p.rating}
                  {"\u2605"}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}

      {products.length === 0 && !summary && (
        <pre className="whitespace-pre-wrap text-xs font-mono text-muted-foreground">
          {JSON.stringify(output, null, 2)}
        </pre>
      )}
    </div>
  );
}
