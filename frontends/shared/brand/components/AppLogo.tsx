import React from "react";

export type AppLogoProps = {
  variant?: "full" | "mark";
  size?: number;
  alt?: string;
  className?: string;
};

const defaultAlt = "NEFT Platform";

export const AppLogo: React.FC<AppLogoProps> = ({
  variant = "mark",
  size = 32,
  alt = defaultAlt,
  className,
}) => {
  const base = (import.meta.env.BASE_URL ?? "/").replace(/\/+$/, "");
  const src = variant === "full" ? `${base}/brand/logo.png` : `${base}/brand/logo-mark.png`;
  return <img src={src} width={size} height={size} alt={alt} className={className} loading="lazy" />;
};

export default AppLogo;
