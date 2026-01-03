import { Link } from "react-router-dom";
import { EmptyState } from "../../../shared/brand/components";

export function ForbiddenPage() {
  return (
    <EmptyState
      title="Нет доступа"
      description="У вашей роли нет доступа к разделу кабинета партнёра."
      action={
        <Link className="ghost neft-btn-secondary" to="/products">
          К продуктам
        </Link>
      }
    />
  );
}
