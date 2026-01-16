import { StatusPage } from "../components/StatusPage";

export function UnauthorizedPage() {
  return (
    <StatusPage
      title="Требуется авторизация"
      description="Ваша сессия истекла или требуется повторный вход. Вернитесь на дашборд и войдите снова."
    />
  );
}
