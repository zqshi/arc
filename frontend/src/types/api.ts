// 超限例外: 纯类型定义文件，无运行时逻辑，按 CLAUDE.md 规范允许超限。
// ─── Core Enums ──────────────────────────────────────────
export type TodoStatus = 'pending' | 'active' | 'suspended' | 'done' | 'error' | 'abandoned';
export type PhaseType = 'clarification' | 'ui_design' | 'architecture' | 'development' | 'testing' | 'deployment' | 'extraction';
export type PhaseStatus = 'pending' | 'active' | 'awaiting_confirm' | 'confirmed' | 'skipped';
export type ArtifactType = 'requirement_spec' | 'ui_design' | 'tech_architecture' | 'dev_report' | 'test_report' | 'deploy_report' | 'experience_card' | 'interaction_design' | 'ui_spec' | 'prototype';

// ─── Artifact Content Types (discriminated union) ────────

export interface RequirementSpecContent {
  background?: string;
  target_users?: Array<{ type: string; traits: string; core_need: string }>;
  core_value?: Record<string, string>;
  user_stories?: Array<{ role: string; goal: string; benefit: string; priority: string; acceptance: string }>;
  acceptance_criteria?: Array<{ id: string; scenario: string; steps: string; expected: string; priority: string }>;
  risks?: Array<{ risk: string; probability: string; impact: string; mitigation: string }>;
  assumptions?: Array<{ assumption: string; confidence: string; validation_method: string }>;
  scope?: string;
  non_functional?: string;
}

export interface InteractionDesignContent {
  user_flows?: Array<{ name?: string; description?: string; mermaid?: string }>;
  page_map?: Array<{ page?: string; entry_from?: string; exits_to?: string[]; triggers?: string }>;
  interaction_rules?: Array<{ component?: string; action?: string; response?: string; feedback?: string }>;
  edge_cases?: string;
}

export interface UISpecContent {
  design_tokens?: Record<string, string>;
  color_palette?: Array<{ name?: string; value?: string; usage?: string }>;
  typography?: string;
  spacing?: string;
  component_specs?: Array<{ name?: string; states?: string; notes?: string }>;
}

export interface PrototypeContent {
  // 工程模式
  project_dir?: string;
  tech_stack?: string;
  routes?: Array<{ path: string; name: string; component: string }>;
  preview_url?: string;
  build_status?: 'success' | 'failed' | 'building';
  build_command?: string;
  artifact_path?: string;
  shared_state?: string[];
}

export interface TechArchitectureContent {
  architecture_overview?: string;
  data_model?: string;
  api_design?: string;
  tech_decisions?: Array<{ decision?: string; options?: string; chosen?: string; reason?: string }>;
  implementation_plan?: string;
}

export interface DevReportContent {
  summary?: string;
  code_changes?: Array<{ file?: string; change_type?: string; description?: string; aggregate?: string }>;
  decisions_made?: Array<{ decision?: string; reason?: string; ddd_rationale?: string }>;
  test_cases?: Array<{ name?: string; type?: string; target_aggregate?: string; given?: string; when?: string; then?: string; status?: 'pass' | 'fail' | 'pending' }>;
  technical_debt?: string;
  next_steps?: string;
}

export interface TestReportContent {
  criteria_verification?: Array<{ criteria?: string; status?: string; evidence?: string }>;
  issues_found?: Array<{ description?: string; severity?: string; suggestion?: string }>;
  coverage_summary?: string;
}

export interface DeployReportContent {
  deploy_log?: string;
  service_url?: string;
  health_check_result?: string;
  rollback_plan?: string;
}

export interface ExperienceCardContent {
  problem?: string;
  solution?: string;
  decisions?: Array<{ point?: string; chosen?: string; reason?: string }>;
  pitfalls?: Array<{ issue?: string; cause?: string; fix?: string }>;
  applicable_scenarios?: string;
  tags?: string[];
}

export type ArtifactContentMap = {
  requirement_spec: RequirementSpecContent;
  interaction_design: InteractionDesignContent;
  ui_spec: UISpecContent;
  ui_design: UISpecContent;
  prototype: PrototypeContent;
  tech_architecture: TechArchitectureContent;
  dev_report: DevReportContent;
  test_report: TestReportContent;
  deploy_report: DeployReportContent;
  experience_card: ExperienceCardContent;
};

