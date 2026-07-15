"use client";

// lib/useLiveFeed.ts — subscribes to the gateway's /ws/requests broadcast.
// Owns: SSR safety, exponential-backoff reconnect, and a bounded rolling buffer.

import { useEffect, useRef, useState } from "react";
import type { LiveEvent } from "@/lib/types";

export type FeedStatus = "connecting" | "open" | "closed";

export interface LiveFeed {
  events: LiveEvent[];
  status: FeedStatus;
}

export function useLiveFeed(max = 50): LiveFeed {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [status, setStatus] = useState<FeedStatus>("connecting");

  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // SSR guard: there is no WebSocket during server render. useEffect never runs
    // on the server, and this extra check keeps us safe under any renderer.
    if (typeof window === "undefined") return;

    const url =
      process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/requests";
    let closedByUnmount = false;

    const connect = () => {
      setStatus("connecting");
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0; // reset backoff on a successful connection
        setStatus("open");
      };

      ws.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data) as LiveEvent;
          if (ev.type !== "request") return;
          setEvents((prev) => [ev, ...prev].slice(0, max)); // prepend, bounded
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        setStatus("closed");
        if (closedByUnmount) return;
        // Exponential backoff capped at 15s.
        const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
        retryRef.current += 1;
        timerRef.current = setTimeout(connect, delay);
      };

      // Funnel errors into onclose so retry logic lives in one place.
      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      // Cleanup on unmount / Fast Refresh / StrictMode double-mount.
      closedByUnmount = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [max]);

  return { events, status };
}
