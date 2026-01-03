export const prefersReducedMotion = (): boolean => {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
};

export const motionConfig = {
  transitionMs: 220,
  easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
};
