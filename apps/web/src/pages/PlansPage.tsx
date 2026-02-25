import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Calendar, Play, X, Edit, Trash2, GitBranch } from 'lucide-react';
import { plansApi, testFlowsApi } from '../services/api';

// 创建计划弹窗
function CreatePlanModal({
  isOpen,
  onClose,
  projectId,
}: {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
}) {
  const [name, setName] = useState('');
  const [flowId, setFlowId] = useState('');
  const [triggerType, setTriggerType] = useState<'manual' | 'cron' | 'webhook'>('manual');
  const [cronExpr, setCronExpr] = useState('0 9 * * *');
  const [error, setError] = useState('');

  const queryClient = useQueryClient();

  const { data: flowsData } = useQuery({
    queryKey: ['testFlows', projectId],
    queryFn: () => testFlowsApi.list(projectId, 1, 100),
    enabled: isOpen,
  });

  const flows = flowsData?.data?.items || [];

  const createMutation = useMutation({
    mutationFn: (data: any) => plansApi.create(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans', projectId] });
      onClose();
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建计划失败');
    },
  });

  const resetForm = () => {
    setName('');
    setFlowId('');
    setTriggerType('manual');
    setCronExpr('0 9 * * *');
    setError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('请输入计划名称');
      return;
    }
    if (!flowId) {
      setError('请选择测试流程');
      return;
    }

    createMutation.mutate({
      name: name.trim(),
      flow_id: flowId,
      trigger_type: triggerType,
      cron_expr: triggerType === 'cron' ? cronExpr : null,
      is_enabled: true,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">创建测试计划</h2>
          <button onClick={() => { onClose(); resetForm(); }} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">{error}</div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              计划名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="每日冒烟测试"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              测试流程 <span className="text-red-500">*</span>
            </label>
            {flows.length === 0 ? (
              <div className="text-sm text-gray-500 p-4 bg-gray-50 rounded-lg text-center">
                暂无可用的测试流程，请先创建流程
              </div>
            ) : (
              <select
                value={flowId}
                onChange={(e) => setFlowId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">-- 请选择流程 --</option>
                {flows.map((flow: any) => (
                  <option key={flow.id} value={flow.id}>{flow.name}</option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              触发方式
            </label>
            <div className="flex gap-2">
              {[
                { value: 'manual', label: '手动触发' },
                { value: 'cron', label: '定时执行' },
                { value: 'webhook', label: 'Webhook' },
              ].map((option) => (
                <label
                  key={option.value}
                  className={`flex-1 flex items-center justify-center p-2 border rounded-lg cursor-pointer transition-colors text-sm ${
                    triggerType === option.value
                      ? 'border-blue-500 bg-blue-50 text-blue-600'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <input
                    type="radio"
                    name="triggerType"
                    value={option.value}
                    checked={triggerType === option.value}
                    onChange={() => setTriggerType(option.value as any)}
                    className="hidden"
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </div>

          {triggerType === 'cron' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Cron表达式
              </label>
              <input
                type="text"
                value={cronExpr}
                onChange={(e) => setCronExpr(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                placeholder="0 9 * * *"
              />
              <p className="text-xs text-gray-500 mt-1">
                示例：0 9 * * * (每天9:00)，0 */2 * * * (每2小时)
              </p>
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={() => { onClose(); resetForm(); }}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {createMutation.isPending ? '创建中...' : '创建计划'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PlansPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['plans', projectId],
    queryFn: () => plansApi.list(projectId!, 1, 50),
    enabled: !!projectId,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ planId, isEnabled }: { planId: string; isEnabled: boolean }) =>
      plansApi.update(planId, { is_enabled: isEnabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans', projectId] });
    },
  });

  const triggerMutation = useMutation({
    mutationFn: (planId: string) => plansApi.trigger(planId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testRuns', projectId] });
    },
  });

  const plans = data?.data?.items || [];

  const triggerTypeLabels: Record<string, string> = {
    manual: '手动触发',
    cron: '定时执行',
    webhook: 'Webhook',
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">测试计划</h2>
          <p className="text-sm text-gray-500">管理定时任务和触发策略</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={18} />
          <span>新建计划</span>
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : plans.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <Calendar size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无测试计划</h3>
          <p className="text-gray-500 mb-6">创建计划来定时执行测试流程</p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            创建计划
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">计划名称</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">测试流程</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">触发方式</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {plans.map((plan: any) => (
                <tr key={plan.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <Calendar size={18} className="text-gray-400" />
                      <span className="font-medium text-gray-900">{plan.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <GitBranch size={14} />
                      <span>{plan.flow_name || '未知流程'}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm">
                      <span className="text-gray-900">{triggerTypeLabels[plan.trigger_type]}</span>
                      {plan.trigger_type === 'cron' && plan.cron_expr && (
                        <p className="text-xs text-gray-500 font-mono">{plan.cron_expr}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => toggleMutation.mutate({ planId: plan.id, isEnabled: !plan.is_enabled })}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full ${
                        plan.is_enabled
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {plan.is_enabled ? '已启用' : '已停用'}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => triggerMutation.mutate(plan.id)}
                        disabled={triggerMutation.isPending}
                        className="p-1.5 hover:bg-green-100 rounded text-gray-400 hover:text-green-600"
                        title="立即执行"
                      >
                        <Play size={16} />
                      </button>
                      <button className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-blue-600" title="编辑">
                        <Edit size={16} />
                      </button>
                      <button className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-red-600" title="删除">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreatePlanModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        projectId={projectId!}
      />
    </div>
  );
}
