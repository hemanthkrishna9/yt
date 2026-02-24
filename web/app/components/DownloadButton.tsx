"use client";

import { getDownloadUrl } from "../lib/api";
import { motion } from "framer-motion";
import { Download } from "lucide-react";

interface Props {
  jobId: string;
}

export default function DownloadButton({ jobId }: Props) {
  return (
    <motion.a
      href={getDownloadUrl(jobId)}
      download
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="inline-flex items-center gap-2 mt-4 py-2.5 px-6 rounded-lg font-medium text-sm text-white transition-all hover:brightness-110 btn-shimmer"
      style={{
        background: "linear-gradient(135deg, var(--accent-emerald), var(--accent-cyan))",
      }}
    >
      <Download className="w-4 h-4" />
      Download Video
    </motion.a>
  );
}
