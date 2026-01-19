import React from "react";
import { EmptyState } from "@shared/brand/components";

interface ComingSoonPageProps {
  title: string;
}

export const ComingSoonPage: React.FC<ComingSoonPageProps> = ({ title }) => (
  <EmptyState title={title} description="Coming soon" />
);

export default ComingSoonPage;
