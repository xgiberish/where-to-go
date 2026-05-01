import { useState } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";

interface Destination {
  id: number;
  name: string;
  country: string;
  emoji: string;
  style: string;
  styleColor: string;
  bestMonth: string;
  vibe: string;
  desc: string;
}

const DESTINATIONS: Destination[] = [
  {
    id: 1,
    name: "Bali",
    country: "Indonesia",
    emoji: "🏝",
    style: "Beach & Nature",
    styleColor: "bg-cyan-900/60 text-cyan-300 border-cyan-700/50",
    bestMonth: "Apr – Oct",
    vibe: "Spiritual · Tropical · Surf",
    desc: "Tropical island paradise with terraced rice fields, ancient temples, world-class surf breaks, and a vibrant arts scene.",
  },
  {
    id: 2,
    name: "Chiang Mai",
    country: "Thailand",
    emoji: "🏔",
    style: "Culture & Adventure",
    styleColor: "bg-green-900/60 text-green-300 border-green-700/50",
    bestMonth: "Nov – Feb",
    vibe: "Trekking · Temples · Cooking",
    desc: "Northern Thai city ringed by mountains and hill tribe villages. Famous for elephant sanctuaries and Lanna cuisine.",
  },
  {
    id: 3,
    name: "Kyoto",
    country: "Japan",
    emoji: "🏯",
    style: "Culture & Heritage",
    styleColor: "bg-pink-900/60 text-pink-300 border-pink-700/50",
    bestMonth: "Mar – May",
    vibe: "Zen · Geisha · Cherry Blossom",
    desc: "Japan's ancient imperial capital with over 1,600 temples, bamboo groves, geisha districts, and world-class cuisine.",
  },
  {
    id: 4,
    name: "Hanoi",
    country: "Vietnam",
    emoji: "🍜",
    style: "Culture & Food",
    styleColor: "bg-orange-900/60 text-orange-300 border-orange-700/50",
    bestMonth: "Oct – Dec",
    vibe: "Street Food · French Quarter · Lakes",
    desc: "Vietnam's capital blends French colonial architecture with thousand-year-old traditions and an electrifying street food scene.",
  },
  {
    id: 5,
    name: "Da Nang",
    country: "Vietnam",
    emoji: "🌊",
    style: "Beach & City",
    styleColor: "bg-cyan-900/60 text-cyan-300 border-cyan-700/50",
    bestMonth: "Mar – Aug",
    vibe: "Beaches · Dragon Bridge · Marble Mountains",
    desc: "Coastal city with 30km of pristine beach, the iconic Dragon Bridge, and the ancient town of Hội An just 30 minutes away.",
  },
  {
    id: 6,
    name: "Seoul",
    country: "South Korea",
    emoji: "🌆",
    style: "Urban & Culture",
    styleColor: "bg-violet-900/60 text-violet-300 border-violet-700/50",
    bestMonth: "Apr – Jun",
    vibe: "K-Culture · Palaces · Nightlife",
    desc: "Dynamic megacity mixing ancient Joseon palaces with K-pop culture, world-class skincare, and exceptional night markets.",
  },
  {
    id: 7,
    name: "Tokyo",
    country: "Japan",
    emoji: "🗼",
    style: "Urban & Technology",
    styleColor: "bg-blue-900/60 text-blue-300 border-blue-700/50",
    bestMonth: "Mar – May",
    vibe: "Futuristic · Anime · Michelin Stars",
    desc: "World's largest city offers jaw-dropping contrasts: neon-lit Shibuya, tranquil Meiji Shrine, and over 230 Michelin-starred restaurants.",
  },
  {
    id: 8,
    name: "Siem Reap",
    country: "Cambodia",
    emoji: "🛕",
    style: "Heritage & Adventure",
    styleColor: "bg-yellow-900/60 text-yellow-300 border-yellow-700/50",
    bestMonth: "Nov – Mar",
    vibe: "Angkor Wat · History · Jungle",
    desc: "Gateway to Angkor Wat — the world's largest religious monument. Sunrise over the ancient temples is truly unforgettable.",
  },
  {
    id: 9,
    name: "Kuala Lumpur",
    country: "Malaysia",
    emoji: "🏙",
    style: "Urban & Multicultural",
    styleColor: "bg-teal-900/60 text-teal-300 border-teal-700/50",
    bestMonth: "Jun – Aug",
    vibe: "Petronas Towers · Street Food · Shopping",
    desc: "Malaysia's vibrant capital features iconic twin towers, extraordinary multicultural cuisine from Malay, Chinese, and Indian traditions.",
  },
  {
    id: 10,
    name: "Singapore",
    country: "Singapore",
    emoji: "🦁",
    style: "Urban & Luxury",
    styleColor: "bg-red-900/60 text-red-300 border-red-700/50",
    bestMonth: "Feb – Apr",
    vibe: "Gardens by the Bay · Food · Modern",
    desc: "City-state of the future with futuristic Gardens by the Bay, the best hawker food in Asia, and spotlessly clean streets.",
  },
  {
    id: 11,
    name: "Palawan",
    country: "Philippines",
    emoji: "🏖",
    style: "Beach & Nature",
    styleColor: "bg-cyan-900/60 text-cyan-300 border-cyan-700/50",
    bestMonth: "Dec – May",
    vibe: "Lagoons · Diving · Pristine",
    desc: "Consistently ranked among the world's best islands — crystal-clear lagoons, secret beaches, and rich marine biodiversity.",
  },
  {
    id: 12,
    name: "Taipei",
    country: "Taiwan",
    emoji: "🌉",
    style: "Urban & Food",
    styleColor: "bg-indigo-900/60 text-indigo-300 border-indigo-700/50",
    bestMonth: "Oct – Dec",
    vibe: "Night Markets · Bubble Tea · Hiking",
    desc: "Friendly, affordable city famous for its legendary night markets, bubble tea culture, and easy access to dramatic mountain gorges.",
  },
];

