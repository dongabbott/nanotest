import { 
  Wifi, 
  Usb, 
  RefreshCw, 
  Loader2,
  AlertCircle
} from 'lucide-react';
import type { LocalDevice } from './types';

interface LocalDeviceListProps {
  devices: LocalDevice[];
  isLoading: boolean;
  onRefresh: () => void;
}

export function LocalDeviceList({ 
  devices, 
  isLoading, 
  onRefresh
}: LocalDeviceListProps) {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'connected':
        return <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">已连接</span>;
      case 'disconnected':
        return <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800 rounded-full">已断开</span>;
      case 'busy':
        return <span className="px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full">使用中</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800 rounded-full">{status}</span>;
    }
  };

  const getPlatformIcon = (platform: string) => {
    return platform === 'ios' ? '🍎' : '🤖';
  };

  const getConnectionIcon = (connection: string) => {
    return connection === 'wifi' ? (
      <Wifi size={14} className="text-blue-500" />
    ) : (
      <Usb size={14} className="text-gray-500" />
    );
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* 头部 */}
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          设备管理 ({devices.length})
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg disabled:opacity-50"
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
            刷新设备
          </button>
        </div>
      </div>

      {/* 设备列表 */}
      {isLoading ? (
        <div className="p-8 text-center text-gray-500">
          <Loader2 className="animate-spin mx-auto mb-2" size={24} />
          正在扫描设备...
        </div>
      ) : devices.length === 0 ? (
        <div className="p-8 text-center">
          <AlertCircle className="mx-auto mb-3 text-gray-400" size={40} />
          <p className="text-gray-500 mb-2">未发现连接的设备</p>
          <p className="text-sm text-gray-400">
            请确保 ADB 或 libimobiledevice 已安装，并且设备已通过 USB 或 WiFi 连接
          </p>
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {devices.map((device) => (
            <div 
              key={device.udid} 
              className="px-6 py-4 hover:bg-gray-50 flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center text-xl">
                  {getPlatformIcon(device.platform)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">
                      {device.name || device.model || device.udid}
                    </span>
                    {getStatusBadge(device.status)}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
                      {getConnectionIcon(device.connection)}
                      {device.connection.toUpperCase()}
                    </span>
                    <span>{device.platform}</span>
                    {device.version && <span>v{device.version}</span>}
                  </div>
                  <div className="text-xs text-gray-400 mt-1 font-mono">
                    {device.udid}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
