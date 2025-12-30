import type { ReactNode } from "react";

type IconProps = {
  size?: number;
  className?: string;
};

const Icon = ({ size = 20, className, children }: IconProps & { children: ReactNode }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    {children}
  </svg>
);

export const ShoppingCart = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="9" cy="20" r="1.5" />
    <circle cx="18" cy="20" r="1.5" />
    <path d="M3 4h2l2.2 10.5a2 2 0 0 0 2 1.5h8.8a2 2 0 0 0 1.9-1.3L22 8H7" />
  </Icon>
);

export const Package = (props: IconProps) => (
  <Icon {...props}>
    <path d="M3 7l9-4 9 4-9 4-9-4z" />
    <path d="M3 7v10l9 4 9-4V7" />
    <path d="M12 11v10" />
  </Icon>
);

export const FileText = (props: IconProps) => (
  <Icon {...props}>
    <path d="M6 3h9l3 3v15H6z" />
    <path d="M9 11h6" />
    <path d="M9 15h6" />
  </Icon>
);

export const FileSpreadsheet = (props: IconProps) => (
  <Icon {...props}>
    <path d="M6 3h9l3 3v15H6z" />
    <path d="M9 10h6" />
    <path d="M9 14h6" />
    <path d="M9 18h6" />
  </Icon>
);

export const LayoutDashboard = (props: IconProps) => (
  <Icon {...props}>
    <rect x="3" y="3" width="8" height="8" rx="1.5" />
    <rect x="13" y="3" width="8" height="5" rx="1.5" />
    <rect x="13" y="10" width="8" height="11" rx="1.5" />
    <rect x="3" y="13" width="8" height="8" rx="1.5" />
  </Icon>
);

export const LineChart = (props: IconProps) => (
  <Icon {...props}>
    <path d="M3 17l6-6 4 4 7-7" />
    <path d="M3 21h18" />
  </Icon>
);

export const Workflow = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="5" cy="5" r="2" />
    <circle cx="19" cy="12" r="2" />
    <circle cx="5" cy="19" r="2" />
    <path d="M7 5h6l4 6" />
    <path d="M7 19h6l4-6" />
  </Icon>
);

export const ClipboardCheck = (props: IconProps) => (
  <Icon {...props}>
    <rect x="6" y="4" width="12" height="17" rx="2" />
    <path d="M9 4h6v3H9z" />
    <path d="M9 13l2 2 4-4" />
  </Icon>
);

export const Settings = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19 12a7 7 0 0 0-.1-1l2.1-1.6-2-3.5-2.5 1a7 7 0 0 0-1.7-1l-.4-2.7h-4l-.4 2.7a7 7 0 0 0-1.7 1l-2.5-1-2 3.5 2.1 1.6a7 7 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7 7 0 0 0 1.7 1l.4 2.7h4l.4-2.7a7 7 0 0 0 1.7-1l2.5 1 2-3.5-2.1-1.6c.1-.3.1-.7.1-1z" />
  </Icon>
);
