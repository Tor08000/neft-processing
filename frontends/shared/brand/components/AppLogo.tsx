import type { CSSProperties, SyntheticEvent } from "react";

import neftMark from "../assets/neft-mark.svg";

export type AppLogoProps = {
  variant?: "full" | "mark";
  size?: number;
  alt?: string;
  className?: string;
};

const defaultAlt = "NEFT Platform";

export function AppLogo({
  variant = "mark",
  size = 32,
  alt = defaultAlt,
  className,
}: AppLogoProps) {
  const classes = ["neft-brand-mark", className].filter(Boolean).join(" ");
  const style = {
    "--neft-brand-mark-size": `${size}px`,
  } as CSSProperties;
  const handleError = (event: SyntheticEvent<HTMLImageElement>) => {
    event.currentTarget.style.display = "none";
    const fallback = event.currentTarget.parentElement?.querySelector(".neft-brand-fallback") as
      | HTMLElement
      | null;
    if (fallback) fallback.style.display = "inline-block";
  };

  return (
    <span className="neft-brand-wrapper" aria-label={alt}>
      <img
        src={neftMark}
        width={size}
        height={size}
        alt={alt}
        className={classes}
        loading="lazy"
        onError={handleError}
        data-variant={variant}
        style={style}
      />
      <span className="neft-brand-fallback" style={{ display: "none" }} aria-hidden="true">
        NEFT
      </span>
    </span>
  );
}

export default AppLogo;
