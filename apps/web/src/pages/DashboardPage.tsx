import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { 
  TrendingUp, 
  TrendingDown, 
  CheckCircle, 
  XCircle, 
  Activity
} from 'lucide-react';
import { testRunsApi } from '../services/api';

export default function DashboardPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data: runsData } = useQuery({
    queryKey: ['runs', projectId],
    queryFn: () => testRunsApi.list(projectId!, 1, 10),
    enabled: !!projectId,
    refetchOnMount: 'always',
  });

  const runs = runsData?.data?.items || [];

  // 计算统计数据
  const totalRuns = runs.length;
  const passedRuns = runs.filter((r: any) => r.status === 'success').length;
  const failedRuns = runs.filter((r: any) => r.status === 'failed').length;
  const passRate = totalRuns > 0 ? Math.round((passedRuns / totalRuns) * 100) : 0;

  const stats = [
    { label: '总执行次数', value: totalRuns, icon: Activity, color: 'blue' },
    { label: '通过', value: passedRuns, icon: CheckCircle, color: 'green' },
    { label: '失败', value: failedRuns, icon: XCircle, color: 'red' },
    { label: '通过率', value: `${passRate}%`, icon: passRate >= 80 ? TrendingUp : TrendingDown, color: passRate >= 80 ? 'green' : 'orange' },
  ];

  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    red: 'bg-red-100 text-red-600',
    orange: 'bg-orange-100 text-orange-600',
  };

  const statusLabels: Record<string, string> = {
    success: '成功',
    failed: '失败',
    running: '运行中',
    queued: '排队中',
  };

  return (
    <div className="space-y-8">
      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-500">{label}</span>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorClasses[color]}`}>
                <Icon size={20} />
              </div>
            </div>
            <div className="text-3xl font-bold text-gray-900">{value}</div>
          </div>
        ))}
      </div>

      {/* 最近执行记录 */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">最近执行记录</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {runs.length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-500">
              暂无执行记录。创建测试流程并触发执行后，数据将显示在这里。
            </div>
          ) : (
            runs.slice(0, 5).map((run: any) => (
              <div key={run.id} className="px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-2 h-2 rounded-full ${
                    run.status === 'success' ? 'bg-green-500' :
                    run.status === 'failed' ? 'bg-red-500' :
                    run.status === 'running' ? 'bg-blue-500 animate-pulse' :
                    'bg-gray-400'
                  }`} />
                  <div>
                    <p className="font-medium text-gray-900">#{run.run_no}</p>
                    <p className="text-sm text-gray-500">
                      {new Date(run.created_at).toLocaleString('zh-CN')}
                    </p>
                  </div>
                </div>
                <span className={`px-3 py-1 text-xs font-medium rounded-full ${
                  run.status === 'success' ? 'bg-green-100 text-green-700' :
                  run.status === 'failed' ? 'bg-red-100 text-red-700' :
                  run.status === 'running' ? 'bg-blue-100 text-blue-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {statusLabels[run.status] || run.status}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
