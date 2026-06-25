import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useConversationSocket } from './useConversationSocket';
import { quotaEvents } from '../lib/quota-events';

// --- mock WebSocket 基建 ---

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static OPEN = 1 as const;
  static CLOSED = 3 as const;

  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  readyState = 0;
  sent: any[] = [];
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.readyState = 3;
    this.closed = true;
  }
  // 测试辅助: 模拟服务端事件
  open() {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }
  message(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  closeEvent(code = 1000) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
  error() {
    this.onerror?.(new Event('error'));
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  localStorage.clear();
  vi.stubGlobal('WebSocket', MockWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function lastWs(): MockWebSocket {
  return MockWebSocket.instances[MockWebSocket.instances.length - 1];
}

describe('useConversationSocket — 连接与基础事件', () => {
  it('建立连接后 isConnected=true', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    expect(result.current.isConnected).toBe(false);
    act(() => lastWs().open());
    expect(result.current.isConnected).toBe(true);
  });

  it('conversationId 为 null 时不连接', () => {
    renderHook(() => useConversationSocket(null));
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('收到 message 事件追加到 messages', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({
      type: 'message',
      message: { id: 'm1', conversation_id: 'c1', role: 'assistant', content: 'hi', created_at: '' },
    }));
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].id).toBe('m1');
  });

  it('重复 message 事件去重', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    const msg = { type: 'message', message: { id: 'm1', conversation_id: 'c1', role: 'assistant', content: 'hi', created_at: '' } } as const;
    act(() => lastWs().message(msg));
    act(() => lastWs().message(msg));
    expect(result.current.messages).toHaveLength(1);
  });
});

describe('useConversationSocket — 流式消息', () => {
  it('stream_start/chunk/end 控制流式状态并拼接内容', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({ type: 'stream_start', message_id: 's1' }));
    expect(result.current.isStreaming).toBe(true);
    act(() => lastWs().message({ type: 'stream_chunk', message_id: 's1', content: 'Hello' }));
    act(() => lastWs().message({ type: 'stream_chunk', message_id: 's1', content: ' World' }));
    act(() => lastWs().message({ type: 'stream_end', message_id: 's1' }));
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.messages[result.current.messages.length - 1].content).toBe('Hello World');
  });

  it('stream_resume 合并缓冲内容', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({ type: 'stream_resume', message_id: 's1', buffered_content: 'restored' }));
    expect(result.current.messages.some((m) => m.content === 'restored')).toBe(true);
    expect(result.current.isStreaming).toBe(true);
  });
});

describe('useConversationSocket — 工具调用与审批', () => {
  it('tool_call 追加 running, tool_result 转 done', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({
      type: 'tool_call', message_id: 'm1', tool_name: 'read_file', tool_input: { path: 'a.ts' }, round: 1,
    }));
    expect(result.current.toolCalls).toHaveLength(1);
    expect(result.current.toolCalls[0].status).toBe('running');
    act(() => lastWs().message({
      type: 'tool_result', message_id: 'm1', tool_name: 'read_file', output_preview: 'content', is_error: false,
    }));
    expect(result.current.toolCalls[0].status).toBe('done');
    expect(result.current.toolCalls[0].output_preview).toBe('content');
  });

  it('approval_required 设置 pendingApproval', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({
      type: 'approval_required', request_id: 'r1', tool_name: 'exec', tool_input: { cmd: 'rm' },
    }));
    expect(result.current.pendingApproval?.request_id).toBe('r1');
  });

  it('respondToApproval 发送响应并清空 pendingApproval', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({
      type: 'approval_required', request_id: 'r1', tool_name: 'exec', tool_input: {},
    }));
    act(() => result.current.respondToApproval('r1', true));
    const ws = lastWs();
    expect(ws.sent.some((s) => s.type === 'approval_response' && s.approved === true)).toBe(true);
    expect(result.current.pendingApproval).toBe(null);
  });
});

describe('useConversationSocket — 编排事件', () => {
  it('orchestration_start/worker_start/complete 驱动 workers 状态', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({ type: 'orchestration_start', plan_id: 'p1', subtask_count: 1 }));
    expect(result.current.orchestrationPhase).toBe('working');
    act(() => lastWs().message({
      type: 'worker_start', worker_id: 'w1', plan_id: 'p1', subtask: { description: 'read', task_type: 'read_analysis' },
    }));
    expect(result.current.workers[0].status).toBe('running');
    act(() => lastWs().message({
      type: 'worker_complete', worker_id: 'w1', output_preview: 'done', tokens_used: 10, elapsed_ms: 5,
    }));
    expect(result.current.workers[0].status).toBe('done');
    act(() => lastWs().message({ type: 'orchestration_complete', plan_id: 'p1', total_tokens: 10, worker_count: 1 }));
    expect(result.current.orchestrationPhase).toBe('complete');
  });
});

describe('useConversationSocket — 发送与心跳', () => {
  it('sendMessage 发送 message 事件并重置编排状态', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => result.current.sendMessage('hello'));
    const ws = lastWs();
    expect(ws.sent.some((s) => s.type === 'message' && s.content === 'hello')).toBe(true);
    expect(result.current.isStreaming).toBe(true);
  });

  it('ping 事件回复 pong', () => {
    renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({ type: 'ping' }));
    expect(lastWs().sent.some((s) => s.type === 'pong')).toBe(true);
  });
});

describe('useConversationSocket — 错误与配额', () => {
  it('error 事件设置 error 并停止流式', () => {
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({ type: 'stream_start', message_id: 's1' }));
    act(() => lastWs().message({ type: 'error', detail: '出错了' }));
    expect(result.current.error).toBe('出错了');
    expect(result.current.isStreaming).toBe(false);
  });

  it('quota_exceeded 触发 quotaEvents 并停止流式', () => {
    const emit = vi.spyOn(quotaEvents, 'emit');
    const { result } = renderHook(() => useConversationSocket('c1'));
    act(() => lastWs().open());
    act(() => lastWs().message({ type: 'stream_start', message_id: 's1' }));
    act(() => lastWs().message({ type: 'quota_exceeded', detail: '额度用尽' }));
    expect(emit).toHaveBeenCalledWith('额度用尽');
    expect(result.current.isStreaming).toBe(false);
  });
});
