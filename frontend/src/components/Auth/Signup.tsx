import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api";

export default function Signup() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Redirect to login 1.5s after successful signup
  useEffect(() => {
    if (!success) return;
    const timer = setTimeout(() => navigate("/login"), 1500);
    return () => clearTimeout(timer);
  }, [success, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.signup(email, password);
      setSuccess(true);
    } catch {
      setError("Sign-up failed. Email may already be in use.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center px-4">
      <Link
        to="/"
        className="flex items-center gap-2 mb-8 text-white hover:text-teal-300 transition-colors"
      >
        <span className="text-2xl">✈</span>
        <span className="font-bold text-lg">Where To Go</span>
      </Link>

      <div className="auth-container w-full" style={{ maxWidth: 400 }}>
        <h1>Create Account</h1>

        {success ? (
          <div style={{ textAlign: "center", padding: "1rem 0" }}>
            <p style={{ color: "#38a169", fontWeight: 600, marginBottom: "0.75rem" }}>
              ✓ Account created successfully!
            </p>
            <p style={{ color: "#718096", fontSize: "0.9rem", marginBottom: "1rem" }}>
              Redirecting to sign in…
            </p>
            <Link to="/login" style={{ color: "#3182ce", fontSize: "0.9rem" }}>
              Go to Login →
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <input
              type="password"
              placeholder="Password (min 8 chars)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
            {error && <p className="error">{error}</p>}
            <button type="submit" disabled={loading}>
              {loading ? "Creating account…" : "Sign Up"}
            </button>
          </form>
        )}

        {!success && (
          <p>
            Have an account? <Link to="/login">Sign in</Link>
          </p>
        )}
      </div>
    </div>
  );
}