const STYLE_FILTERS = [
  "All",
  "Beach & Nature",
  "Culture & Heritage",
  "Urban & Culture",
  "Culture & Adventure",
  "Culture & Food",
];

export default function Destinations() {
  const [filter, setFilter] = useState("All");

  const filtered =
    filter === "All"
      ? DESTINATIONS
      : DESTINATIONS.filter((d) => d.style === filter);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <Navbar />

      <div className="pt-24 pb-20 max-w-7xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-extrabold mb-3">
            East &amp; Southeast{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-300">
              Asia Destinations
            </span>
          </h1>
          <p className="text-slate-400 text-lg max-w-xl mx-auto">
            12 handpicked destinations our AI knows in depth — each with
            cultural context, best season, and travel style tags.
          </p>
        </div>

        {/* Map context banner */}
        <div className="bg-gradient-to-r from-teal-900/30 to-indigo-900/30 border border-slate-700/40 rounded-2xl p-5 mb-8 flex items-center gap-4">
          <div className="text-3xl">🗺</div>
          <div>
            <p className="text-sm font-semibold text-white">
              Coverage Area: 30°N – 10°S · 95°E – 122°E
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              Indonesia · Thailand · Japan · Vietnam · South Korea · Cambodia ·
              Malaysia · Singapore · Philippines · Taiwan
            </p>
          </div>
          <Link
            to="/planner"
            className="ml-auto text-sm font-semibold bg-teal-600 hover:bg-teal-500 text-white px-4 py-2 rounded-lg transition-all whitespace-nowrap"
          >
            Plan a Trip →
          </Link>
        </div>

        {/* Style filters */}
        <div className="flex flex-wrap gap-2 mb-8">
          {STYLE_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`text-sm px-4 py-1.5 rounded-full border transition-all ${
                filter === s
                  ? "bg-teal-600 border-teal-500 text-white"
                  : "bg-slate-800/50 border-slate-700/50 text-slate-400 hover:border-slate-500 hover:text-slate-200"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Cards grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {filtered.map((dest) => (
            <div
              key={dest.id}
              className="bg-slate-800/40 border border-slate-700/40 rounded-2xl p-5 hover:border-teal-700/50 hover:bg-slate-800/60 transition-all group cursor-default"
            >
              <div className="flex items-start justify-between mb-3">
                <span className="text-4xl">{dest.emoji}</span>
                <span
                  className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${dest.styleColor}`}
                >
                  {dest.style}
                </span>
              </div>

              <h3 className="text-lg font-bold text-white">{dest.name}</h3>
              <p className="text-sm text-slate-400 mb-2">{dest.country}</p>

              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                {dest.desc}
              </p>

              <div className="flex flex-col gap-1.5 text-xs text-slate-400 border-t border-slate-700/50 pt-3">
                <span>
                  <span className="text-slate-500 mr-1">📅</span> Best:{" "}
                  <span className="text-slate-300">{dest.bestMonth}</span>
                </span>
                <span>
                  <span className="text-slate-500 mr-1">✨</span>
                  <span className="text-slate-300">{dest.vibe}</span>
                </span>
              </div>
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center text-slate-500 py-20">
            No destinations match this filter.
          </div>
        )}
      </div>
    </div>
  );
}
