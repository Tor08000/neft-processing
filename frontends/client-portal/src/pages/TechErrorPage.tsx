import { Link } from "react-router-dom";
import { AppErrorState } from "../components/states";
import { useClient } from "../auth/ClientContext";
import { useAuth } from "../auth/AuthContext";

export function TechErrorPage() {
  const { client, refresh } = useClient();
  const { user } = useAuth();
  const errorId = client?.flags?.error_id ?? client?.access_reason ?? null;
  const requestId = client?.flags?.request_id ?? null;
  const homePath = user ? "/" : "/login";

  return (
    <div className="stack">
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
      <div className="actions">
        <Link className="ghost neft-btn-secondary" to={homePath}>
          На главную
        </Link>
      </div>
    </div>
  );
}
