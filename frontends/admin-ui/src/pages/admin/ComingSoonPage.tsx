import React from "react";
import { EmptyState } from "@shared/ui/EmptyState";

interface ComingSoonPageProps {
  title: string;
}

export const ComingSoonPage: React.FC<ComingSoonPageProps> = ({ title }) => (
  <div className="neft-container">
    <EmptyState
      title={title}
      description="Раздел в разработке."
      hint="Мы завершаем настройки и скоро добавим эту страницу."
    />
  </div>
);

export default ComingSoonPage;
