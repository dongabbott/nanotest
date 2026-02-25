import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Wifi,
  RefreshCw,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  Loader2,
  Server,
  Usb,
  Globe,
  Zap,
  Copy,
  Check,
  X,
  Apple,
  Bot,
  Play,
} from 'lucide-react';
import { devicesApi, packagesApi } from '../services/api';
import {
  LocalDeviceList,
  SessionList,
  SessionActionResultModal,
  CreateSessionModal,
} from '../components/devices';
import type { LocalDevice, RemoteServer, SessionInfo } from '../components/devices/types';

// ============================================================================
// 辅助组件
// ============================================================================

function DeviceCard({ 
  device, 
  onInstall,
}: { 
  device: LocalDevice;
  onInstall: (device: LocalDevice) => void;
}) {
  const [copied, setCopied] = useState(false);
  
  const copyUdid = async () => {
    await navigator.clipboard.writeText(device.udid);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusColors = {
    connected: 'bg-green-100 text-green-700 border-green-200',
    disconnected: 'bg-gray-100 text-gray-500 border-gray-200',
    busy: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  };

  const statusLabels = {
    connected: '已连接',
    disconnected: '已断开',
    busy: '使用中',
  };

  const PlatformIcon = device.platform === 'ios' ? Apple : Bot;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
          device.platform === 'ios' ? 'bg-gray-100' : 'bg-green-100'
        }`}>
          <PlatformIcon size={24} className={device.platform === 'ios' ? 'text-gray-700' : 'text-green-700'} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{device.name}</h3>
            <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${statusColors[device.status]}`}>
              {statusLabels[device.status]}
            </span>
          </div>
          
          <div className="mt-1 space-y-1">
            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                {device.connection === 'usb' ? <Usb size={14} /> : <Wifi size={14} />}
                {device.connection === 'usb' ? 'USB' : 'WiFi'}
              </span>
              <span>{device.platform === 'ios' ? 'iOS' : 'Android'} {device.version}</span>
              {device.model && <span>{device.model}</span>}
            </div>
            
            <div className="flex items-center gap-2">
              <code className="text-xs bg-gray-100 px-2 py-0.5 rounded font-mono text-gray-600 truncate max-w-[200px]">
                {device.udid}
              </code>
              <button
                onClick={copyUdid}
                className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600"
                title="复制 UDID"
              >
                {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
              </button>
              <button
                onClick={() => onInstall(device)}
                disabled={device.status !== 'connected'}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                title={device.status === 'connected' ? '安装应用' : '设备未连接'}
              >
                <Plus size={14} />
                安装
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function InstallAppModal({
  isOpen,
  onClose,
  device,
}: {
  isOpen: boolean;
  onClose: () => void;
  device: LocalDevice | null;
}) {
  const [selectedPackageId, setSelectedPackageId] = useState<string>('');
  const [resultText, setResultText] = useState<string>('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['installPackages', device?.platform],
    queryFn: async () => packagesApi.list({ platform: device?.platform, page: 1, page_size: 100 }),
    enabled: isOpen && !!device,
  });

  const packages = data?.data?.items || [];

  useEffect(() => {
    if (!isOpen) return;
    setResultText('');
    if (!selectedPackageId && packages.length > 0) {
      setSelectedPackageId(packages[0].id);
    }
  }, [isOpen, packages, selectedPackageId]);

  const installMutation = useMutation({
    mutationFn: async () => {
      if (!device) throw new Error('设备不存在');
      if (!selectedPackageId) throw new Error('请选择安装包');
      return devicesApi.installPackage({
        udid: device.udid,
        platform: device.platform,
        package_id: selectedPackageId,
      });
    },
    onSuccess: (resp) => {
      const d = resp.data;
      const txt = [
        `结果: ${d.success ? '成功' : '失败'}`,
        d.message ? `信息: ${d.message}` : '',
        d.stdout ? `STDOUT:\n${d.stdout}` : '',
        d.stderr ? `STDERR:\n${d.stderr}` : '',
      ].filter(Boolean).join('\n\n');
      setResultText(txt);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || err?.message || '安装失败';
      setResultText(String(msg));
    },
  });

  if (!isOpen || !device) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-xl">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">安装应用</h2>
            <div className="text-xs text-gray-500 mt-1">
              {device.platform === 'ios' ? 'iOS' : 'Android'} · {device.udid}
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex items-center gap-3 min-w-0">
            <label className="text-sm font-medium text-gray-700 w-20">安装包</label>
            <div className="flex-1 min-w-0">
              <select
                value={selectedPackageId}
                onChange={(e) => setSelectedPackageId(e.target.value)}
                className="w-full min-w-0 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 overflow-hidden text-ellipsis whitespace-nowrap"
                disabled={isLoading || installMutation.isPending}
              >
                {packages.length === 0 ? (
                  <option value="">暂无可用安装包</option>
                ) : (
                  packages.map((p: any) => (
                    <option key={p.id} value={p.id}>
                      {(p.app_name || p.package_name) + ' · ' + p.version_name}
                    </option>
                  ))
                )}
              </select>
            </div>
            <button
              onClick={() => refetch()}
              disabled={isLoading || installMutation.isPending}
              className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              title="刷新安装包列表"
            >
              <RefreshCw size={16} />
            </button>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              disabled={installMutation.isPending}
            >
              取消
            </button>
            <button
              onClick={() => installMutation.mutate()}
              disabled={!selectedPackageId || installMutation.isPending || packages.length === 0}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
            >
              {installMutation.isPending ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
              安装
            </button>
          </div>

          {resultText && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap">{resultText}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RemoteServerCard({
  server,
  onTest,
  onRefresh,
  onDelete,
  isLoading,
}: {
  server: RemoteServer;
  onTest: () => void;
  onRefresh: () => void;
  onDelete: () => void;
  isLoading?: boolean;
}) {
  const statusColors = {
    online: 'bg-green-100 text-green-700',
    offline: 'bg-red-100 text-red-700',
    unknown: 'bg-gray-100 text-gray-500',
  };

  const statusLabels = {
    online: '在线',
    offline: '离线',
    unknown: '未知',
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
          server.status === 'online' ? 'bg-green-100' : 'bg-gray-100'
        }`}>
          <Server size={24} className={server.status === 'online' ? 'text-green-700' : 'text-gray-500'} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{server.name}</h3>
            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColors[server.status]}`}>
              {statusLabels[server.status]}
            </span>
          </div>
          
          <div className="mt-1 text-sm text-gray-500">
            <span className="font-mono">{server.host}:{server.port}</span>
            {server.path && <span className="text-gray-400">{server.path}</span>}
          </div>
          
          {server.device_count !== undefined && server.status === 'online' && (
            <div className="mt-1 text-sm text-gray-500">{server.device_count} 台设备可用</div>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onTest}
            disabled={isLoading}
            className="p-2 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-blue-600"
            title="测试连接"
          >
            {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Zap size={18} />}
          </button>
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="p-2 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-green-600"
            title="刷新设备"
          >
            <RefreshCw size={18} />
          </button>
          <button
            onClick={onDelete}
            className="p-2 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-red-600"
            title="删除"
          >
            <Trash2 size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

function AddRemoteServerModal({
  isOpen,
  onClose,
  onAdd,
}: {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (data: any) => void;
}) {
  const [formData, setFormData] = useState({
    name: '',
    host: '',
    port: 4723,
    path: '',
  });
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      await devicesApi.testRemoteConnection({
        host: formData.host,
        port: formData.port,
        path: formData.path,
      });
      setTestResult({ success: true, message: '连接成功' });
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.response?.data?.detail || '连接失败，请检查地址和端口',
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAdd(formData);
  };

  const resetForm = () => {
    setFormData({ name: '', host: '', port: 4723, path: '' });
    setTestResult(null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">添加远程 Appium 服务器</h2>
          <button onClick={() => { onClose(); resetForm(); }} className="p-2 hover:bg-gray-100 rounded-lg text-gray-400">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">服务器名称</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="例如：测试服务器 A"
              required
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">主机地址</label>
              <input
                type="text"
                value={formData.host}
                onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="192.168.1.100"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">端口</label>
              <input
                type="number"
                value={formData.port}
                onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">路径 (可选)</label>
            <input
              type="text"
              value={formData.path}
              onChange={(e) => setFormData({ ...formData, path: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="/wd/hub"
            />
            <p className="text-xs text-gray-500 mt-1">Appium 2.x/3.x 通常留空</p>
          </div>

          {testResult && (
            <div className={`p-4 rounded-lg ${testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
              <div className="flex items-center gap-2">
                {testResult.success ? (
                  <CheckCircle size={18} className="text-green-600" />
                ) : (
                  <XCircle size={18} className="text-red-600" />
                )}
                <span className={`font-medium ${testResult.success ? 'text-green-700' : 'text-red-700'}`}>
                  {testResult.message}
                </span>
              </div>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={handleTest}
              disabled={!formData.host || !formData.port || isTesting}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isTesting ? <Loader2 size={18} className="animate-spin" /> : <Zap size={18} />}
              测试连接
            </button>
            <button
              type="submit"
              disabled={!formData.name || !formData.host}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              添加服务器
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// 主页面组件
// ============================================================================

export default function DevicesPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'local' | 'servers' | 'sessions'>('local');
  const [showAddServerModal, setShowAddServerModal] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [localDevices, setLocalDevices] = useState<LocalDevice[]>([]);
  const [installDevice, setInstallDevice] = useState<LocalDevice | null>(null);
  const [isCreateSessionModalOpen, setIsCreateSessionModalOpen] = useState(false);
  const [sessionActionResult, setSessionActionResult] = useState<{
    action: string;
    result: any;
  } | null>(null);

  // 数据查询
  const { data: remoteServersData, isLoading: isLoadingServers } = useQuery({
    queryKey: ['remoteServers'],
    queryFn: () => devicesApi.listRemoteServers(),
  });

  const { data: sessionsData, isLoading: isLoadingSessions, refetch: refetchSessions } = useQuery({
    queryKey: ['activeSessions'],
    queryFn: () => devicesApi.listSessions(),
    refetchInterval: 10000,
  });

  // Mutations
  const addServerMutation = useMutation({
    mutationFn: devicesApi.addRemoteServer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['remoteServers'] });
      setShowAddServerModal(false);
    },
  });

  const deleteServerMutation = useMutation({
    mutationFn: devicesApi.deleteRemoteServer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['remoteServers'] });
    },
  });

  const testConnectionMutation = useMutation({
    mutationFn: ({ host, port, path }: { host: string; port: number; path: string }) =>
      devicesApi.testConnection(host, port, path),
  });

  const refreshServerMutation = useMutation({
    mutationFn: (serverId: string) => devicesApi.refreshRemoteDevices(serverId),
  });

  // 事件处理
  const handleScanLocal = async () => {
    setIsScanning(true);
    try {
      const response = await devicesApi.scanLocalDevices();
      setLocalDevices(response.data?.devices || []);
    } finally {
      setIsScanning(false);
    }
  };

  const handleSessionActionResult = (action: string, result: any) => {
    setSessionActionResult({ action, result });
  };

  // 初始化加载
  useEffect(() => {
    handleScanLocal();
  }, []);

  // Tab 切换时刷新数据
  useEffect(() => {
    if (activeTab === 'local') {
      handleScanLocal();
    } else if (activeTab === 'servers') {
      queryClient.invalidateQueries({ queryKey: ['remoteServers'] });
    } else if (activeTab === 'sessions') {
      queryClient.invalidateQueries({ queryKey: ['activeSessions'] });
    }
  }, [activeTab, queryClient]);

  // 数据处理
  const remoteServers: RemoteServer[] = (remoteServersData?.data || []).map((s: any) => ({
    ...s,
    status: s.status || 'unknown',
  }));
  const sessions: SessionInfo[] = sessionsData?.data?.sessions || [];
  const connectedDevices = localDevices.filter(d => d.status === 'connected');

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 头部 */}
      <div className="bg-white border-b border-gray-200 sticky top-16 z-40">
        <div className="px-8 py-4">
          <h1 className="text-xl font-bold text-gray-900">设备管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理设备、远程 Appium 服务器和会话</p>
        </div>

        {/* Tab 导航 */}
        <div className="px-8">
          <div className="flex gap-6">
            <button
              onClick={() => setActiveTab('local')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'local' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <Usb size={18} />
                设备管理
                {connectedDevices.length > 0 && (
                  <span className="px-2 py-0.5 text-xs bg-green-100 text-green-600 rounded-full">{connectedDevices.length}</span>
                )}
              </div>
            </button>
            <button
              onClick={() => setActiveTab('servers')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'servers' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <Globe size={18} />
                Appium 服务
                {remoteServers.length > 0 && (
                  <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-600 rounded-full">{remoteServers.length}</span>
                )}
              </div>
            </button>
            <button
              onClick={() => setActiveTab('sessions')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'sessions' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <Play size={18} />
                会话
                <span className={`px-2 py-0.5 text-xs rounded-full ${
                  sessions.length > 0 ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
                }`}>{sessions.length}</span>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="p-8">
        {/* 本地设备 Tab */}
        {activeTab === 'local' && (
          <div className="space-y-6">
            {/* 本地设备列表 */}
            <LocalDeviceList
              devices={localDevices}
              isLoading={isScanning}
              onRefresh={handleScanLocal}
            />

            {/* 连接的设备卡片 */}
            {connectedDevices.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  已连接设备详情
                </h3>
                <div className="grid gap-3">
                  {connectedDevices.map((device) => (
                    <DeviceCard key={device.id} device={device} onInstall={(d) => setInstallDevice(d)} />
                  ))}
                </div>
              </div>
            )}

            {/* 帮助信息 */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-2">如何连接设备？</h4>
              <div className="grid md:grid-cols-2 gap-4 text-sm text-blue-800">
                <div>
                  <div className="font-medium flex items-center gap-2 mb-1">
                    <Bot size={16} />
                    Android 设备
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-blue-700">
                    <li>启用开发者选项和 USB 调试</li>
                    <li>使用 USB 连接设备到电脑</li>
                    <li>运行 <code className="bg-blue-100 px-1 rounded">adb devices</code> 验证</li>
                  </ul>
                </div>
                <div>
                  <div className="font-medium flex items-center gap-2 mb-1">
                    <Apple size={16} />
                    iOS 设备
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-blue-700">
                    <li>安装 Xcode 和 Command Line Tools</li>
                    <li>使用 USB 连接设备到 Mac</li>
                    <li>在设备上点击"信任此电脑"</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 远程服务器 Tab */}
        {activeTab === 'servers' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-500">
                {isLoadingServers ? '加载中...' : `共 ${remoteServers.length} 台远程服务器`}
              </div>
              <button
                onClick={() => setShowAddServerModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                <Plus size={18} />
                添加服务器
              </button>
            </div>

            {remoteServers.length > 0 ? (
              <div className="grid gap-3">
                {remoteServers.map((server) => (
                  <RemoteServerCard
                    key={server.id}
                    server={server}
                    onTest={() => testConnectionMutation.mutate({
                      host: server.host,
                      port: server.port,
                      path: server.path || '',
                    })}
                    onRefresh={() => refreshServerMutation.mutate(server.id)}
                    onDelete={() => {
                      if (confirm(`确定要删除服务器 "${server.name}" 吗？`)) {
                        deleteServerMutation.mutate(server.id);
                      }
                    }}
                    isLoading={testConnectionMutation.isPending || refreshServerMutation.isPending}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-16 bg-white rounded-xl border-2 border-dashed border-gray-300">
                <Server size={48} className="mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">未配置远程服务器</h3>
                <p className="text-gray-500 mb-4">添加远程 Appium 服务器以连接云端或其他机器上的设备</p>
                <button
                  onClick={() => setShowAddServerModal(true)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  添加服务器
                </button>
              </div>
            )}

            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <h4 className="font-medium text-purple-900 mb-2">关于远程 Appium 服务器</h4>
              <div className="text-sm text-purple-800 space-y-2">
                <p>远程服务器允许您连接到其他机器上运行的 Appium 服务，适用于：</p>
                <ul className="list-disc list-inside space-y-1 text-purple-700">
                  <li>连接到云设备平台 (如 BrowserStack、Sauce Labs)</li>
                  <li>使用局域网内其他机器上连接的设备</li>
                  <li>搭建分布式测试环境</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* 会话 Tab */}
        {activeTab === 'sessions' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-500">共 {sessions.length} 个活跃会话</div>
              <button
                onClick={() => setIsCreateSessionModalOpen(true)}
                disabled={connectedDevices.length === 0}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                title={connectedDevices.length === 0 ? '没有已连接的设备' : '创建 Appium Session'}
              >
                <Plus size={18} />
                创建 Session
              </button>
            </div>
            <SessionList
              sessions={sessions}
              isLoading={isLoadingSessions}
              onRefresh={() => refetchSessions()}
              onActionResult={handleSessionActionResult}
            />
          </div>
        )}
      </div>

      {/* Modals */}
      <AddRemoteServerModal
        isOpen={showAddServerModal}
        onClose={() => setShowAddServerModal(false)}
        onAdd={(data) => addServerMutation.mutate(data)}
      />

      <InstallAppModal isOpen={!!installDevice} onClose={() => setInstallDevice(null)} device={installDevice} />

      <CreateSessionModal
        isOpen={isCreateSessionModalOpen}
        onClose={() => setIsCreateSessionModalOpen(false)}
        devices={localDevices}
      />

      <SessionActionResultModal
        isOpen={!!sessionActionResult}
        onClose={() => setSessionActionResult(null)}
        action={sessionActionResult?.action || ''}
        result={sessionActionResult?.result}
      />
    </div>
  );
}