export type ArtifactContent = ArtifactContentMap[keyof ArtifactContentMap];
export type ConversationPurpose = 'clarification' | 'ui_design' | 'architecture' | 'development' | 'testing' | 'deployment' | 'review' | 'unified' | 'planning';
export type MessageRole = 'user' | 'assistant' | 'system';
export type ProjectStatus = 'active' | 'archived';
export type VersionStatus = 'planning' | 'active' | 'released';
export type ExecutionMode = 'pipeline' | 'conversation'; // deprecated

export type ProcessConstraint = 'strict' | 'moderate' | 'free';

export interface ProcessConfig {
  constraint: ProcessConstraint;
  gate_strictness: string;
  auto_extract: boolean;
  require_explicit_confirm: boolean;
  show_phase_ui: boolean;
}
export type UserRole = 'admin' | 'member' | 'viewer';

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
  local_path: string;
  conventions: string;
  codebase_summary: string;
  scan_status?: 'idle' | 'scanning' | 'completed' | 'error';
  scan_progress?: string;
  scan_error?: string;
  status: ProjectStatus;
  execution_mode: ExecutionMode; // deprecated
  process_constraint: ProcessConstraint;
  project_type: ProjectType;
  process_config?: ProcessConfig;
  pipeline_config?: Record<string, unknown>;
  conversation_config?: Record<string, unknown>;
  github_connected?: boolean;
  github_repo?: string | null;
  created_at: string;
  updated_at: string;
}

export type WorkspaceType = 'local' | 'github' | 'temporary';
export type ProjectType = 'static_site'; // v5.9.0: 静态站点型; v6.0.0+ 扩展 binary_app 等

export interface CreateProjectRequest {
  name: string;
  description?: string;
  tech_stack?: string;
  repo_url?: string;
  local_path?: string;
  conventions?: string;
  execution_mode?: ExecutionMode;
  project_type?: ProjectType;
  workspace_type?: WorkspaceType;
  github_token?: string;
}

export interface UpdateProjectRequest {
  name?: string;
  description?: string;
  tech_stack?: string;
  repo_url?: string;
  local_path?: string;
  conventions?: string;
  execution_mode?: ExecutionMode;
  pipeline_config?: Record<string, unknown>;
  conversation_config?: Record<string, unknown>;
}

// ─── Project Member ────────────────────────────────────
export interface ProjectMember {
  user_id: string;
  display_name: string;
  username: string | null;
  role: UserRole;
  joined_at: string;
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
  prototype_preview_url: string;
  todo_stats?: { pending: number; active: number; done: number; error: number; total: number };
  has_analysis?: boolean;
  analysis_stale?: boolean;
  created_at: string;
  updated_at: string;
}

export type VersionType = 'major' | 'minor' | 'patch';

// v5.5.0: 部署记录 (对应后端 Deployment 实体)
export type DeploymentStatus = 'pending' | 'building' | 'uploading' | 'deployed' | 'failed' | 'rolled_back';

export interface Deployment {
  id: string;
  project_id: string;
  version_id: string;
  todo_id: string | null;
  status: DeploymentStatus;
  deploy_type: string;
  deploy_url: string | null;
  storage_prefix: string | null;
  files_uploaded: number;
  error_message: string | null;
  created_at: string;
  deployed_at: string | null;
}

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
  execution_mode: ExecutionMode;
  needs_attention: boolean;
  tags: Tag[];
  blocked_by: string[];
  blocks: string[];
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
  phase_id: string | null;
  artifact_type: ArtifactType;
  content: ArtifactContent;
  version: number;
  is_confirmed: boolean;
  confirmed_at: string | null;
  preview_url: string | null;
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
export type ExperienceCategory = 'technical' | 'business_rule' | 'pitfall' | 'architecture_decision' | 'scope_change' | 'estimation';
export type ExperienceSource = 'todo_completion' | 'scope_change' | 'version_release' | 'manual';

