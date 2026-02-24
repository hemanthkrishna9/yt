"use client";

import { useEffect, useRef } from "react";
import { useJobSSE } from "../hooks/useJobSSE";
import { motion } from "framer-motion";
import { Terminal, AlertCircle } from "lucide-react";

interface Props {
  jobId: string;
  onDone: (outcome: "completed" | "failed") => void;
}

const STATUS_COLORS: Record<string, string> = {
  connecting: "bg-yellow-500",
  streaming: "bg-indigo-500",
  done: "bg-emerald-500",
  failed: "bg-red-500",
};

export default function JobProgress({ jobId, onDone }: Props) {
  const { lines, status, error } = useJobSSE(jobId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  useEffect(() => {
    if (status === "done") onDone("completed");
    else if (status === "failed") onDone("failed");
  }, [status, onDone]);

  return (
    <div className="mt-4">
      {/* Status bar */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[status]} animate-pulse`} />
        <span className="text-sm font-medium text-zinc-300 capitalize">{status}</span>
        <span className="text-xs text-zinc-600 font-mono">ID: {jobId.slice(0, 8)}</span>
      </div>

      {/* Terminal window */}
      <div className="rounded-xl overflow-hidden border border-white/[0.06]">
        {/* macOS title bar */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-zinc-900/80 border-b border-white/[0.06]">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
            <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
            <span className="w-3 h-3 rounded-full bg-[#28c840]" />
          </div>
          <div className="flex items-center gap-1.5 ml-3 text-zinc-500">
            <Terminal className="w-3.5 h-3.5" />
            <span className="text-xs font-medium">job output</span>
          </div>
        </div>

        {/* Terminal body */}
        <div className="bg-[--terminal-bg] p-4 h-80 overflow-y-auto font-mono text-xs terminal-scroll">
          {lines.map((line, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="whitespace-pre-wrap text-emerald-400/90 leading-relaxed"
            >
              {line}
            </motion.div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm text-red-400">
            <span className="font-medium">Error: </span>{error}
          </p>
        </div>
      )}
    </div>
  );
}
