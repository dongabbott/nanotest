// 设备管理相关类型定义
export interface LocalDevice {
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

export interface RemoteServer {
  id: string;
  name: string;
  host: string;
  port: number;
  path?: string;
  status: 'online' | 'offline' | 'unknown';
  last_connected?: string;
  device_count?: number;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  serverInfo?: {
    version: string;
    buildTime: string;
  };
  devices?: LocalDevice[];
}

export interface AppPackageOption {
  id: string;
  filename: string;
  platform: 'android' | 'ios';
  package_name: string;
  app_name?: string;
  version_name: string;
  version_code?: number;
  build_number?: string;
}

export interface SessionInfo {
  session_id: string;
  device_udid: string;
  device_name?: string;
  platform: string;
  platform_version?: string;
  package_id?: string;
  package_name?: string;
  app_name?: string;
  server_url: string;
  status: 'active' | 'disconnected' | 'error';
  created_at: string;
  capabilities: Record<string, unknown>;
}

export interface DevicePool {
  id: string;
  name: string;
  description?: string;
  selection_strategy?: string;
  platform_filter?: string;
  tag_filter?: string[];
  created_at: string;
  updated_at: string;
}

export interface Device {
  id: string;
  name: string;
  udid: string;
  platform: string;
  platform_version?: string;
  model?: string;
  manufacturer?: string;
  status: string;
  pool_id?: string;
  capabilities?: Record<string, unknown>;
  tags?: string[];
}
