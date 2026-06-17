// filepath: d:\project\nanotest\apps\web\src\components\AIStepPreviewModal.tsx
import { useState } from 'react';
import ReactDOM from 'react-dom';
import {
  Check,
  X,
  Sparkles,
  MousePointer2,
  Type,
  ArrowUpDown,
  Clock,
  CheckCircle,
  Camera,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

// ============ Types ============

interface AIStep {
  type: string;
  selector?: { strategy: string; value: string };
  text?: string;
  clearFirst?: boolean;
  direction?: string;
  duration?: number;
  condition?: string;
  expected?: string;
  description?: string;
  fullPage?: boolean;
}

interface AIGenerateResult {
  success: boolean;
  test_name?: string;
  description?: string;
  steps: AIStep[];
  confidence: number;
  notes?: string;
  model?: string;
  latency_ms: number;
  error?: string;
}

interface AIStepPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: AIGenerateResult;
  onConfirm: (steps: AIStep[], testName?: string) => void;
}

// ============ Constants ============

const TYPE_CONFIG: Record<string, { label: string; icon: any; color: string }> = {
  tap: { label: '点击', icon: MousePointer2, color: 'text-blue-600 bg-blue-100' },
  type: { label: '输入', icon: Type, color: 'text-green-600 bg-green-100' },
  scroll: { label: '滚动', icon: ArrowUpDown, color: 'text-indigo-600 bg-indigo-100' },
  swipe: { label: '滑动', icon: ArrowUpDown, color: 'text-purple-600 bg-purple-100' },
  wait: { label: '等待', icon: Clock, color: 'text-yellow-600 bg-yellow-100' },
  assert: { label: '断言', icon: CheckCircle, color: 'text-red-600 bg-red-100' },
  screenshot: { label: '截图', icon: Camera, color: 'text-pink-600 bg-pink-100' },
  back: { label: '返回', icon: ArrowUpDown, color: 'text-gray-600 bg-gray-100' },
};

// ============ Step Card ============

