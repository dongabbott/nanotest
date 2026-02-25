import { useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Loader2, 
  RefreshCw, 
  Trash2, 
  Camera, 
  Code, 
  Play, 
  Square, 
  RotateCcw,
  Smartphone,
  Clock
} from 'lucide-react';
import { devicesApi } from '../../services/api';
import type { SessionInfo } from './types';

interface SessionListProps {
  sessions: SessionInfo[];
  isLoading: boolean;
  onRefresh: () => void;
  onActionResult?: (action: string, result: any) => void;
}

export function SessionList({ sessions, isLoading, onRefresh, onActionResult }: SessionListProps) {
  const queryClient = useQueryClient();

  // 终止 Session
  const terminateMutation = useMutation({
    mutationFn: (sessionId: string) => devicesApi.terminateSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeSessions'] });
    },
  });

  // Session 操作
  const actionMutation = useMutation({
    mutationFn: ({ sessionId, action }: { sessionId: string; action: string }) =>
      devicesApi.performSessionAction(sessionId, action),
    onSuccess: (response, variables) => {
      if (onActionResult) {
        onActionResult(variables.action, response.data);
      }
    },
  });

  const handleAction = (sessionId: string, action: string) => {
    actionMutation.mutate({ sessionId, action });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'disconnected': return 'bg-yellow-100 text-yellow-800';
      case 'error': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active': return '活跃';
      case 'disconnected': return '已断开';
      case 'error': return '错误';
      default: return status;
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8">
        <div className="flex items-center justify-center text-gray-500">
          <Loader2 className="animate-spin mr-2" size={20} />
          加载中...
        </div>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8">
        <div className="flex items-center justify-between">
          <div className="text-gray-500 text-sm">暂无活跃会话</div>
          <button
            onClick={onRefresh}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
            title="刷新"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          活跃 Sessions ({sessions.length})
        </h3>
        <button
          onClick={onRefresh}
          className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
          title="刷新"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      <div className="divide-y divide-gray-100">
        {sessions.map((session) => (
          <div key={session.session_id} className="p-4 hover:bg-gray-50">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2">
                  <Smartphone size={18} className="text-gray-400 flex-shrink-0" />
                  <span className="font-medium text-gray-900 truncate">
                    {session.app_name || session.package_name || '未知应用'}
                  </span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(session.status)}`}>
                    {getStatusText(session.status)}
                  </span>
                </div>
                
                <div className="ml-7 space-y-1 text-sm text-gray-500">
                  <div>设备: {session.device_name || session.device_udid}</div>
                  <div>平台: {session.platform} {session.platform_version}</div>
                  <div className="flex items-center gap-1">
                    <Clock size={12} />
                    创建于: {new Date(session.created_at).toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-400 font-mono truncate">
                    Session ID: {session.session_id}
                  </div>
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="flex items-center gap-1 ml-4">
                <button
                  onClick={() => handleAction(session.session_id, 'screenshot')}
                  disabled={actionMutation.isPending}
                  className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
                  title="截图"
                >
                  <Camera size={16} />
                </button>
                <button
                  onClick={() => handleAction(session.session_id, 'source')}
                  disabled={actionMutation.isPending}
                  className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg"
                  title="页面源码"
                >
                  <Code size={16} />
                </button>
                <button
                  onClick={() => handleAction(session.session_id, 'launch_app')}
                  disabled={actionMutation.isPending}
                  className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded-lg"
                  title="启动应用"
                >
                  <Play size={16} />
                </button>
                <button
                  onClick={() => handleAction(session.session_id, 'close_app')}
                  disabled={actionMutation.isPending}
                  className="p-2 text-gray-500 hover:text-orange-600 hover:bg-orange-50 rounded-lg"
                  title="关闭应用"
                >
                  <Square size={16} />
                </button>
                <button
                  onClick={() => handleAction(session.session_id, 'reset_app')}
                  disabled={actionMutation.isPending}
                  className="p-2 text-gray-500 hover:text-yellow-600 hover:bg-yellow-50 rounded-lg"
                  title="重置应用"
                >
                  <RotateCcw size={16} />
                </button>
                <button
                  onClick={() => {
                    if (confirm('确定要终止此 Session 吗？')) {
                      terminateMutation.mutate(session.session_id);
                    }
                  }}
                  disabled={terminateMutation.isPending}
                  className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
                  title="终止 Session"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Session 操作结果弹窗
export function SessionActionResultModal({
  isOpen,
  onClose,
  action,
  result,
}: {
  isOpen: boolean;
  onClose: () => void;
  action: string;
  result: any;
}) {
  if (!isOpen || !result) return null;

  const getTitle = () => {
    switch (action) {
      case 'screenshot': return '截图结果';
      case 'source': return '页面源码';
      case 'launch_app': return '启动应用';
      case 'close_app': return '关闭应用';
      case 'reset_app': return '重置应用';
      default: return '操作结果';
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">{getTitle()}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </div>

        <div className="p-6 overflow-auto flex-1">
          {!result.success ? (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg">
              {result.message || '操作失败'}
            </div>
          ) : action === 'screenshot' && result.data?.screenshot ? (
            <div className="text-center">
              <img
                src={`data:image/png;base64,${result.data.screenshot}`}
                alt="Screenshot"
                className="max-w-full h-auto mx-auto border rounded-lg shadow"
                style={{ maxHeight: '70vh' }}
              />
            </div>
          ) : action === 'source' && result.data?.source ? (
            <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto text-xs font-mono" style={{ maxHeight: '70vh' }}>
              {result.data.source}
            </pre>
          ) : (
            <div className="bg-green-50 text-green-600 px-4 py-3 rounded-lg">
              {result.message || '操作成功'}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
