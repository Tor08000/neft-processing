import { useEffect, useRef } from "react";

export function useConditionalPolling(enabled: boolean, interval: number, callback: () => void) {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const timer = window.setInterval(() => {
      callbackRef.current();
    }, interval);

    return () => {
      window.clearInterval(timer);
    };
  }, [enabled, interval]);
}
