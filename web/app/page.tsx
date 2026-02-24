"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Config, getConfig } from "./lib/api";
import { isLoggedIn, getEmail, logout } from "./lib/auth";
import DubForm from "./components/DubForm";
import JobProgress from "./components/JobProgress";
import DownloadButton from "./components/DownloadButton";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, LogOut, Sparkles } from "lucide-react";

export default function Home() {
  const router = useRouter();
  const [config, setConfig] = useState<Config | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobDone, setJobDone] = useState(false);
  const [jobStatus, setJobStatus] = useState<"running" | "completed" | "failed">("running");
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }
    setAuthChecked(true);
    getConfig().then(setConfig).catch(console.error);
  }, [router]);

  function handleJobStarted(id: string) {
    setJobId(id);
    setJobDone(false);
    setJobStatus("running");
  }

  const handleDone = useCallback((outcome: "completed" | "failed") => {
    setJobDone(true);
    setJobStatus(outcome);
  }, []);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  if (!authChecked || !config) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-2xl mx-auto py-12 px-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-indigo-400" />
            <span className="gradient-text">YT Dubber</span>
          </h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-500">{getEmail()}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              Logout
            </button>
          </div>
        </div>
        <p className="text-zinc-500 mb-8">Dub YouTube videos in Indian languages</p>
        <div className="h-px bg-white/[0.06] mb-8" />

        {/* Form card */}
        <AnimatePresence mode="wait">
          {!jobId ? (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="glass-card p-6"
            >
              <DubForm config={config} onJobStarted={handleJobStarted} />
            </motion.div>
          ) : (
            <motion.div
              key="progress"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            >
              <JobProgress jobId={jobId} onDone={handleDone} />
              {jobDone && jobStatus === "completed" && <DownloadButton jobId={jobId} />}
              {jobDone && jobStatus === "failed" && (
                <div className="mt-4 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <p className="text-sm text-red-400 font-medium">Job failed. Check the log above for details.</p>
                </div>
              )}
              <button
                onClick={() => setJobId(null)}
                className="mt-4 text-sm text-zinc-500 hover:text-zinc-300 transition-colors underline underline-offset-4"
              >
                Start new job
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
