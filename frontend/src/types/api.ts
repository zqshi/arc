// ─── Core Enums ──────────────────────────────────────────
export type TodoStatus = 'pending' | 'active' | 'done' | 'error';
export type PhaseType = 'clarification' | 'ui_design' | 'architecture' | 'development' | 'testing' | 'deployment' | 'extraction';
export type PhaseStatus = 'pending' | 'active' | 'awaiting_confirm' | 'confirmed' | 'skipped';
export type ArtifactType = 'requirement_spec' | 'ui_design' | 'tech_architecture' | 'dev_report' | 'test_report' | 'deploy_report' | 'experience_card';
export type ConversationPurpose = 'clarification' | 'ui_design' | 'architecture' | 'development' | 'testing' | 'deployment' | 'review';
export type MessageRole = 'user' | 'assistant' | 'system';
export type ProjectStatus = 'active' | 'archived';
export type VersionStatus = 'planning' | 'active' | 'released';

// ─── Shared ──────────────────────────────────────────────
export interface Tag {
  label: string;
  color: string;
}

// ─── Project ────────────────────────────────────────────
export interface Project {
  id: string;
  name: string;
  description: string;
  tech_stack: string;
  repo_url: string;
  conventions: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectRequest {
  name: string;
  description?: string;
  tech_stack?: string;
  repo_url?: string;
  conventions?: string;
}

export interface UpdateProjectRequest {
  name?: string;
  description?: string;
  tech_stack?: string;
  repo_url?: string;
  conventions?: string;
}

// ─── Version ────────────────────────────────────────────
export interface Version {
  id: string;
  project_id: string;
  name: string;
  goal: string;
  status: VersionStatus;
  parent_version_id: string | null;
  order: number;
  changelog: string;
  todo_stats?: { pending: number; active: number; done: number; error: number; total: number };
  created_at: string;
  updated_at: string;
}

export type VersionType = 'major' | 'minor' | 'patch';

export interface CreateVersionRequest {
  name?: string;
  goal?: string;
  parent_version_id?: string;
  version_type?: VersionType;
}

// ─── Todo ────────────────────────────────────────────────
export interface Todo {
  id: string;
  title: string;
  description: string;
  status: TodoStatus;
  project_id: string | null;
  version_id: string | null;
  project_name: string | null;
  version_name: string | null;
  priority: number;
  current_phase: PhaseType | null;
  tags: Tag[];
  created_at: string;
  updated_at: string;
}

export interface CreateTodoRequest {
  title: string;
  description?: string;
  project_id?: string;
  version_id?: string;
  priority?: number;
  tags?: Tag[];
}

export interface UpdateTodoRequest {
  title?: string;
  description?: string;
  project_id?: string;
  version_id?: string;
  priority?: number;
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
export type ExperienceScope = 'personal' | 'project';
export type ExperienceStatus = 'draft' | 'confirmed' | 'archived';

export interface Experience {
  id: string;
  todo_id?: string;
  project_id?: string;
  title: string;
  scope: ExperienceScope;
  status: ExperienceStatus;
  problem: string;
  solution: string;
  decisions: string[];
  pitfalls: string[];
  applicable_scenarios?: string;
  tags: Tag[];
  confidence: number;
  reuse_count: number;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface UpdateExperienceRequest {
  title?: string;
  problem?: string;
  solution?: string;
  decisions?: string[];
  pitfalls?: string[];
  applicable_scenarios?: string;
  scope?: string;
}

export interface ExperienceRef {
  id: string;
  title: string;
  scope: string;
}

// ─── Agent ──────────────────────────────────────────────
export type AgentType = 'openhands' | 'codex' | 'claude_code' | 'cursor';
export type AgentSessionStatus = 'pending' | 'running' | 'paused' | 'completed' | 'error' | 'cancelled';

export interface AgentSession {
  id: string;
  todo_id: string;
  phase_id: string;
  agent_type: AgentType;
  external_session_id: string | null;
  status: AgentSessionStatus;
  task_context: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error_reason: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentTypeInfo {
  value: string;
  label: string;
}

export interface AvailableAgentsResponse {
  agents: AgentTypeInfo[];
  default: string;
}

export interface AgentEvent {
  id: string;
  content: string;
  timestamp: string | null;
  metadata: Record<string, unknown>;
}

// ─── Settings ──────────────────────────────────────────
export interface SystemSettings {
  llm_provider: string;
  openai_base_url: string;
  openai_model: string;
  openai_api_key_set: boolean;
  anthropic_base_url: string;
  anthropic_model: string;
  anthropic_api_key_set: boolean;
  deepseek_base_url: string;
  deepseek_model: string;
  deepseek_api_key_set: boolean;
  openhands_url: string;
  openhands_api_key_set: boolean;
  agent_default: string;
  agent_development: string;
  agent_testing: string;
  agent_deployment: string;
}

// ─── Helpers ─────────────────────────────────────────────
export const PHASE_ORDER: PhaseType[] = [
  'clarification', 'ui_design', 'architecture', 'development', 'testing', 'deployment', 'extraction',
];

export const AGENT_EXECUTION_PHASES: Set<PhaseType> = new Set(['development', 'testing', 'deployment']);

export const PHASE_LABELS: Record<PhaseType, string> = {
  clarification: '需求澄清',
  ui_design: 'UI设计',
  architecture: '技术架构',
  development: '开发实现',
  testing: '测试验证',
  deployment: '部署上线',
  extraction: '经验沉淀',
};

export const EXPERIENCE_STATUS_LABELS: Record<ExperienceStatus, string> = {
  draft: '待审核',
  confirmed: '已确认',
  archived: '已归档',
};

export const STATUS_LABELS: Record<TodoStatus, string> = {
  pending: '待启动',
  active: '进行中',
  done: '已完成',
  error: '异常',
};
