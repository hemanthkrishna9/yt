"use client";

import { useState } from "react";
import { Config, submitDub } from "../lib/api";
import { Link, Globe, Mic, Play, Loader2, ChevronDown, AlertCircle } from "lucide-react";

interface Props {
  config: Config;
  onJobStarted: (jobId: string) => void;
}

export default function DubForm({ config, onJobStarted }: Props) {
  const [url, setUrl] = useState("");
  const [sourceLang, setSourceLang] = useState("en-IN");
  const [targetLang, setTargetLang] = useState("hi-IN");
  const [speaker, setSpeaker] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await submitDub({
        url: url || undefined,
        source_lang: sourceLang,
        target_lang: targetLang,
        speaker: speaker || undefined,
      });
      onJobStarted(res.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setLoading(false);
    }
  }

  const selectWrapperClass = "relative";
  const selectClass =
    "w-full appearance-none bg-zinc-800/80 border border-white/10 rounded-lg pl-9 pr-8 py-2.5 text-sm text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all";

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label className="flex items-center gap-1.5 text-sm font-medium text-[--text-secondary] mb-1.5">
          <Link className="w-3.5 h-3.5" />
          YouTube URL
        </label>
        <div className="relative">
          <Link className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/shorts/..."
            required
            className="w-full bg-zinc-800/80 border border-white/10 rounded-lg pl-9 pr-3 py-2.5 text-sm text-zinc-50 placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-[--text-secondary] mb-1.5">
            <Globe className="w-3.5 h-3.5" />
            Source Language
          </label>
          <div className={selectWrapperClass}>
            <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 z-10 pointer-events-none" />
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none" />
            <select
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              className={selectClass}
            >
              {Object.entries(config.languages).map(([code, name]) => (
                <option key={code} value={code}>{name}</option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-[--text-secondary] mb-1.5">
            <Globe className="w-3.5 h-3.5" />
            Target Language
          </label>
          <div className={selectWrapperClass}>
            <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 z-10 pointer-events-none" />
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none" />
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              className={selectClass}
            >
              {Object.entries(config.languages).map(([code, name]) => (
                <option key={code} value={code}>{name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div>
        <label className="flex items-center gap-1.5 text-sm font-medium text-[--text-secondary] mb-1.5">
          <Mic className="w-3.5 h-3.5" />
          Speaker (optional)
        </label>
        <div className={selectWrapperClass}>
          <Mic className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 z-10 pointer-events-none" />
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none" />
          <select
            value={speaker}
            onChange={(e) => setSpeaker(e.target.value)}
            className={selectClass}
          >
            <option value="">Auto (default for language)</option>
            {config.speakers.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={loading || !url}
        className="w-full py-2.5 rounded-lg font-medium text-sm text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed btn-shimmer flex items-center justify-center gap-2"
        style={{
          background: "linear-gradient(135deg, var(--accent-indigo), var(--accent-violet))",
        }}
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Submitting...
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            Start Dubbing
          </>
        )}
      </button>
    </form>
  );
}
