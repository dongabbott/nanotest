import React, { useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Clock, CheckCircle, XCircle, Loader2, X, GitBranch, Smartphone } from 'lucide-react';
import { testRunsApi, testFlowsApi, devicesApi } from '../services/api';

// 触发运行弹窗
function TriggerRunModal({
  isOpen,
  onClose,
  projectId,
  preselectedFlowId,
}: {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  preselectedFlowId?: string;
}) {
  const [selectedFlowId, setSelectedFlowId] = useState(preselectedFlowId || '');
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [error, setError] = useState('');

  const queryClient = useQueryClient();

  const { data: flowsData } = useQuery({
    queryKey: ['testFlows', projectId],
    queryFn: () => testFlowsApi.list(projectId, 1, 100),
    enabled: isOpen,
  });

  // 获取活跃的 Appium Sessions
  const { data: sessionsData } = useQuery({
    queryKey: ['activeSessions'],
    queryFn: () => devicesApi.listSessions(),
    enabled: isOpen,
  });

  const flows = flowsData?.data?.items || [];
  const sessions = (sessionsData?.data?.sessions || []).filter(
    (s: any) => s.status === 'active'
  );

  const triggerMutation = useMutation({
    mutationFn: (data: { flowId: string; sessionId?: string }) =>
      testRunsApi.trigger(data.flowId, {
        sessionId: data.sessionId || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testRuns', projectId] });
      onClose();
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '触发执行失败');
    },
  });

  const resetForm = () => {
    setSelectedFlowId('');
    setSelectedSessionId('');
    setError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFlowId) {
      setError('请选择测试流程');
      return;
    }

    triggerMutation.mutate({
      flowId: selectedFlowId,
      sessionId: selectedSessionId || undefined,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">触发测试执行</h2>
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
              选择测试流程 <span className="text-red-500">*</span>
            </label>
            {flows.length === 0 ? (
              <div className="text-sm text-gray-500 p-4 bg-gray-50 rounded-lg text-center">
                暂无可用的测试流程，请先创建流程
              </div>
            ) : (
              <select
                value={selectedFlowId}
                onChange={(e) => setSelectedFlowId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">-- 请选择流程 --</option>
                {flows.map((flow: any) => (
                  <option key={flow.id} value={flow.id}>
                    {flow.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Appium Session 选择（可选） */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <span className="flex items-center gap-1.5">
                <Smartphone size={14} />
                关联设备会话
                <span className="text-xs text-gray-400 font-normal">（可选，不选则模拟执行）</span>
              </span>
            </label>
            {sessions.length === 0 ? (
              <div className="text-sm text-gray-500 p-3 bg-gray-50 rounded-lg text-center">
                暂无活跃会话，请先在「设备管理 → 会话」中创建
              </div>
            ) : (
              <select
                value={selectedSessionId}
                onChange={(e) => setSelectedSessionId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">-- 不关联设备（模拟执行） --</option>
                {sessions.map((session: any) => (
                  <option key={session.session_id} value={session.session_id}>
                    {session.app_name || session.package_name || '未知应用'} · {session.device_name || session.device_udid} ({session.platform})
                  </option>
                ))}
              </select>
            )}
            {selectedSessionId && (
              <p className="mt-1.5 text-xs text-green-600 flex items-center gap-1">
                <CheckCircle size={12} />
                将使用真机执行测试
              </p>
            )}
          </div>

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
              disabled={triggerMutation.isPending || flows.length === 0}
              className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {triggerMutation.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  启动中...
                </>
              ) : (
                <>
                  <Play size={16} />
                  开始执行
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function TestRunsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const preselectedFlowId = searchParams.get('flow') || undefined;
  const [isModalOpen, setIsModalOpen] = useState(!!preselectedFlowId);

  const { data, isLoading } = useQuery({
    queryKey: ['testRuns', projectId],
    queryFn: () => testRunsApi.list(projectId!, 1, 50),
    enabled: !!projectId,
    refetchInterval: 5000,
    refetchOnMount: 'always',
  });

  const runs = data?.data?.items || [];

  const statusConfig: Record<string, { icon: any; color: string; bg: string; label: string }> = {
    queued: { icon: Clock, color: 'text-gray-600', bg: 'bg-gray-100', label: '排队中' },
    running: { icon: Loader2, color: 'text-blue-600', bg: 'bg-blue-100', label: '运行中' },
    passed: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-100', label: '成功' },
    success: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-100', label: '成功' },
    failed: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-100', label: '失败' },
    partial: { icon: CheckCircle, color: 'text-yellow-600', bg: 'bg-yellow-100', label: '部分通过' },
    cancelled: { icon: XCircle, color: 'text-gray-600', bg: 'bg-gray-100', label: '已取消' },
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">执行记录</h2>
          <p className="text-sm text-gray-500">查看和管理测试执行</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
        >
          <Play size={18} />
          <span>触发执行</span>
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <Play size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无执行记录</h3>
          <p className="text-gray-500 mb-6">选择测试流程并触发执行</p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition-colors"
          >
            触发执行
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">执行编号</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">流程</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">开始时间</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">耗时</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">结果</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {runs.map((run: any) => {
                const status = statusConfig[run.status] || statusConfig.queued;
                const StatusIcon = status.icon;
                const duration = run.finished_at && run.started_at
                  ? Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000)
                  : null;

                return (
                  <tr key={run.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <Link
                        to={`${run.id}`}
                        className="font-medium text-blue-600 hover:text-blue-800"
                      >
                        #{run.run_no}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <GitBranch size={14} />
                        <span>{run.flow_name || '未知'}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full ${status.bg} ${status.color}`}>
                        <StatusIcon size={14} className={run.status === 'running' ? 'animate-spin' : ''} />
                        {status.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {run.started_at ? new Date(run.started_at).toLocaleString('zh-CN') : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {duration !== null ? `${duration}秒` : run.status === 'running' ? '...' : '-'}
                    </td>
                    <td className="px-6 py-4">
                      {run.summary ? (
                        <div className="flex items-center gap-3 text-xs">
                          <span className="text-green-600">{run.summary.passed || 0} 通过</span>
                          <span className="text-red-600">{run.summary.failed || 0} 失败</span>
                          <span className="text-gray-500">{run.summary.skipped || 0} 跳过</span>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <TriggerRunModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        projectId={projectId!}
        preselectedFlowId={preselectedFlowId}
      />
    </div>
  );
}
