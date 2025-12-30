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

export const LayoutDashboard = (props: IconProps) => (
  <Icon {...props}>
    <rect x="3" y="3" width="8" height="8" rx="1.5" />
    <rect x="13" y="3" width="8" height="5" rx="1.5" />
    <rect x="13" y="10" width="8" height="11" rx="1.5" />
    <rect x="3" y="13" width="8" height="8" rx="1.5" />
  </Icon>
);

export const Fuel = (props: IconProps) => (
  <Icon {...props}>
    <rect x="4" y="3" width="10" height="18" rx="2" />
    <path d="M14 7h3l2 2v8a2 2 0 0 1-2 2h-3" />
    <path d="M7 7h4" />
  </Icon>
);

export const BadgeDollarSign = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v10" />
    <path d="M9.5 9.5c0-1 1-2 2.5-2h2.5" />
    <path d="M14.5 14.5c0 1-1 2-2.5 2H9.5" />
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

export const Package = (props: IconProps) => (
  <Icon {...props}>
    <path d="M3 7l9-4 9 4-9 4-9-4z" />
    <path d="M3 7v10l9 4 9-4V7" />
    <path d="M12 11v10" />
  </Icon>
);

export const ShieldCheck = (props: IconProps) => (
  <Icon {...props}>
    <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </Icon>
);

export const Wallet = (props: IconProps) => (
  <Icon {...props}>
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M16 10h5v4h-5z" />
  </Icon>
);

export const FileText = (props: IconProps) => (
  <Icon {...props}>
    <path d="M6 3h9l3 3v15H6z" />
    <path d="M9 11h6" />
    <path d="M9 15h6" />
  </Icon>
);

export const Wrench = (props: IconProps) => (
  <Icon {...props}>
    <path d="M14.5 5.5a4 4 0 0 0-5.5 5.5L4 16l4 4 5-5a4 4 0 0 0 5.5-5.5l-2.5 2.5-2.5-2.5 2.5-2.5z" />
  </Icon>
);

export const LinkIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M10 13a4 4 0 0 1 0-6l2-2a4 4 0 0 1 6 6l-1 1" />
    <path d="M14 11a4 4 0 0 1 0 6l-2 2a4 4 0 0 1-6-6l1-1" />
  </Icon>
);

export const Settings = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19 12a7 7 0 0 0-.1-1l2.1-1.6-2-3.5-2.5 1a7 7 0 0 0-1.7-1l-.4-2.7h-4l-.4 2.7a7 7 0 0 0-1.7 1l-2.5-1-2 3.5 2.1 1.6a7 7 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7 7 0 0 0 1.7 1l.4 2.7h4l.4-2.7a7 7 0 0 0 1.7-1l2.5 1 2-3.5-2.1-1.6c.1-.3.1-.7.1-1z" />
  </Icon>
);

export const MessageCircle = (props: IconProps) => (
  <Icon {...props}>
    <path d="M21 11a8 8 0 0 1-8 8H7l-4 3 1.2-4.5A8 8 0 1 1 21 11z" />
  </Icon>
);
