import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
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

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded relative">
          <strong className="font-bold">Something went wrong.</strong>
          <span className="block sm:inline"> Please refresh the page.</span>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;