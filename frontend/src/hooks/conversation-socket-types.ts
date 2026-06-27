/**
 * useConversationSocket 的 WebSocket 事件与状态类型定义 (从 useConversationSocket.ts 拆出, v6.11 T4)。
 * 纯类型, 无运行时逻辑。
 * ApprovalInfo / ToolCallInfo / WorkerInfo 经 useConversationSocket re-export 保持原 import 路径
 * (ToolCallDisplay.tsx 等消费方零改动)。
 */
import type { Message } from '../types/api';

interface WsMessageEvent {
  type: 'message';
  message: Message;
}

interface WsStreamStartEvent {
  type: 'stream_start';
  message_id: string;
}

interface WsStreamChunkEvent {
  type: 'stream_chunk';
  message_id: string;
  content: string;
}

interface WsStreamEndEvent {
  type: 'stream_end';
  message_id: string;
}

interface WsErrorEvent {
  type: 'error';
  detail: string;
}

interface WsArtifactsExtractedEvent {
  type: 'artifacts_extracted';
  artifacts: string[];
  artifact_names: string[];
  tracker?: {
    required: string[];
    deliverables: Record<string, string>;
    completion_pct: number;
    is_complete: boolean;
  };
}

interface WsToolCallEvent {
  type: 'tool_call';
  message_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  round: number;
  parallel?: boolean;
}

interface WsToolResultEvent {
  type: 'tool_result';
  message_id: string;
  tool_name: string;
  output_preview: string;
  is_error: boolean;
  parallel?: boolean;
}

interface WsToolErrorEvent {
  type: 'tool_error';
  message_id: string;
  detail: string;
}

interface WsQuotaExceededEvent {
  type: 'quota_exceeded';
  detail: string;
}

interface WsApprovalRequiredEvent {
  type: 'approval_required';
  request_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface ApprovalInfo {
  request_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface ToolCallInfo {
  id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  output_preview?: string;
  is_error?: boolean;
  status: 'running' | 'done';
  parallel?: boolean;
  round?: number;
}

export type WsEvent =
  | WsMessageEvent
  | WsStreamStartEvent
  | WsStreamChunkEvent
  | WsStreamEndEvent
  | WsErrorEvent
  | WsArtifactsExtractedEvent
  | WsToolCallEvent
  | WsToolResultEvent
  | WsToolErrorEvent
  | WsQuotaExceededEvent
  | WsApprovalRequiredEvent
  | { type: 'stream_resume'; message_id: string; buffered_content: string }
  | { type: 'orchestration_start'; plan_id: string; subtask_count: number }
  | { type: 'worker_start'; worker_id: string; plan_id: string; subtask: { description: string; task_type: string } }
  | { type: 'worker_complete'; worker_id: string; output_preview: string; tokens_used: number; elapsed_ms: number }
  | { type: 'worker_error'; worker_id: string; error: string }
  | { type: 'synthesis_start'; plan_id: string }
  | { type: 'orchestration_complete'; plan_id: string; total_tokens: number; worker_count: number }
  | { type: 'token_expired' }
  | { type: 'ping' };

export interface WorkerInfo {
  id: string;
  description: string;
  task_type: string;
  status: 'pending' | 'running' | 'done' | 'error';
  output_preview?: string;
  tokens_used?: number;
  elapsed_ms?: number;
}
