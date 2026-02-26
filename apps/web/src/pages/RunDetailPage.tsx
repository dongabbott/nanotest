import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronLeft,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Brain,
  Loader2,
  ChevronDown,
  ChevronRight,
  Monitor,
  Smartphone,
  Server,
  Hash,
  Calendar,
  Timer,
  FileText,
  Image,
  Copy,
  Check,
  RefreshCw,
  Ban,
} from 'lucide-react';
import { testRunsApi } from '../services/api';

// ============================================================================
// 状态配置
// ============================================================================

const statusConfig: Record<string, { icon: any; color: string; bg: string; label: string; border: string }> = {
  passed: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50', label: '通过', border: 'border-green-200' },
  success: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50', label: '成功', border: 'border-green-200' },
  failed: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50', label: '失败', border: 'border-red-200' },
  error: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50', label: '错误', border: 'border-red-200' },
  running: { icon: Loader2, color: 'text-blue-600', bg: 'bg-blue-50', label: '运行中', border: 'border-blue-200' },
  queued: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-50', label: '排队中', border: 'border-gray-200' },
  pending: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-50', label: '等待中', border: 'border-gray-200' },
  skipped: { icon: Ban, color: 'text-gray-400', bg: 'bg-gray-50', label: '跳过', border: 'border-gray-200' },
  cancelled: { icon: Ban, color: 'text-gray-500', bg: 'bg-gray-50', label: '已取消', border: 'border-gray-200' },
  partial: { icon: AlertTriangle, color: 'text-yellow-600', bg: 'bg-yellow-50', label: '部分通过', border: 'border-yellow-200' },
};

function getStatus(s: string) {
  return statusConfig[s] || statusConfig.pending;
}

