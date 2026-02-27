import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import {
  Play,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Code,
  Copy,
  Check,
  Square,
  Diamond,
  Hexagon,
  GitBranch,
  X,
  Move,
  Layers
} from 'lucide-react';

// ============ 类型定义 ============

interface Position {
  x: number;
  y: number;
}

interface FlowNode {
  id: string;
  type: 'start' | 'end' | 'test_case' | 'condition' | 'parallel' | 'group';
  label: string;
  position: Position;
  data?: {
    testCaseId?: string;
    condition?: string;
    description?: string;
    timeout?: number;
    retries?: number;
    onFailure?: 'stop' | 'continue' | 'skip_children';
  };
}

interface FlowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string; // 用于条件分支
}

interface FlowDefinition {
  name: string;
  description?: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
  variables?: Record<string, string>;
}

// ============ 常量 ============

const NODE_TYPES = {
  start: { label: '开始', icon: Play, color: 'green', shape: 'circle' },
  end: { label: '结束', icon: Square, color: 'red', shape: 'circle' },
  test_case: { label: '测试用例', icon: Layers, color: 'blue', shape: 'rectangle' },
  condition: { label: '条件分支', icon: Diamond, color: 'yellow', shape: 'diamond' },
  parallel: { label: '并行执行', icon: GitBranch, color: 'purple', shape: 'hexagon' },
  group: { label: '用例组', icon: Hexagon, color: 'gray', shape: 'rectangle' },
};

const GRID_SIZE = 20;
const NODE_WIDTH = 160;
const NODE_HEIGHT = 60;

// ============ 工具函数 ============

const generateId = () => `node_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
const generateEdgeId = () => `edge_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;

const snapToGrid = (value: number) => Math.round(value / GRID_SIZE) * GRID_SIZE;

// ============ 节点组件 ============

