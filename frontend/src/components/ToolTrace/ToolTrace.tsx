// ── Types ─────────────────────────────────────────────────────────────────────

export interface ToolEntry {
  tool_name: string;
  input?: Record<string, unknown>;
  output?: unknown;
  error?: string | null;
  timestamp?: string;   // ISO 8601
  duration_ms?: number;
}

interface Props {
  tools_used: ToolEntry[];
}

// ── Color palette (matched by substring in tool_name) ─────────────────────────

const PALETTE: [string, string][] = [
  ["rag", "#6b46c1"],
  ["retrieval", "#6b46c1"],
  ["classifier", "#2b6cb0"],
  ["ml", "#2b6cb0"],
  ["weather", "#c05621"],
  ["live", "#c05621"],
  ["api", "#c05621"],
  ["search", "#276749"],
];

function toolColor(name: string): string {
  const lower = name.toLowerCase();
  for (const [key, color] of PALETTE) {
    if (lower.includes(key)) return color;
  }
  return "#4a5568";
}

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtDuration(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function JsonBlock({ value }: { value: unknown }) {
  const text =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return <pre className="tt-json">{text}</pre>;
}

function ToolItem({ entry, index }: { entry: ToolEntry; index: number }) {
  const color = toolColor(entry.tool_name);
  const hasError = Boolean(entry.error);
  const hasInput =
    entry.input !== undefined && Object.keys(entry.input).length > 0;
  const hasOutput = entry.output !== undefined;

  return (
    <details className="tt-item">
      <summary className="tt-summary">
        <span className="tt-num">{index + 1}</span>

        <span
          className="tt-badge"
          style={{
            background: `${color}18`,
            color,
            border: `1px solid ${color}44`,
          }}
        >
          {entry.tool_name}
        </span>

        <span
          className={`tt-dot ${hasError ? "tt-dot--err" : "tt-dot--ok"}`}
          title={hasError ? `Error: ${entry.error ?? ""}` : "Success"}
        />

        {entry.duration_ms !== undefined && (
          <span className="tt-meta">{fmtDuration(entry.duration_ms)}</span>
        )}

        {entry.timestamp && (
          <span className="tt-meta tt-meta--time">{fmtTime(entry.timestamp)}</span>
        )}
      </summary>

      <div className="tt-body">
        {hasInput && (
          <div className="tt-section">
            <span className="tt-label">Input</span>
            <JsonBlock value={entry.input} />
          </div>
        )}

        {hasOutput && !hasError && (
          <div className="tt-section">
            <span className="tt-label">Output</span>
            <JsonBlock value={entry.output} />
          </div>
        )}

        {hasError && (
          <div className="tt-section">
            <span className="tt-label tt-label--err">Error</span>
            <JsonBlock value={entry.error} />
          </div>
        )}
      </div>
    </details>
  );
}

// ── Root component ────────────────────────────────────────────────────────────

export default function ToolTrace({ tools_used }: Props) {
  if (!tools_used?.length) return null;

  const errorCount = tools_used.filter((t) => t.error).length;
  const totalDuration = tools_used.reduce(
    (sum, t) => sum + (t.duration_ms ?? 0),
    0
  );

  return (
    <details className="tool-trace tt-root">
      <summary className="tt-root-summary">
        <span className="tt-root-label">
          {tools_used.length} tool call{tools_used.length !== 1 ? "s" : ""}
        </span>
        {totalDuration > 0 && (
          <span className="tt-meta">{fmtDuration(totalDuration)} total</span>
        )}
        {errorCount > 0 && (
          <span className="tt-err-count">
            {errorCount} error{errorCount !== 1 ? "s" : ""}
          </span>
        )}
      </summary>

      <div className="tt-list">
        {tools_used.map((entry, i) => (
          <ToolItem key={i} entry={entry} index={i} />
        ))}
      </div>
    </details>
  );
}
