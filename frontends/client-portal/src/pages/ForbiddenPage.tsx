import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <div className="empty-state empty-state--full">
      <h1>Нет доступа</h1>
      <p className="muted">У вас нет прав для просмотра этой страницы.</p>
      <div className="actions">
        <Link className="ghost" to="/login">
          Войти под другой учетной записью
        </Link>
      </div>
    </div>
  );
}
