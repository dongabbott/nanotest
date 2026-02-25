import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { 
  ChevronLeft, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertTriangle,
  Brain
} from 'lucide-react';
import { testRunsApi } from '../services/api';

export default function RunDetailPage() {
  const { projectId, runId } = useParams<{ projectId: string; runId: string }>();

  const { data: runData, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => testRunsApi.get(runId!),
    enabled: !!runId,
  });

  const run = runData?.data;

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-gray-200 rounded w-1/4"></div>
        <div className="h-32 bg-gray-200 rounded"></div>
        <div className="h-64 bg-gray-200 rounded"></div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500">未找到执行记录</p>
      </div>
    );
  }

  const statusLabels: Record<string, string> = {
    success: '成功',
    failed: '失败',
    running: '运行中',
    queued: '排队中',
    cancelled: '已取消',
  };

  const statusColors: Record<string, string> = {
    success: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    running: 'bg-blue-100 text-blue-700',
    queued: 'bg-gray-100 text-gray-700',
    cancelled: 'bg-gray-100 text-gray-700',
  };

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            to={`/projects/${projectId}/runs`}
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ChevronLeft size={16} />
            <span>返回执行列表</span>
          </Link>
          <h2 className="text-xl font-bold text-gray-900">#{run.run_no}</h2>
        </div>
        <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusColors[run.status] || statusColors.queued}`}>
          {statusLabels[run.status] || run.status}
        </span>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle size={20} className="text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{run.summary?.passed || 0}</p>
              <p className="text-sm text-gray-500">通过</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <XCircle size={20} className="text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{run.summary?.failed || 0}</p>
              <p className="text-sm text-gray-500">失败</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Clock size={20} className="text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {run.finished_at && run.started_at
                  ? `${Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000)}秒`
                  : '-'}
              </p>
              <p className="text-sm text-gray-500">耗时</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Brain size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{run.summary?.risk_score || '-'}</p>
              <p className="text-sm text-gray-500">风险评分</p>
            </div>
          </div>
        </div>
      </div>

      {/* AI分析区域 */}
      {run.ai_summary && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Brain size={20} className="text-purple-600" />
            <h3 className="font-semibold text-gray-900">AI分析</h3>
          </div>
          <p className="text-gray-700">{run.ai_summary}</p>
        </div>
      )}

      {/* 测试步骤时间线 */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">测试步骤</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {(run.nodes || []).length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-500">
              暂无测试步骤记录
            </div>
          ) : (
            (run.nodes || []).map((node: any, index: number) => (
              <div key={node.id} className="px-6 py-4">
                <div className="flex items-start gap-4">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                    node.status === 'success' ? 'bg-green-100' :
                    node.status === 'failed' ? 'bg-red-100' :
                    'bg-gray-100'
                  }`}>
                    {node.status === 'success' ? (
                      <CheckCircle size={16} className="text-green-600" />
                    ) : node.status === 'failed' ? (
                      <XCircle size={16} className="text-red-600" />
                    ) : (
                      <Clock size={16} className="text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-medium text-gray-900">{node.node_key}</p>
                      <span className="text-sm text-gray-500">
                        {node.duration_ms ? `${node.duration_ms}毫秒` : '-'}
                      </span>
                    </div>
                    {node.error_message && (
                      <div className="mt-2 p-3 bg-red-50 rounded-lg">
                        <div className="flex items-start gap-2">
                          <AlertTriangle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                          <p className="text-sm text-red-700">{node.error_message}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
