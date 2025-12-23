import React from 'react';

const searilizeError = (error: any) => {
  if (error instanceof Error) {
    return error.message + '\n' + error.stack;
  }
  return JSON.stringify(error, null, 2);
};

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: any }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 border border-red-500 dark:border-red-400 rounded bg-red-50 dark:bg-red-900/20">
          <h2 className="text-red-600 dark:text-red-400 font-medium">Something went wrong.</h2>
          <pre className="mt-2 text-sm text-gray-700 dark:text-gray-300 overflow-auto">{searilizeError(this.state.error)}</pre>
        </div>
      );
    }

    return this.props.children;
  }
}
