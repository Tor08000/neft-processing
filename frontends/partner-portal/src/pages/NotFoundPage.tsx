import { Link } from "react-router-dom";
import { EmptyState } from "../../../shared/brand/components";

export function NotFoundPage() {
  return (
    <EmptyState
      title="Страница не найдена"
      description="Проверьте адрес или вернитесь в кабинет партнёра."
      action={
        <Link className="ghost neft-btn-secondary" to="/products">
          К продуктам
        </Link>
      }
    />
  );
}
