import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";

export function ForbiddenPage() {
  return (
    <EmptyState
      title="Нет доступа"
      description="У вас нет прав для просмотра этой страницы."
      action={
        <Link className="ghost neft-btn-secondary" to="/login">
          Войти под другой учетной записью
        </Link>
      }
    />
  );
}
