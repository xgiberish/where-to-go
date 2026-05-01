import { useState } from "react";
import type { CostBreakdown, ToolEntry } from "../services/api";
import { api } from "../services/api";
import ToolTracePanel from "./ToolTracePanel";

interface Props {
  query: string;
  content: string;
  trace?: ToolEntry[];
  runId?: string;
  status: "completed" | "failed";
  costAnalysis?: CostBreakdown;
}

type DiscordState = "idle" | "sending" | "sent" | "failed" | "unconfigured";

function fmt(n: number) {
  return n.toLocaleString();
}

function usd(n: number) {
  if (n === 0) return "$0.00";
  if (n < 0.0001) return `< $0.0001`;
  return `$${n.toFixed(4)}`;
}

function CostPanel({ cost }: { cost: CostBreakdown }) {
  const [open, setOpen] = useState(false);
  const total = cost.total_input_tokens + cost.total_output_tokens;

  return (
    <div className="mx-4 mb-3 rounded-xl border border-slate-700/40 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-slate-800/50 hover:bg-slate-700/40 transition-colors text-left"
      >
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
          💰 Cost Analysis
        </span>
        <span className="text-xs text-emerald-400 font-semibold ml-1">
          Groq FREE
        </span>
        <span className="text-xs text-slate-600 ml-auto">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="bg-slate-900/40 px-4 py-3 space-y-3 text-xs">
          {/* Token counts per model */}
          <div className="space-y-1.5">
            <p className="text-slate-500 uppercase font-bold tracking-wider text-[10px]">Token usage</p>
            <div className="grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-1 items-center">
              <span className="text-slate-400 truncate">{cost.cheap_model} <span className="text-slate-600">({cost.cheap_calls} call{cost.cheap_calls !== 1 ? "s" : ""})</span></span>
              <span className="text-slate-500">{fmt(cost.cheap_input_tokens)} in</span>
              <span className="text-slate-500">{fmt(cost.cheap_output_tokens)} out</span>

              <span className="text-slate-400 truncate">{cost.strong_model} <span className="text-slate-600">({cost.strong_calls} call{cost.strong_calls !== 1 ? "s" : ""})</span></span>
              <span className="text-slate-500">{fmt(cost.strong_input_tokens)} in</span>
              <span className="text-slate-500">{fmt(cost.strong_output_tokens)} out</span>
            </div>
            <p className="text-slate-500 pt-0.5">
              Total: <span className="text-slate-300">{fmt(cost.total_input_tokens)}</span> in +{" "}
              <span className="text-slate-300">{fmt(cost.total_output_tokens)}</span> out ={" "}
              <span className="text-white font-semibold">{fmt(total)}</span> tokens
            </p>
          </div>

          {/* Cost comparison */}
          <div className="space-y-1.5">
            <p className="text-slate-500 uppercase font-bold tracking-wider text-[10px]">Equivalent cost on paid models</p>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-emerald-400 font-semibold">Groq (llama-3.1 / llama-3.3)</span>
                <span className="text-emerald-400 font-bold">FREE</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Gemini 3.1 Flash-Lite <span className="text-slate-600">($0.125/$0.75 per 1M)</span></span>
                <span className="text-slate-300">{usd(cost.gemini_flash_lite_usd)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Gemini 3.1 Flash <span className="text-slate-600">($0.50/$3.00 per 1M)</span></span>
                <span className="text-slate-300">{usd(cost.gemini_flash_usd)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Gemini 3.1 Pro <span className="text-slate-600">($2.00/$12.00 per 1M)</span></span>
                <span className="text-slate-300">{usd(cost.gemini_pro_usd)}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TripPlanCard({ query, content, trace, status, costAnalysis }: Props) {
  const [copied, setCopied] = useState(false);
  const [discordState, setDiscordState] = useState<DiscordState>("idle");
  const [discordMsg, setDiscordMsg] = useState("");

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDiscord = async () => {
    setDiscordState("sending");
    setDiscordMsg("");
    try {
      const { data } = await api.sendToDiscord(query, content, status, trace);
      if (data.success) {
        setDiscordState("sent");
        setDiscordMsg(data.message);
      } else {
        // Distinguish "not configured" from generic failure
        if (data.message.toLowerCase().includes("not configured")) {
          setDiscordState("unconfigured");
        } else {
          setDiscordState("failed");
        }
        setDiscordMsg(data.message);
      }
    } catch {
      setDiscordState("failed");
      setDiscordMsg("Could not reach the server. Try again.");
    }
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

  const discordButton = () => {
    if (discordState === "sending") {
      return (
        <button
          disabled
          className="text-xs px-2.5 py-1 rounded-full border border-indigo-700/50 bg-indigo-900/40 text-indigo-300 opacity-60 cursor-not-allowed"
        >
          Sending…
        </button>
      );
    }
    if (discordState === "sent") {
      return (
        <span className="text-xs px-2.5 py-1 rounded-full border border-green-700/50 bg-green-900/40 text-green-300 font-medium">
          🔔 Sent to Discord ✓
        </span>
      );
    }
    if (discordState === "unconfigured") {
      return (
        <span className="text-xs px-2.5 py-1 rounded-full border border-slate-600/50 bg-slate-800/40 text-slate-500">
          🔕 Discord not configured
        </span>
      );
    }
    if (discordState === "failed") {
      return (
        <button
          onClick={handleDiscord}
          className="text-xs px-2.5 py-1 rounded-full border border-red-700/50 bg-red-900/30 text-red-300 hover:bg-red-900/50 transition-all"
        >
          ✗ Retry Discord
        </button>
      );
    }
    return (
      <button
        onClick={handleDiscord}
        className="text-xs px-2.5 py-1 rounded-full border border-indigo-700/50 bg-indigo-900/30 text-indigo-300 hover:bg-indigo-900/50 hover:border-indigo-600/60 transition-all"
      >
        🔔 Send to Discord
      </button>
    );
  };

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/40 overflow-hidden">
      {/* Card header */}
      <div className="flex items-center gap-3 px-5 py-3 bg-teal-900/30 border-b border-slate-700/40 flex-wrap gap-y-2">
        <span className="text-lg">✈</span>
        <span className="font-semibold text-teal-300 text-sm">Trip Plan Ready</span>
        <div className="flex gap-2 ml-auto flex-wrap">
          {discordButton()}
          <button
            onClick={handleCopy}
            className="text-xs px-2.5 py-1 rounded-full border border-slate-600/50 text-slate-400 hover:text-white hover:border-slate-400 transition-all"
          >
            {copied ? "✓ Copied" : "Copy Plan"}
          </button>
        </div>
      </div>

      {/* Discord feedback message */}
      {discordMsg && discordState !== "sent" && (
        <div
          className={`px-5 py-2 text-xs border-b ${
            discordState === "failed" || discordState === "unconfigured"
              ? "bg-slate-800/60 border-slate-700/40 text-slate-400"
              : "bg-green-950/30 border-green-800/30 text-green-300"
          }`}
        >
          {discordMsg}
        </div>
      )}

      {/* Plan content */}
      <div className="px-5 py-4">
        <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
          {content}
        </p>
      </div>

      {/* Tool trace */}
      {trace && trace.length > 0 && (
        <div className="px-4 pb-3">
          <ToolTracePanel trace={trace} />
        </div>
      )}

      {/* Cost analysis */}
      {costAnalysis && costAnalysis.total_input_tokens > 0 && (
        <CostPanel cost={costAnalysis} />
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
