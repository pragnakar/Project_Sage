import { useState } from "react";

const COLORS = {
  bg: "#0f1117",
  surface: "#1a1d27",
  border: "#2a2d3e",
  accent: "#7c6af7",
  accentSoft: "#2d2850",
  green: "#34d399",
  greenSoft: "#0d2e22",
  blue: "#60a5fa",
  blueSoft: "#1a2840",
  orange: "#fb923c",
  orangeSoft: "#2d1a0e",
  yellow: "#fbbf24",
  yellowSoft: "#2a1f00",
  text: "#e2e8f0",
  textMuted: "#64748b",
  textDim: "#94a3b8",
};

const TOOLTIPS = {
  llm: "LLM stays outside Groot. Claude, ChatGPT, or any MCP-compatible agent calls Groot tools over MCP or HTTP. Groot never embeds a model.",
  mcp: "Groot exposes tools via MCP (stdio or SSE) and REST HTTP. Same protocol SAGE uses. LLMs call create_page, write_blob, list_artifacts etc.",
  runtime: "FastAPI server. Validates all tool calls, enforces sandboxing, routes to artifact store or page server. The deterministic layer.",
  toolRegistry: "Pluggable tool registry. Core tools ship with Groot. App-specific tools (e.g. SAGE's solve_optimization) register at startup.",
  artifactStore: "SQLite + filesystem. Every component, page, blob, schema the LLM creates is stored here. The flywheel — grows every session.",
  pageServer: "Serves the React shell and all registered pages. Each create_page call adds a new route. No rebuild needed.",
  sage: "First Groot app. Registers SAGE-specific tools (solve, explain, etc.) and SAGE-specific React pages (dashboard, sensitivity). Imports sage-solver-core.",
  hermes: "Future: COBOL→Mojo translation interface. Groot provides the runtime; Hermes provides the domain tools.",
  athena: "Future: AI governance audit interface. Same pattern — Groot runtime, Athena domain tools.",
  claudeChat: "This chat. Claude generates React components here for Peter to approve. Approved artifacts get staged to Groot via create_page. Chat = design surface.",
};

function Tooltip({ text, visible }) {
  if (!visible) return null;
  return (
    <div style={{
      position: "absolute",
      bottom: "calc(100% + 10px)",
      left: "50%",
      transform: "translateX(-50%)",
      background: "#1e2235",
      border: `1px solid ${COLORS.accent}`,
      borderRadius: 8,
      padding: "10px 14px",
      width: 260,
      fontSize: 12,
      lineHeight: 1.6,
      color: COLORS.textDim,
      zIndex: 100,
      pointerEvents: "none",
      boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
    }}>
      {text}
      <div style={{
        position: "absolute",
        top: "100%",
        left: "50%",
        transform: "translateX(-50%)",
        width: 0,
        height: 0,
        borderLeft: "6px solid transparent",
        borderRight: "6px solid transparent",
        borderTop: `6px solid ${COLORS.accent}`,
      }} />
    </div>
  );
}

function Box({ label, sublabel, color, softColor, tooltipKey, hovered, setHovered, style = {} }) {
  const isHovered = hovered === tooltipKey;
  return (
    <div
      style={{
        position: "relative",
        background: isHovered ? softColor : COLORS.surface,
        border: `1.5px solid ${isHovered ? color : COLORS.border}`,
        borderRadius: 10,
        padding: "10px 16px",
        cursor: "default",
        transition: "all 0.15s ease",
        userSelect: "none",
        ...style,
      }}
      onMouseEnter={() => setHovered(tooltipKey)}
      onMouseLeave={() => setHovered(null)}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: isHovered ? color : COLORS.text }}>{label}</div>
      {sublabel && <div style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }}>{sublabel}</div>}
      <Tooltip text={TOOLTIPS[tooltipKey]} visible={isHovered} />
    </div>
  );
}

