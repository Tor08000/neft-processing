import type { ReactNode } from "react";

type BrandIconProps = {
  size?: number;
  className?: string;
  children: ReactNode;
};

const BaseIcon = ({ size = 18, className, children }: BrandIconProps) => (
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

export const DashboardIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <rect x="3" y="3" width="8" height="8" rx="1.5" />
    <rect x="13" y="3" width="8" height="5" rx="1.5" />
    <rect x="13" y="10" width="8" height="11" rx="1.5" />
    <rect x="3" y="13" width="8" height="8" rx="1.5" />
  </BaseIcon>
);

export const UsersIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <path d="M16 20v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1" />
    <circle cx="9.5" cy="7" r="3" />
    <path d="M21 20v-1a4 4 0 0 0-3-3.87" />
    <path d="M16.5 4.2a3 3 0 0 1 0 5.6" />
  </BaseIcon>
);

export const WalletIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M16 10h5v4h-5z" />
  </BaseIcon>
);

export const BriefcaseIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <rect x="3" y="7" width="18" height="12" rx="2" />
    <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </BaseIcon>
);

export const FileIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <path d="M6 3h9l3 3v15H6z" />
    <path d="M9 11h6" />
    <path d="M9 15h6" />
  </BaseIcon>
);

export const CartIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <circle cx="9" cy="20" r="1.5" />
    <circle cx="18" cy="20" r="1.5" />
    <path d="M3 4h2l2.2 10.5a2 2 0 0 0 2 1.5h8.8a2 2 0 0 0 1.9-1.3L22 8H7" />
  </BaseIcon>
);

export const WorkflowIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <circle cx="5" cy="5" r="2" />
    <circle cx="19" cy="12" r="2" />
    <circle cx="5" cy="19" r="2" />
    <path d="M7 5h6l4 6" />
    <path d="M7 19h6l4-6" />
  </BaseIcon>
);

export const LogisticsIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <rect x="1.5" y="8" width="12" height="8" rx="1.5" />
    <path d="M13.5 10h4l3 3v3h-7z" />
    <circle cx="6" cy="18.5" r="1.5" />
    <circle cx="17.5" cy="18.5" r="1.5" />
  </BaseIcon>
);

export const ChartIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <path d="M3 3v18h18" />
    <rect x="7" y="11" width="3" height="6" rx="1" />
    <rect x="12" y="7" width="3" height="10" rx="1" />
    <rect x="17" y="5" width="3" height="12" rx="1" />
  </BaseIcon>
);

export const ShieldIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </BaseIcon>
);

export const AuditIcon = (props: Omit<BrandIconProps, "children">) => (
  <BaseIcon {...props}>
    <path d="M12 8v5l3 2" />
    <circle cx="12" cy="12" r="8" />
  </BaseIcon>
);
