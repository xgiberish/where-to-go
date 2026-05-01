import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import type { ToolEntry } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";
import ToolTrace from "../ToolTrace/ToolTrace";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolsUsed?: ToolEntry[];
}

export default function ChatInterface() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const send = async () => {
    const query = input.trim();
    if (!query || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setLoading(true);
    try {
      const { data } = await api.queryAgent(query);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response ?? "Your trip is being planned…",
          toolsUsed: data.tool_trace,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <header>
        <h2>Where To Go</h2>
        <button onClick={handleLogout}>Logout</button>
      </header>

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <p>{m.content}</p>
            {m.toolsUsed && <ToolTrace tools_used={m.toolsUsed} />}
          </div>
        ))}
        {loading && <div className="message assistant">Planning your trip…</div>}
      </div>

      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Where do you want to go?"
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
