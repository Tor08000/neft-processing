import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  acceptPartnerServiceRequest,
  completePartnerServiceRequest,
  listPartnerServiceRequests,
  rejectPartnerServiceRequest,
  startPartnerServiceRequest,
  type ServiceRequestItem,
} from "../api/serviceRequests";

export function ServiceRequestsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ServiceRequestItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      setItems(await listPartnerServiceRequests(user));
    } catch {
      setError("Не удалось загрузить заявки");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const act = async (id: string, action: "accept" | "reject" | "start" | "complete") => {
    try {
      if (action === "accept") await acceptPartnerServiceRequest(user, id);
      if (action === "reject") await rejectPartnerServiceRequest(user, id);
      if (action === "start") await startPartnerServiceRequest(user, id);
      if (action === "complete") await completePartnerServiceRequest(user, id);
      await load();
    } catch {
      setError("Не удалось выполнить действие");
    }
  };

  return (
    <div className="card">
      <h2>Service Requests</h2>
      {error ? <p className="muted">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Client</th>
            <th>Service</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.client_id}</td>
              <td>{item.service_id}</td>
              <td>{item.status}</td>
              <td>
                <button onClick={() => act(item.id, "accept")}>Accept</button>
                <button onClick={() => act(item.id, "reject")}>Reject</button>
                <button onClick={() => act(item.id, "start")}>Start</button>
                <button onClick={() => act(item.id, "complete")}>Complete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
