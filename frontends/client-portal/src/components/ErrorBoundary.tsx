import type { ReactNode } from "react";
import React from "react";

interface ErrorBoundaryState {
  hasError: boolean;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="card error-boundary__card">
            <h1>Произошла ошибка</h1>
            <p className="muted">Попробуйте обновить страницу. Если проблема повторяется — сообщите в поддержку.</p>
            <div className="actions">
              <button type="button" onClick={this.handleReload}>
                Перезагрузить
              </button>
              <button type="button" className="ghost">
                Сообщить в поддержку
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
