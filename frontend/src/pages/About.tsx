import Navbar from "../components/Navbar";

const stack = [
  {
    icon: "🔍",
    label: "RAG Retrieval",
    color: "from-violet-900/40 to-violet-800/20 border-violet-700/40",
    badge: "pgvector + sentence-transformers",
    points: [
      "Destination documents chunked and embedded at 768 dimensions",
      "Semantic similarity search over Postgres pgvector store",
      "Top-K results injected as LLM context for accurate synthesis",
    ],
  },
  {
    icon: "🧠",
    label: "Travel Style Classifier",
    color: "from-blue-900/40 to-blue-800/20 border-blue-700/40",
    badge: "scikit-learn · Random Forest",
    points: [
      "Classifies free-text queries into travel style categories",
      "Trained on curated travel preference profiles",
      "Output guides destination weighting in the agent pipeline",
    ],
  },
  {
    icon: "🌤",
    label: "Live Condition Checks",
    color: "from-amber-900/40 to-amber-800/20 border-amber-700/40",
    badge: "Weather API · AviationStack",
    points: [
      "Current weather retrieved for recommended destination",
      "Flight route search from Beirut to destination airports",
      "Results embedded in the final trip plan synthesis",
    ],
  },
  {
    icon: "🤖",
    label: "LangGraph ReAct Agent",
    color: "from-teal-900/40 to-teal-800/20 border-teal-700/40",
    badge: "Groq LLM · LangGraph",
    points: [
      "ReAct pattern: rewrite → RAG → ML → live data → synthesize",
      "Multi-step tool use with full trace logged per request",
      "Powered by Llama 3.3 70B via Groq free tier",
    ],
  },
  {
    icon: "🔐",
    label: "Authenticated Runs",
    color: "from-slate-800/40 to-slate-700/20 border-slate-600/40",
    badge: "FastAPI · JWT",
    points: [
      "Every agent run tied to an authenticated user account",
      "Full run history stored: query, response, tool trace",
      "JWT-based auth with secure bcrypt password hashing",
    ],
  },
  {
    icon: "🔔",
    label: "Discord Notifications",
    color: "from-indigo-900/40 to-indigo-800/20 border-indigo-700/40",
    badge: "Discord Webhooks",
    points: [
      "Rich embed sent to your Discord channel on every completed run",
      "Includes trip plan, tools used, and run status",
      "Non-blocking background task — never slows the response",
    ],
  },
];

export default function About() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <div className="pt-24 pb-20 max-w-5xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-4xl font-extrabold mb-4">
            How{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-300">
              Where To Go
            </span>{" "}
            Works
          </h1>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto leading-relaxed">
            A full AI pipeline that combines retrieval-augmented generation,
            ML classification, live data, and multi-step reasoning to deliver
            personalized East &amp; Southeast Asia travel plans.
          </p>
        </div>

        {/* Pipeline diagram */}
        <div className="bg-slate-800/30 border border-slate-700/40 rounded-2xl p-6 mb-14">
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-widest mb-4">
            Agent Pipeline
          </p>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {[
              { label: "Query", color: "bg-slate-700" },
              { label: "→", color: "" },
              { label: "Rewrite", color: "bg-teal-800/60" },
              { label: "→", color: "" },
              { label: "RAG Search", color: "bg-violet-800/60" },
              { label: "→", color: "" },
              { label: "ML Classify", color: "bg-blue-800/60" },
              { label: "→", color: "" },
              { label: "Live Data", color: "bg-amber-800/60" },
              { label: "→", color: "" },
              { label: "Synthesize", color: "bg-teal-800/60" },
              { label: "→", color: "" },
              { label: "Plan + Discord", color: "bg-indigo-800/60" },
            ].map((step, i) =>
              step.color ? (
                <span
                  key={i}
                  className={`${step.color} px-3 py-1.5 rounded-lg font-medium text-white`}
                >
                  {step.label}
                </span>
              ) : (
                <span key={i} className="text-slate-600 font-bold">
                  {step.label}
                </span>
              )
            )}
          </div>
        </div>

        {/* Stack cards */}
        <div className="grid sm:grid-cols-2 gap-6">
          {stack.map((item) => (
            <div
              key={item.label}
              className={`bg-gradient-to-br ${item.color} border rounded-2xl p-6`}
            >
              <div className="flex items-start gap-3 mb-3">
                <span className="text-2xl">{item.icon}</span>
                <div>
                  <h3 className="font-bold text-white">{item.label}</h3>
                  <span className="text-xs text-slate-400 font-mono">
                    {item.badge}
                  </span>
                </div>
              </div>
              <ul className="space-y-1.5">
                {item.points.map((p) => (
                  <li key={p} className="text-sm text-slate-300 flex gap-2">
                    <span className="text-teal-400 flex-shrink-0">·</span>
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
