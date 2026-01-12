import React from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";

export const ForbiddenPage: React.FC = () => {
  return (
    <EmptyState
      title="403 — Доступ запрещён"
      description="У вас нет прав доступа к этому разделу."
      action={
        <Link className="ghost neft-btn-secondary" to="/users">
          Вернуться на главную
        </Link>
      }
    />
  );
};

export default ForbiddenPage;
