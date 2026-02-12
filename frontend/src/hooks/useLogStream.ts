import { useCallback, useEffect, useRef, useState } from "react";

export interface LogEntry {
  ts: string;
  level: string;
  logger: string;
  message: string;
  traceback?: string;
}

const MAX_ENTRIES = 500;
const WS_RETRY_MS = 2000;
const WS_MAX_RETRIES = 5;

export function useLogStream() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    // Fetch initial backlog
    fetch("/api/logs?limit=200")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: LogEntry[]) => {
        if (mountedRef.current) setEntries(data);
      })
      .catch((err) => {
        console.warn("[LogStream] Failed to fetch backlog:", err);
      });

    function connectWs() {
      if (!mountedRef.current) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/logs`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (mountedRef.current) {
          setConnected(true);
          retryRef.current = 0;
        }
      };

      ws.onmessage = (msg) => {
        if (!mountedRef.current) return;
        try {
          const entry: LogEntry = JSON.parse(msg.data);
          setEntries((prev) => {
            const next = [...prev, entry];
            return next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next;
          });
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        // Auto-retry with back-off
        if (retryRef.current < WS_MAX_RETRIES) {
          retryRef.current += 1;
          setTimeout(connectWs, WS_RETRY_MS * retryRef.current);
        }
      };

      ws.onerror = () => {
        // onclose fires after onerror, retry happens there
        if (mountedRef.current) setConnected(false);
      };
    }

    connectWs();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  const clear = useCallback(() => setEntries([]), []);

  return { entries, connected, clear };
}
