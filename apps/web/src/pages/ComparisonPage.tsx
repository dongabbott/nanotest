// filepath: d:\project\nanotest\apps\web\src\pages\ComparisonPage.tsx
import { useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  GitCompare, 
  CheckCircle, 
  XCircle, 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown,
  ArrowRight,
  Brain,
  Image
} from 'lucide-react';
import { comparisonsApi, testRunsApi } from '../services/api';

export default function ComparisonPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const comparisonId = searchParams.get('id');
  
  const [baselineRunId, setBaselineRunId] = useState('');
  const [targetRunId, setTargetRunId] = useState('');

  // 获取运行列表用于选择
  const { data: runsData } = useQuery({
    queryKey: ['testRuns', projectId],
    queryFn: () => testRunsApi.list(projectId!, 1, 50),
    enabled: !!projectId,
  });

  // 获取对比结果
  const { data: comparisonData, isLoading: comparisonLoading } = useQuery({
    queryKey: ['comparison', comparisonId],
    queryFn: () => comparisonsApi.get(comparisonId!),
    enabled: !!comparisonId,
  });

  // 创建对比
  const compareMutation = useMutation({
    mutationFn: () => comparisonsApi.compare(baselineRunId, targetRunId),
    onSuccess: (data) => {
      const newId = data.data.comparison_id;
      window.location.search = `?id=${newId}`;
    },
  });

  const runs = runsData?.data?.items || [];
  const comparison = comparisonData?.data;

  const getRiskLevelColor = (score: number) => {
    if (score >= 80) return 'text-red-600 bg-red-100';
    if (score >= 60) return 'text-orange-600 bg-orange-100';
    if (score >= 30) return 'text-yellow-600 bg-yellow-100';
    return 'text-green-600 bg-green-100';
  };

  const getRiskLevelLabel = (score: number) => {
    if (score >= 80) return '高风险';
    if (score >= 60) return '中风险';
    if (score >= 30) return '低风险';
    return '正常';
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">运行对比</h2>
        <p className="text-sm text-gray-500">对比两次测试运行的差异和变化</p>
      </div>

      {/* 选择对比 */}
      {!comparisonId && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-medium text-gray-900 mb-4">选择对比运行</h3>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                基线运行 (Baseline)
              </label>
              <select
                value={baselineRunId}
                onChange={(e) => setBaselineRunId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- 选择基线 --</option>
                {runs.filter((r: any) => r.status === 'success' || r.status === 'failed').map((run: any) => (
                  <option key={run.id} value={run.id}>
                    #{run.run_no} - {new Date(run.created_at).toLocaleDateString('zh-CN')}
                  </option>
                ))}
              </select>
            </div>

            <ArrowRight size={24} className="text-gray-400 flex-shrink-0 mt-6" />

            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                目标运行 (Target)
              </label>
              <select
                value={targetRunId}
                onChange={(e) => setTargetRunId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- 选择目标 --</option>
                {runs.filter((r: any) => r.status === 'success' || r.status === 'failed').map((run: any) => (
                  <option key={run.id} value={run.id}>
                    #{run.run_no} - {new Date(run.created_at).toLocaleDateString('zh-CN')}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => compareMutation.mutate()}
              disabled={!baselineRunId || !targetRunId || compareMutation.isPending}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 mt-6"
            >
              {compareMutation.isPending ? '对比中...' : '开始对比'}
            </button>
          </div>
        </div>
      )}

      {/* 对比结果 */}
      {comparisonId && comparisonLoading && (
        <div className="animate-pulse space-y-4">
          <div className="h-32 bg-gray-200 rounded-lg"></div>
          <div className="h-64 bg-gray-200 rounded-lg"></div>
        </div>
      )}

      {comparison && (
        <div className="space-y-6">
          {/* 风险评分卡片 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`w-16 h-16 rounded-xl flex items-center justify-center ${getRiskLevelColor(comparison.risk_score)}`}>
                  <span className="text-2xl font-bold">{Math.round(comparison.risk_score)}</span>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">风险评分</h3>
                  <p className={`text-sm font-medium ${getRiskLevelColor(comparison.risk_score).split(' ')[0]}`}>
                    {getRiskLevelLabel(comparison.risk_score)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <div className="text-center">
                  <p className="text-gray-500">基线运行</p>
                  <p className="font-medium text-gray-900">#{comparison.baseline_run_no || comparison.baseline_run_id?.slice(0, 8)}</p>
                </div>
                <ArrowRight size={20} className="text-gray-400" />
                <div className="text-center">
                  <p className="text-gray-500">目标运行</p>
                  <p className="font-medium text-gray-900">#{comparison.target_run_no || comparison.target_run_id?.slice(0, 8)}</p>
                </div>
              </div>
            </div>
          </div>

          {/* 差异摘要 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <CheckCircle size={20} className="text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {comparison.diff_summary?.fixed || 0}
                  </p>
                  <p className="text-sm text-gray-500">已修复</p>
                </div>
              </div>
              <p className="text-xs text-gray-500">基线失败 → 目标通过</p>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                  <XCircle size={20} className="text-red-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {comparison.diff_summary?.new_failures || 0}
                  </p>
                  <p className="text-sm text-gray-500">新增失败</p>
                </div>
              </div>
              <p className="text-xs text-gray-500">基线通过 → 目标失败</p>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
                  <AlertTriangle size={20} className="text-yellow-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {comparison.diff_summary?.visual_diffs || 0}
                  </p>
                  <p className="text-sm text-gray-500">视觉差异</p>
                </div>
              </div>
              <p className="text-xs text-gray-500">检测到的UI变化</p>
            </div>
          </div>

          {/* 详细差异列表 */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center gap-2">
              <GitCompare size={20} className="text-gray-400" />
              <h3 className="font-semibold text-gray-900">差异详情</h3>
            </div>
            
            {(!comparison.diff_summary?.details || comparison.diff_summary.details.length === 0) ? (
              <div className="px-6 py-8 text-center text-gray-500">
                暂无详细差异数据
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {comparison.diff_summary.details.map((diff: any, index: number) => (
                  <div key={index} className="px-6 py-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                          diff.type === 'fixed' ? 'bg-green-100' :
                          diff.type === 'new_failure' ? 'bg-red-100' :
                          'bg-yellow-100'
                        }`}>
                          {diff.type === 'fixed' ? (
                            <TrendingUp size={14} className="text-green-600" />
                          ) : diff.type === 'new_failure' ? (
                            <TrendingDown size={14} className="text-red-600" />
                          ) : (
                            <Image size={14} className="text-yellow-600" />
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{diff.step_name || diff.node_key}</p>
                          <p className="text-sm text-gray-500">{diff.description}</p>
                        </div>
                      </div>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                        diff.type === 'fixed' ? 'bg-green-100 text-green-700' :
                        diff.type === 'new_failure' ? 'bg-red-100 text-red-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {diff.type === 'fixed' ? '已修复' :
                         diff.type === 'new_failure' ? '新失败' : '视觉差异'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI分析建议 */}
          {comparison.ai_analysis && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Brain size={20} className="text-purple-600" />
                <h3 className="font-semibold text-gray-900">AI分析建议</h3>
              </div>
              <div className="prose prose-sm max-w-none text-gray-700">
                <p>{comparison.ai_analysis}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 空状态 */}
      {!comparisonId && runs.length === 0 && (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <GitCompare size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无可对比的运行</h3>
          <p className="text-gray-500">请先执行一些测试运行后再进行对比</p>
        </div>
      )}
    </div>
  );
}
