import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  resetKey?: string | number;
}

interface State {
  hasError: boolean;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false });
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <main
          role="alert"
          className="flex flex-grow flex-col items-center justify-center bg-gray-50 px-4 text-center"
        >
          <img src="/abacus.svg" alt="Abacus" className="mb-6 h-16 w-auto" />
          <h1 className="text-xl font-semibold text-gray-800">Une erreur est survenue</h1>
          <p className="mt-2 max-w-sm text-gray-500">
            Quelque chose s'est mal passé. Veuillez réessayer.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-8 rounded-lg bg-gray-900 px-6 py-2.5 font-medium text-white transition hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-400"
          >
            Recharger la page
          </button>
        </main>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
