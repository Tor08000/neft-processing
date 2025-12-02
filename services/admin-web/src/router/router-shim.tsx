import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

interface MatchResult {
  params: Record<string, string>;
}

interface RouteProps {
  path: string;
  element: React.ReactElement;
}

interface RouterContextValue {
  pathname: string;
  navigate: (to: string) => void;
  params: Record<string, string>;
}

const RouterContext = createContext<RouterContextValue | null>(null);

function matchPath(pattern: string, pathname: string): MatchResult | null {
  const patternParts = pattern.split("/").filter(Boolean);
  const pathParts = pathname.split("/").filter(Boolean);
  if (patternParts.length !== pathParts.length) return null;
  const params: Record<string, string> = {};

  for (let i = 0; i < patternParts.length; i += 1) {
    const patternPart = patternParts[i];
    const pathPart = pathParts[i];
    if (patternPart.startsWith(":")) {
      params[patternPart.slice(1)] = decodeURIComponent(pathPart);
    } else if (patternPart !== pathPart) {
      return null;
    }
  }

  return { params };
}

export const BrowserRouter: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [pathname, setPathname] = useState<string>(window.location.pathname);

  useEffect(() => {
    const handler = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);

  const navigate = (to: string) => {
    if (to !== window.location.pathname) {
      window.history.pushState({}, "", to);
      setPathname(to);
    }
  };

  const value = useMemo<RouterContextValue>(
    () => ({ pathname, navigate, params: {} }),
    [pathname],
  );

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
};

export const Route: React.FC<RouteProps> = () => null;

export const Routes: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const router = useContext(RouterContext);
  if (!router) throw new Error("Routes must be used inside BrowserRouter");

  let match: MatchResult | null = null;
  let element: React.ReactElement | null = null;

  for (const child of React.Children.toArray(children)) {
    if (!React.isValidElement<RouteProps>(child)) continue;
    const props = child.props as RouteProps;
    const result = matchPath(props.path, router.pathname);
    if (result) {
      match = result;
      element = props.element;
      break;
    }
  }

  if (!element) return null;

  const params = match ? match.params : {};

  const value: RouterContextValue = {
    pathname: router.pathname,
    navigate: router.navigate,
    params,
  };

  return <RouterContext.Provider value={value}>{element}</RouterContext.Provider>;
};

export function Link({ to, children, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) {
  const router = useContext(RouterContext);
  if (!router) throw new Error("Link must be used inside BrowserRouter");

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    router.navigate(to);
  };

  return (
    <a href={to} onClick={handleClick} {...rest}>
      {children}
    </a>
  );
}

export function useLocation() {
  const router = useContext(RouterContext);
  if (!router) throw new Error("useLocation must be used inside BrowserRouter");
  return { pathname: router.pathname };
}

export function useNavigate() {
  const router = useContext(RouterContext);
  if (!router) throw new Error("useNavigate must be used inside BrowserRouter");
  return router.navigate;
}

export function useParams<T extends Record<string, string>>() {
  const router = useContext(RouterContext);
  if (!router) throw new Error("useParams must be used inside BrowserRouter");
  return router.params as T;
}
