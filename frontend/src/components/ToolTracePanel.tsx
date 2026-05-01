import { useState } from "react";
import type { ToolEntry } from "../services/api";

interface Props {
  trace: ToolEntry[];
  discordSent?: boolean | null;
}

function toolMeta(name: string): { icon: string; color: string } {
  const n = name.toLowerCase();
  if (n.includes("rag") || n.includes("retrieval") || n.includes("search"))
    return { icon: "🔍", color: "bg-violet-900/60 text-violet-300 border-violet-700/50" };
  if (n.includes("classify") || n.includes("ml") || n.includes("style"))
    return { icon: "🧠", color: "bg-blue-900/60 text-blue-300 border-blue-700/50" };
  if (n.includes("weather"))
    return { icon: "🌤", color: "bg-amber-900/60 text-amber-300 border-amber-700/50" };
  if (n.includes("flight") || n.includes("aviation"))
    return { icon: "✈", color: "bg-sky-900/60 text-sky-300 border-sky-700/50" };
  if (n.includes("discord") || n.includes("webhook"))
    return { icon: "🔔", color: "bg-indigo-900/60 text-indigo-300 border-indigo-700/50" };
  return { icon: "⚙", color: "bg-slate-700/60 text-slate-300 border-slate-600/50" };
}

function CallEntry({ entry }: { entry: ToolEntry & { type: "call" } }) {
  const [open, setOpen] = useState(false);
  const { icon, color } = toolMeta(entry.tool);

  return (
    <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-700/30 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${color}`}>
          {icon} {entry.tool}
        </span>
        <span className="text-xs text-slate-500 ml-auto">
          {open ? "▲ hide" : "▼ input"}
        </span>
      </button>
      {open && entry.input && (
        <div className="px-4 pb-3 border-t border-slate-700/40">
          <p className="text-xs text-slate-500 uppercase font-bold tracking-wider pt-2 pb-1">Input</p>
          <pre className="text-xs text-slate-300 bg-slate-900/60 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words">
            {JSON.stringify(entry.input, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function ResultEntry({ entry }: { entry: ToolEntry & { type: "result" } }) {
  const [open, setOpen] = useState(false);
  const { icon, color } = toolMeta(entry.tool);
  const preview = entry.output
    ? entry.output.length > 80
      ? entry.output.slice(0, 80) + "…"
      : entry.output
    : "";

  return (
    <div className="bg-slate-800/40 border border-slate-700/30 rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-700/20 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border opacity-70 ${color}`}>
          ↩ {icon} result
        </span>
        {!open && (
          <span className="text-xs text-slate-500 truncate max-w-xs">{preview}</span>
        )}
        <span className="text-xs text-slate-600 ml-auto flex-shrink-0">
          {open ? "▲" : "▼"}
        </span>
      </button>
      {open && entry.output && (
        <div className="px-4 pb-3 border-t border-slate-700/30">
          <pre className="text-xs text-slate-400 bg-slate-900/40 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words pt-2 mt-2">
            {entry.output}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function ToolTracePanel({ trace, discordSent }: Props) {
  const [open, setOpen] = useState(false);

  const calls = trace.filter((t) => t.type === "call");
  const toolNames = [...new Set(calls.map((t) => t.tool))];

  return (
    <div className="mt-3 rounded-xl border border-slate-700/40 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-slate-800/60 hover:bg-slate-700/50 transition-colors text-left"
      >
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
          🛠 Tool Trace
        </span>
        <div className="flex gap-1.5 flex-wrap">
          {toolNames.map((n) => {
            const { icon, color } = toolMeta(n);
            return (
              <span key={n} className={`text-xs px-2 py-0.5 rounded-full border ${color}`}>
                {icon} {n}
              </span>
            );
          })}
        </div>
        {discordSent !== undefined && discordSent !== null && (
          <span
            className={`ml-1 text-xs px-2 py-0.5 rounded-full border font-semibold ${
              discordSent
                ? "bg-indigo-900/60 text-indigo-300 border-indigo-700/50"
                : "bg-slate-700/60 text-slate-400 border-slate-600/50"
            }`}
          >
            {discordSent ? "🔔 Discord ✓" : "🔕 Discord –"}
          </span>
        )}
        <span className="ml-auto text-xs text-slate-600">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="bg-slate-900/40 p-4 flex flex-col gap-2">
          {trace.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-2">No tools fired.</p>
          )}
          {trace.map((entry, i) =>
            entry.type === "call" ? (
              <CallEntry key={i} entry={entry as ToolEntry & { type: "call" }} />
            ) : (
              <ResultEntry key={i} entry={entry as ToolEntry & { type: "result" }} />
            )
          )}
        </div>
      )}
    </div>
  );
}
