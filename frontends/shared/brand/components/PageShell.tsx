import React from "react";

export type PageShellProps = {
  children: React.ReactNode;
  className?: string;
};

export const PageShell: React.FC<PageShellProps> = ({ children, className }) => {
  return <div className={`brand-page-shell${className ? ` ${className}` : ""}`}>{children}</div>;
};

export default PageShell;