export interface Experience {
  id: string;
  todo_id?: string;
  project_id?: string;
  version_id?: string;
  source_experience_id?: string;
  title: string;
  scope: ExperienceScope;
  status: ExperienceStatus;
  category: ExperienceCategory;
  source: ExperienceSource;
  problem: string;
  solution: string;
  decisions: string[];
  pitfalls: string[];
  applicable_scenarios?: string;
  tags: Tag[];
  confidence: number;
  reuse_count: number;
  half_life_days: number;
  is_stale: boolean;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ScopeDiff {
  is_first_apply: boolean;
  added?: Array<{ title: string; complexity?: string }>;
  removed_active?: Array<{ id: string; title: string }>;
  removed_pending?: Array<{ id: string; title: string }>;
  removed_done?: Array<{ id: string; title: string }>;
  unchanged_count?: number;
}

export interface ConflictItem {
  type: 'write_conflict' | 'cross_aggregate' | 'new_aggregate';
  severity: 'high' | 'medium' | 'low';
  features: string[];
  aggregate: string;
  description: string;
  suggestion: string;
}

export interface ConflictAnalysis {
  conflicts: ConflictItem[];
  risk_summary: string;
  parallel_safe: string[];
  sequential_required: Array<{ first: string; then: string; reason: string }>;
}

export interface UpdateExperienceRequest {
  title?: string;
  problem?: string;
  solution?: string;
  decisions?: string[];
  pitfalls?: string[];
  applicable_scenarios?: string;
  scope?: string;
  category?: string;
  source?: string;
  tags?: Tag[];
  half_life_days?: number;
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
  suspended: '已暂停',
  done: '已完成',
  error: '异常',
  abandoned: '已废弃',
};

export const EXPERIENCE_CATEGORY_LABELS: Record<ExperienceCategory, string> = {
  technical: '技术',
  business_rule: '业务规则',
  pitfall: '踩坑',
  architecture_decision: '架构决策',
  scope_change: '范围变更',
  estimation: '估算校准',
};

export const EXPERIENCE_SOURCE_LABELS: Record<ExperienceSource, string> = {
  todo_completion: '需求完成',
  scope_change: '范围变更',
  version_release: '版本发布',
  manual: '手动录入',
};

// ─── Planning ──────────────────────────────────────────
export interface PlanningDocument {
  id: string;
  project_id: string;
  filename: string;
  content_type: string;
  size: number;
  status: string;
  parsed_features: Array<Record<string, unknown>> | null;
  created_at: string;
}

export interface RoadmapFeature {
  title?: string;
  complexity?: string | number;
  priority?: string | number;
  [key: string]: unknown;
}

export interface RoadmapVersion {
  name?: string;
  goal?: string;
  estimated_sprints?: number;
  scope_rationale?: string;
  features?: RoadmapFeature[];
  risks?: string[];
  [key: string]: unknown;
}

export interface RoadmapData {
  strategy?: string;
  strategy_rationale?: string;
  total_estimated_weeks?: number;
  timeline_mermaid?: string;
  versions?: RoadmapVersion[];
  [key: string]: unknown;
}

export interface PlanningSession {
  id: string;
  project_id: string;
  version_id: string | null;
  document_ids: string[];
  constraints: Record<string, unknown>;
  roadmap: RoadmapData;
  conversation_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ─── Deliverables (Conversation Mode) ──────────────────
export interface DeliverableTracker {
  todo_id: string;
  required: string[];
  deliverables: Record<string, string>;
  completion_pct: number;
  is_complete: boolean;
}

export interface DomainModelSubdomain {
  name: string;
  type: '核心域' | '支撑域' | '通用域';
  description: string;
  priority?: number;
}

export interface DomainModelContext {
  name: string;
  subdomain: string;
  description: string;
  team?: string;
}

export interface DomainModelAggregate {
  name: string;
  context: string;
  description: string;
  root: string;
  entities: string[];
  value_objects: string[];
  events: string[];
  methods: string[];
  fields?: string[];
  source?: string;
}

export interface DomainModelRelation {
  from: string;
  to: string;
  type: string;
  description: string;
  integration?: string;
}

export interface DomainModel {
  subdomains: DomainModelSubdomain[];
  contexts: DomainModelContext[];
  aggregates: DomainModelAggregate[];
  relations: DomainModelRelation[];
  aggregate_relations: DomainModelRelation[];
  updated_at?: string;
  version?: number;
}

export interface DomainModelValidationIssue {
  severity: 'error' | 'warning' | 'info';
  category: 'strategic' | 'tactical' | 'naming' | 'completeness';
  title: string;
  detail: string;
  suggestion: string;
}

export interface DomainModelValidation {
  score: number;
  level: 'excellent' | 'good' | 'needs_improvement' | 'poor';
  issues: DomainModelValidationIssue[];
  strengths: string[];
  summary: string;
  feedbacks_created?: number;
}

// ─── Review Feedback (v3.0+) ─────────────────────────────
export type ReviewFeedbackStatus = 'pending' | 'accepted' | 'deferred' | 'rejected';
export type ModelChangeScope = 'additive' | 'structural' | 'breaking';
export type RiskLevel = 'none' | 'low' | 'medium' | 'high' | 'critical';

export interface ReviewFeedback {
  id: string;
  project_id: string;
  source_todo_id: string | null;
  model_version: number;
  scope: ModelChangeScope;
  status: ReviewFeedbackStatus;
  issue: DomainModelValidationIssue;
  resolution_note: string;
  created_at: string;
  resolved_at: string | null;
}

export interface DomainModelSnapshot {
  version: number;
  trigger: string;
  trigger_todo_id: string;
  created_at: string;
}

export interface ImpactItem {
  todo_id: string;
  todo_title: string;
  current_phase: string;
  affected_aggregates: string[];
  risk: RiskLevel;
  recommendation: string;
}

export interface ImpactReport {
  project_id: string;
  affected_aggregates: string[];
  change_scope: ModelChangeScope;
  max_risk: RiskLevel;
  blocked_count: number;
  summary: string;
  items: ImpactItem[];
}

export interface UpgradeResult {
  success: boolean;
  strategy: 'block' | 'defer';
  new_model_version: number | null;
  suspended_todo_ids: string[];
  auto_resumed_todo_ids: string[];
  deferred_feedback_ids: string[];
}

export const EXECUTION_MODE_LABELS: Record<ExecutionMode, string> = {
  pipeline: 'Pipeline 模式',
  conversation: '对话模式',
};

export const EXECUTION_MODE_DESCRIPTIONS: Record<ExecutionMode, string> = {
  pipeline: '固定七阶段流水线：需求澄清 → UI设计 → 技术架构 → 开发 → 测试 → 部署 → 经验沉淀。适合团队协作、流程规范的场景。',
  conversation: '自由对话驱动：AI根据需求自动拆解任务并产出交付物，无固定阶段约束。适合强个体、快速迭代的场景。',
};

export const PROCESS_CONSTRAINT_LABELS: Record<ProcessConstraint, string> = {
  strict: '严格模式',
  moderate: '适中模式',
  free: '自由模式',
};

export const PROCESS_CONSTRAINT_DESCRIPTIONS: Record<ProcessConstraint, string> = {
  strict: '强制阶段排序 + 质量门禁 + 显式确认。每个交付物必须通过 Gate 评审后才能推进。适合团队协作、质量优先的场景。',
  moderate: '推荐顺序 + 宽松门禁 + 可跳过。有方法论引导但不卡死，适合有经验的个体快速迭代。',
  free: '无阶段约束 + 自动提取交付物。AI 自主判断节奏，对话中自然产出结构化成果。适合探索性工作。',
};

// ─── Mode Switch ──────────────────────────────────────────
export interface ModeSwitchImpact {
  active_count: number;
  pending_count: number;
  safe_to_switch: boolean;
}

// ─── Task Stream (Conversation Mode Orchestration) ─────────
export type TaskStreamEventType = 'connected' | 'task_status' | 'task_chunk' | 'task_done' | 'error';

export interface TaskStreamEvent {
  event: TaskStreamEventType;
  todo_id?: string;
  status?: 'idle' | 'running' | 'error';
  stage?: string;
  content?: string;
  artifacts?: string[];
  detail?: string;
}

export interface BatchStartResult {
  todo_id: string;
  status: 'started' | 'error';
  conversation_id?: string;
  detail?: string;
}

export interface QuickMessageResponse {
  message_id: string;
  status: 'accepted';
}

// ─── Billing ─────────────────────────────────────────────
export interface UsageResponse {
  plan: string;
  projects_used: number;
  projects_limit: number;
  members_used: number;
  members_limit: number;
  ai_calls_today: number;
  ai_calls_limit: number;
}

export interface PlanLimitsResponse {
  free: Record<string, number>;
  pro: Record<string, number>;
  team: Record<string, number>;
}

