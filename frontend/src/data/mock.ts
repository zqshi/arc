import type { TodoStatus, PhaseType } from '../types/api';

export interface MockTodo {
  id: string;
  title: string;
  description: string;
  status: TodoStatus;
  current_phase: PhaseType | null;
  tags: { label: string; color: string }[];
  createdAt: string;
}

export const statusMap: Record<TodoStatus, { label: string; color: string }> = {
  pending: { label: '待启动', color: 'status-pending' },
  active: { label: '进行中', color: 'status-analyzing' },
  done: { label: '已完成', color: 'status-done' },
  error: { label: '异常', color: 'status-error' },
};

export const todos: MockTodo[] = [
  {
    id: '1',
    title: '用户登录模块重构',
    description: '将现有的 session-based 认证迁移到 JWT + refresh token 方案，支持多端登录',
    status: 'active',
    current_phase: 'development',
    tags: [
      { label: '后端', color: '#4A9FD8' },
      { label: '安全', color: '#EF4444' },
    ],
    createdAt: '2 小时前',
  },
  {
    id: '2',
    title: '订单列表性能优化',
    description: '订单列表页加载超过 3 秒，需要优化查询和前端渲染性能',
    status: 'active',
    current_phase: 'clarification',
    tags: [
      { label: '性能', color: '#E5A93D' },
      { label: '前端', color: '#34D399' },
    ],
    createdAt: '5 小时前',
  },
  {
    id: '3',
    title: '接入微信支付 V3',
    description: '商城模块需要接入微信支付 V3 API，支持 JSAPI、Native、H5 三种支付方式',
    status: 'pending',
    current_phase: null,
    tags: [
      { label: '支付', color: '#A78BFA' },
      { label: '第三方', color: '#F59E0B' },
    ],
    createdAt: '1 天前',
  },
  {
    id: '4',
    title: '数据导出功能开发',
    description: '支持将报表数据导出为 Excel / CSV 格式，含异步导出和下载通知',
    status: 'active',
    current_phase: 'architecture',
    tags: [
      { label: '功能', color: '#4A9FD8' },
    ],
    createdAt: '1 天前',
  },
  {
    id: '5',
    title: '用户画像标签系统设计',
    description: '设计并实现用户画像标签体系，支持自动打标和手动标注，供推荐系统使用',
    status: 'done',
    current_phase: 'extraction',
    tags: [
      { label: '数据', color: '#34D399' },
      { label: '推荐', color: '#EC4899' },
    ],
    createdAt: '3 天前',
  },
  {
    id: '6',
    title: '消息推送服务重构',
    description: '统一站内信、邮件、短信、Push 推送通道，抽象消息中心服务',
    status: 'done',
    current_phase: 'extraction',
    tags: [
      { label: '架构', color: '#F59E0B' },
      { label: '后端', color: '#4A9FD8' },
    ],
    createdAt: '5 天前',
  },
];
