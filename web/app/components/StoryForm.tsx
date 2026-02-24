"use client";

import { useState } from "react";
import { Config, submitStory } from "../lib/api";

interface Props {
  config: Config;
  onJobStarted: (jobId: string) => void;
}

export default function StoryForm({ config, onJobStarted }: Props) {
  const [mode, setMode] = useState<"theme" | "text">("theme");
  const [theme, setTheme] = useState("aesop");
  const [keyword, setKeyword] = useState("");
  const [text, setText] = useState("");
  const [targetLang, setTargetLang] = useState("hi-IN");
  const [speaker, setSpeaker] = useState("");
  const [mood, setMood] = useState("default");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await submitStory({
        text: mode === "text" ? text : undefined,
        theme: mode === "theme" ? theme : undefined,
        keyword: mode === "theme" && keyword ? keyword : undefined,
        target_lang: targetLang,
        speaker: speaker || undefined,
        mood,
        no_upload: true,
      });
      onJobStarted(res.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setLoading(false);
    }
  }

  const isValid = mode === "text" ? text.trim().length > 0 : true;

  const selectClass =
    "w-full appearance-none bg-zinc-800/80 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-zinc-50 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2 mb-2">
        <button
          type="button"
          onClick={() => setMode("theme")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            mode === "theme"
              ? "bg-gradient-to-r from-indigo-500 to-violet-500 text-white"
              : "bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-white/[0.06]"
          }`}
        >
          Pick a Theme
        </button>
        <button
          type="button"
          onClick={() => setMode("text")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            mode === "text"
              ? "bg-gradient-to-r from-indigo-500 to-violet-500 text-white"
              : "bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-white/[0.06]"
          }`}
        >
          Paste Story
        </button>
      </div>

      {mode === "theme" ? (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-[--text-secondary] mb-1.5">Theme</label>
            <select
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              className={selectClass}
            >
              {config.themes.map((t) => (
                <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[--text-secondary] mb-1.5">Keyword (optional)</label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g. tortoise"
              className="w-full bg-zinc-800/80 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-zinc-50 placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
            />
          </div>
        </div>
      ) : (
        <div>
          <label className="block text-sm font-medium text-[--text-secondary] mb-1.5">Story Text</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Once upon a time..."
            rows={4}
            className="w-full bg-zinc-800/80 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-zinc-50 placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
          />
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-[--text-secondary] mb-1.5">Language</label>
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
        <div>
          <label className="block text-sm font-medium text-[--text-secondary] mb-1.5">Speaker</label>
          <select
            value={speaker}
            onChange={(e) => setSpeaker(e.target.value)}
            className={selectClass}
          >
            <option value="">Auto</option>
            {config.speakers.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-[--text-secondary] mb-1.5">Mood</label>
          <select
            value={mood}
            onChange={(e) => setMood(e.target.value)}
            className={selectClass}
          >
            {config.moods.map((m) => (
              <option key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={loading || !isValid}
        className="w-full py-2.5 rounded-lg font-medium text-sm text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed btn-shimmer"
        style={{
          background: "linear-gradient(135deg, var(--accent-indigo), var(--accent-violet))",
        }}
      >
        {loading ? "Submitting..." : "Generate Story Short"}
      </button>
    </form>
  );
}
