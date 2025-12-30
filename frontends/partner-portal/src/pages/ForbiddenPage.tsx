import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <div className="empty-state empty-state--full">
      <h1>Доступ ограничен</h1>
      <p className="muted">У вашей роли нет доступа к разделу кабинета партнёра.</p>
      <div className="actions">
        <Link className="ghost" to="/">
          Вернуться на дашборд
        </Link>
      </div>
    </div>
  );
}
