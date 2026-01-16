import type { ReactNode } from "react";
import React from "react";
import { StatusPage } from "./StatusPage";

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
        <StatusPage
          title="Что-то пошло не так"
          description="Попробуйте вернуться на дашборд или обновить страницу. Если проблема повторяется — сообщите в поддержку."
          secondaryAction={
            <button type="button" className="secondary" onClick={this.handleReload}>
              Перезагрузить
            </button>
          }
        />
      );
    }

    return this.props.children;
  }
}
