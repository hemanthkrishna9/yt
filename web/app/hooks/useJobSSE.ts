"use client";

import { useEffect, useRef, useState } from "react";
import { getEventsUrl } from "../lib/api";

export function useJobSSE(jobId: string | null) {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState<"connecting" | "streaming" | "done" | "failed">("connecting");
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    setLines([]);
    setStatus("connecting");
    setError(null);

    const es = new EventSource(getEventsUrl(jobId));
    esRef.current = es;

    es.onopen = () => setStatus("streaming");

    es.onmessage = (e) => {
      setLines((prev) => [...prev, e.data]);
    };

    es.addEventListener("error", (e) => {
      setError((e as MessageEvent).data);
    });

    es.addEventListener("done", (e) => {
      const data = (e as MessageEvent).data;
      setStatus(data === "completed" ? "done" : "failed");
      es.close();
    });

    es.onerror = () => {
      setStatus("failed");
      es.close();
    };

    return () => {
      es.close();
    };
  }, [jobId]);

  return { lines, status, error };
}
