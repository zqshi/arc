import { Component, type ReactNode, Fragment } from 'react';
import { RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  resetKey: number;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState((prev) => ({ hasError: false, error: null, resetKey: prev.resetKey + 1 }));
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      // 区分"后端不可达"(网络层失败 status=0) 与普通页面错误, 给准确文案
      const isServiceDown =
        (this.state.error as { status?: number } | null)?.status === 0;
      const title = isServiceDown ? '服务暂时不可用' : '页面出错了';
      const hint = isServiceDown
        ? '无法连接后端服务, 请稍后重试。若持续出现, 请联系管理员检查服务状态。'
        : this.state.error?.message || '发生了未知错误';

      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-status-error/10">
            <span className="text-lg">!</span>
          </div>
          <div>
            <h2 className="mb-1 text-sm font-semibold text-text-primary">{title}</h2>
            <p className="max-w-sm text-xs text-text-secondary">{hint}</p>
          </div>
          <button
            onClick={this.handleReset}
            className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
          >
            <RefreshCw size={12} />
            重试
          </button>
        </div>
      );
    }

    return <Fragment key={this.state.resetKey}>{this.props.children}</Fragment>;
  }
}