function Arrow({ vertical = false, label, color = COLORS.textMuted }) {
  if (vertical) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, margin: "4px 0" }}>
        {label && <div style={{ fontSize: 10, color: COLORS.textMuted, fontFamily: "monospace" }}>{label}</div>}
        <div style={{ width: 1.5, height: 18, background: color }} />
        <div style={{ width: 0, height: 0, borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderTop: `6px solid ${color}` }} />
      </div>
    );
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      {label && <div style={{ fontSize: 10, color: COLORS.textMuted, fontFamily: "monospace" }}>{label}</div>}
      <div style={{ height: 1.5, width: 24, background: color }} />
      <div style={{ width: 0, height: 0, borderTop: "5px solid transparent", borderBottom: "5px solid transparent", borderLeft: `6px solid ${color}` }} />
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: "0.12em",
      textTransform: "uppercase",
      color: COLORS.textMuted,
      marginBottom: 8,
    }}>
      {children}
    </div>
  );
}

function FlywheelBadge() {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 6,
      background: "#1a1f0e",
      border: "1px solid #4ade80",
      borderRadius: 20,
      padding: "4px 12px",
      fontSize: 11,
      color: "#4ade80",
      fontWeight: 600,
    }}>
      <span style={{ fontSize: 14 }}>↻</span> Artifact flywheel — grows every session
    </div>
  );
}

