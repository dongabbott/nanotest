import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, GitBranch, Edit, Trash2, Play, ArrowLeft } from 'lucide-react';
import { testFlowsApi, testCasesApi } from '../services/api';
import DAGFlowDesigner from '../components/DAGFlowDesigner';

// 流程定义类型
interface FlowDefinition {
  name: string;
  description?: string;
  nodes: Array<{
    id: string;
    type: 'start' | 'end' | 'test_case' | 'condition' | 'parallel' | 'group';
    label: string;
    position: { x: number; y: number };
    data?: Record<string, any>;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    label?: string;
    condition?: string;
  }>;
  variables?: Record<string, string>;
}

// 创建/编辑测试流程页面
function FlowDesignerPage({
  projectId,
  flowId,
  onBack,
}: {
  projectId: string;
  flowId?: string;
  onBack: () => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [flowDefinition, setFlowDefinition] = useState<FlowDefinition | null>(null);
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const queryClient = useQueryClient();

  // 获取项目下的测试用例列表
  const { data: testCasesData } = useQuery({
    queryKey: ['testCases', projectId],
    queryFn: () => testCasesApi.list(projectId, 1, 200),
    enabled: !!projectId,
  });

  const testCases = (testCasesData?.data?.items || []).map((tc: any) => ({
    id: tc.id,
    name: tc.name,
  }));

  // 如果是编辑模式，加载现有流程
  const { data: flowData, isLoading: isLoadingFlow } = useQuery({
    queryKey: ['testFlow', flowId],
    queryFn: () => testFlowsApi.get(flowId!),
    enabled: !!flowId,
  });

  // 初始化流程数据
  useEffect(() => {
    if (flowId && flowData?.data) {
      const flow = flowData.data;
      setName(flow.name || '');
      setDescription(flow.description || '');
      
      // 转换后端格式到设计器格式
      const graphJson = flow.graph_json || {};
      setFlowDefinition({
        name: flow.name,
        description: flow.description,
        nodes: graphJson.nodes || [
          { id: 'start', type: 'start', label: '开始', position: { x: 100, y: 200 } },
          { id: 'end', type: 'end', label: '结束', position: { x: 600, y: 200 } },
        ],
        edges: graphJson.edges || [],
        variables: graphJson.variables,
      });
    } else if (!flowId) {
      // 新建模式，设置默认值
      setFlowDefinition({
        name: '新测试流程',
        nodes: [
          { id: 'start', type: 'start', label: '开始', position: { x: 100, y: 200 } },
          { id: 'end', type: 'end', label: '结束', position: { x: 600, y: 200 } },
        ],
        edges: [],
      });
    }
  }, [flowId, flowData]);

  // 创建流程
  const createMutation = useMutation({
    mutationFn: (data: { name: string; graph_json: object; description?: string }) =>
      testFlowsApi.create(projectId, data),
    onSuccess: async (res: any) => {
      try {
        const createdFlowId = res?.data?.id;
        if (createdFlowId && flowDefinition) {
          const nodes = flowDefinition.nodes || [];
          const desired = nodes
            .filter((n) => n.type === 'test_case')
            .map((n) => ({
              nodeKey: n.id,
              testCaseId: n.data?.testCaseId as string | undefined,
              timeoutSec: n.data?.timeout as number | undefined,
            }))
            .filter((x) => !!x.nodeKey && !!x.testCaseId);

          const desiredKeys = new Set(desired.map((d) => d.nodeKey));
          const existingRes = await testFlowsApi.listBindings(createdFlowId);
          const existing = existingRes?.data || [];

          await Promise.all(
            desired.map((d) =>
              testFlowsApi.upsertBinding(createdFlowId, {
                node_key: d.nodeKey,
                test_case_id: d.testCaseId!,
                timeout_sec: typeof d.timeoutSec === 'number' ? d.timeoutSec : undefined,
              })
            )
          );

          await Promise.all(
            existing
              .filter((b: any) => !desiredKeys.has(b.node_key))
              .map((b: any) => testFlowsApi.deleteBinding(createdFlowId, b.node_key))
          );
        }

        queryClient.invalidateQueries({ queryKey: ['testFlows', projectId] });
        onBack();
      } catch (err: any) {
        setError(err.response?.data?.detail || '保存绑定失败');
        setIsSaving(false);
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建流程失败');
      setIsSaving(false);
    },
  });

  // 更新流程
  const updateMutation = useMutation({
    mutationFn: (data: { name: string; graph_json: object; description?: string }) =>
      testFlowsApi.update(flowId!, data),
    onSuccess: async () => {
      try {
        if (flowId && flowDefinition) {
          const nodes = flowDefinition.nodes || [];
          const desired = nodes
            .filter((n) => n.type === 'test_case')
            .map((n) => ({
              nodeKey: n.id,
              testCaseId: n.data?.testCaseId as string | undefined,
              timeoutSec: n.data?.timeout as number | undefined,
            }))
            .filter((x) => !!x.nodeKey && !!x.testCaseId);

          const desiredKeys = new Set(desired.map((d) => d.nodeKey));
          const existingRes = await testFlowsApi.listBindings(flowId);
          const existing = existingRes?.data || [];

          await Promise.all(
            desired.map((d) =>
              testFlowsApi.upsertBinding(flowId, {
                node_key: d.nodeKey,
                test_case_id: d.testCaseId!,
                timeout_sec: typeof d.timeoutSec === 'number' ? d.timeoutSec : undefined,
              })
            )
          );

          await Promise.all(
            existing
              .filter((b: any) => !desiredKeys.has(b.node_key))
              .map((b: any) => testFlowsApi.deleteBinding(flowId, b.node_key))
          );
        }

        queryClient.invalidateQueries({ queryKey: ['testFlows', projectId] });
        queryClient.invalidateQueries({ queryKey: ['testFlow', flowId] });
        onBack();
      } catch (err: any) {
        setError(err.response?.data?.detail || '保存绑定失败');
        setIsSaving(false);
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '更新流程失败');
      setIsSaving(false);
    },
  });

  // 处理流程变化
  const handleFlowChange = (flow: FlowDefinition) => {
    setFlowDefinition(flow);
  };

  // 保存流程
  const handleSave = () => {
    if (!name.trim()) {
      setError('请输入流程名称');
      return;
    }

    if (!flowDefinition) {
      setError('流程定义不能为空');
      return;
    }

    setError('');
    setIsSaving(true);

    const graphJson = {
      nodes: flowDefinition.nodes,
      edges: flowDefinition.edges,
      variables: flowDefinition.variables,
    };

    const payload = {
      name: name.trim(),
      graph_json: graphJson,
      description: description.trim() || undefined,
    };

    if (flowId) {
      updateMutation.mutate(payload);
    } else {
      createMutation.mutate(payload);
    }
  };

  if (flowId && isLoadingFlow) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="flex items-center gap-1 text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft size={20} />
            <span>返回</span>
          </button>
          <div className="h-6 w-px bg-gray-300" />
          <h2 className="text-lg font-semibold text-gray-900">
            {flowId ? '编辑测试流程' : '创建测试流程'}
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? '保存中...' : flowId ? '保存更改' : '创建流程'}
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mx-6 mt-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* 流程基本信息 */}
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <div className="flex gap-6">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              流程名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="输入流程名称"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="可选的流程描述"
            />
          </div>
        </div>
      </div>

      {/* 可视化流程设计器 */}
      <div className="flex-1 p-6 bg-gray-100 overflow-hidden">
        {flowDefinition && (
          <DAGFlowDesigner
            initialFlow={flowDefinition}
            onChange={handleFlowChange}
            testCases={testCases}
          />
        )}
      </div>
    </div>
  );
}

