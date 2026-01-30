import { AppErrorState } from "../components/states";
import { useClient } from "../auth/ClientContext";

export function ServiceUnavailablePage() {
  const { refresh } = useClient();
  return (
    <AppErrorState
      message="Сервис временно недоступен. Попробуйте позже."
      onRetry={refresh}
    />
  );
}
