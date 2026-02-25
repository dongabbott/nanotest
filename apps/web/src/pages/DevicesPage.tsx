import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Smartphone,
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
  AlertTriangle,
  Zap,
  ExternalLink,
  Copy,
  Check,
  X,
  Apple,
  Bot,
  Monitor,
  Edit,
  MoreHorizontal,
} from 'lucide-react';
import { devicesApi, packagesApi } from '../services/api';

interface LocalDevice {
  id: string;
  udid: string;
  name: string;
  platform: 'android' | 'ios';
  version: string;
  status: 'connected' | 'disconnected' | 'busy';
  connection: 'usb' | 'wifi';
  model?: string;
  manufacturer?: string;
}

interface RemoteServer {
  id: string;
  name: string;
  host: string;
  port: number;
  path?: string;
  status: 'online' | 'offline' | 'unknown';
  last_connected?: string;
  device_count?: number;
}

interface ConnectionTestResult {
  success: boolean;
  message: string;
  serverInfo?: {
    version: string;
    buildTime: string;
  };
  devices?: LocalDevice[];
}

interface AppPackageOption {
  id: string;
  filename: string;
  platform: 'android' | 'ios';
  package_name: string;
  app_name?: string;
  version_name: string;
  version_code?: number;
  build_number?: string;
}

function DevicePoolSettingsModal({
  isOpen,
  onClose,
  pool,
  onSave,
}: {
  isOpen: boolean;
  onClose: () => void;
  pool: any;
  onSave: (data: any) => void;
}) {
  const [name, setName] = useState(pool?.name || '');
  const [description, setDescription] = useState(pool?.description || '');

  if (!isOpen || !pool) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({ name, description });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">编辑设备池</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">设备池名称</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">描述</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="设备池描述"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              保存
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  isLoading?: boolean;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <AlertTriangle size={20} className="text-red-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          </div>
          <p className="text-gray-600 mb-6">{message}</p>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={isLoading}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              取消
            </button>
            <button
              onClick={onConfirm}
              disabled={isLoading}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isLoading && <Loader2 size={16} className="animate-spin" />}
              确认删除
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateDevicePoolModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      devicesApi.createPool('', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devicePools'] });
      onClose();
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建设备池失败');
    },
  });

  const resetForm = () => {
    setName('');
    setDescription('');
    setError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('请输入设备池名称');
      return;
    }
    createMutation.mutate({ 
      name: name.trim(), 
      description: description.trim() || undefined 
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">创建设备池</h2>
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
              设备池名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Android真机池"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              描述
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="用于执行Android测试的设备池"
            />
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
              disabled={createMutation.isPending}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {createMutation.isPending && <Loader2 size={16} className="animate-spin" />}
              {createMutation.isPending ? '创建中...' : '创建设备池'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DevicePoolCard({
  pool,
  devices,
  onEdit,
  onDelete,
  onRefresh,
}: {
  pool: any;
  devices: any[];
  onEdit: () => void;
  onDelete: () => void;
  onRefresh: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const poolDevices = devices.filter((d: any) => d.pool_id === pool.id);
  const availableCount = poolDevices.filter((d: any) => d.status === 'available').length;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
      <div className="px-6 py-4 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Monitor size={20} className="text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{pool.name}</h3>
              <p className="text-sm text-gray-500">{pool.description || '暂无描述'}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${
              availableCount > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
            }`}>
              {availableCount} 可用 / {poolDevices.length} 总计
            </span>
            
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-2 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600"
              >
                <MoreHorizontal size={18} />
              </button>
              
              {showMenu && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                  <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 w-40">
                    <button
                      onClick={() => { onRefresh(); setShowMenu(false); }}
                      className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
                    >
                      <RefreshCw size={14} />
                      刷新设备
                    </button>
                    <button
                      onClick={() => { onEdit(); setShowMenu(false); }}
                      className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
                    >
                      <Edit size={14} />
                      编辑设置
                    </button>
                    <hr className="my-1" />
                    <button
                      onClick={() => { onDelete(); setShowMenu(false); }}
                      className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-2"
                    >
                      <Trash2 size={14} />
                      删除设备池
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {poolDevices.length > 0 ? (
        <div className="divide-y divide-gray-100">
          {poolDevices.slice(0, 5).map((device: any) => (
            <div key={device.id} className="px-6 py-3 flex items-center justify-between hover:bg-gray-50">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  device.status === 'available' ? 'bg-green-500' :
                  device.status === 'busy' ? 'bg-blue-500' : 'bg-gray-400'
                }`} />
                <Smartphone size={16} className="text-gray-400" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {device.name || device.model || '未命名设备'}
                  </p>
                  <p className="text-xs text-gray-500">
                    {device.platform} {device.platform_version}
                  </p>
                </div>
              </div>
              <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                device.status === 'available' ? 'bg-green-100 text-green-700' :
                device.status === 'busy' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {device.status === 'available' ? '空闲' : device.status === 'busy' ? '使用中' : '离线'}
              </span>
            </div>
          ))}
          {poolDevices.length > 5 && (
            <div className="px-6 py-2 text-center text-sm text-gray-500">
              还有 {poolDevices.length - 5} 台设备...
            </div>
          )}
        </div>
      ) : (
        <div className="px-6 py-8 text-center text-gray-500">
          <Smartphone size={32} className="mx-auto mb-2 text-gray-300" />
          <p className="text-sm">此设备池暂无设备</p>
        </div>
      )}
    </div>
  );
}

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
                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 disabled:hover:bg-blue-50"
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

  const packages: AppPackageOption[] = data?.data?.items || [];

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
                  packages.map((p) => (
                    <option key={p.id} value={p.id}>
                      {(p.app_name || p.package_name) + ' · ' + p.version_name + ' · ' + p.filename}
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
            <div className="mt-1 text-sm text-gray-500">
              {server.device_count} 台设备可用
            </div>
          )}
          
          {server.last_connected && (
            <div className="mt-1 text-xs text-gray-400">
              上次连接: {new Date(server.last_connected).toLocaleString('zh-CN')}
            </div>
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
    username: '',
    password: '',
  });
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const response = await devicesApi.testRemoteConnection({
        host: formData.host,
        port: formData.port,
        path: formData.path,
      });
      setTestResult({
        success: true,
        message: '连接成功',
        serverInfo: response.data?.serverInfo,
        devices: response.data?.devices,
      });
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
    setFormData({
      name: '',
      host: '',
      port: 4723,
      path: '',
      username: '',
      password: '',
    });
    setTestResult(null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">添加远程 Appium 服务器</h2>
          <button
            onClick={() => { onClose(); resetForm(); }}
            className="p-2 hover:bg-gray-100 rounded-lg text-gray-400"
          >
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
                placeholder="192.168.1.100 或 appium.example.com"
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
                placeholder="4723"
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
            <p className="text-xs text-gray-500 mt-1">Appium 2.x 通常留空，Appium 1.x 使用 /wd/hub</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">用户名 (可选)</label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="用户名"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">密码 (可选)</label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="密码"
              />
            </div>
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
              {testResult.serverInfo && (
                <div className="mt-2 text-sm text-green-600">
                  Appium 版本: {testResult.serverInfo.version}
                </div>
              )}
              {testResult.devices && testResult.devices.length > 0 && (
                <div className="mt-2 text-sm text-green-600">
                  发现 {testResult.devices.length} 台设备
                </div>
              )}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={handleTest}
              disabled={!formData.host || !formData.port || isTesting}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isTesting ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Zap size={18} />
              )}
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

