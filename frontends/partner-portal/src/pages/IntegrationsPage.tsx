import { EmptyState } from "../components/states";

export function IntegrationsPage() {
  return (
    <div className="stack">
      <section className="card">
        <h2>Интеграции</h2>
        <p className="muted">Управление вебхуками и API-ключами будет доступно после подключения Integration Hub.</p>
      </section>

      <section className="card">
        <EmptyState
          title="Интеграции ещё не настроены"
          description="Как только интеграции будут доступны, они появятся в этом разделе."
        />
      </section>
    </div>
  );
}
