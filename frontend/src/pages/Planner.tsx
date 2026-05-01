import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import TripPlanCard from "../components/TripPlanCard";
import { api } from "../services/api";
import type { CostBreakdown, ToolEntry } from "../services/api";
import { useAuth } from "../hooks/useAuth";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  query?: string;
  status?: "completed" | "failed";
  trace?: ToolEntry[];
  runId?: string;
  costAnalysis?: CostBreakdown;
  pending?: boolean;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PROGRESS_STEPS = [
  "Understanding your preferences",
  "Searching destination knowledge",
  "Checking travel style fit",
  "Checking weather & flights",
  "Preparing final plan",
  "Finalising recommendation",
];

const CHIPS = [
  "Flying from Beirut",
  "Budget: $1500",
  "Travel month: July",
  "I like hiking",
  "Not too touristy",
  "Warm weather",
  "Family friendly",
  "Culture + food",
  "Beach + relaxation",
];

const EXAMPLE_PROMPTS = [
  "I have 2 weeks in July, flying from Beirut, budget ~$1500. I love hiking, warm weather, and places that aren't too crowded. Where should I go in Southeast Asia?",
  "Looking for a cultural trip in East Asia, 10 days in April, budget $2000. I want temples, local food, and good public transport.",
  "Beach holiday for 1 week in December with my partner, flying from Beirut. Somewhere tropical and affordable. What do you recommend?",
];

const GUIDE_PROMPT =
  'I have 10–14 days in July, flying from Beirut, budget around $1500, I like hiking, nature, warm weather, and places that are not too touristy. I prefer safe, affordable destinations in East or Southeast Asia.';

// ── Progress animation component ──────────────────────────────────────────────

