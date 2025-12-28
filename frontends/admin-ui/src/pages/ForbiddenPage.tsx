import React from "react";
import { Link } from "react-router-dom";

export const ForbiddenPage: React.FC = () => {
  return (
    <div className="card" style={{ maxWidth: 520, margin: "40px auto", textAlign: "center" }}>
      <h2>403 — Доступ запрещён</h2>
      <p style={{ marginBottom: 16 }}>У вас нет прав доступа к этому разделу.</p>
      <Link className="button" to="/">
        Вернуться на главную
      </Link>
    </div>
  );
};

export default ForbiddenPage;
