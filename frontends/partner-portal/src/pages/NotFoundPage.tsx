import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="empty-state empty-state--full">
      <h1>Страница не найдена</h1>
      <p className="muted">Проверьте адрес или вернитесь в кабинет партнёра.</p>
      <div className="actions">
        <Link className="ghost" to="/">
          На дашборд
        </Link>
      </div>
    </div>
  );
}
