import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AuthPageProps {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<void>;
}

export function AuthPage({ onLogin, onRegister }: AuthPageProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await onLogin(email, password);
      } else {
        await onRegister(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dark flex h-screen flex-col items-center justify-center bg-background text-foreground overflow-hidden">
      {/* Ambient glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-[40%] -left-[20%] h-[80%] w-[60%] rounded-full bg-neon-cyan/[0.03] blur-[120px]" />
        <div className="absolute -bottom-[30%] -right-[20%] h-[70%] w-[50%] rounded-full bg-neon-purple/[0.04] blur-[120px]" />
      </div>

      {/* Logo */}
      <div className="relative mb-8 flex flex-col items-center gap-3">
        <div className="h-10 w-10 rounded-full entity-orb-mini shadow-[0_0_32px_rgba(6,182,212,0.3)]" />
        <h1 className="text-2xl font-semibold tracking-widest lowercase">
          <span className="bg-gradient-to-r from-neon-cyan to-neon-purple bg-clip-text text-transparent">
            evoco
          </span>
        </h1>
        <p className="text-xs text-muted-foreground/60 tracking-wider">
          Autonomous web intelligence
        </p>
      </div>

      <Card className="glass-panel relative w-full max-w-sm border-border/30">
        <CardHeader className="pb-4">
          <CardTitle className="text-center text-xs font-medium tracking-widest uppercase">
            <span className="bg-gradient-to-r from-neon-cyan to-neon-emerald bg-clip-text text-transparent">
              {mode === "login" ? "Sign In" : "Create Account"}
            </span>
          </CardTitle>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="gradient-border rounded-lg">
              <Input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                className="border-0 bg-background/50 focus-visible:ring-neon-cyan/30"
              />
            </div>

            <div className="gradient-border rounded-lg">
              <Input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading}
                className="border-0 bg-background/50 focus-visible:ring-neon-cyan/30"
              />
            </div>

            {error && (
              <div className="rounded-md border border-neon-rose/30 bg-neon-rose/[0.08] px-3 py-2 text-xs text-neon-rose">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading || !email || !password}
              className="mt-1 bg-gradient-to-r from-neon-cyan to-neon-purple text-white font-semibold hover:from-neon-cyan/90 hover:to-neon-purple/90 transition-all duration-300 hover:shadow-[0_0_20px_rgba(6,182,212,0.3)] disabled:opacity-40"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span
                    className="h-3 w-3 rounded-full border-2 border-white/70 border-t-transparent"
                    style={{ animation: "breathe 1.5s ease-in-out infinite" }}
                  />
                  {mode === "login" ? "Signing in..." : "Creating account..."}
                </span>
              ) : mode === "login" ? (
                "Sign In"
              ) : (
                "Create Account"
              )}
            </Button>
          </form>

          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="text-xs text-muted-foreground/60 hover:text-neon-cyan transition-colors"
            >
              {mode === "login"
                ? "No account? Create one"
                : "Already have an account? Sign in"}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
