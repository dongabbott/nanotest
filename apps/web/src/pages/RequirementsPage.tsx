import React, { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BookText, Plus, Search, X, Trash2, Sparkles, RefreshCw } from 'lucide-react';
import { requirementsApi } from '../services/api';

type RequirementFormData = {
  key: string;
  title: string;
  description: string;
  acceptance_criteria: string;
  business_rules: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'draft' | 'active' | 'deprecated' | 'archived';
  platform: 'android' | 'ios' | 'hybrid' | 'common';
  tags: string;
  change_log: string;
};

const emptyForm: RequirementFormData = {
  key: '',
  title: '',
  description: '',
  acceptance_criteria: '',
  business_rules: '',
  priority: 'medium',
  status: 'draft',
  platform: 'common',
  tags: '',
  change_log: '',
};

function toLines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function RequirementModal({
  projectId,
  isOpen,
  onClose,
  editItem,
}: {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  editItem?: any;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState('');
  const [form, setForm] = useState<RequirementFormData>(() => {
    if (!editItem) return emptyForm;
    return {
      key: editItem.key || '',
      title: editItem.title || '',
      description: editItem.description || '',
      acceptance_criteria: (editItem.acceptance_criteria || []).join('\n'),
      business_rules: (editItem.business_rules || []).join('\n'),
      priority: editItem.priority || 'medium',
      status: editItem.status || 'draft',
      platform: editItem.platform || 'common',
      tags: (editItem.tags || []).join(', '),
      change_log: '',
    };
  });

  React.useEffect(() => {
    if (!isOpen) return;
    if (!editItem) {
      setForm(emptyForm);
      setError('');
      return;
    }
    setForm({
      key: editItem.key || '',
      title: editItem.title || '',
      description: editItem.description || '',
      acceptance_criteria: (editItem.acceptance_criteria || []).join('\n'),
      business_rules: (editItem.business_rules || []).join('\n'),
      priority: editItem.priority || 'medium',
      status: editItem.status || 'draft',
      platform: editItem.platform || 'common',
      tags: (editItem.tags || []).join(', '),
      change_log: '',
    });
    setError('');
  }, [editItem, isOpen]);

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        key: form.key.trim(),
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        acceptance_criteria: toLines(form.acceptance_criteria),
        business_rules: toLines(form.business_rules),
        priority: form.priority,
        status: form.status,
        platform: form.platform,
        tags: form.tags.split(',').map((item) => item.trim()).filter(Boolean),
        change_log: form.change_log.trim() || undefined,
      };

      if (editItem) {
        return requirementsApi.update(editItem.id, payload);
      }
      return requirementsApi.create(projectId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements', projectId] });
      queryClient.invalidateQueries({ queryKey: ['requirementSearch', projectId] });
      onClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '保存需求失败');
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="w-full max-w-3xl rounded-xl bg-white shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{editItem ? '编辑需求' : '新建需求'}</h2>
            <p className="text-sm text-gray-500">支持版本快照与后续向量检索。</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!form.key.trim() || !form.title.trim()) {
              setError('请输入需求编号和标题');
              return;
            }
            mutation.mutate();
          }}
          className="space-y-4 p-6"
        >
          {error && <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700">需求编号</span>
              <input
                value={form.key}
                onChange={(e) => setForm((prev) => ({ ...prev, key: e.target.value }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="REQ-LOGIN-001"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700">标题</span>
              <input
                value={form.title}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="用户应能使用手机号验证码登录"
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700">优先级</span>
              <select
                value={form.priority}
                onChange={(e) => setForm((prev) => ({ ...prev, priority: e.target.value as RequirementFormData['priority'] }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
                <option value="critical">关键</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700">状态</span>
              <select
                value={form.status}
                onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value as RequirementFormData['status'] }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="draft">草稿</option>
                <option value="active">生效</option>
                <option value="deprecated">废弃</option>
                <option value="archived">归档</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700">平台</span>
              <select
                value={form.platform}
                onChange={(e) => setForm((prev) => ({ ...prev, platform: e.target.value as RequirementFormData['platform'] }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="common">通用</option>
                <option value="android">Android</option>
                <option value="ios">iOS</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </label>
          </div>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">需求描述</span>
            <textarea
              rows={4}
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              placeholder="描述业务目标、适用范围、前置条件等。"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">验收标准（每行一条）</span>
            <textarea
              rows={5}
              value={form.acceptance_criteria}
              onChange={(e) => setForm((prev) => ({ ...prev, acceptance_criteria: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              placeholder="输入手机号后点击获取验证码\n验证码有效期 5 分钟"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">业务规则（每行一条）</span>
            <textarea
              rows={4}
              value={form.business_rules}
              onChange={(e) => setForm((prev) => ({ ...prev, business_rules: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
              placeholder="未注册手机号不可登录\n验证码连续错误 5 次需限流"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700">标签（逗号分隔）</span>
              <input
                value={form.tags}
                onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                placeholder="登录, 风控, 验证码"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700">变更说明</span>
              <input
                value={form.change_log}
                onChange={(e) => setForm((prev) => ({ ...prev, change_log: e.target.value }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
                placeholder="记录此次版本变化"
              />
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50">
              取消
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? '保存中...' : editItem ? '保存修改' : '创建需求'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function RequirementsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState('');
  const [semanticQuery, setSemanticQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<any | undefined>();

  const { data, isLoading } = useQuery({
    queryKey: ['requirements', projectId, keyword],
    queryFn: () => requirementsApi.list(projectId!, { q: keyword || undefined, page_size: 100 }),
    enabled: !!projectId,
  });

  const semanticSearch = useQuery({
    queryKey: ['requirementSearch', projectId, semanticQuery],
    queryFn: () => requirementsApi.search(projectId!, { query: semanticQuery, top_k: 8 }),
    enabled: !!projectId && semanticQuery.trim().length > 0,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => requirementsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements', projectId] });
      queryClient.invalidateQueries({ queryKey: ['requirementSearch', projectId] });
    },
  });

  const reindexMutation = useMutation({
    mutationFn: (id: string) => requirementsApi.reindex(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements', projectId] });
      queryClient.invalidateQueries({ queryKey: ['requirementSearch', projectId] });
    },
  });

  const items = data?.data?.items || [];
  const semanticItems = semanticSearch.data?.data?.items || [];
  const summary = useMemo(() => {
    const activeCount = items.filter((item: any) => item.status === 'active').length;
    const criticalCount = items.filter((item: any) => item.priority === 'critical').length;
    return { total: items.length, activeCount, criticalCount };
  }, [items]);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 p-6 text-white shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-blue-100">
              <BookText size={16} />
              <span>项目需求管理</span>
            </div>
            <h1 className="text-2xl font-bold">需求中心</h1>
            <p className="mt-2 text-sm text-blue-100">维护需求、验收标准和业务规则，为用例生成与执行分析提供可靠上下文。</p>
          </div>
          <button
            onClick={() => {
              setEditItem(undefined);
              setIsModalOpen(true);
            }}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-4 py-2 font-medium text-blue-700 hover:bg-blue-50"
          >
            <Plus size={18} />
            <span>新建需求</span>
          </button>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl bg-white/10 p-4">
            <div className="text-sm text-blue-100">总需求数</div>
            <div className="mt-1 text-2xl font-semibold">{summary.total}</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4">
            <div className="text-sm text-blue-100">生效中</div>
            <div className="mt-1 text-2xl font-semibold">{summary.activeCount}</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4">
            <div className="text-sm text-blue-100">关键需求</div>
            <div className="mt-1 text-2xl font-semibold">{summary.criticalCount}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">需求列表</h2>
              <p className="text-sm text-gray-500">支持编号、标题和规则关键字过滤。</p>
            </div>
            <div className="relative w-full md:w-80">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="搜索需求编号或标题"
              />
            </div>
          </div>

          <div className="space-y-4">
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-28 animate-pulse rounded-xl bg-gray-100" />
                ))}
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-xl border border-dashed border-gray-300 px-6 py-12 text-center text-sm text-gray-500">
                暂无需求，先创建第一条需求。
              </div>
            ) : (
              items.map((item: any) => (
                <div key={item.id} className="rounded-xl border border-gray-200 p-4 transition-shadow hover:shadow-sm">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{item.key}</span>
                        <span className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-600">{item.platform}</span>
                        <span className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">{item.priority}</span>
                        <span className="rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-700">{item.status}</span>
                        <span className="rounded bg-purple-50 px-2 py-1 text-xs text-purple-700">v{item.version}</span>
                      </div>
                      <h3 className="mt-3 text-base font-semibold text-gray-900">{item.title}</h3>
                      {item.description && <p className="mt-2 text-sm leading-6 text-gray-600">{item.description}</p>}
                      {!!item.acceptance_criteria?.length && (
                        <div className="mt-3">
                          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">验收标准</div>
                          <ul className="space-y-1 text-sm text-gray-600">
                            {item.acceptance_criteria.slice(0, 3).map((criterion: string) => (
                              <li key={criterion} className="flex gap-2">
                                <span className="mt-2 h-1.5 w-1.5 rounded-full bg-blue-500" />
                                <span>{criterion}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-row gap-2 lg:flex-col">
                      <button
                        onClick={() => {
                          setEditItem(item);
                          setIsModalOpen(true);
                        }}
                        className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                      >
                        编辑
                      </button>
                      <button
                        onClick={() => reindexMutation.mutate(item.id)}
                        disabled={reindexMutation.isPending}
                        className="inline-flex items-center gap-1 rounded-lg border border-blue-200 px-3 py-2 text-sm text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                      >
                        <RefreshCw size={14} />
                        重建索引
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(item.id)}
                        disabled={deleteMutation.isPending}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                      >
                        <Trash2 size={14} />
                        删除
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-gray-900">
            <Sparkles size={18} className="text-violet-600" />
            <h2 className="text-lg font-semibold">语义检索</h2>
          </div>
          <p className="mt-2 text-sm text-gray-500">调用后端需求搜索接口，优先使用向量检索，失败时自动回退到关键词搜索。</p>

          <div className="mt-4 flex gap-2">
            <input
              value={semanticQuery}
              onChange={(e) => setSemanticQuery(e.target.value)}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500"
              placeholder="例如：登录验证码有效期、异常提示、限流规则"
            />
            <button
              onClick={() => semanticSearch.refetch()}
              className="rounded-lg bg-violet-600 px-4 py-2 text-white hover:bg-violet-700"
            >
              搜索
            </button>
          </div>

          <div className="mt-5 space-y-3">
            {semanticSearch.isFetching ? (
              <div className="rounded-xl bg-violet-50 px-4 py-6 text-sm text-violet-700">正在执行语义检索...</div>
            ) : semanticQuery.trim() && semanticItems.length === 0 ? (
              <div className="rounded-xl border border-dashed border-gray-300 px-4 py-6 text-sm text-gray-500">没有找到匹配需求。</div>
            ) : semanticItems.map((item: any) => (
              <div key={item.requirement.id} className="rounded-xl border border-violet-100 bg-violet-50/50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-violet-700">{item.requirement.key}</div>
                    <div className="mt-1 text-sm font-semibold text-gray-900">{item.requirement.title}</div>
                  </div>
                  <div className="rounded bg-white px-2 py-1 text-xs text-violet-700">score {Number(item.score || 0).toFixed(3)}</div>
                </div>
                {!!item.matched_chunks?.length && (
                  <div className="mt-3 space-y-2">
                    {item.matched_chunks.map((chunk: string) => (
                      <div key={chunk} className="rounded-lg bg-white px-3 py-2 text-sm leading-6 text-gray-600">
                        {chunk}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>

      {projectId && (
        <RequirementModal
          projectId={projectId}
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          editItem={editItem}
        />
      )}
    </div>
  );
}