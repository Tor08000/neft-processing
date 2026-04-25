import type { CSSProperties, SyntheticEvent } from "react";

import neftMark from "../assets/neft-mark.svg";

export type AppLogoTone = "default" | "white" | "gold" | "danger" | "black";

export type AppLogoProps = {
  variant?: "full" | "mark";
  tone?: AppLogoTone;
  size?: number;
  alt?: string;
  className?: string;
};

const defaultAlt = "NEFT Platform";

export function AppLogo({
  variant = "mark",
  tone = "default",
  size = 32,
  alt = defaultAlt,
  className,
}: AppLogoProps) {
  const classes = ["neft-brand-mark", `is-${tone}`, className].filter(Boolean).join(" ");
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
    <span className={`neft-brand-wrapper is-${tone}`} aria-label={alt} data-variant={variant}>
      <img
        src={neftMark}
        width={size}
        height={size}
        alt={alt}
        className={classes}
        loading="lazy"
        onError={handleError}
        style={style}
      />
      <span className="neft-brand-fallback" style={{ display: "none" }} aria-hidden="true">
        NEFT
      </span>
      {variant === "full" ? (
        <span className="neft-brand-copy" aria-hidden="true">
          <span className="neft-brand-wordmark">NEFT</span>
          <span className="neft-brand-submark">platform</span>
        </span>
      ) : null}
    </span>
  );
}

export default AppLogo;
