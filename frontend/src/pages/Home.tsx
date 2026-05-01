import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";

const features = [
  {
    icon: "🔍",
    title: "RAG Destination Search",
    desc: "Semantic search over curated East & Southeast Asia destination knowledge, retrieving the best matches for your preferences.",
  },
  {
    icon: "🧠",
    title: "Travel Style Classifier",
    desc: "ML model trained on traveler profiles classifies your style — beach lover, culture seeker, adventure hunter — for spot-on matches.",
  },
  {
    icon: "🌤",
    title: "Live Conditions",
    desc: "Real-time weather data and flight route lookups from Beirut keep your plan grounded in actual availability.",
  },
  {
    icon: "🔔",
    title: "Discord Delivery",
    desc: "Every completed plan is fired to your Discord channel as a rich notification — share it instantly with your travel crew.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      {/* Hero */}
      <section className="relative pt-24 pb-20 overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-teal-900/40 via-slate-950 to-indigo-900/30 pointer-events-none" />
        <div className="absolute top-20 left-1/4 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-5xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 bg-teal-900/50 border border-teal-700/50 text-teal-300 text-xs font-semibold px-4 py-1.5 rounded-full mb-6">
            <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-pulse" />
            East &amp; Southeast Asia · AI-Powered
          </div>

          <h1 className="text-5xl sm:text-6xl font-extrabold leading-tight mb-6">
            Your AI Smart{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-500 to-cyan-500">
              Travel Planner
            </span>
          </h1>

          <p className="text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Describe your dream trip. Our AI searches destination knowledge,
            classifies your travel style, checks live weather &amp; flights from
            Beirut, and delivers a personalized plan in seconds.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              to="/planner"
              className="inline-flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-all shadow-lg shadow-teal-900/40 hover:shadow-teal-800/60"
            >
              <span>Start Planning</span>
              <span>→</span>
            </Link>
            <Link
              to="/about"
              className="inline-flex items-center justify-center gap-2 border border-slate-600 hover:border-slate-400 text-slate-300 hover:text-white font-semibold px-8 py-3.5 rounded-xl transition-all"
            >
              Learn More
            </Link>
          </div>
        </div>
      </section>

      {/* Destination pills */}
      <section className="py-6 overflow-hidden">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-wrap gap-2 justify-center">
            {["🏝 Bali", "🏯 Kyoto", "🌆 Tokyo", "🌸 Seoul", "🛕 Siem Reap",
              "🌊 Da Nang", "🌴 Palawan", "🍜 Hanoi", "🦁 Singapore",
              "🏔 Chiang Mai", "🌉 Taipei", "🏙 Kuala Lumpur"].map((d) => (
              <span
                key={d}
                className="bg-slate-800/60 border border-slate-700/50 text-slate-300 text-sm px-3 py-1.5 rounded-full"
              >
                {d}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 max-w-6xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-3">How It Works</h2>
          <p className="text-slate-400 text-lg">
            Every query runs through a full AI pipeline — no generic results.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 hover:border-teal-700/50 transition-all group"
            >
              <div className="text-3xl mb-4">{f.icon}</div>
              <h3 className="text-base font-semibold text-white mb-2">
                {f.title}
              </h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA banner */}
      <section className="py-16 bg-gradient-to-r from-teal-900/40 to-indigo-900/40 border-y border-slate-700/30">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold mb-4">
            Ready to plan your next adventure?
          </h2>
          <p className="text-slate-400 mb-8">
            Create an account and get your personalized Asia travel plan in under
            60 seconds.
          </p>
          <Link
            to="/signup"
            className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-all"
          >
            Create Free Account →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 text-center text-sm text-slate-500 border-t border-slate-800">
        Where To Go · AI Travel Planner · East &amp; Southeast Asia
      </footer>
    </div>
  );
}
