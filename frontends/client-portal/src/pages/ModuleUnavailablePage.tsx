import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";

type ModuleUnavailablePageProps = {
  title: string;
  description?: string;
};

export function ModuleUnavailablePage({ title, description }: ModuleUnavailablePageProps) {
  return (
    <EmptyState
      title={`${title} недоступен по подписке`}
      description={description ?? "Обновите план или обратитесь к администратору организации."}
      action={
        <Link className="ghost neft-btn-secondary" to="/subscription">
          Перейти к подписке
        </Link>
      }
    />
  );
}
