import type { ToolEntry } from "../../services/api";

interface Props {
  tools_used: ToolEntry[];
}

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

function ToolItem({ entry, index }: { entry: ToolEntry; index: number }) {
  const name = entry.tool;
  const color = toolColor(name);
  const hasInput = entry.input !== undefined && Object.keys(entry.input).length > 0;

  return (
    <details className="tt-item">
      <summary className="tt-summary">
        <span className="tt-num">{index + 1}</span>
        <span
          className="tt-badge"
          style={{ background: `${color}18`, color, border: `1px solid ${color}44` }}
        >
          {entry.type === "call" ? "→" : "←"} {name}
        </span>
      </summary>
      <div className="tt-body">
        {hasInput && (
          <div className="tt-section">
            <span className="tt-label">Input</span>
            <pre className="tt-json">{JSON.stringify(entry.input, null, 2)}</pre>
          </div>
        )}
        {entry.output && (
          <div className="tt-section">
            <span className="tt-label">Output</span>
            <pre className="tt-json">{entry.output}</pre>
          </div>
        )}
      </div>
    </details>
  );
}

export default function ToolTrace({ tools_used }: Props) {
  if (!tools_used?.length) return null;
  return (
    <details className="tool-trace tt-root">
      <summary className="tt-root-summary">
        <span className="tt-root-label">
          {tools_used.filter((t) => t.type === "call").length} tool call
          {tools_used.filter((t) => t.type === "call").length !== 1 ? "s" : ""}
        </span>
      </summary>
      <div className="tt-list">
        {tools_used.map((entry, i) => (
          <ToolItem key={i} entry={entry} index={i} />
        ))}
      </div>
    </details>
  );
}
