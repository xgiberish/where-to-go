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
  cost_analysis?: CostBreakdown;
}

export interface AgentRunSummary {
  id: string;
  query: string;
  status: string;
  created_at: string;
}

export interface CostBreakdown {
  cheap_model: string;
  cheap_calls: number;
  cheap_input_tokens: number;
  cheap_output_tokens: number;
  strong_model: string;
  strong_calls: number;
  strong_input_tokens: number;
  strong_output_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  actual_cost_usd: number;
  gemini_flash_lite_usd: number;
  gemini_flash_usd: number;
  gemini_pro_usd: number;
}

export interface DiscordSendResponse {
  success: boolean;
  message: string;
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

  sendToDiscord: (
    query: string,
    response: string,
    status: string,
    tool_trace?: ToolEntry[],
  ) =>
    client.post<DiscordSendResponse>("/webhooks/discord/send-plan", {
      query,
      response,
      status,
      tool_trace,
    }),
};
