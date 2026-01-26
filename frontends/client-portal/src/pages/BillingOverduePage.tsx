import { AppErrorState, AppLoadingState } from "../components/states";
import { BillingOverdueState } from "../components/BillingOverdueState";
import { useClient } from "../auth/ClientContext";

export function BillingOverduePage() {
  const { client, portalState, refresh } = useClient();

  if (portalState === "LOADING") {
    return <AppLoadingState label="Загружаем данные биллинга..." />;
  }

  if (portalState === "SERVICE_UNAVAILABLE") {
    return <AppErrorState message="Сервис временно недоступен. Попробуйте позже." onRetry={refresh} />;
  }

  if (portalState === "NETWORK_DOWN") {
    return <AppErrorState message="Нет соединения с сервером. Проверьте подключение к интернету." onRetry={refresh} />;
  }

  if (portalState === "API_MISCONFIGURED") {
    return <AppErrorState message="Маршрут портала недоступен. Проверьте настройки API." onRetry={refresh} />;
  }

  if (portalState === "ERROR_FATAL") {
    return <AppErrorState message="Не удалось загрузить данные биллинга." onRetry={refresh} />;
  }

  return <BillingOverdueState billing={client?.billing} />;
}
