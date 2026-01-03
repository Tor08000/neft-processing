export const brandTokens = {
  colors: {
    background: "#0B0F14",
    backgroundAlt: "#0F1621",
    surface: "#121B27",
    surfaceAlt: "#162235",
    border: "#243247",
    borderAlt: "#2E3F5C",
    text: "#EAF0F8",
    textMuted: "#A9B4C4",
    textFaint: "#7B879A",
    accent: "#B6FF3B",
    accentHover: "#A6F72A",
    accentSoft: "rgba(182, 255, 59, 0.14)",
    accentGlow: "rgba(182, 255, 59, 0.28)",
    success: "#2FEA9B",
    warning: "#FFB020",
    danger: "#FF4D4D",
    info: "#4DA3FF",
    neutral: "#94A3B8",
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
    sans: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial, sans-serif",
    mono: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  },
} as const;

export type BrandTokens = typeof brandTokens;