export default function DevicesPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'pools' | 'local' | 'servers'>('pools');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingPool, setEditingPool] = useState<any>(null);
  const [deletingPool, setDeletingPool] = useState<any>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showAddServerModal, setShowAddServerModal] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [localDevices, setLocalDevices] = useState<LocalDevice[]>([]);
  const [scanError, setScanError] = useState<string | null>(null);
  const [installDevice, setInstallDevice] = useState<LocalDevice | null>(null);

  const { data: poolsData, isLoading: poolsLoading, refetch: refetchPools } = useQuery({
    queryKey: ['devicePools'],
    queryFn: () => devicesApi.listPools(),
  });

  const { data: devicesData, isLoading: devicesLoading, refetch: refetchDevices } = useQuery({
    queryKey: ['devices'],
    queryFn: () => devicesApi.listDevices(),
  });

  const { data: remoteServersData, isLoading: isLoadingServers } = useQuery({
    queryKey: ['remoteServers'],
    queryFn: () => devicesApi.listRemoteServers(),
  });

  const updatePoolMutation = useMutation({
    mutationFn: ({ poolId, data }: { poolId: string; data: any }) =>
      devicesApi.updatePool(poolId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devicePools'] });
      setEditingPool(null);
    },
  });

  const deletePoolMutation = useMutation({
    mutationFn: (poolId: string) => devicesApi.deletePool(poolId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devicePools'] });
      setDeletingPool(null);
    },
  });

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['remoteServers'] });
    },
  });

  const refreshServerMutation = useMutation({
    mutationFn: (serverId: string) => devicesApi.refreshRemoteDevices(serverId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['remoteServers'] });
    },
  });

  const handleScanLocal = async () => {
    setIsScanning(true);
    setScanError(null);
    try {
      const response = await devicesApi.scanLocalDevices();
      setLocalDevices(response.data?.devices || []);
    } catch (error: any) {
      setScanError(error.response?.data?.detail || '扫描本地设备失败');
      setLocalDevices([
        {
          id: '1',
          udid: 'emulator-5554',
          name: 'Android Emulator',
          platform: 'android',
          version: '13.0',
          status: 'connected',
          connection: 'usb',
          model: 'Pixel 6',
          manufacturer: 'Google',
        },
        {
          id: '2',
          udid: 'R58M40XXXXX',
          name: 'Samsung Galaxy S23',
          platform: 'android',
          version: '14.0',
          status: 'connected',
          connection: 'usb',
          model: 'SM-S911B',
          manufacturer: 'Samsung',
        },
      ]);
    } finally {
      setIsScanning(false);
    }
  };

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([refetchPools(), refetchDevices()]);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    handleScanLocal();
  }, []);

  const pools = poolsData?.data?.items || [];
  const devices = devicesData?.data?.items || [];
  const remoteServers: RemoteServer[] = (remoteServersData?.data || []).map((s: any) => ({
    ...s,
    status: s.status || 'unknown',
  }));
  const isLoading = poolsLoading || devicesLoading;

  const totalDevices = devices.length;
  const availableDevices = devices.filter((d: any) => d.status === 'available').length;
  const busyDevices = devices.filter((d: any) => d.status === 'busy').length;
  const connectedDevices = localDevices.filter(d => d.status === 'connected');

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 sticky top-16 z-40">
        <div className="px-8 py-4">
          <h1 className="text-xl font-bold text-gray-900">设备管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理设备池、本地设备和远程 Appium 服务器</p>
        </div>

        <div className="px-8">
          <div className="flex gap-6">
            <button
              onClick={() => setActiveTab('pools')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'pools'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <Monitor size={18} />
                设备池
                {pools.length > 0 && (
                  <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-600 rounded-full">
                    {pools.length}
                  </span>
                )}
              </div>
            </button>
            <button
              onClick={() => setActiveTab('local')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'local'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <Usb size={18} />
                本地设备
                {connectedDevices.length > 0 && (
                  <span className="px-2 py-0.5 text-xs bg-green-100 text-green-600 rounded-full">
                    {connectedDevices.length}
                  </span>
                )}
              </div>
            </button>
            <button
              onClick={() => setActiveTab('servers')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'servers'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <Globe size={18} />
                Appium 服务
                {remoteServers.length > 0 && (
                  <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-600 rounded-full">
                    {remoteServers.length}
                  </span>
                )}
              </div>
            </button>
          </div>
        </div>
      </div>

      <div className="p-8">
        {activeTab === 'pools' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div className="grid grid-cols-4 gap-4 flex-1">
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-sm text-gray-500">设备池</div>
                  <div className="text-2xl font-bold text-gray-900 mt-1">{pools.length}</div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-sm text-gray-500">总设备</div>
                  <div className="text-2xl font-bold text-gray-900 mt-1">{totalDevices}</div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-sm text-gray-500">空闲设备</div>
                  <div className="text-2xl font-bold text-green-600 mt-1">{availableDevices}</div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-sm text-gray-500">使用中</div>
                  <div className="text-2xl font-bold text-blue-600 mt-1">{busyDevices}</div>
                </div>
              </div>
              <div className="flex items-center gap-3 ml-4">
                <button
                  onClick={handleRefreshAll}
                  disabled={isRefreshing}
                  className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700 disabled:opacity-50"
                >
                  <RefreshCw size={18} className={isRefreshing ? 'animate-spin' : ''} />
                  <span>刷新</span>
                </button>
                <button
                  onClick={() => setIsCreateModalOpen(true)}
                  className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Plus size={18} />
                  <span>新建设备池</span>
                </button>
              </div>
            </div>

            {isLoading ? (
              <div className="space-y-4">
                {[1, 2].map((i) => (
                  <div key={i} className="h-48 bg-gray-100 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : pools.length === 0 ? (
              <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
                <Monitor size={48} className="mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">暂无设备池</h3>
                <p className="text-gray-500 mb-6 max-w-md mx-auto">
                  创建设备池来组织和管理您的测试设备，支持按项目或用途分组
                </p>
                <button
                  onClick={() => setIsCreateModalOpen(true)}
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  创建设备池
                </button>
              </div>
            ) : (
              <div className="grid gap-4">
                {pools.map((pool: any) => (
                  <DevicePoolCard
                    key={pool.id}
                    pool={pool}
                    devices={devices}
                    onEdit={() => setEditingPool(pool)}
                    onDelete={() => setDeletingPool(pool)}
                    onRefresh={handleRefreshAll}
                  />
                ))}
              </div>
            )}

            {devices.filter((d: any) => !d.pool_id).length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle size={20} className="text-yellow-600 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-yellow-800">
                      有 {devices.filter((d: any) => !d.pool_id).length} 台设备未分配到设备池
                    </h4>
                    <p className="text-sm text-yellow-700 mt-1">
                      未分配的设备不会被自动用于测试执行，请将它们添加到合适的设备池中
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'local' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-500">
                {isScanning ? '正在扫描本地设备...' : `共发现 ${localDevices.length} 台设备`}
              </div>
              <button
                onClick={handleScanLocal}
                disabled={isScanning}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {isScanning ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <RefreshCw size={18} />
                )}
                刷新设备
              </button>
            </div>

            {scanError && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-start gap-3">
                <AlertTriangle size={20} className="text-yellow-600 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-medium text-yellow-800">扫描提示</div>
                  <div className="text-sm text-yellow-700 mt-1">{scanError}</div>
                  <div className="text-sm text-yellow-600 mt-2">
                    请确保 ADB (Android) 或 Xcode (iOS) 已正确安装并配置
                  </div>
                </div>
              </div>
            )}

            {connectedDevices.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  已连接 ({connectedDevices.length})
                </h3>
                <div className="grid gap-3">
                  {connectedDevices.map((device) => (
                    <DeviceCard key={device.id} device={device} onInstall={(d) => setInstallDevice(d)} />
                  ))}
                </div>
              </div>
            )}

            {localDevices.filter(d => d.status !== 'connected').length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-500 mb-3 flex items-center gap-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                  已断开 ({localDevices.filter(d => d.status !== 'connected').length})
                </h3>
                <div className="grid gap-3 opacity-60">
                  {localDevices.filter(d => d.status !== 'connected').map((device) => (
                    <DeviceCard key={device.id} device={device} onInstall={(d) => setInstallDevice(d)} />
                  ))}
                </div>
              </div>
            )}

            {localDevices.length === 0 && !isScanning && (
              <div className="text-center py-16 bg-white rounded-xl border-2 border-dashed border-gray-300">
                <Smartphone size={48} className="mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">未发现本地设备</h3>
                <p className="text-gray-500 mb-4 max-w-md mx-auto">
                  请确保设备已通过 USB 连接并启用了开发者模式 (Android) 或信任此电脑 (iOS)
                </p>
                <button
                  onClick={handleScanLocal}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  重新扫描
                </button>
              </div>
            )}

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
                    <li>在设备上允许 USB 调试</li>
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
                    <li>运行 <code className="bg-blue-100 px-1 rounded">xcrun xctrace list devices</code></li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

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
                <p className="text-gray-500 mb-4 max-w-md mx-auto">
                  添加远程 Appium 服务器以连接云端或其他机器上的设备
                </p>
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
                <p className="mt-2">
                  <a href="https://appium.io" target="_blank" rel="noopener" className="text-purple-600 hover:underline flex items-center gap-1">
                    了解更多关于 Appium
                    <ExternalLink size={14} />
                  </a>
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      <CreateDevicePoolModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />

      <DevicePoolSettingsModal
        isOpen={!!editingPool}
        onClose={() => setEditingPool(null)}
        pool={editingPool}
        onSave={(data) => {
          if (editingPool) {
            updatePoolMutation.mutate({ poolId: editingPool.id, data });
          }
        }}
      />

      <DeleteConfirmModal
        isOpen={!!deletingPool}
        onClose={() => setDeletingPool(null)}
        onConfirm={() => {
          if (deletingPool) {
            deletePoolMutation.mutate(deletingPool.id);
          }
        }}
        title="删除设备池"
        message={`确定要删除设备池 "${deletingPool?.name}" 吗？此操作无法撤销，池中的设备将变为未分配状态。`}
        isLoading={deletePoolMutation.isPending}
      />

      <AddRemoteServerModal
        isOpen={showAddServerModal}
        onClose={() => setShowAddServerModal(false)}
        onAdd={(data) => addServerMutation.mutate(data)}
      />

      <InstallAppModal
        isOpen={!!installDevice}
        onClose={() => setInstallDevice(null)}
        device={installDevice}
      />
    </div>
  );
}