function FlowNodeComponent({
  node,
  isSelected,
  isConnecting,
  onSelect,
  onMove,
  onStartConnect,
  onEndConnect,
  onDelete,
  onEdit,
}: {
  node: FlowNode;
  isSelected: boolean;
  isConnecting: boolean;
  onSelect: () => void;
  onMove: (position: Position) => void;
  onStartConnect: () => void;
  onEndConnect: () => void;
  onDelete: () => void;
  onEdit: () => void;
}) {
  const nodeType = NODE_TYPES[node.type];
  const Icon = nodeType.icon;
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<Position | null>(null);
  const deleteRef = useRef<HTMLButtonElement>(null);
  const connectOutRef = useRef<HTMLDivElement>(null);
  const connectInRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    e.stopPropagation();

    // If mousedown is on delete button or connect handles, do NOT start drag or select
    const target = e.target as HTMLElement;
    if (deleteRef.current?.contains(target)) return;
    if (connectOutRef.current?.contains(target)) return;
    if (connectInRef.current?.contains(target)) return;

    onSelect();
    setIsDragging(true);
    setDragStart({ x: e.clientX - node.position.x, y: e.clientY - node.position.y });
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    // If click is on delete button or connect handles, do nothing here
    const target = e.target as HTMLElement;
    if (deleteRef.current?.contains(target)) return;
    if (connectOutRef.current?.contains(target)) return;
    if (connectInRef.current?.contains(target)) return;

    onSelect();
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !dragStart) return;
    const newX = snapToGrid(e.clientX - dragStart.x);
    const newY = snapToGrid(e.clientY - dragStart.y);
    onMove({ x: newX, y: newY });
  }, [isDragging, dragStart, onMove]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setDragStart(null);
  }, []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const getShapeClasses = () => {
    const base = `absolute flex items-center justify-center transition-all cursor-move select-none`;
    const selected = isSelected ? 'ring-2 ring-blue-500 ring-offset-2' : '';
    const connecting = isConnecting ? 'ring-2 ring-green-500 animate-pulse' : '';
    
    switch (node.type) {
      case 'start':
      case 'end':
        return `${base} ${selected} ${connecting} w-12 h-12 rounded-full bg-${nodeType.color}-500 text-white`;
      case 'condition':
        return `${base} ${selected} ${connecting} w-40 h-16 bg-${nodeType.color}-100 border-2 border-${nodeType.color}-500 rotate-0`;
      default:
        return `${base} ${selected} ${connecting} w-40 h-14 rounded-lg bg-white border-2 border-${nodeType.color}-500 shadow-sm`;
    }
  };

  return (
    <div
      className={getShapeClasses()}
      style={{
        left: node.position.x,
        top: node.position.y,
        zIndex: isSelected ? 10 : 1,
      }}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onDoubleClick={(e) => { e.stopPropagation(); onEdit(); }}
    >
      {/* 节点内容 */}
      {node.type === 'start' || node.type === 'end' ? (
        <Icon size={20} />
      ) : (
        <div className="flex items-center gap-2 px-3 w-full">
          <Icon size={16} className={`text-${nodeType.color}-600 flex-shrink-0`} />
          <span className="text-sm font-medium text-gray-800 truncate flex-1">
            {node.label}
          </span>
        </div>
      )}

      {/* 连接点 */}
      {isSelected && (
        <>
          {/* 输出连接点 (右侧) */}
          <div
            ref={connectOutRef}
            className="absolute w-4 h-4 bg-blue-500 rounded-full cursor-crosshair hover:bg-blue-600 hover:scale-125 transition-transform"
            style={{ 
              right: node.type === 'start' || node.type === 'end' ? -6 : -8, 
              top: '50%', 
              transform: 'translateY(-50%)' 
            }}
            onMouseDown={(e) => {
              e.stopPropagation();
              setIsDragging(false);
              setDragStart(null);
              onStartConnect();
            }}
            title="拖拽创建连接"
          />
          {/* 输入连接点 (左侧) */}
          <div
            ref={connectInRef}
            className="absolute w-4 h-4 bg-green-500 rounded-full cursor-pointer hover:bg-green-600 hover:scale-125 transition-transform"
            style={{ 
              left: node.type === 'start' || node.type === 'end' ? -6 : -8, 
              top: '50%', 
              transform: 'translateY(-50%)' 
            }}
            onMouseUp={(e) => {
              e.stopPropagation();
              onEndConnect();
            }}
            title="连接到此节点"
          />
        </>
      )}

      {/* 删除按钮 */}
      {isSelected && node.type !== 'start' && node.type !== 'end' && (
        <button
          ref={deleteRef}
          className="absolute -top-3 -right-3 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600 z-50"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}

// ============ 连线组件 ============

function FlowEdgeComponent({
  edge,
  sourceNode,
  targetNode,
  isSelected,
  onSelect,
  onDelete,
}: {
  edge: FlowEdge;
  sourceNode: FlowNode;
  targetNode: FlowNode;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  // 计算节点边缘连接点
  const getNodeEdge = (node: FlowNode, direction: 'left' | 'right') => {
    const w = node.type === 'start' || node.type === 'end' ? 48 : NODE_WIDTH;
    const h = node.type === 'start' || node.type === 'end' ? 48 : NODE_HEIGHT;
    return {
      x: node.position.x + (direction === 'right' ? w : 0),
      y: node.position.y + h / 2,
    };
  };

  const source = getNodeEdge(sourceNode, 'right');
  const target = getNodeEdge(targetNode, 'left');

  // 计算贝塞尔曲线控制点
  const dx = target.x - source.x;
  const controlOffset = Math.min(Math.abs(dx) / 2, 100);

  const pathD = `M ${source.x} ${source.y} C ${source.x + controlOffset} ${source.y}, ${target.x - controlOffset} ${target.y}, ${target.x} ${target.y}`;

  // 箭头位置
  const midX = (source.x + target.x) / 2;
  const midY = (source.y + target.y) / 2;

  return (
    <g
      onClick={(e) => {
        // Prevent canvas click from clearing selection when selecting an edge.
        e.stopPropagation();
        onSelect();
      }}
      className="cursor-pointer"
    >
      {/* 可点击区域 (更宽) */}
      <path
        d={pathD}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
      />
      {/* 实际线条 */}
      <path
        d={pathD}
        fill="none"
        stroke={isSelected ? '#3B82F6' : '#9CA3AF'}
        strokeWidth={isSelected ? 3 : 2}
        markerEnd="url(#arrowhead)"
        className="transition-colors"
      />
      {/* 标签 */}
      {edge.label && (
        <text
          x={midX}
          y={midY - 10}
          textAnchor="middle"
          className="text-xs fill-gray-600"
        >
          {edge.label}
        </text>
      )}
      {/* 删除按钮 */}
      {isSelected && (
        <g
          transform={`translate(${midX - 12}, ${midY - 12})`}
          onPointerDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onPointerUp={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onClick={(e) => {
            // Ensure delete click isn't swallowed by parent selection handler
            e.preventDefault();
            e.stopPropagation();
            onDelete();
          }}
          style={{ pointerEvents: 'all' }}
          className="cursor-pointer"
        >
          {/* larger hit area */}
          <rect x={0} y={0} width={24} height={24} fill="transparent" />
          <circle r={10} cx={12} cy={12} fill="#EF4444" />
          <text x={12} y={16} textAnchor="middle" fill="white" fontSize={14}>×</text>
        </g>
      )}
    </g>
  );
}

// ============ 节点编辑弹窗 ============

function NodeEditModal({
  node,
  onSave,
  onClose,
  testCases,
}: {
  node: FlowNode;
  onSave: (node: FlowNode) => void;
  onClose: () => void;
  testCases: Array<{ id: string; name: string }>;
}) {
  const [editedNode, setEditedNode] = useState<FlowNode>({ ...node });

  const handleSave = () => {
    onSave(editedNode);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">编辑节点</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">节点名称</label>
            <input
              type="text"
              value={editedNode.label}
              onChange={(e) => setEditedNode({ ...editedNode, label: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {editedNode.type === 'test_case' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">关联测试用例</label>
              <select
                value={editedNode.data?.testCaseId || ''}
                onChange={(e) => setEditedNode({
                  ...editedNode,
                  data: { ...editedNode.data, testCaseId: e.target.value }
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- 选择用例 --</option>
                {testCases.map(tc => (
                  <option key={tc.id} value={tc.id}>{tc.name}</option>
                ))}
              </select>
            </div>
          )}

          {editedNode.type === 'condition' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">条件表达式</label>
              <input
                type="text"
                value={editedNode.data?.condition || ''}
                onChange={(e) => setEditedNode({
                  ...editedNode,
                  data: { ...editedNode.data, condition: e.target.value }
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm"
                placeholder="${result} == 'success'"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            <textarea
              value={editedNode.data?.description || ''}
              onChange={(e) => setEditedNode({
                ...editedNode,
                data: { ...editedNode.data, description: e.target.value }
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              rows={2}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">超时 (秒)</label>
              <input
                type="number"
                value={editedNode.data?.timeout || ''}
                onChange={(e) => setEditedNode({
                  ...editedNode,
                  data: { ...editedNode.data, timeout: e.target.value ? parseInt(e.target.value) : undefined }
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="300"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">失败时</label>
              <select
                value={editedNode.data?.onFailure || 'stop'}
                onChange={(e) => setEditedNode({
                  ...editedNode,
                  data: { ...editedNode.data, onFailure: e.target.value as any }
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="stop">停止执行</option>
                <option value="continue">继续执行</option>
                <option value="skip_children">跳过子节点</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

// ============ 主组件 ============

export default function DAGFlowDesigner({
  initialFlow,
  onChange,
  testCases = [],
}: {
  initialFlow?: FlowDefinition;
  onChange?: (flow: FlowDefinition) => void;
  testCases?: Array<{ id: string; name: string }>;
}) {
  const [flow, setFlow] = useState<FlowDefinition>(initialFlow || {
    name: '新测试流程',
    nodes: [
      { id: 'start', type: 'start', label: '开始', position: { x: 100, y: 200 } },
      { id: 'end', type: 'end', label: '结束', position: { x: 600, y: 200 } },
    ],
    edges: [],
  });

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [connectingFrom, setConnectingFrom] = useState<string | null>(null);
  const [connectingToPos, setConnectingToPos] = useState<Position | null>(null);
  const [editingNode, setEditingNode] = useState<FlowNode | null>(null);
  const [viewMode, setViewMode] = useState<'design' | 'code'>('design');
  const [zoom, setZoom] = useState(1);
  const [copied, setCopied] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);

  const canvasRef = useRef<HTMLDivElement>(null);

  const getNodeCenter = useCallback((nodeId: string): Position | null => {
    const n = flow.nodes.find(x => x.id === nodeId);
    if (!n) return null;
    const w = n.type === 'start' || n.type === 'end' ? 48 : NODE_WIDTH;
    const h = n.type === 'start' || n.type === 'end' ? 48 : NODE_HEIGHT;
    return { x: n.position.x + w / 2, y: n.position.y + h / 2 };
  }, [flow.nodes]);

  const getMousePosInCanvas = useCallback((e: MouseEvent | ReactMouseEvent, canvas: HTMLDivElement) => {
    const rect = canvas.getBoundingClientRect();
    const clientX = 'clientX' in e ? e.clientX : 0;
    const clientY = 'clientY' in e ? e.clientY : 0;
    return {
      x: (clientX - rect.left) / zoom,
      y: (clientY - rect.top) / zoom,
    };
  }, [zoom]);

  // 更新流程
  const updateFlow = useCallback((updates: Partial<FlowDefinition>) => {
    const updated = { ...flow, ...updates };
    setFlow(updated);
    onChange?.(updated);
  }, [flow, onChange]);

  // 添加节点
  const addNode = useCallback((type: FlowNode['type']) => {
    const newNode: FlowNode = {
      id: generateId(),
      type,
      label: NODE_TYPES[type].label,
      position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
      data: {},
    };
    updateFlow({ nodes: [...flow.nodes, newNode] });
    setSelectedNodeId(newNode.id);
  }, [flow.nodes, updateFlow]);

  // 更新节点
  const updateNode = useCallback((nodeId: string, updates: Partial<FlowNode>) => {
    updateFlow({
      nodes: flow.nodes.map(n => n.id === nodeId ? { ...n, ...updates } : n)
    });
  }, [flow.nodes, updateFlow]);

  // 删除节点
  const deleteNode = useCallback((nodeId: string) => {
    if (nodeId === 'start' || nodeId === 'end') return;
    setConnectingFrom(null);
    setConnectingToPos(null);
    updateFlow({
      nodes: flow.nodes.filter(n => n.id !== nodeId),
      edges: flow.edges.filter(e => e.source !== nodeId && e.target !== nodeId),
    });
    setSelectedNodeId(null);
  }, [flow.edges, flow.nodes, updateFlow]);

  // 删除连线
  const deleteEdge = useCallback((edgeId: string) => {
    setConnectingFrom(null);
    setConnectingToPos(null);
    updateFlow({ edges: flow.edges.filter(e => e.id !== edgeId) });
    setSelectedEdgeId(null);
  }, [flow.edges, updateFlow]);

  // 添加连线
  const addEdge = useCallback((source: string, target: string) => {
    if (source === target) return;

    // 查找源节点和目标节点
    const sourceNode = flow.nodes.find(n => n.id === source);
    const targetNode = flow.nodes.find(n => n.id === target);
    if (!sourceNode || !targetNode) return;

    // 规则：不允许从"结束"节点发出连线
    if (sourceNode.type === 'end') {
      setWarning('结束节点不能作为连线起点');
      setTimeout(() => setWarning(null), 2000);
      return;
    }

    // 规则：不允许连入"开始"节点
    if (targetNode.type === 'start') {
      setWarning('开始节点不能作为连线终点');
      setTimeout(() => setWarning(null), 2000);
      return;
    }

    // 规则：开始和结束之间不能直接连线
    if (sourceNode.type === 'start' && targetNode.type === 'end') {
      setWarning('开始和结束之间不能直接连线，请添加测试用例节点');
      setTimeout(() => setWarning(null), 2000);
      return;
    }

    const exists = flow.edges.some(e => e.source === source && e.target === target);
    if (exists) {
      setWarning('该连线已存在');
      setTimeout(() => setWarning(null), 2000);
      return;
    }

    const newEdge: FlowEdge = {
      id: generateEdgeId(),
      source,
      target,
    };
    updateFlow({ edges: [...flow.edges, newEdge] });
  }, [flow.nodes, flow.edges, updateFlow]);

  // 开始连接
  const startConnect = useCallback((nodeId: string) => {
    setConnectingFrom(nodeId);
    setConnectingToPos(null);
  }, []);

  // 结束连接
  const endConnect = useCallback((targetId: string) => {
    if (connectingFrom && connectingFrom !== targetId) {
      addEdge(connectingFrom, targetId);
    }
    setConnectingFrom(null);
    setConnectingToPos(null);
  }, [connectingFrom, addEdge]);

  const cancelConnect = useCallback(() => {
    setConnectingFrom(null);
    setConnectingToPos(null);
  }, []);

  useEffect(() => {
    if (!connectingFrom) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onMove = (evt: MouseEvent) => {
      setConnectingToPos(getMousePosInCanvas(evt, canvas));
    };
    const onKeyDown = (evt: KeyboardEvent) => {
      if (evt.key === 'Escape') cancelConnect();
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [connectingFrom, cancelConnect, getMousePosInCanvas]);

  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    // Clicking blank canvas clears selection; when connecting, it cancels connect.
    if (e.target !== e.currentTarget) return;
    if (connectingFrom) {
      cancelConnect();
      return;
    }
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, [connectingFrom, cancelConnect]);

  const flowJson = useMemo(() => {
    const output = {
      name: flow.name,
      description: flow.description,
      nodes: flow.nodes.map(({ id, type, label, position, data }) => ({
        id, type, label, position,
        ...(data && Object.keys(data).length > 0 ? { data } : {}),
      })),
      edges: flow.edges.map(({ id, source, target, label, condition }) => ({
        id, source, target,
        ...(label ? { label } : {}),
        ...(condition ? { condition } : {}),
      })),
      ...(flow.variables && Object.keys(flow.variables).length > 0 ? { variables: flow.variables } : {}),
    };
    return JSON.stringify(output, null, 2);
  }, [flow]);

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(flowJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleZoom = (delta: number) => {
    setZoom(z => Math.min(Math.max(z + delta, 0.5), 2));
  };

  return (
    <div className="h-full flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-4">
          <div className="flex bg-gray-200 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('design')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'design' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600'
              }`}
            >
              <Move size={16} className="inline mr-1.5" />
              设计
            </button>
            <button
              onClick={() => setViewMode('code')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'code' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600'
              }`}
            >
              <Code size={16} className="inline mr-1.5" />
              代码
            </button>
          </div>

          {viewMode === 'design' && (
            <div className="flex items-center gap-1 ml-4">
              <span className="text-sm text-gray-500 mr-2">添加节点:</span>
              {(['test_case', 'condition', 'parallel', 'group'] as const).map(type => {
                const nodeType = NODE_TYPES[type];
                const Icon = nodeType.icon;
                return (
                  <button
                    key={type}
                    onClick={() => addNode(type)}
                    className={`p-2 rounded-lg border border-gray-200 hover:bg-${nodeType.color}-50 hover:border-${nodeType.color}-300 transition-colors`}
                    title={`添加${nodeType.label}`}
                  >
                    <Icon size={18} className={`text-${nodeType.color}-600`} />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {viewMode === 'design' && (
            <div className="flex items-center gap-1 mr-4">
              <button onClick={() => handleZoom(-0.1)} className="p-1.5 hover:bg-gray-200 rounded">
                <ZoomOut size={18} />
              </button>
              <span className="text-sm text-gray-600 w-12 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => handleZoom(0.1)} className="p-1.5 hover:bg-gray-200 rounded">
                <ZoomIn size={18} />
              </button>
              <button onClick={() => setZoom(1)} className="p-1.5 hover:bg-gray-200 rounded" title="重置">
                <Maximize2 size={18} />
              </button>
            </div>
          )}

          <button
            onClick={copyToClipboard}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-100"
          >
            {copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {viewMode === 'design' ? (
          <div
            ref={canvasRef}
            className="w-full h-full relative bg-gray-50 overflow-auto"
            style={{
              backgroundImage: 'radial-gradient(circle, #ddd 1px, transparent 1px)',
              backgroundSize: `${GRID_SIZE}px ${GRID_SIZE}px`,
            }}
            onClick={handleCanvasClick}
          >
            <svg
              className="absolute inset-0 pointer-events-none"
              style={{
                width: '100%',
                height: '100%',
                transform: `scale(${zoom})`,
                transformOrigin: 'top left',
              }}
            >
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="10"
                  markerHeight="7"
                  refX="9"
                  refY="3.5"
                  orient="auto"
                >
                  <polygon points="0 0, 10 3.5, 0 7" fill="#9CA3AF" />
                </marker>
              </defs>
              <g className="pointer-events-auto">
                {flow.edges.map(edge => {
                  const sourceNode = flow.nodes.find(n => n.id === edge.source);
                  const targetNode = flow.nodes.find(n => n.id === edge.target);
                  if (!sourceNode || !targetNode) return null;
                  return (
                    <FlowEdgeComponent
                      key={edge.id}
                      edge={edge}
                      sourceNode={sourceNode}
                      targetNode={targetNode}
                      isSelected={selectedEdgeId === edge.id}
                      onSelect={() => { setSelectedEdgeId(edge.id); setSelectedNodeId(null); }}
                      onDelete={() => deleteEdge(edge.id)}
                    />
                  );
                })}
              </g>

              {connectingFrom && (
                (() => {
                  const from = getNodeCenter(connectingFrom);
                  const to = connectingToPos;
                  if (!from || !to) return null;
                  const dx = to.x - from.x;
                  const controlOffset = Math.min(Math.abs(dx) / 2, 120);
                  const d = `M ${from.x} ${from.y} C ${from.x + controlOffset} ${from.y}, ${to.x - controlOffset} ${to.y}, ${to.x} ${to.y}`;
                  return (
                    <path
                      d={d}
                      fill="none"
                      stroke="#2563EB"
                      strokeWidth={2}
                      strokeDasharray="6 6"
                      opacity={0.9}
                    />
                  );
                })()
              )}
            </svg>

            <div
              style={{
                transform: `scale(${zoom})`,
                transformOrigin: 'top left',
                width: '2000px',
                height: '1000px',
              }}
              onClick={(e) => {
                if (e.target === e.currentTarget) return;
                e.stopPropagation();
              }}
            >
              {flow.nodes.map(node => (
                <FlowNodeComponent
                  key={node.id}
                  node={node}
                  isSelected={selectedNodeId === node.id}
                  isConnecting={connectingFrom !== null && connectingFrom !== node.id}
                  onSelect={() => {
                    // Only treat a node click as "complete connection" when user is in connect mode.
                    // Otherwise, normal select should work (so delete button can show).
                    if (connectingFrom) {
                      if (connectingFrom !== node.id) endConnect(node.id);
                      return;
                    }
                    setSelectedNodeId(node.id);
                    setSelectedEdgeId(null);
                  }}
                  onMove={(pos) => updateNode(node.id, { position: pos })}
                  onStartConnect={() => startConnect(node.id)}
                  onEndConnect={() => endConnect(node.id)}
                  onDelete={() => deleteNode(node.id)}
                  onEdit={() => setEditingNode(node)}
                />
              ))}
            </div>

            {connectingFrom && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm shadow-lg">
                连线中：点击目标节点完成连接，按 ESC 或点击空白处取消
              </div>
            )}

            {/* 非法连线警告提示 */}
            {warning && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm shadow-lg animate-pulse">
                {warning}
              </div>
            )}
          </div>
        ) : (
          <div className="h-full">
            <pre className="h-full p-4 bg-gray-900 text-gray-100 text-sm font-mono overflow-auto">
              {flowJson}
            </pre>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200 bg-gray-50 text-sm text-gray-600">
        <div className="flex items-center gap-4">
          <span>节点: {flow.nodes.length}</span>
          <span>连线: {flow.edges.length}</span>
        </div>
        <div>
          {selectedNodeId && <span>已选中: {flow.nodes.find(n => n.id === selectedNodeId)?.label}</span>}
        </div>
      </div>

      {editingNode && (
        <NodeEditModal
          node={editingNode}
          testCases={testCases}
          onSave={(updated) => updateNode(updated.id, updated)}
          onClose={() => setEditingNode(null)}
        />
      )}
    </div>
  );
}
