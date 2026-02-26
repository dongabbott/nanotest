import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use((config) => {
  const storage = localStorage.getItem('auth-storage');
  if (storage) {
    const { state } = JSON.parse(storage);
    if (state?.token) {
      config.headers.Authorization = `Bearer ${state.token}`;
    }
  }
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth-storage');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post('/api/v1/auth/login/json', { email, password }),
  me: () => apiClient.get('/api/v1/auth/me'),
};

// Projects API
export const projectsApi = {
  list: () => apiClient.get('/api/v1/projects'),
  get: (id: string) => apiClient.get(`/api/v1/projects/${id}`),
  create: (data: { name: string; platform: string; repo_url?: string }) =>
    apiClient.post('/api/v1/projects', data),
  update: (id: string, data: Partial<{ name: string; platform: string }>) =>
    apiClient.patch(`/api/v1/projects/${id}`, data),
  delete: (id: string) => apiClient.delete(`/api/v1/projects/${id}`),
};

// Test Cases API
export const testCasesApi = {
  list: (projectId: string, page = 1, pageSize = 50) =>
    apiClient.get(`/api/v1/projects/${projectId}/cases`, {
      params: { page, page_size: pageSize },
    }),
  get: (caseId: string) => apiClient.get(`/api/v1/cases/${caseId}`),
  create: (projectId: string, data: { name: string; description?: string; dsl_content: any; tags?: string[] }) =>
    apiClient.post(`/api/v1/projects/${projectId}/cases`, data),
  update: (caseId: string, data: Partial<{ name: string; description?: string; dsl_content: any; tags: string[] }>) =>
    apiClient.put(`/api/v1/cases/${caseId}`, data),
  validateDsl: (dsl_content: any) => apiClient.post('/api/v1/cases/validate-dsl', { dsl_content }),
};

// Test Flows API
export const testFlowsApi = {
  list: (projectId: string, page = 1, pageSize = 50) =>
    apiClient.get(`/api/v1/projects/${projectId}/flows`, {
      params: { page, page_size: pageSize },
    }),
  get: (flowId: string) => apiClient.get(`/api/v1/flows/${flowId}`),
  create: (projectId: string, data: { name: string; graph_json: object }) =>
    apiClient.post(`/api/v1/projects/${projectId}/flows`, data),
  update: (flowId: string, data: Partial<{ name: string; graph_json: object }>) =>
    apiClient.put(`/api/v1/flows/${flowId}`, data),
  compile: (flowId: string) => apiClient.post(`/api/v1/flows/${flowId}/compile`),
  listBindings: (flowId: string) =>
    apiClient.get(`/api/v1/flows/${flowId}/bindings`),
  upsertBinding: (flowId: string, data: {
    node_key: string;
    test_case_id: string;
    retry_policy?: Record<string, unknown>;
    timeout_sec?: number;
  }) =>
    apiClient.post(`/api/v1/flows/${flowId}/bindings`, data),
  deleteBinding: (flowId: string, nodeKey: string) =>
    apiClient.delete(`/api/v1/flows/${flowId}/bindings/${encodeURIComponent(nodeKey)}`),
};

// Test Runs API
export const testRunsApi = {
  list: (projectId: string, page = 1, pageSize = 50) =>
    apiClient.get(`/api/v1/projects/${projectId}/runs`, {
      params: { page, page_size: pageSize },
    }),
  get: (runId: string) => apiClient.get(`/api/v1/runs/${runId}`),
  getDetail: (runId: string) => apiClient.get(`/api/v1/runs/${runId}/detail`),
  getNodes: (runId: string) => apiClient.get(`/api/v1/runs/${runId}/nodes`),
  getSteps: (runId: string) => apiClient.get(`/api/v1/runs/${runId}/steps`),
  trigger: (
    flowId: string,
    options?: { planId?: string; sessionId?: string }
  ) =>
    apiClient.post(`/api/v1/flows/${flowId}/runs`, {
      planId: options?.planId,
      sessionId: options?.sessionId,
    }),
  cancel: (runId: string) => apiClient.post(`/api/v1/runs/${runId}/cancel`),
  aiAnalyze: (runId: string) => apiClient.post(`/api/v1/runs/${runId}/ai-analyze`),
  getAiSummary: (runId: string) => apiClient.get(`/api/v1/runs/${runId}/ai-summary`),
  getRiskScore: (runId: string) => apiClient.get(`/api/v1/runs/${runId}/risk-score`),
};

// Comparisons API
export const comparisonsApi = {
  compare: (baselineRunId: string, targetRunId: string) =>
    apiClient.post('/api/v1/runs/compare', {
      baseline_run_id: baselineRunId,
      target_run_id: targetRunId,
    }),
  get: (comparisonId: string) => apiClient.get(`/api/v1/comparisons/${comparisonId}`),
};

// Devices API
export const devicesApi = {
  // 设备
  listDevices: (_projectId?: string, poolId?: string) =>
    apiClient.get('/api/v1/devices', { params: { pool_id: poolId } }),
  getDevice: (deviceId: string) =>
    apiClient.get(`/api/v1/devices/${deviceId}`),
  updateDevice: (deviceId: string, data: Partial<{ status: string; name: string }>) =>
    apiClient.patch(`/api/v1/devices/${deviceId}`, data),

  // 本地设备扫描
  scanLocalDevices: () =>
    apiClient.post('/api/v1/devices/scan-local'),

  installPackage: (data: { udid: string; platform: 'android' | 'ios'; package_id: string }) =>
    apiClient.post('/api/v1/devices/install-package', data),
  
  // 远程 Appium 服务器连接
  testRemoteConnection: (data: { host: string; port: number; path?: string }) =>
    apiClient.post('/api/v1/devices/test-connection', data),
  
  // 添加远程服务器配置
  addRemoteServer: (data: { 
    name: string; 
    host: string; 
    port: number; 
    path?: string;
    username?: string;
    password?: string;
  }) =>
    apiClient.post('/api/v1/devices/remote-servers', data),
  
  // 获取远程服务器列表
  listRemoteServers: () =>
    apiClient.get('/api/v1/devices/remote-servers'),
  
  deleteRemoteServer: (serverId: string) =>
    apiClient.delete(`/api/v1/devices/remote-servers/${serverId}`),
  
  testConnection: (host: string, port: number, path: string) =>
    apiClient.post('/api/v1/devices/test-connection', { host, port, path }),
  
  refreshRemoteDevices: (serverId: string) =>
    apiClient.post(`/api/v1/devices/remote-servers/${serverId}/refresh`),
  
  startSession: (serverUrl: string, capabilities: object) =>
    apiClient.post('/api/v1/devices/session/start', { server_url: serverUrl, capabilities }),
  
  getPageSource: (sessionId: string) =>
    apiClient.post(`/api/v1/devices/session/${sessionId}/page-source`),
  
  stopSession: (sessionId: string) =>
    apiClient.delete(`/api/v1/devices/session/${sessionId}`),
  
  // ==========================================================================
  // Session Management (基于包和设备创建/管理 Session)
  // ==========================================================================
  
  // 基于包和设备创建 Session
  createSessionFromPackage: (data: {
    device_udid: string;
    package_id: string;
    server_url?: string;
    no_reset?: boolean;
    full_reset?: boolean;
    auto_launch?: boolean;
    extra_capabilities?: Record<string, unknown>;
  }) => apiClient.post('/api/v1/devices/sessions/create-from-package', data),
  
  // 列出所有活跃 Sessions
  listSessions: () => apiClient.get('/api/v1/devices/sessions'),
  
  // 获取 Session 详情
  getSession: (sessionId: string) => apiClient.get(`/api/v1/devices/sessions/${sessionId}`),
  
  // 执行 Session 操作 (screenshot, source, launch_app, close_app, reset_app)
  performSessionAction: (sessionId: string, action: string, appId?: string) =>
    apiClient.post(`/api/v1/devices/sessions/${sessionId}/action`, { action, app_id: appId }),
  
  // 刷新 Session 状态
  refreshSession: (sessionId: string) =>
    apiClient.post(`/api/v1/devices/sessions/${sessionId}/refresh`),
  
  // 终止 Session 并释放设备
  terminateSession: (sessionId: string) =>
    apiClient.delete(`/api/v1/devices/sessions/${sessionId}/terminate`),
};

// Plans API
export const plansApi = {
  list: (projectId: string, page = 1, pageSize = 50) =>
    apiClient.get(`/api/v1/projects/${projectId}/plans`, {
      params: { page, page_size: pageSize },
    }),
  get: (planId: string) =>
    apiClient.get(`/api/v1/plans/${planId}`),
  create: (projectId: string, data: {
    name: string;
    flow_id: string;
    trigger_type: string;
    cron_expr?: string | null;
    is_enabled?: boolean;
  }) =>
    apiClient.post(`/api/v1/projects/${projectId}/plans`, data),
  update: (planId: string, data: Partial<{
    name: string;
    trigger_type: string;
    cron_expr: string;
    is_enabled: boolean;
  }>) =>
    apiClient.patch(`/api/v1/plans/${planId}`, data),
  delete: (planId: string) =>
    apiClient.delete(`/api/v1/plans/${planId}`),
  trigger: (planId: string) =>
    apiClient.post(`/api/v1/plans/${planId}/trigger`),
};

// Packages API
export const packagesApi = {
  // 上传包
  upload: (projectId: string, file: File, description?: string, tags?: string[]) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    if (description) formData.append('description', description);
    if (tags && tags.length > 0) formData.append('tags', tags.join(','));
    return apiClient.post('/api/v1/packages/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  // 列表
  list: (params?: { project_id?: string; platform?: string; page?: number; page_size?: number }) =>
    apiClient.get('/api/v1/packages', { params }),
  
  // 获取单个
  get: (packageId: string) =>
    apiClient.get(`/api/v1/packages/${packageId}`),
  
  // 更新
  update: (packageId: string, data: { description?: string; tags?: string[]; status?: string }) =>
    apiClient.patch(`/api/v1/packages/${packageId}`, data),
  
  // 删除
  delete: (packageId: string) =>
    apiClient.delete(`/api/v1/packages/${packageId}`),
  
  // 获取下载地址
  getDownloadUrl: (packageId: string) =>
    apiClient.get(`/api/v1/packages/${packageId}/download`),
  
  // 获取图标地址
  getIconUrl: (packageId: string) =>
    apiClient.get(`/api/v1/packages/${packageId}/icon`),
  
  // 按包名查找
  getByPackageName: (packageName: string) =>
    apiClient.get(`/api/v1/packages/by-name/${encodeURIComponent(packageName)}`),
};

export default apiClient;