export default function GrootArchitecture() {
  const [hovered, setHovered] = useState(null);

  return (
    <div style={{
      background: COLORS.bg,
      minHeight: "100vh",
      fontFamily: "'Inter', -apple-system, sans-serif",
      padding: "32px 24px",
      color: COLORS.text,
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 36 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.text, marginBottom: 6 }}>
          🌱 Project Groot — Runtime Architecture
        </div>
        <div style={{ fontSize: 13, color: COLORS.textMuted }}>
          Hover any component for details · v0.1 MVP scope
        </div>
      </div>

      <div style={{ maxWidth: 720, margin: "0 auto", display: "flex", flexDirection: "column", alignItems: "center", gap: 0 }}>

        {/* === LLM CLIENTS === */}
        <div style={{ width: "100%" }}>
          <SectionLabel>LLM Clients — External</SectionLabel>
          <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
            <Box
              label="Claude Desktop"
              sublabel="MCP stdio"
              color={COLORS.accent}
              softColor={COLORS.accentSoft}
              tooltipKey="llm"
              hovered={hovered}
              setHovered={setHovered}
              style={{ flex: 1 }}
            />
            <Box
              label="ChatGPT"
              sublabel="MCP SSE"
              color={COLORS.accent}
              softColor={COLORS.accentSoft}
              tooltipKey="llm"
              hovered={hovered}
              setHovered={setHovered}
              style={{ flex: 1 }}
            />
            <div
              style={{
                position: "relative",
                flex: 1,
                background: hovered === "claudeChat" ? "#0d1f2d" : COLORS.surface,
                border: `1.5px solid ${hovered === "claudeChat" ? COLORS.blue : "#3b82f6aa"}`,
                borderRadius: 10,
                padding: "10px 16px",
                cursor: "default",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={() => setHovered("claudeChat")}
              onMouseLeave={() => setHovered(null)}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: hovered === "claudeChat" ? COLORS.blue : "#93c5fd" }}>
                Claude in Chat ✦
              </div>
              <div style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }}>design surface</div>
              <Tooltip text={TOOLTIPS.claudeChat} visible={hovered === "claudeChat"} />
            </div>
          </div>
        </div>

        <Arrow vertical label="MCP / HTTP" color={COLORS.accent} />

        {/* === GROOT RUNTIME === */}
        <div style={{
          width: "100%",
          background: COLORS.accentSoft,
          border: `1.5px solid ${COLORS.accent}`,
          borderRadius: 14,
          padding: 20,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: COLORS.accent, marginBottom: 14 }}>
            Groot Runtime · FastAPI
          </div>

          {/* Tool Registry + Runtime core */}
          <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
            <Box
              label="Tool Registry"
              sublabel="pluggable · validates all calls"
              color={COLORS.yellow}
              softColor={COLORS.yellowSoft}
              tooltipKey="toolRegistry"
              hovered={hovered}
              setHovered={setHovered}
              style={{ flex: 1 }}
            />
            <Box
              label="Groot Runtime Core"
              sublabel="sandboxing · routing · auth"
              color={COLORS.accent}
              softColor={COLORS.accentSoft}
              tooltipKey="runtime"
              hovered={hovered}
              setHovered={setHovered}
              style={{ flex: 1.4 }}
            />
            <Box
              label="MCP Transport"
              sublabel="stdio + SSE"
              color={COLORS.yellow}
              softColor={COLORS.yellowSoft}
              tooltipKey="mcp"
              hovered={hovered}
              setHovered={setHovered}
              style={{ flex: 1 }}
            />
          </div>

          {/* Storage + Page Server */}
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <Box
                label="Artifact Store"
                sublabel="SQLite + filesystem"
                color={COLORS.green}
                softColor={COLORS.greenSoft}
                tooltipKey="artifactStore"
                hovered={hovered}
                setHovered={setHovered}
              />
              <div style={{ marginTop: 8, padding: "8px 12px", background: COLORS.greenSoft, borderRadius: 8, border: `1px dashed ${COLORS.green}44` }}>
                <div style={{ fontSize: 10, color: COLORS.green, fontWeight: 600, marginBottom: 4 }}>Accumulates →</div>
                {["React components", "Pages · routes", "Blobs · schemas", "Session memory"].map(item => (
                  <div key={item} style={{ fontSize: 11, color: COLORS.textMuted, lineHeight: 1.8 }}>• {item}</div>
                ))}
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <Box
                label="Page Server"
                sublabel="React shell · dynamic routes"
                color={COLORS.blue}
                softColor={COLORS.blueSoft}
                tooltipKey="pageServer"
                hovered={hovered}
                setHovered={setHovered}
              />
              <div style={{ marginTop: 8, padding: "8px 12px", background: COLORS.blueSoft, borderRadius: 8, border: `1px dashed ${COLORS.blue}44` }}>
                <div style={{ fontSize: 10, color: COLORS.blue, fontWeight: 600, marginBottom: 4 }}>Serves →</div>
                {["/ dashboard", "/apps/:name", "/artifacts", "API · /docs"].map(item => (
                  <div key={item} style={{ fontSize: 11, color: COLORS.textMuted, lineHeight: 1.8, fontFamily: "monospace" }}>• {item}</div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <Arrow vertical label="imports · registers tools" color={COLORS.textMuted} />

        {/* === GROOT APPS === */}
        <div style={{ width: "100%" }}>
          <SectionLabel>Groot Apps — Domain Modules</SectionLabel>
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{
              flex: 1.4,
              background: COLORS.greenSoft,
              border: `1.5px solid ${COLORS.green}`,
              borderRadius: 10,
              padding: "12px 16px",
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: COLORS.green, marginBottom: 6 }}>
                sage/ · v0.2 ← First Groot app
              </div>
              <div style={{ fontSize: 11, color: COLORS.textMuted, lineHeight: 1.7 }}>
                solve · explain · feasibility<br />
                sensitivity dashboard · report<br />
                imports sage-solver-core
              </div>
            </div>
            <Box
              label="hermes/"
              sublabel="COBOL→Mojo · future"
              color={COLORS.orange}
              softColor={COLORS.orangeSoft}
              tooltipKey="hermes"
              hovered={hovered}
              setHovered={setHovered}
              style={{ flex: 1 }}
            />
            <Box
              label="athena/"
              sublabel="AI governance · future"
              color={COLORS.blue}
              softColor={COLORS.blueSoft}
              tooltipKey="athena"
              hovered={hovered}
              setHovered={setHovered}
              style={{ flex: 1 }}
            />
          </div>
        </div>

        {/* Flywheel badge */}
        <div style={{ marginTop: 28 }}>
          <FlywheelBadge />
        </div>

        {/* Legend */}
        <div style={{
          marginTop: 24,
          padding: "14px 20px",
          background: COLORS.surface,
          border: `1px solid ${COLORS.border}`,
          borderRadius: 10,
          width: "100%",
          display: "flex",
          gap: 24,
          flexWrap: "wrap",
          justifyContent: "center",
        }}>
          {[
            { color: COLORS.accent, label: "Groot core" },
            { color: COLORS.green, label: "Artifact / storage layer" },
            { color: COLORS.blue, label: "Web / serving layer" },
            { color: COLORS.yellow, label: "Protocol / transport" },
            { color: COLORS.orange, label: "Future Groot apps" },
          ].map(({ color, label }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <div style={{ width: 10, height: 10, borderRadius: 3, background: color }} />
              <span style={{ fontSize: 11, color: COLORS.textMuted }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