function StatusBadge({ status, size = 'sm' }: { status: string; size?: 'sm' | 'md' }) {
  const cfg = getStatus(status);
  const Icon = cfg.icon;
  const sizeClass = size === 'md' ? 'px-3 py-1.5 text-sm' : 'px-2 py-0.5 text-xs';
  return (
    <span className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${cfg.bg} ${cfg.color} ${cfg.border} ${sizeClass}`}>
      <Icon size={size === 'md' ? 16 : 14} className={status === 'running' ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  );
}

// ============================================================================
// 辅助函数
// ============================================================================

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '-';
  if (ms < 1000) return `${ms}ms`;
  const seconds = (ms / 1000).toFixed(1);
  return `${seconds}s`;
}

function formatTimeDiff(start?: string | null, end?: string | null): string {
  if (!start || !end) return '-';
  const diff = new Date(end).getTime() - new Date(start).getTime();
  if (diff < 1000) return `${diff}ms`;
  if (diff < 60000) return `${(diff / 1000).toFixed(1)}秒`;
  const mins = Math.floor(diff / 60000);
  const secs = Math.round((diff % 60000) / 1000);
  return `${mins}分${secs}秒`;
}

function formatTime(ts?: string | null): string {
  if (!ts) return '-';
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

// ============================================================================
// 可复制文本
// ============================================================================

function CopyText({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <span className="inline-flex items-center gap-1 group">
      <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-700 max-w-[200px] truncate">
        {text}
      </code>
      <button onClick={handleCopy} className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-gray-200">
        {copied ? <Check size={12} className="text-green-600" /> : <Copy size={12} className="text-gray-400" />}
      </button>
    </span>
  );
}

// ============================================================================
// 步骤详情行
// ============================================================================

function StepRow({ step, index }: { step: any; index: number }) {
  const [expanded, setExpanded] = useState(step.status === 'failed');
  const cfg = getStatus(step.status);

  const meta = step.input_payload?.metadata || {};
  const screenshotCaptureMs = typeof meta.screenshot_capture_ms === 'number' ? meta.screenshot_capture_ms : null;
  const screenshotUploadMs = typeof meta.screenshot_upload_ms === 'number' ? meta.screenshot_upload_ms : null;

  const hasDetail = step.error_message || step.assertion_result?.expected || step.screenshot_object_key ||
    (step.input_payload && Object.keys(step.input_payload).length > 0) ||
    screenshotCaptureMs != null || screenshotUploadMs != null;

  const [openingScreenshot, setOpeningScreenshot] = useState(false);

  const openScreenshot = async () => {
    // Prefer the plain screenshot_url returned by the API
    const directUrl = step.screenshot_url;
    if (directUrl) {
      window.open(directUrl, '_blank', 'noopener,noreferrer');
      return;
    }

    // Fallback: presign if only object_key is available
    if (!step.screenshot_object_key) return;
    setOpeningScreenshot(true);
    try {
      const resp = await testRunsApi.presignOssObject(step.screenshot_object_key, 3600);
      const url = resp.data?.url;
      if (url) window.open(url, '_blank', 'noopener,noreferrer');
    } finally {
      setOpeningScreenshot(false);
    }
  };

  return (
    <div className={`border-l-2 ${step.status === 'failed' ? 'border-red-400' : step.status === 'passed' ? 'border-green-300' : 'border-gray-200'}`}>
      <div
        className={`flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer ${expanded ? 'bg-gray-50' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        {/* 序号 */}
        <span className="text-xs text-gray-400 w-6 text-right font-mono">{index + 1}</span>

        {/* 状态图标 */}
        <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${cfg.bg}`}>
          {step.status === 'passed' ? (
            <CheckCircle size={14} className="text-green-500" />
          ) : step.status === 'failed' ? (
            <XCircle size={14} className="text-red-500" />
          ) : (
            <Clock size={14} className="text-gray-400" />
          )}
        </div>

        {/* 操作名 */}
        <div className="flex-1 min-w-0">
          <span className="font-medium text-gray-800 text-sm">{step.action}</span>
          {step.input_payload?.target && (
            <span className="ml-2 text-xs text-gray-500 font-mono">{step.input_payload.target}</span>
          )}
          {step.input_payload?.value && (
            <span className="ml-1 text-xs text-blue-600">= "{step.input_payload.value}"</span>
          )}
        </div>

        {/* 耗时 */}
        <span className="text-xs text-gray-400 w-16 text-right">{formatDuration(step.duration_ms)}</span>

        {/* 展开箭头 */}
        {hasDetail ? (
          expanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />
        ) : (
          <span className="w-3.5" />
        )}
      </div>

      {/* 展开详情 */}
      {expanded && hasDetail && (
        <div className="px-4 pb-3 ml-[3.75rem] space-y-2">
          {/* 输入参数 */}
          {step.input_payload && Object.keys(step.input_payload).length > 0 && (
            <div className="text-xs">
              <span className="font-medium text-gray-500">输入参数：</span>
              <pre className="mt-1 p-2 bg-gray-100 rounded text-gray-700 overflow-x-auto">
                {JSON.stringify(step.input_payload, null, 2)}
              </pre>
            </div>
          )}

          {/* 断言结果 */}
          {step.assertion_result && (step.assertion_result.expected || step.assertion_result.actual) && (
            <div className="text-xs">
              <span className="font-medium text-gray-500">断言结果：</span>
              <div className="mt-1 p-2 bg-gray-100 rounded space-y-1">
                {step.assertion_result.expected && (
                  <div><span className="text-gray-500">期望：</span><span className="text-gray-800">{String(step.assertion_result.expected)}</span></div>
                )}
                {step.assertion_result.actual && (
                  <div><span className="text-gray-500">实际：</span><span className={step.status === 'failed' ? 'text-red-600 font-medium' : 'text-gray-800'}>{String(step.assertion_result.actual)}</span></div>
                )}
              </div>
            </div>
          )}

          {/* 错误信息 */}
          {step.error_message && (
            <div className="flex items-start gap-2 p-2.5 bg-red-50 border border-red-200 rounded-lg">
              <AlertTriangle size={14} className="text-red-500 flex-shrink-0 mt-0.5" />
              <pre className="text-xs text-red-700 whitespace-pre-wrap break-all flex-1">{step.error_message}</pre>
            </div>
          )}

          {/* 截图耗时 */}
          {(screenshotCaptureMs != null || screenshotUploadMs != null) && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Image size={14} />
              <span>截图耗时：</span>
              <span className="font-mono">
                {screenshotCaptureMs != null ? `采集 ${screenshotCaptureMs}ms` : ''}
                {screenshotCaptureMs != null && screenshotUploadMs != null ? ' · ' : ''}
                {screenshotUploadMs != null ? `上传 ${screenshotUploadMs}ms` : ''}
              </span>
            </div>
          )}

          {/* 截图 */}
          {step.screenshot_object_key && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Image size={14} />
              <span>截图：</span>
              <CopyText text={step.screenshot_object_key} />
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  openScreenshot();
                }}
                disabled={openingScreenshot}
                className="ml-1 px-2 py-0.5 border border-gray-300 rounded hover:bg-gray-50 text-gray-600 disabled:opacity-50"
              >
                {openingScreenshot ? '打开中...' : '查看'}
              </button>
            </div>
          )}

          {/* 日志 */}
          {step.raw_log_object_key && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <FileText size={14} />
              <span>日志：</span>
              <CopyText text={step.raw_log_object_key} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 节点卡片 (可展开/折叠)
// ============================================================================

function NodeCard({ node }: { node: any }) {
  const [expanded, setExpanded] = useState(node.status === 'failed');
  const cfg = getStatus(node.status);
  const steps: any[] = node.steps || [];
  const passedSteps = steps.filter((s: any) => s.status === 'passed').length;
  const failedSteps = steps.filter((s: any) => s.status === 'failed').length;

  return (
    <div className={`bg-white rounded-xl border ${cfg.border} overflow-hidden`}>
      {/* 节点头 */}
      <div
        className={`flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors`}
        onClick={() => setExpanded(!expanded)}
      >
        {/* 状态 */}
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${cfg.bg}`}>
          <cfg.icon size={18} className={`${cfg.color} ${node.status === 'running' ? 'animate-spin' : ''}`} />
        </div>

        {/* 信息 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-semibold text-gray-900 truncate">{node.node_key}</h4>
            <StatusBadge status={node.status} />
          </div>
          <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
            <span>第 {node.attempt} 次尝试</span>
            <span>{formatDuration(node.duration_ms)}</span>
            {steps.length > 0 && (
              <span>
                {steps.length} 步骤
                {passedSteps > 0 && <span className="text-green-600 ml-1">✓{passedSteps}</span>}
                {failedSteps > 0 && <span className="text-red-600 ml-1">✗{failedSteps}</span>}
              </span>
            )}
          </div>
        </div>

        {/* 展开 */}
        {expanded ? <ChevronDown size={18} className="text-gray-400" /> : <ChevronRight size={18} className="text-gray-400" />}
      </div>

      {/* 错误摘要（折叠状态也显示） */}
      {!expanded && node.error_message && (
        <div className="mx-5 mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertTriangle size={14} className="text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-700 line-clamp-2">{node.error_message}</p>
          </div>
        </div>
      )}

      {/* 展开内容 */}
      {expanded && (
        <div className="border-t border-gray-100">
          {/* 节点级错误 */}
          {node.error_message && (
            <div className="mx-5 my-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-start gap-2 mb-1">
                <AlertTriangle size={14} className="text-red-500 flex-shrink-0 mt-0.5" />
                <span className="text-xs font-medium text-red-800">
                  {node.error_code ? `[${node.error_code}] ` : ''}错误详情
                </span>
              </div>
              <pre className="text-xs text-red-700 whitespace-pre-wrap break-all ml-5">{node.error_message}</pre>
            </div>
          )}

          {/* 步骤列表 */}
          {steps.length > 0 ? (
            <div className="divide-y divide-gray-100">
              {steps.map((step: any, i: number) => (
                <StepRow key={step.id || i} step={step} index={i} />
              ))}
            </div>
          ) : (
            <div className="px-5 py-6 text-center text-sm text-gray-400">
              暂无步骤记录
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 环境配置面板
// ============================================================================

function EnvConfigPanel({ envConfig }: { envConfig: Record<string, any> }) {
  if (!envConfig || Object.keys(envConfig).length === 0) return null;

  const isReal = true;
  const items = [
    { icon: Monitor, label: '执行模式', value: isReal ? '真机执行' : '模拟执行', highlight: true },
    envConfig.platform && { icon: Smartphone, label: '平台', value: envConfig.platform },
    envConfig.device_udid && { icon: Smartphone, label: '设备 UDID', value: envConfig.device_udid, mono: true },
    envConfig.appium_server_url && { icon: Server, label: 'Appium 服务', value: envConfig.appium_server_url, mono: true },
    envConfig.appium_session_id && { icon: Hash, label: 'Session ID', value: envConfig.appium_session_id, mono: true },
    envConfig.app_package && { icon: FileText, label: '应用包名', value: envConfig.app_package, mono: true },
    envConfig.app_activity && { icon: FileText, label: 'Activity', value: envConfig.app_activity, mono: true },
  ].filter(Boolean) as { icon: any; label: string; value: string; mono?: boolean; highlight?: boolean }[];

  if (items.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <Server size={16} className="text-gray-500" />
        执行环境
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <item.icon size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <span className="text-xs text-gray-500">{item.label}</span>
              <div className={`text-sm ${item.highlight ? 'font-medium text-blue-700' : 'text-gray-800'} ${item.mono ? 'font-mono text-xs break-all' : ''}`}>
                {item.value}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// 主页面
// ============================================================================

export default function RunDetailPage() {
  const { projectId, runId } = useParams<{ projectId: string; runId: string }>();

  const { data: detailData, isLoading, error, refetch } = useQuery({
    queryKey: ['runDetail', runId],
    queryFn: () => testRunsApi.getDetail(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.data?.status;
      return status === 'running' || status === 'queued' ? 3000 : false;
    },
  });

  const run = detailData?.data;

  // Loading
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin text-blue-500" />
        <span className="ml-3 text-gray-500">加载执行详情...</span>
      </div>
    );
  }

  // Error
  if (error || !run) {
    return (
      <div className="text-center py-16 space-y-4">
        <XCircle size={48} className="mx-auto text-red-400" />
        <p className="text-gray-500">{error ? '加载失败，请重试' : '未找到执行记录'}</p>
        <Link to={`/projects/${projectId}/runs`} className="text-blue-600 hover:underline text-sm">
          ← 返回列表
        </Link>
      </div>
    );
  }

  const nodes: any[] = run.nodes || [];
  const summary = run.summary || {};
  const envConfig = run.env_config || {};
  const totalNodes = summary.total_nodes || nodes.length;
  const passedNodes = summary.passed_nodes || 0;
  const failedNodes = summary.failed_nodes || 0;
  const skippedNodes = summary.skipped_nodes || 0;
  const totalSteps = summary.total_steps || 0;
  const passedSteps = summary.passed_steps || 0;
  const failedSteps = summary.failed_steps || 0;
  const errorMessage = summary.error;

  return (
    <div className="space-y-6">
      {/* ============ 头部 ============ */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            to={`/projects/${projectId}/runs`}
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ChevronLeft size={16} />
            <span>返回执行列表</span>
          </Link>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-gray-900">#{run.run_no}</h2>
            <StatusBadge status={run.status} size="md" />
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <Calendar size={14} />
              {formatTime(run.started_at || run.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <Timer size={14} />
              {formatTimeDiff(run.started_at, run.finished_at)}
            </span>
            {envConfig.use_real_runner && (
              <span className="flex items-center gap-1 text-blue-600">
                <Smartphone size={14} />
                真机执行
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw size={14} />
          刷新
        </button>
      </div>

      {/* ============ 全局错误 ============ */}
      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-800 mb-1">执行错误</h4>
              <pre className="text-sm text-red-700 whitespace-pre-wrap break-all">{errorMessage}</pre>
            </div>
          </div>
        </div>
      )}

      {/* ============ 统计卡片 ============ */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 mb-1">测试节点</p>
          <p className="text-2xl font-bold text-gray-900">{totalNodes}</p>
        </div>
        <div className="bg-white rounded-xl border border-green-200 p-4">
          <p className="text-xs text-green-600 mb-1 flex items-center gap-1"><CheckCircle size={12} />通过节点</p>
          <p className="text-2xl font-bold text-green-700">{passedNodes}</p>
        </div>
        <div className="bg-white rounded-xl border border-red-200 p-4">
          <p className="text-xs text-red-600 mb-1 flex items-center gap-1"><XCircle size={12} />失败节点</p>
          <p className="text-2xl font-bold text-red-700">{failedNodes}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 mb-1">总步骤</p>
          <p className="text-2xl font-bold text-gray-900">{totalSteps}</p>
          {totalSteps > 0 && (
            <div className="flex items-center gap-2 mt-1 text-xs">
              <span className="text-green-600">✓{passedSteps}</span>
              <span className="text-red-600">✗{failedSteps}</span>
            </div>
          )}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 mb-1 flex items-center gap-1"><Ban size={12} />跳过</p>
          <p className="text-2xl font-bold text-gray-500">{skippedNodes}</p>
        </div>
      </div>

      {/* ============ 通过率进度条 ============ */}
      {totalNodes > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">节点通过率</span>
            <span className="text-sm font-bold text-gray-900">
              {Math.round((passedNodes / totalNodes) * 100)}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
            <div className="h-full flex">
              <div className="bg-green-500 transition-all" style={{ width: `${(passedNodes / totalNodes) * 100}%` }} />
              <div className="bg-red-500 transition-all" style={{ width: `${(failedNodes / totalNodes) * 100}%` }} />
              <div className="bg-gray-400 transition-all" style={{ width: `${(skippedNodes / totalNodes) * 100}%` }} />
            </div>
          </div>
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-green-500 rounded-full" />通过</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500 rounded-full" />失败</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-gray-400 rounded-full" />跳过</span>
          </div>
        </div>
      )}

      {/* ============ 环境配置 ============ */}
      <EnvConfigPanel envConfig={envConfig} />

      {/* ============ 节点详情 ============ */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <FileText size={16} className="text-gray-500" />
            执行节点详情
          </h3>
          {nodes.length > 0 && (
            <span className="text-xs text-gray-400">{nodes.length} 个节点</span>
          )}
        </div>

        {nodes.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 text-center py-12">
            {run.status === 'queued' ? (
              <>
                <Clock size={40} className="mx-auto text-gray-300 mb-3" />
                <p className="text-gray-500">等待执行...</p>
                <p className="text-xs text-gray-400 mt-1">任务已进入队列，Celery Worker 将很快开始执行</p>
              </>
            ) : run.status === 'running' ? (
              <>
                <Loader2 size={40} className="mx-auto text-blue-400 mb-3 animate-spin" />
                <p className="text-gray-500">正在执行中...</p>
                <p className="text-xs text-gray-400 mt-1">页面将自动刷新</p>
              </>
            ) : (
              <>
                <FileText size={40} className="mx-auto text-gray-300 mb-3" />
                <p className="text-gray-500">暂无执行节点记录</p>
                {errorMessage && <p className="text-xs text-gray-400 mt-1">执行可能在初始化阶段发生错误</p>}
              </>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {nodes.map((node: any) => (
              <NodeCard key={node.id} node={node} />
            ))}
          </div>
        )}
      </div>

      {/* ============ AI 分析区域（预留） ============ */}
      {run.status && ['passed', 'failed', 'partial'].includes(run.status) && (
        <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl border border-purple-200 p-5">
          <div className="flex items-center gap-2 mb-2">
            <Brain size={18} className="text-purple-600" />
            <h3 className="font-semibold text-purple-900">AI 智能分析</h3>
          </div>
          <p className="text-sm text-purple-700">
            执行已完成，可触发 AI 分析自动生成问题诊断报告和优化建议。
          </p>
        </div>
      )}
    </div>
  );
}
