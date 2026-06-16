import React, { useState, useEffect } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Clock, CheckCircle, XCircle, Loader2, X, GitBranch, Smartphone, Package, RefreshCw } from 'lucide-react';
import { testRunsApi, testFlowsApi, devicesApi, packagesApi } from '../services/api';

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
  const [sessionMode, setSessionMode] = useState<'existing' | 'new'>('existing');
  const [error, setError] = useState('');

  // New session states
  const [newSessionDevice, setNewSessionDevice] = useState('');
  const [newSessionPackage, setNewSessionPackage] = useState('');
  const [newSessionServerId, setNewSessionServerId] = useState('local');
  const [newSessionServerUrl, setNewSessionServerUrl] = useState('http://127.0.0.1:4723');
  const [newSessionNoReset, setNewSessionNoReset] = useState(false);
  const [newSessionFullReset, setNewSessionFullReset] = useState(true);
  const [newSessionAutoLaunch, setNewSessionAutoLaunch] = useState(true);
  const [isCreatingAndRunning, setIsCreatingAndRunning] = useState(false);

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
    enabled: isOpen && sessionMode === 'existing',
    refetchInterval: 10000,
  });

  // 获取设备列表（新建 session 用）- 使用 ADB 实时扫描，与设备管理页面一致
  const { data: devicesData } = useQuery({
    queryKey: ['devicesForSession'],
    queryFn: () => devicesApi.scanLocalDevices(),
    enabled: isOpen && sessionMode === 'new',
  });

  // 获取应用包列表（新建 session 用）
  const { data: packagesData } = useQuery({
    queryKey: ['packagesForSession'],
    queryFn: () => packagesApi.list(),
    enabled: isOpen && sessionMode === 'new',
  });

  // 获取远程 Appium 服务器列表
  const { data: remoteServersData } = useQuery({
    queryKey: ['remoteServersForSession'],
    queryFn: () => devicesApi.listRemoteServers(),
    enabled: isOpen && sessionMode === 'new',
  });

  const flows = flowsData?.data?.items || [];
  const allSessions = sessionsData?.data?.sessions || [];
  const sessions = allSessions.filter(
    (s: any) => s.status === 'active' || s.status === 'expired' || s.status === 'disconnected'
  );

  // scanLocalDevices 返回 { devices: [...], count, message }
  const allDevices = devicesData?.data?.devices || [];
  // 扫描结果状态: connected / disconnected / busy
  const availableDevices = allDevices.filter((d: any) => d.status === 'connected');
  const allPackages = packagesData?.data?.items || [];
  const remoteServers = remoteServersData?.data || [];

  // 根据选中设备过滤应用包
  const selectedDeviceInfo = availableDevices.find((d: any) => d.udid === newSessionDevice);
  const filteredPackages = selectedDeviceInfo
    ? allPackages.filter((p: any) => p.platform === selectedDeviceInfo.platform)
    : allPackages;

  // Auto-select device if only one available
  useEffect(() => {
    if (isOpen && sessionMode === 'new' && availableDevices.length === 1 && !newSessionDevice) {
      setNewSessionDevice(availableDevices[0].udid);
    }
  }, [isOpen, sessionMode, availableDevices, newSessionDevice]);

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
      setIsCreatingAndRunning(false);
    },
  });

  // 创建新 Session 的 mutation
  const createSessionMutation = useMutation({
    mutationFn: (data: {
      device_udid: string;
      package_id: string;
      server_url?: string;
      no_reset?: boolean;
      full_reset?: boolean;
      auto_launch?: boolean;
    }) => devicesApi.createSessionFromPackage(data),
    onSuccess: (response: any) => {
      // Session 创建成功，获取 session_id 并触发执行
      const newSessionId = response.data?.session_id;
      if (newSessionId) {
        queryClient.invalidateQueries({ queryKey: ['activeSessions'] });
        // 直接用新 session_id 触发 flow run
        triggerMutation.mutate({
          flowId: selectedFlowId,
          sessionId: newSessionId,
        });
      } else {
        setError('Session 创建成功但未返回 session_id');
        setIsCreatingAndRunning(false);
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建 Session 失败');
      setIsCreatingAndRunning(false);
    },
  });

  const resetForm = () => {
    setSelectedFlowId('');
    setSelectedSessionId('');
    setSessionMode('existing');
    setNewSessionDevice('');
    setNewSessionPackage('');
    setNewSessionServerId('local');
    setNewSessionServerUrl('http://127.0.0.1:4723');
    setNewSessionNoReset(false);
    setNewSessionFullReset(true);
    setNewSessionAutoLaunch(true);
    setError('');
    setIsCreatingAndRunning(false);
  };

  const buildServerUrl = (): string | undefined => {
    if (newSessionServerId === 'local') {
      return newSessionServerUrl || 'http://127.0.0.1:4723';
    }
    const picked = remoteServers.find((s: any) => s.id === newSessionServerId);
    if (!picked) return undefined;
    const path = (picked.path || '').trim();
    const normalizedPath = path ? (path.startsWith('/') ? path : `/${path}`) : '';
    return `http://${picked.host}:${picked.port}${normalizedPath}`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFlowId) {
      setError('请选择测试流程');
      return;
    }

    if (sessionMode === 'existing') {
      if (!selectedSessionId) {
        setError('请选择关联设备会话');
        return;
      }
      triggerMutation.mutate({
        flowId: selectedFlowId,
        sessionId: selectedSessionId,
      });
    } else {
      // 新建 Session 模式
      if (!newSessionDevice) {
        setError('请选择设备');
        return;
      }
      if (!newSessionPackage) {
        setError('请选择应用包');
        return;
      }
      const url = buildServerUrl();
      if (!url) {
        setError('请选择 Appium Server');
        return;
      }
      setIsCreatingAndRunning(true);
      setError('');
      // 先创建 session，成功后自动触发执行
      createSessionMutation.mutate({
        device_udid: newSessionDevice,
        package_id: newSessionPackage,
        server_url: url,
        no_reset: newSessionNoReset,
        full_reset: newSessionFullReset,
        auto_launch: newSessionAutoLaunch,
      });
    }
  };

  if (!isOpen) return null;

  const isSubmitting = triggerMutation.isPending || isCreatingAndRunning;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white">
          <h2 className="text-lg font-semibold text-gray-900">触发测试执行</h2>
          <button onClick={() => { onClose(); resetForm(); }} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">{error}</div>
          )}

          {/* 选择测试流程 */}
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

          {/* Session 模式切换 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <span className="flex items-center gap-1.5">
                <Smartphone size={14} />
                关联设备会话 <span className="text-red-500">*</span>
              </span>
            </label>
            <div className="flex gap-2 mb-3">
              <button
                type="button"
                onClick={() => { setSessionMode('existing'); setError(''); }}
                className={`flex-1 px-3 py-2 text-sm font-medium rounded-lg border transition-colors ${
                  sessionMode === 'existing'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-600 hover:border-gray-400'
                }`}
              >
                选择已有会话
              </button>
              <button
                type="button"
                onClick={() => { setSessionMode('new'); setError(''); }}
                className={`flex-1 px-3 py-2 text-sm font-medium rounded-lg border transition-colors ${
                  sessionMode === 'new'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-600 hover:border-gray-400'
                }`}
              >
                <span className="flex items-center justify-center gap-1">
                  <RefreshCw size={13} />
                  新建并重置
                </span>
              </button>
            </div>
          </div>

          {/* 已有 Session 选择 */}
          {sessionMode === 'existing' && (
            <div>
              {sessions.length === 0 ? (
                <div className="text-sm text-gray-500 p-3 bg-gray-50 rounded-lg text-center">
                  暂无活跃会话，请先在「设备管理 → 会话」中创建，或切换到「新建并重置」
                </div>
              ) : (
                <select
                  value={selectedSessionId}
                  onChange={(e) => setSelectedSessionId(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                >
                  <option value="">-- 请选择会话 --</option>
                  {sessions.map((session: any) => {
                    const isExpired = session.status === 'expired' || session.status === 'disconnected';
                    const statusLabel = isExpired ? ' ⚠️ 已过期(将自动恢复)' : ' ✅';
                    return (
                      <option key={session.session_id} value={session.session_id}>
                        {session.app_name || session.package_name || '未知应用'} · {session.device_name || session.device_udid} ({session.platform}){statusLabel}
                      </option>
                    );
                  })}
                </select>
              )}
              {selectedSessionId && (
                <p className="mt-1.5 text-xs text-green-600 flex items-center gap-1">
                  <CheckCircle size={12} />
                  将使用真机执行测试
                </p>
              )}
            </div>
          )}

          {/* 新建 Session 表单 */}
          {sessionMode === 'new' && (
            <div className="space-y-4 bg-orange-50 border border-orange-200 rounded-lg p-4">
              <p className="text-xs text-orange-600 flex items-center gap-1">
                <RefreshCw size={12} />
                将创建新的 Appium Session 并重置应用数据（fullReset），然后执行测试
              </p>

              {/* 设备选择 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Smartphone size={14} className="inline mr-1" />
                  选择设备 <span className="text-red-500">*</span>
                </label>
                {availableDevices.length === 0 ? (
                  <div className="text-sm text-yellow-600 bg-yellow-50 px-3 py-2 rounded-lg">
                    {allDevices.length === 0
                      ? '没有发现已连接的设备，请确认设备已通过 USB 连接或 ADB WiFi 已连接'
                      : `发现 ${allDevices.length} 个设备均忙碌，请释放其他会话后重试`}
                  </div>
                ) : (
                  <select
                    value={newSessionDevice}
                    onChange={(e) => { setNewSessionDevice(e.target.value); setNewSessionPackage(''); }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                  >
                    <option value="">-- 选择设备 --</option>
                    {availableDevices.map((d: any) => (
                      <option key={d.udid} value={d.udid}>
                        {d.name || d.model || d.udid} ({d.platform}) - {d.udid}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* 应用包选择 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Package size={14} className="inline mr-1" />
                  选择应用包 <span className="text-red-500">*</span>
                </label>
                {filteredPackages.length === 0 ? (
                  <div className="text-sm text-yellow-600 bg-yellow-50 px-3 py-2 rounded-lg">
                    {newSessionDevice ? '没有匹配该设备平台的应用包' : '请先选择设备'}
                  </div>
                ) : (
                  <select
                    value={newSessionPackage}
                    onChange={(e) => setNewSessionPackage(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                  >
                    <option value="">-- 选择应用包 --</option>
                    {filteredPackages.map((pkg: any) => (
                      <option key={pkg.id} value={pkg.id}>
                        {pkg.app_name || pkg.package_name} v{pkg.version_name} ({pkg.platform})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Appium Server 选择 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Appium Server
                </label>
                <select
                  value={newSessionServerId}
                  onChange={(e) => setNewSessionServerId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm mb-2"
                >
                  <option value="local">本地（http://127.0.0.1:4723）</option>
                  {remoteServers.map((s: any) => (
                    <option key={s.id} value={s.id}>
                      {s.name}（{s.host}:{s.port}{s.path ? s.path : ''}）
                    </option>
                  ))}
                </select>
                {newSessionServerId === 'local' && (
                  <input
                    type="text"
                    value={newSessionServerUrl}
                    onChange={(e) => setNewSessionServerUrl(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                    placeholder="http://127.0.0.1:4723"
                  />
                )}
              </div>

              {/* Session 选项 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Session 选项</label>
                <div className="space-y-1.5">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newSessionNoReset}
                      onChange={(e) => {
                        setNewSessionNoReset(e.target.checked);
                        if (e.target.checked) setNewSessionFullReset(false);
                      }}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">noReset - 保留应用数据（不重置）</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newSessionFullReset}
                      onChange={(e) => {
                        setNewSessionFullReset(e.target.checked);
                        if (e.target.checked) setNewSessionNoReset(false);
                      }}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">fullReset - 完全重置应用（卸载重装）</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newSessionAutoLaunch}
                      onChange={(e) => setNewSessionAutoLaunch(e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">autoLaunch - 自动启动应用</span>
                  </label>
                </div>
              </div>
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
              disabled={isSubmitting || flows.length === 0}
              className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  {isCreatingAndRunning ? '创建会话并启动...' : '启动中...'}
                </>
              ) : (
                <>
                  <Play size={16} />
                  {sessionMode === 'new' ? '新建会话并执行' : '开始执行'}
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

  const pageSize = 20;
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['testRuns', projectId, page, pageSize],
    queryFn: () => testRunsApi.list(projectId!, page, pageSize) as any,
    enabled: !!projectId,
    refetchInterval: 5000,
    refetchOnMount: 'always',
    placeholderData: (prev) => prev,
  });

  const runs: any[] = (data as any)?.data?.items || [];
  const total: number = (data as any)?.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

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

          {/* Pagination */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 px-6 py-4 border-t bg-gray-50">
            <div className="text-xs text-gray-500">
              共 {total} 条 · 第 {page} / {totalPages} 页
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-white disabled:opacity-50"
              >
                上一页
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-white disabled:opacity-50"
              >
                下一页
              </button>
            </div>
          </div>
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
