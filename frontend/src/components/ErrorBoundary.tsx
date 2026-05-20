import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="app" style={{ padding: 40, textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <pre style={{ color: '#dc2626', maxWidth: 600, margin: '16px auto', overflow: 'auto' }}>
            {this.state.error.message}
          </pre>
          <button className="btn btn-primary" onClick={this.handleReset}>
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
