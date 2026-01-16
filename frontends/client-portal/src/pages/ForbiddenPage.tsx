import { StatusPage } from "../components/StatusPage";

export function ForbiddenPage() {
  return (
    <StatusPage title="Нет доступа" description="У вас нет прав для просмотра этой страницы." />
  );
}
