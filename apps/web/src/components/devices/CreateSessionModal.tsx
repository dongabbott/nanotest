import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { X, Loader2, Smartphone, Package } from 'lucide-react';
import { devicesApi, packagesApi } from '../../services/api';
import type { LocalDevice, AppPackageOption, RemoteServer } from './types';

interface CreateSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  devices: LocalDevice[];
}

export function CreateSessionModal({ isOpen, onClose, devices }: CreateSessionModalProps) {
  const [selectedDevice, setSelectedDevice] = useState('');
  const [selectedPackage, setSelectedPackage] = useState('');
  const [serverUrl, setServerUrl] = useState('http://127.0.0.1:4723');
  const [selectedServerId, setSelectedServerId] = useState('local');
  const [noReset, setNoReset] = useState(true);
  const [fullReset, setFullReset] = useState(false);
  const [autoLaunch, setAutoLaunch] = useState(true);
  const [error, setError] = useState('');

  const queryClient = useQueryClient();

  // 获取应用包列表
  const { data: packagesData } = useQuery({
    queryKey: ['packages'],
    queryFn: () => packagesApi.list(),
    enabled: isOpen,
  });

  const packages: AppPackageOption[] = packagesData?.data?.items || [];

  const { data: remoteServersData, isLoading: isLoadingRemoteServers } = useQuery({
    queryKey: ['remoteServers'],
    queryFn: () => devicesApi.listRemoteServers(),
    enabled: isOpen,
  });

  const remoteServers: RemoteServer[] = remoteServersData?.data || [];

  // 根据选中设备过滤应用包
  const selectedDeviceInfo = devices.find(d => d.udid === selectedDevice);
  const filteredPackages = selectedDeviceInfo
    ? packages.filter(p => p.platform === selectedDeviceInfo.platform)
    : packages;

  // 可用设备（已连接状态）
  const availableDevices = devices.filter(d => d.status === 'connected');

  const createSessionMutation = useMutation({
    mutationFn: (data: {
      device_udid: string;
      package_id: string;
      server_url?: string;
      no_reset?: boolean;
      full_reset?: boolean;
      auto_launch?: boolean;
    }) => devicesApi.createSessionFromPackage(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeSessions'] });
      onClose();
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建 Session 失败');
    },
  });

  const resetForm = () => {
    setSelectedDevice('');
    setSelectedPackage('');
    setServerUrl('http://127.0.0.1:4723');
    setSelectedServerId('local');
    setNoReset(true);
    setFullReset(false);
    setAutoLaunch(true);
    setError('');
  };

  useEffect(() => {
    if (isOpen && availableDevices.length === 1) {
      setSelectedDevice(availableDevices[0].udid);
    }
  }, [isOpen, availableDevices]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDevice) {
      setError('请选择设备');
      return;
    }
    if (!selectedPackage) {
      setError('请选择应用包');
      return;
    }

    let url = serverUrl || '';
    if (selectedServerId === 'local') {
      url = url || 'http://127.0.0.1:4723';
    } else {
      const picked = remoteServers.find((s) => s.id === selectedServerId);
      if (!picked) {
        setError('请选择 Appium Server');
        return;
      }
      const path = (picked.path || '').trim();
      const normalizedPath = path ? (path.startsWith('/') ? path : `/${path}`) : '';
      url = `http://${picked.host}:${picked.port}${normalizedPath}`;
    }

    createSessionMutation.mutate({
      device_udid: selectedDevice,
      package_id: selectedPackage,
      server_url: url || undefined,
      no_reset: noReset,
      full_reset: fullReset,
      auto_launch: autoLaunch,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white">
          <h2 className="text-lg font-semibold text-gray-900">创建 Appium Session</h2>
          <button onClick={() => { onClose(); resetForm(); }} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">{error}</div>
          )}

          {/* 设备选择 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Smartphone size={16} className="inline mr-1" />
              选择设备 <span className="text-red-500">*</span>
            </label>
            {availableDevices.length === 0 ? (
              <div className="text-sm text-yellow-600 bg-yellow-50 px-4 py-3 rounded-lg">
                没有可用的已连接设备，请先连接设备并刷新设备列表
              </div>
            ) : (
              <select
                value={selectedDevice}
                onChange={(e) => {
                  setSelectedDevice(e.target.value);
                  setSelectedPackage(''); // 切换设备时清空选中的包
                }}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- 选择设备 --</option>
                {availableDevices.map((device) => (
                  <option key={device.udid} value={device.udid}>
                    {device.name || device.model || device.udid} ({device.platform}) - {device.udid}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* 应用包选择 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Package size={16} className="inline mr-1" />
              选择应用包 <span className="text-red-500">*</span>
            </label>
            {filteredPackages.length === 0 ? (
              <div className="text-sm text-yellow-600 bg-yellow-50 px-4 py-3 rounded-lg">
                {selectedDevice ? '没有匹配该设备平台的应用包' : '请先选择设备或上传应用包'}
              </div>
            ) : (
              <select
                value={selectedPackage}
                onChange={(e) => setSelectedPackage(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- 选择应用包 --</option>
                {filteredPackages.map((pkg) => (
                  <option key={pkg.id} value={pkg.id}>
                    {pkg.app_name || pkg.package_name} v{pkg.version_name} ({pkg.platform})
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Appium Server URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Appium Server URL
            </label>
            <div className="grid grid-cols-1 gap-2">
              <select
                value={selectedServerId}
                onChange={(e) => setSelectedServerId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="local">本地（http://127.0.0.1:4723）</option>
                {remoteServers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}（{s.host}:{s.port}{s.path ? s.path : ''}）
                  </option>
                ))}
              </select>

              <input
                type="text"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                disabled={selectedServerId !== 'local'}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                placeholder="http://127.0.0.1:4723"
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {isLoadingRemoteServers ? '正在加载远程 Appium 服务列表…' : '选择远程服务将自动拼接 URL；本地可手动编辑'}
            </p>
          </div>

          {/* Session 选项 */}
          <div className="space-y-3">
            <label className="block text-sm font-medium text-gray-700">Session 选项</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={noReset}
                  onChange={(e) => setNoReset(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">noReset - 保留应用数据</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={fullReset}
                  onChange={(e) => setFullReset(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">fullReset - 完全重置应用</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoLaunch}
                  onChange={(e) => setAutoLaunch(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">autoLaunch - 自动启动应用</span>
              </label>
            </div>
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
              disabled={createSessionMutation.isPending || availableDevices.length === 0}
              className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {createSessionMutation.isPending && <Loader2 size={16} className="animate-spin" />}
              {createSessionMutation.isPending ? '创建中...' : '创建 Session'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
