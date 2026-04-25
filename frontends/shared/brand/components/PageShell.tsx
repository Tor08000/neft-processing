import type { ReactNode } from "react";

export type PageShellProps = {
  children: ReactNode;
  className?: string;
};

export function PageShell({ children, className }: PageShellProps) {
  return (
    <div className={`brand-page-shell${className ? ` ${className}` : ""}`}>
      {children}
    </div>
  );
}

export default PageShell;
