import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api";

export default function Signup() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.signup(email, password);
      navigate("/login");
    } catch {
      setError("Sign-up failed. Email may already be in use.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <h1>Create Account</h1>
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
      <p>
        Have an account? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}
