import React from "react";
import { EmptyState } from "@shared/ui/EmptyState";

interface ComingSoonPageProps {
  title: string;
}

export const ComingSoonPage: React.FC<ComingSoonPageProps> = ({ title }) => (
  <div className="neft-container">
    <EmptyState title={title} description="Coming soon" />
  </div>
);

export default ComingSoonPage;
