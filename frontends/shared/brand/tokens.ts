export const brandTokens = {
  colors: {
    background: "#0B1F2A",
    backgroundAlt: "#111827",
    surface: "#1F2937",
    surfaceAlt: "#2C3E50",
    border: "#2C3E50",
    borderAlt: "#243447",
    text: "#E5E7EB",
    textMuted: "#9CA3AF",
    textFaint: "#6B7280",
    accent: "#15A1C7",
    accentHover: "#15A1C7",
    accentSoft: "rgba(21, 161, 199, 0.18)",
    accentGlow: "rgba(21, 161, 199, 0.32)",
    success: "#0EE8A8",
    warning: "#FFB020",
    danger: "#E5484D",
    info: "#3B82F6",
    neutral: "#9CA3AF",
  },
  radii: {
    card: "16px",
    control: "12px",
    pill: "999px",
  },
  shadows: {
    sm: "0 1px 0 rgba(0,0,0,0.35), 0 8px 16px rgba(0,0,0,0.25)",
    md: "0 2px 0 rgba(0,0,0,0.35), 0 14px 28px rgba(0,0,0,0.32)",
    lg: "0 3px 0 rgba(0,0,0,0.40), 0 20px 42px rgba(0,0,0,0.40)",
  },
  spacing: {
    xs: "6px",
    sm: "10px",
    md: "16px",
    lg: "24px",
    xl: "32px",
  },
  typography: {
    sans: "Inter, system-ui, 'Segoe UI', sans-serif",
    mono: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  },
} as const;

export type BrandTokens = typeof brandTokens;
