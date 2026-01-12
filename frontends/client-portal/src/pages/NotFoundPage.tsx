import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";

export function NotFoundPage() {
  return (
    <EmptyState
      title="Страница не найдена"
      description="Проверьте адрес или вернитесь в список документов."
      action={
        <Link className="ghost neft-btn-secondary" to="/billing">
          Перейти к документам
        </Link>
      }
    />
  );
}
