import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useToast } from './Toast';
import type { Capability, CapabilityType, CapabilityStatus } from '../types/api';

interface CapabilityEditorModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (cap: Capability) => void;
  capability?: Capability | null; // 传入=编辑, 缺省=新增
}

const TYPE_OPTIONS: { value: CapabilityType; label: string; hint: string }[] = [
  { value: 'agent', label: 'Agent', hint: '声明一个可用 Coding Agent' },
  { value: 'skill', label: 'Skill', hint: 'SKILL.md 能力封装 (prompt+工具集)' },
  { value: 'mcp', label: 'MCP', hint: '外部 MCP server 工具 (stdio/http)' },
];

const STATUS_OPTIONS: { value: CapabilityStatus; label: string }[] = [
  { value: 'active', label: '启用' },
  { value: 'disabled', label: '禁用' },
];

type SkillSource = 'directory' | 'inline';

export function CapabilityEditorModal({ open, onClose, onSaved, capability }: CapabilityEditorModalProps) {
  const { toast } = useToast();
  const isEdit = !!capability;

  const [name, setName] = useState('');
  const [type, setType] = useState<CapabilityType>('agent');
  const [status, setStatus] = useState<CapabilityStatus>('active');
  // skill 结构化 config (C3: 对接 C1 SkillLoader 多来源 directory/inline)
  const [skillSource, setSkillSource] = useState<SkillSource>('directory');
  const [skillDirectory, setSkillDirectory] = useState('');
  const [skillContent, setSkillContent] = useState('');
  // agent/mcp 仍用 JSON textarea (C2 schema 缓做)
  const [configText, setConfigText] = useState('{}');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (capability) {
      setName(capability.name);
      setType(capability.type);
      setStatus(capability.status);
      const cfg = capability.config ?? {};
      if (capability.type === 'skill') {
        setSkillSource(cfg.source === 'inline' ? 'inline' : 'directory');
        setSkillDirectory(typeof cfg.directory === 'string' ? cfg.directory : '');
        setSkillContent(typeof cfg.content === 'string' ? cfg.content : '');
        setConfigText('{}');
      } else {
        setConfigText(JSON.stringify(cfg, null, 2));
        setSkillSource('directory');
        setSkillDirectory('');
        setSkillContent('');
      }
    } else {
      setName('');
      setType('agent');
      setStatus('active');
      setSkillSource('directory');
      setSkillDirectory('');
      setSkillContent('');
      setConfigText('{}');
    }
  }, [open, capability]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const buildConfig = (): Record<string, unknown> | null => {
    if (type === 'skill') {
      if (skillSource === 'inline') {
        if (!skillContent.trim()) {
          toast('inline skill 需填写 SKILL.md 内容', 'error');
          return null;
        }
        return { source: 'inline', content: skillContent };
      }
      return skillDirectory.trim()
        ? { source: 'directory', directory: skillDirectory.trim() }
        : {};
    }
    try {
      return configText.trim() ? JSON.parse(configText) : {};
    } catch {
      toast('config 不是合法 JSON', 'error');
      return null;
    }
  };

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed) { toast('请填写能力名称', 'error'); return; }

    const config = buildConfig();
    if (config === null) return;

    setSaving(true);
    try {
      const saved = isEdit
        ? await api.updateCapability(capability!.id, { name: trimmed, config, status })
        : await api.createCapability({ name: trimmed, type, config, status, scope: 'global' });
      toast(isEdit ? '能力已更新' : '能力已创建', 'success');
      onSaved(saved);
      onClose();
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : '保存失败', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative mx-4 w-full max-w-lg animate-slide-up rounded-xl border border-border-active bg-bg-card shadow-2xl sm:mx-auto">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="text-sm font-semibold text-text-primary">{isEdit ? '编辑能力' : '新增能力'}</h2>
          <button onClick={onClose} className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-bg-elevated hover:text-text-secondary transition-colors">
            <X size={14} />
          </button>
        </div>

        <div className="max-h-[70vh] space-y-4 overflow-y-auto px-5 py-4">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-text-tertiary">名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：code-reviewer / prd-writer"
              className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent/50 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-[11px] font-medium text-text-tertiary">类型</label>
            {isEdit ? (
              <div className="flex h-9 items-center rounded-md border border-border bg-bg-elevated px-3 text-sm text-text-secondary">
                {type}
                <span className="ml-2 text-[10px] text-text-muted">(类型不可修改)</span>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {TYPE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setType(opt.value)}
                    className={`rounded-md border p-2 text-left transition-all ${type === opt.value ? 'border-accent/50 bg-accent/5 ring-1 ring-accent/20' : 'border-border hover:border-border-active'}`}
                  >
                    <span className={`block text-xs font-medium ${type === opt.value ? 'text-accent' : 'text-text-secondary'}`}>{opt.label}</span>
                    <span className="mt-0.5 block text-[10px] leading-tight text-text-muted">{opt.hint}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="mb-1 block text-[11px] font-medium text-text-tertiary">状态</label>
            <div className="flex gap-2">
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setStatus(opt.value)}
                  className={`rounded-md border px-3 py-1.5 text-xs transition-all ${status === opt.value ? 'border-accent/50 bg-accent/5 text-accent' : 'border-border text-text-secondary hover:border-border-active'}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {type === 'skill' ? (
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-text-tertiary">Skill 来源</label>
                <div className="flex gap-2">
                  {(['directory', 'inline'] as SkillSource[]).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setSkillSource(s)}
                      className={`rounded-md border px-3 py-1.5 text-xs transition-all ${skillSource === s ? 'border-accent/50 bg-accent/5 text-accent' : 'border-border text-text-secondary hover:border-border-active'}`}
                    >
                      {s === 'directory' ? '目录 (SKILL.md)' : '内联文本'}
                    </button>
                  ))}
                </div>
              </div>
              {skillSource === 'directory' ? (
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-text-tertiary">Skill 目录路径</label>
                  <input
                    value={skillDirectory}
                    onChange={(e) => setSkillDirectory(e.target.value)}
                    placeholder="例如：~/.claude/skills/code-reviewer"
                    className="h-9 w-full rounded-md border border-border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent/50 focus:outline-none"
                  />
                  <p className="mt-1 text-[10px] text-text-muted">读取该目录下的 SKILL.md。留空 = 使用默认配置。</p>
                </div>
              ) : (
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-text-tertiary">SKILL.md 内容</label>
                  <textarea
                    value={skillContent}
                    onChange={(e) => setSkillContent(e.target.value)}
                    rows={8}
                    placeholder={'---\nname: code-reviewer\ndescription: ...\n---\n\n# 内容...'}
                    className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-muted focus:border-accent/50 focus:outline-none"
                  />
                  <p className="mt-1 text-[10px] text-text-muted">直接填写 SKILL.md 文本，无需文件。可用 skill-creator 生成后粘贴。</p>
                </div>
              )}
            </div>
          ) : (
            <div>
              <label className="mb-1 block text-[11px] font-medium text-text-tertiary">配置 (JSON)</label>
              <textarea
                value={configText}
                onChange={(e) => setConfigText(e.target.value)}
                rows={6}
                placeholder='{}'
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-muted focus:border-accent/50 focus:outline-none"
              />
              <p className="mt-1 text-[10px] text-text-muted">
                {type === 'mcp'
                  ? 'stdio: {"transport":"stdio","command","args","env"}；http: {"transport":"http","url","headers"}'
                  : 'agent: { agent_key, ... }。留空或 {} = 使用默认配置。'}
              </p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3.5">
          <button onClick={onClose} className="rounded-md border border-border px-3.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary">
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="rounded-md bg-accent px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