function ProgressCard({ stepIndex }: { stepIndex: number }) {
  return (
    <div className="rounded-2xl border border-teal-800/50 bg-slate-800/60 p-5 max-w-lg">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-3 h-3 rounded-full bg-teal-500 animate-pulse" />
        <span className="text-sm font-semibold text-teal-300">Building your trip plan…</span>
      </div>
      <div className="space-y-2">
        {PROGRESS_STEPS.map((step, i) => (
          <div key={step} className="flex items-center gap-3">
            <div
              className={`w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center text-xs transition-all ${
                i < stepIndex
                  ? "bg-teal-500 text-white"
                  : i === stepIndex
                  ? "bg-teal-900 border-2 border-teal-500 animate-pulse"
                  : "bg-slate-700 border border-slate-600"
              }`}
            >
              {i < stepIndex && "✓"}
            </div>
            <span
              className={`text-xs transition-colors ${
                i < stepIndex
                  ? "text-teal-400 line-through opacity-60"
                  : i === stepIndex
                  ? "text-white font-medium"
                  : "text-slate-600"
              }`}
            >
              {step}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({
  onPrompt,
}: {
  onPrompt: (p: string) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-12 text-center">
      <div className="text-5xl mb-4">🗺</div>
      <h2 className="text-xl font-bold text-white mb-2">
        Where do you want to go?
      </h2>
      <p className="text-sm text-slate-400 mb-8 max-w-sm">
        Ask about any East or Southeast Asia trip. The AI will search
        destinations, check your travel style, and verify live conditions.
      </p>

      {/* Guide card */}
      <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-4 mb-6 max-w-md text-left">
        <p className="text-xs text-teal-400 font-semibold uppercase tracking-wider mb-2">
          Example — Best Results
        </p>
        <p className="text-sm text-slate-300 leading-relaxed italic">
          "{GUIDE_PROMPT}"
        </p>
        <button
          onClick={() => onPrompt(GUIDE_PROMPT)}
          className="mt-3 text-xs text-teal-400 hover:text-teal-300 underline underline-offset-2"
        >
          Use this prompt →
        </button>
      </div>

      {/* Example prompts */}
      <div className="w-full max-w-md space-y-2">
        {EXAMPLE_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => onPrompt(p)}
            className="w-full text-left text-sm bg-slate-800/40 border border-slate-700/40 hover:border-teal-700/50 hover:bg-slate-800/70 rounded-xl px-4 py-3 text-slate-300 hover:text-white transition-all"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main Planner ──────────────────────────────────────────────────────────────

export default function Planner() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const stepTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!token) navigate("/login");
  }, [token, navigate]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Advance progress steps during loading
  useEffect(() => {
    if (loading) {
      setStepIndex(0);
      stepTimer.current = setInterval(() => {
        setStepIndex((prev) =>
          prev < PROGRESS_STEPS.length - 2 ? prev + 1 : prev
        );
      }, 1400);
    } else {
      if (stepTimer.current) clearInterval(stepTimer.current);
    }
    return () => {
      if (stepTimer.current) clearInterval(stepTimer.current);
    };
  }, [loading]);

  const addChip = (chip: string) => {
    setInput((prev) => {
      if (prev.trim()) return prev.trimEnd() + ", " + chip;
      return chip;
    });
  };

  const send = async (overrideQuery?: string) => {
    const query = (overrideQuery ?? input).trim();
    if (!query || loading) return;

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();

    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: query },
    ]);
    setLoading(true);

    try {
      const { data } = await api.queryAgent(query);

      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: "assistant",
          content: data.response ?? "No response returned.",
          query,
          status: data.status as "completed" | "failed",
          trace: data.tool_trace,
          runId: data.run_id,
          costAnalysis: data.cost_analysis,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: "assistant",
          content: "Something went wrong. Please try again.",
          status: "failed",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const isEmpty = messages.length === 0 && !loading;

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      <Navbar />

      {/* Sub-header */}
      <div className="fixed top-16 left-0 right-0 z-40 bg-slate-900/90 backdrop-blur border-b border-slate-700/40 px-4 py-2 flex items-center gap-3">
        <span className="text-xs text-slate-400 font-medium">AI Planner</span>
        <span className="w-1 h-1 rounded-full bg-slate-600" />
        <span className="text-xs text-teal-400">
          East &amp; Southeast Asia
        </span>
        <button
          onClick={handleLogout}
          className="ml-auto text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          Sign out
        </button>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col max-w-3xl w-full mx-auto px-4 pt-32 pb-36">
        {isEmpty ? (
          <EmptyState onPrompt={(p) => { setInput(p); }} />
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${
                  m.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {m.role === "user" ? (
                  <div className="bg-teal-700 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-[80%] text-sm leading-relaxed">
                    {m.content}
                  </div>
                ) : (
                  <div className="max-w-[90%] w-full">
                    <TripPlanCard
                      query={m.query ?? ""}
                      content={m.content}
                      trace={m.trace}
                      runId={m.runId}
                      status={m.status ?? "completed"}
                      costAnalysis={m.costAnalysis}
                    />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <ProgressCard stepIndex={stepIndex} />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Fixed input area */}
      <div className="fixed bottom-0 left-0 right-0 bg-slate-950/95 backdrop-blur border-t border-slate-700/40 px-4 py-3">
        <div className="max-w-3xl mx-auto">
          {/* Chips */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            {CHIPS.map((chip) => (
              <button
                key={chip}
                onClick={() => addChip(chip)}
                disabled={loading}
                className="text-xs bg-slate-800/60 border border-slate-700/40 hover:border-teal-700/50 hover:text-teal-300 text-slate-400 px-2.5 py-1 rounded-full transition-all disabled:opacity-40"
              >
                + {chip}
              </button>
            ))}
          </div>

          {/* Input row */}
          <div className="flex gap-2">
            <textarea
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Where do you want to go? Describe your trip…"
              disabled={loading}
              className="flex-1 bg-slate-800/60 border border-slate-700/40 focus:border-teal-600/60 text-white placeholder-slate-500 rounded-xl px-4 py-2.5 text-sm resize-none focus:outline-none transition-colors disabled:opacity-50"
            />
            <button
              onClick={() => send()}
              disabled={loading || !input.trim()}
              className="bg-teal-600 hover:bg-teal-500 disabled:opacity-40 text-white font-semibold px-5 py-2.5 rounded-xl transition-all self-end text-sm"
            >
              {loading ? "…" : "Send"}
            </button>
          </div>

          <p className="text-xs text-slate-600 mt-1.5 text-center">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
