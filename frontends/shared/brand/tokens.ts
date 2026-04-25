import { brandColors } from "./tokens/colors";
import { brandMotion } from "./tokens/motion";
import { brandRadius } from "./tokens/radius";
import { brandShadow } from "./tokens/shadow";
import { brandSpacing } from "./tokens/spacing";
import { brandTypography } from "./tokens/typography";

export const brandTokens = {
  colors: brandColors,
  motion: brandMotion,
  radii: brandRadius,
  shadows: brandShadow,
  spacing: brandSpacing,
  typography: brandTypography,
} as const;

export type BrandTokens = typeof brandTokens;
