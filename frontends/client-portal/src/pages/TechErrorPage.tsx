import { AppErrorState } from "../components/states";
import { useClient } from "../auth/ClientContext";

export function TechErrorPage() {
  const { client, refresh } = useClient();
  const errorId = client?.flags?.error_id ?? client?.access_reason ?? null;
  const requestId = client?.flags?.request_id ?? null;

  return (
    <AppErrorState
      message={
        <>
          <div>Техническая ошибка. Попробуйте снова позже.</div>
          {errorId ? <div>Error ID: {String(errorId)}</div> : null}
          {requestId ? <div>Request ID: {String(requestId)}</div> : null}
        </>
      }
      onRetry={refresh}
    />
  );
}
