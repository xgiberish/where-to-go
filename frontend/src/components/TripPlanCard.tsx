import { useState } from "react";
import type { ToolEntry } from "../services/api";
import ToolTracePanel from "./ToolTracePanel";

interface Props {
  content: string;
  trace?: ToolEntry[];
  runId?: string;
  status: "completed" | "failed";
  discordConfigured?: boolean;
}

export default function TripPlanCard({ content, trace, status, discordConfigured }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (status === "failed") {
    return (
      <div className="rounded-2xl border border-red-800/50 bg-red-950/30 p-5">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">⚠</span>
          <span className="font-semibold text-red-300 text-sm">Agent Error</span>
        </div>
        <p className="text-sm text-red-200/80 leading-relaxed">{content}</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/40 overflow-hidden">
      {/* Card header */}
      <div className="flex items-center gap-3 px-5 py-3 bg-teal-900/30 border-b border-slate-700/40">
        <span className="text-lg">✈</span>
        <span className="font-semibold text-teal-300 text-sm">Trip Plan Ready</span>
        <div className="flex gap-2 ml-auto">
          {discordConfigured !== undefined && (
            <span
              className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
                discordConfigured
                  ? "bg-indigo-900/60 text-indigo-300 border-indigo-700/50"
                  : "bg-slate-700/40 text-slate-500 border-slate-600/40"
              }`}
            >
              {discordConfigured ? "🔔 Discord Sent" : "🔕 Discord Off"}
            </span>
          )}
          <button
            onClick={handleCopy}
            className="text-xs px-2.5 py-1 rounded-full border border-slate-600/50 text-slate-400 hover:text-white hover:border-slate-400 transition-all"
          >
            {copied ? "✓ Copied" : "Copy Plan"}
          </button>
        </div>
      </div>

      {/* Plan content */}
      <div className="px-5 py-4">
        <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
          {content}
        </p>
      </div>

      {/* Tool trace */}
      {trace && trace.length > 0 && (
        <div className="px-4 pb-4">
          <ToolTracePanel trace={trace} discordSent={discordConfigured} />
        </div>
      )}

      {/* Disclaimer */}
      <div className="mx-4 mb-4 px-4 py-3 bg-amber-950/30 border border-amber-800/30 rounded-xl">
        <p className="text-xs text-amber-200/60 leading-relaxed">
          <span className="font-semibold text-amber-300/80">Note:</span> Live
          prices and availability can change quickly. Due to current global
          instability, fuel prices, airline capacity, and regional conflict,
          flight and budget estimates may fluctuate from real booking prices.
          Always verify before purchasing.
        </p>
      </div>
    </div>
  );
}
