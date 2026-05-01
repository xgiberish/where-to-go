import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Navbar() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/");
    setMenuOpen(false);
  };

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-medium transition-colors ${
      isActive
        ? "text-teal-400"
        : "text-slate-300 hover:text-white"
    }`;

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-900/95 backdrop-blur border-b border-slate-700/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 group">
            <span className="text-2xl">✈</span>
            <span className="font-bold text-white text-lg">
              Where To Go
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
            <NavLink to="/" end className={linkClass}>Home</NavLink>
            <NavLink to="/destinations" className={linkClass}>Destinations</NavLink>
            <NavLink to="/about" className={linkClass}>About</NavLink>
            {token && (
              <NavLink to="/planner" className={linkClass}>Planner</NavLink>
            )}
          </div>

          {/* Auth actions */}
          <div className="hidden md:flex items-center gap-3">
            {token ? (
              <button
                onClick={handleLogout}
                className="text-sm font-medium text-slate-300 hover:text-white border border-slate-600 hover:border-slate-400 px-4 py-1.5 rounded-full transition-all"
              >
                Sign Out
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  to="/signup"
                  className="text-sm font-semibold bg-teal-600 hover:bg-teal-500 text-white px-4 py-1.5 rounded-full transition-all"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden text-slate-300 hover:text-white"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden bg-slate-900 border-t border-slate-700/50 px-4 py-4 flex flex-col gap-3">
          <NavLink to="/" end className={linkClass} onClick={() => setMenuOpen(false)}>Home</NavLink>
          <NavLink to="/destinations" className={linkClass} onClick={() => setMenuOpen(false)}>Destinations</NavLink>
          <NavLink to="/about" className={linkClass} onClick={() => setMenuOpen(false)}>About</NavLink>
          {token && (
            <NavLink to="/planner" className={linkClass} onClick={() => setMenuOpen(false)}>Planner</NavLink>
          )}
          <div className="pt-2 border-t border-slate-700/50 flex flex-col gap-2">
            {token ? (
              <button onClick={handleLogout} className="text-sm text-slate-300 hover:text-white text-left">
                Sign Out
              </button>
            ) : (
              <>
                <Link to="/login" className="text-sm text-slate-300 hover:text-white" onClick={() => setMenuOpen(false)}>
                  Sign In
                </Link>
                <Link to="/signup" className="text-sm font-semibold text-teal-400" onClick={() => setMenuOpen(false)}>
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
