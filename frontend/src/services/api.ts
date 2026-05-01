import axios from "axios";

const TOKEN_KEY = "wtg_token";

const client = axios.create({ baseURL: "/api/v1" });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

/** A single tool invocation entry from extract_tool_trace */
export interface ToolEntry {
  type: "call" | "result";
  tool: string;
  input?: Record<string, unknown>;
  output?: string;
}

export interface AgentResponse {
  run_id: string;
  status: string;
  response?: string;
  tool_trace?: ToolEntry[];
}

export interface AgentRunSummary {
  id: string;
  query: string;
  status: string;
  created_at: string;
}

export const api = {
  signup: (email: string, password: string) =>
    client.post("/auth/signup", { email, password }),

  login: (email: string, password: string) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    return client.post<LoginResponse>("/auth/login", form);
  },

  queryAgent: (query: string) =>
    client.post<AgentResponse>("/agent/query", { query }),

  getHistory: () => client.get<AgentRunSummary[]>("/history/"),
};