export default function TestFlowsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [viewMode, setViewMode] = useState<'list' | 'create' | 'edit'>('list');
  const [editingFlowId, setEditingFlowId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['testFlows', projectId],
    queryFn: () => testFlowsApi.list(projectId!, 1, 50),
    enabled: !!projectId,
    refetchOnMount: 'always',
  });

  const deleteMutation = useMutation({
    mutationFn: (flowId: string) => testFlowsApi.update(flowId, { status: 'archived' } as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testFlows', projectId] });
    },
  });

  const flows = data?.data?.items || [];

  const statusLabels: Record<string, string> = {
    active: '启用',
    draft: '草稿',
    archived: '已归档',
  };

  // 打开创建页面
  const handleCreate = () => {
    setEditingFlowId(null);
    setViewMode('create');
  };

  // 打开编辑页面
  const handleEdit = (flowId: string) => {
    setEditingFlowId(flowId);
    setViewMode('edit');
  };

  // 返回列表
  const handleBack = () => {
    setViewMode('list');
    setEditingFlowId(null);
  };

  // 渲染设计器页面
  if (viewMode === 'create' || viewMode === 'edit') {
    return (
      <FlowDesignerPage
        projectId={projectId!}
        flowId={editingFlowId || undefined}
        onBack={handleBack}
      />
    );
  }

  // 渲染列表页面
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">测试流程</h2>
          <p className="text-sm text-gray-500">使用可视化设计器创建和管理测试执行流程</p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={18} />
          <span>新建流程</span>
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : flows.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <GitBranch size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无测试流程</h3>
          <p className="text-gray-500 mb-6">使用可视化设计器创建您的第一个测试流程</p>
          <button
            onClick={handleCreate}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            创建流程
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {flows.map((flow: any) => (
            <div
              key={flow.id}
              className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg hover:border-blue-300 transition-all"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                  <GitBranch size={20} className="text-purple-600" />
                </div>
                <div className="flex items-center gap-1">
                  <Link
                    to={`/projects/${projectId}/runs?flow=${flow.id}`}
                    className="p-1.5 hover:bg-green-100 rounded text-gray-400 hover:text-green-600"
                    title="执行流程"
                  >
                    <Play size={16} />
                  </Link>
                  <button
                    onClick={() => handleEdit(flow.id)}
                    className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-blue-600"
                    title="编辑"
                  >
                    <Edit size={16} />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(flow.id)}
                    className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-red-600"
                    title="删除"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">{flow.name}</h3>
              <p className="text-sm text-gray-500 mb-4 line-clamp-2">
                {flow.description || '暂无描述'}
              </p>
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span className={`px-2 py-1 rounded-full ${
                  flow.status === 'active' ? 'bg-green-100 text-green-700' :
                  flow.status === 'draft' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {statusLabels[flow.status] || flow.status}
                </span>
                <span>{new Date(flow.updated_at).toLocaleDateString('zh-CN')}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
