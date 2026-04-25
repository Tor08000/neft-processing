import React from "react";
import type { ReactNode } from "react";
import { AdminCrashPage } from "../pages/admin/AdminStatusPages";

interface AdminErrorBoundaryProps {
  children: ReactNode;
  resetKey?: string;
}

interface AdminErrorBoundaryState {
  hasError: boolean;
}

export class AdminErrorBoundary extends React.Component<AdminErrorBoundaryProps, AdminErrorBoundaryState> {
  state: AdminErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AdminErrorBoundaryState {
    return { hasError: true };
  }

  componentDidUpdate(prevProps: AdminErrorBoundaryProps) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false });
    }
  }

  componentDidCatch(error: unknown) {
    console.error("Admin route crashed", error);
  }

  render() {
    if (this.state.hasError) {
      return <AdminCrashPage />;
    }
    return this.props.children;
  }
}