function StepPreviewCard({
  step,
  index,
  checked,
  onToggle,
}: {
  step: AIStep;
  index: number;
  checked: boolean;
  onToggle: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const config = TYPE_CONFIG[step.type] || TYPE_CONFIG.tap;
  const Icon = config.icon;

  const getSummary = () => {
    switch (step.type) {
      case 'tap':
        return step.selector?.value ? `点击 ${step.selector.value.split('/').pop() || step.selector.value}` : '点击元素';
      case 'type':
        return step.text ? `输入 "${step.text.substring(0, 30)}${step.text.length > 30 ? '...' : ''}"` : '输入文本';
      case 'scroll':
        return `向${step.direction || '下'}滚动`;
      case 'swipe':
        return `向${step.direction || '上'}滑动`;
      case 'wait':
        return step.condition ? `等待元素${step.condition}` : `等待 ${step.duration || 1000}ms`;
      case 'assert':
        return `断言: ${step.condition}${step.expected ? ` = "${step.expected}"` : ''}`;
      case 'screenshot':
        return '截取屏幕截图';
      case 'back':
        return '返回上一页';
      default:
        return step.description || step.type;
    }
  };

  return (
    <div className={`border rounded-lg transition-all ${checked ? 'border-blue-300 bg-white' : 'border-gray-200 bg-gray-50 opacity-60'}`}>
      <div className="flex items-center gap-2 px-3 py-2 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => { e.stopPropagation(); onToggle(); }}
          onClick={(e) => e.stopPropagation()}
          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <div className={`w-6 h-6 rounded flex items-center justify-center ${config.color}`}>
          <Icon size={14} />
        </div>
        <span className="text-xs font-medium text-gray-400">#{index + 1}</span>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-gray-800">{config.label}</span>
          <span className="text-sm text-gray-500 ml-2 truncate">{getSummary()}</span>
        </div>
        {expanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
      </div>

      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-gray-100 space-y-1.5">
          {step.description && (
            <div className="text-xs text-gray-600">
              <span className="text-gray-400">说明：</span>{step.description}
            </div>
          )}
          {step.selector && (
            <div className="text-xs font-mono text-gray-500">
              <span className="text-gray-400">定位：</span>
              <span className="bg-gray-100 px-1.5 py-0.5 rounded">{step.selector.strategy}</span>
              <span className="ml-1">{step.selector.value}</span>
            </div>
          )}
          {step.text && step.type !== 'type' && (
            <div className="text-xs text-gray-500">
              <span className="text-gray-400">值：</span>{step.text}
            </div>
          )}
          {step.expected && (
            <div className="text-xs text-gray-500">
              <span className="text-gray-400">期望：</span>{step.expected}
            </div>
          )}
          {step.duration != null && step.type === 'wait' && (
            <div className="text-xs text-gray-500">
              <span className="text-gray-400">时长：</span>{step.duration}ms
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============ Main Component ============

export default function AIStepPreviewModal({ isOpen, onClose, result, onConfirm }: AIStepPreviewModalProps) {
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(
    new Set(result.steps.map((_, i) => i))
  );
  const [testName, setTestName] = useState(result.test_name || '');

  const handleToggle = (index: number) => {
    const next = new Set(selectedIndices);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    setSelectedIndices(next);
  };

  const handleSelectAll = () => {
    if (selectedIndices.size === result.steps.length) {
      setSelectedIndices(new Set());
    } else {
      setSelectedIndices(new Set(result.steps.map((_, i) => i)));
    }
  };

  const handleConfirm = () => {
    const selected = result.steps
      .filter((_, i) => selectedIndices.has(i))
      .map((step) => ({ ...step, id: `step_${Date.now()}_${Math.random().toString(36).substr(2, 6)}` }));
    onConfirm(selected, testName || undefined);
  };

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.3)' }} onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles size={20} className="text-purple-600" />
            <div>
              <h3 className="font-semibold text-gray-900">AI 生成的测试步骤</h3>
              <div className="text-xs text-gray-500 flex items-center gap-3 mt-0.5">
                <span>共 {result.steps.length} 个步骤</span>
                <span>置信度 {Math.round(result.confidence * 100)}%</span>
                {result.model && <span>模型: {result.model}</span>}
                <span>耗时 {result.latency_ms}ms</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded text-gray-400">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-5 space-y-4">
          {/* Test name input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">用例名称</label>
            <input
              type="text"
              value={testName}
              onChange={(e) => setTestName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
              placeholder="输入测试用例名称"
            />
          </div>

          {/* Notes */}
          {result.notes && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
              <span className="font-medium">AI 备注：</span> {result.notes}
            </div>
          )}

          {/* Select all */}
          <div className="flex items-center justify-between">
            <button
              onClick={handleSelectAll}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {selectedIndices.size === result.steps.length ? '取消全选' : '全选'}
            </button>
            <span className="text-xs text-gray-500">
              已选择 {selectedIndices.size}/{result.steps.length}
            </span>
          </div>

          {/* Steps list */}
          <div className="space-y-2">
            {result.steps.map((step, i) => (
              <StepPreviewCard
                key={i}
                step={step}
                index={i}
                checked={selectedIndices.has(i)}
                onToggle={() => handleToggle(i)}
              />
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-gray-200 flex items-center justify-between bg-gray-50">
          <div className="text-xs text-gray-500">
            确认后将加载到步骤编辑器中
          </div>
          <div className="flex gap-3">
            <button onClick={onClose} className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 text-sm">
              取消
            </button>
            <button
              onClick={handleConfirm}
              disabled={selectedIndices.size === 0}
              className="px-5 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm flex items-center gap-2"
            >
              <Check size={16} />
              添加 {selectedIndices.size} 个步骤
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

export type { AIGenerateResult, AIStep };
