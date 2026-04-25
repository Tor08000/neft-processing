export const brandTypography = {
  family: {
    sans: 'Inter, Manrope, "SF Pro Display", system-ui, sans-serif',
    mono: '"JetBrains Mono", ui-monospace, monospace',
  },
  display: {
    lg: { fontSize: "40px", lineHeight: "48px", fontWeight: 700 },
    md: { fontSize: "32px", lineHeight: "40px", fontWeight: 700 },
    sm: { fontSize: "28px", lineHeight: "36px", fontWeight: 700 },
  },
  heading: {
    lg: { fontSize: "24px", lineHeight: "32px", fontWeight: 700 },
    md: { fontSize: "20px", lineHeight: "28px", fontWeight: 700 },
    sm: { fontSize: "18px", lineHeight: "24px", fontWeight: 700 },
  },
  body: {
    lg: { fontSize: "16px", lineHeight: "24px", fontWeight: 400 },
    md: { fontSize: "14px", lineHeight: "20px", fontWeight: 400 },
    sm: { fontSize: "12px", lineHeight: "18px", fontWeight: 400 },
  },
  label: {
    lg: { fontSize: "14px", lineHeight: "20px", fontWeight: 600 },
    md: { fontSize: "12px", lineHeight: "16px", fontWeight: 600 },
    sm: { fontSize: "11px", lineHeight: "14px", fontWeight: 600 },
  },
  metric: {
    lg: { fontSize: "36px", lineHeight: "40px", fontWeight: 700 },
    md: { fontSize: "28px", lineHeight: "32px", fontWeight: 700 },
    sm: { fontSize: "22px", lineHeight: "28px", fontWeight: 700 },
  },
} as const;
