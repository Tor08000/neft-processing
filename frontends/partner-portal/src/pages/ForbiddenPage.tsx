import { Link } from "react-router-dom";
import { ForbiddenState } from "../components/states";

export function ForbiddenPage() {
  return (
    <ForbiddenState
      description="У вашей роли нет доступа к разделу кабинета партнёра."
      action={
        <Link className="ghost" to="/">
          Вернуться на дашборд
        </Link>
      }
    />
  );
}
