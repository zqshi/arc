// ─── Core Enums ──────────────────────────────────────────
export type TodoStatus = 'pending' | 'active' | 'done' | 'error';
export type PhaseType = 'clarification' | 'ui_design' | 'architecture' | 'development' | 'testing' | 'deployment' | 'extraction';
export type PhaseStatus = 'pending' | 'active' | 'awaiting_confirm' | 'confirmed' | 'skipped';
export type ArtifactType = 'requirement_spec' | 'ui_design' | 'tech_architecture' | 'dev_report' | 'test_report' | 'deploy_report' | 'experience_card';
export type ConversationPurpose = 'clarification' | 'ui_design' | 'architecture' | 'development' | 'testing' | 'deployment' | 'review';
export type MessageRole = 'user' | 'assistant' | 'system';

// ─── Shared ──────────────────────────────────────────────
export interface Tag {
  label: string;
  color: string;
}

// ─── Todo ────────────────────────────────────────────────
export interface Todo {
  id: string;
  title: string;
  description: string;
  status: TodoStatus;
  current_phase: PhaseType | null;
  tags: Tag[];
  created_at: string;
  updated_at: string;
}

export interface CreateTodoRequest {
  title: string;
  description?: string;
  tags?: Tag[];
}

export interface UpdateTodoRequest {
  title?: string;
  description?: string;
  tags?: Tag[];
}

// ─── Pipeline ────────────────────────────────────────────
export interface PipelinePhase {
  id: string;
  todo_id: string;
  phase_type: PhaseType;
  status: PhaseStatus;
  conversation_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Artifact {
  id: string;
  todo_id: string;
  phase_id: string;
  artifact_type: ArtifactType;
  content: Record<string, unknown>;
  version: number;
  is_confirmed: boolean;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PipelineState {
  todo_id: string;
  current_phase: PhaseType | null;
  phases: PipelinePhase[];
  artifacts: Artifact[];
}

// ─── Conversation ────────────────────────────────────────
export interface Conversation {
  id: string;
  todo_id: string;
  purpose: ConversationPurpose;
  messages: Message[];
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

// ─── Experience ──────────────────────────────────────────
export type ExperienceScope = 'todo' | 'project' | 'global';

export interface Experience {
  id: string;
  todo_id?: string;
  title: string;
  scope: ExperienceScope;
  problem: string;
  solution: string;
  decisions: string[];
  pitfalls: string[];
  applicable_scenarios?: string;
  tags: Tag[];
  confidence: number;
  reuse_count: number;
  source?: string;
  created_at: string;
}

// ─── Helpers ─────────────────────────────────────────────
export const PHASE_ORDER: PhaseType[] = [
  'clarification', 'ui_design', 'architecture', 'development', 'testing', 'deployment', 'extraction',
];

export const PHASE_LABELS: Record<PhaseType, string> = {
  clarification: '需求澄清',
  ui_design: 'UI设计',
  architecture: '技术架构',
  development: '开发实现',
  testing: '测试验证',
  deployment: '部署上线',
  extraction: '经验沉淀',
};

export const STATUS_LABELS: Record<TodoStatus, string> = {
  pending: '待启动',
  active: '进行中',
  done: '已完成',
  error: '异常',
};
