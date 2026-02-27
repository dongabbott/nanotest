import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { 
  Plus, 
  Trash2, 
  GripVertical, 
  ChevronDown, 
  ChevronRight,
  Eye,
  Code,
  Copy,
  Check,
  AlertCircle,
  Smartphone,
  MousePointer,
  Type,
  Image,
  Clock,
  RotateCcw,
  Settings,
  Search,
  Wand2,
} from 'lucide-react';
import { dslApi } from '../services/api';

// DSL 步骤类型定义
interface DSLStep {
  id: string;
  action: string;
  target?: string;
  value?: string;
  expected?: string;
  timeout?: number;
  retries?: number;
  screenshot?: boolean;
  description?: string;
  conditions?: {
    if?: string;
    unless?: string;
  };
}

interface DSLTestCase {
  name: string;
  description?: string;
  tags?: string[];
  setup?: DSLStep[];
  steps: DSLStep[];
  teardown?: DSLStep[];
  variables?: Record<string, string>;
}

// 可用的动作类型
const ACTION_TYPES = [
  { value: 'tap', label: '点击', icon: MousePointer, category: 'interaction' },
  { value: 'long_press', label: '长按', icon: MousePointer, category: 'interaction' },
  { value: 'double_tap', label: '双击', icon: MousePointer, category: 'interaction' },
  { value: 'swipe', label: '滑动', icon: Smartphone, category: 'interaction' },
  { value: 'scroll', label: '滚动', icon: Smartphone, category: 'interaction' },
  { value: 'tap_xy', label: '坐标点击', icon: MousePointer, category: 'interaction' },
  { value: 'input', label: '输入文本', icon: Type, category: 'input' },
  { value: 'clear', label: '清空输入', icon: Type, category: 'input' },
  { value: 'hide_keyboard', label: '隐藏键盘', icon: Smartphone, category: 'input' },
  { value: 'assert_visible', label: '断言可见', icon: Eye, category: 'assertion' },
  { value: 'assert_text', label: '断言文本', icon: Type, category: 'assertion' },
  { value: 'assert_contains', label: '断言包含', icon: Type, category: 'assertion' },
  { value: 'assert_exists', label: '断言存在', icon: Check, category: 'assertion' },
  { value: 'assert_not_exists', label: '断言不存在', icon: Check, category: 'assertion' },
  { value: 'wait', label: '等待', icon: Clock, category: 'control' },
  { value: 'wait_for', label: '等待元素', icon: Clock, category: 'control' },
  { value: 'wait_invisible', label: '等待消失', icon: Clock, category: 'control' },
  { value: 'screenshot', label: '截图', icon: Image, category: 'utility' },
  { value: 'back', label: '返回', icon: RotateCcw, category: 'navigation' },
  { value: 'home', label: '主页', icon: Smartphone, category: 'navigation' },
  { value: 'launch_app', label: '启动应用', icon: Smartphone, category: 'navigation' },
  { value: 'close_app', label: '关闭应用', icon: Smartphone, category: 'navigation' },
  { value: 'reset_app', label: '重启应用', icon: Smartphone, category: 'navigation' },
];

const ACTION_CATEGORIES = {
  interaction: { label: '交互操作', color: 'blue' },
  input: { label: '输入操作', color: 'green' },
  assertion: { label: '断言验证', color: 'purple' },
  control: { label: '流程控制', color: 'yellow' },
  navigation: { label: '导航操作', color: 'gray' },
  utility: { label: '工具操作', color: 'pink' },
};

// 生成唯一ID
const generateId = () => `step_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

type GeneratorMeta = {
  id: string;
  signature: string;
  description?: string;
  examples?: string[];
};

function insertAtCursor(input: HTMLInputElement | HTMLTextAreaElement, text: string) {
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? input.value.length;
  const next = input.value.slice(0, start) + text + input.value.slice(end);
  input.value = next;
  const pos = start + text.length;
  input.setSelectionRange(pos, pos);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

function GeneratorPicker({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (example: string) => void;
}) {
  const [q, setQ] = useState('');
  const [items, setItems] = useState<GeneratorMeta[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const res = await dslApi.listGenerators();
      setItems(res.data?.items || []);
      setLoaded(true);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || '加载生成器失败');
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    if (loaded) return;
    load();
  }, [open, loaded, load]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return items;
    return items.filter((it) => {
      const hay = `${it.id} ${it.signature} ${it.description || ''} ${(it.examples || []).join(' ')}`.toLowerCase();
      return hay.includes(query);
    });
  }, [q, items]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" onMouseDown={onClose}>
      <div
        className="bg-white w-full max-w-2xl rounded-xl border border-gray-200 shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <div className="font-semibold text-gray-900">插入内置生成器</div>
          <button className="text-gray-400 hover:text-gray-700" onClick={onClose} type="button">
            ×
          </button>
        </div>

        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="relative flex-1">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                placeholder="搜索：random_email / uuid / now..."
              />
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            </div>
            <button type="button" onClick={load} className="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
              刷新
            </button>
          </div>

          {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3">{error}</div>}

          <div className="max-h-[420px] overflow-auto space-y-2">
            {filtered.map((g) => (
              <div key={g.id} className="border border-gray-200 rounded-lg p-3 hover:bg-gray-50">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-sm text-gray-900">{g.signature}</div>
                    {g.description && <div className="text-xs text-gray-500 mt-1">{g.description}</div>}
                  </div>
                </div>
                {(g.examples || []).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(g.examples || []).map((ex) => (
                      <button
                        key={ex}
                        type="button"
                        onClick={() => onPick(ex)}
                        className="px-2 py-1 text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200 rounded hover:bg-blue-100"
                        title="点击插入"
                      >
                        {ex}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => navigator.clipboard.writeText((g.examples || [])[0] || '')}
                      className="px-2 py-1 text-xs border border-gray-300 rounded hover:bg-white"
                    >
                      复制示例
                    </button>
                  </div>
                )}
              </div>
            ))}

            {loaded && filtered.length === 0 && (
              <div className="text-sm text-gray-500 text-center py-10">未找到匹配的生成器</div>
            )}
          </div>

          <div className="text-xs text-gray-500 mt-3">
            语法：在输入值中使用 <code className="font-mono">${'{'}...{'}'}</code>，例如 <code className="font-mono">${'{'}random_email(){'}'}</code>。
          </div>
        </div>
      </div>
    </div>
  );
}

// 单个步骤编辑器
function StepEditor({
  step,
  index,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: {
  step: DSLStep;
  index: number;
  onUpdate: (step: DSLStep) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showGeneratorPicker, setShowGeneratorPicker] = useState(false);
  const valueInputRef = useRef<HTMLInputElement>(null);
  const expectedInputRef = useRef<HTMLInputElement>(null);
  const activeInputRef = useRef<HTMLInputElement | null>(null);

  const openPickerFor = (which: 'value' | 'expected') => {
    activeInputRef.current = which === 'value' ? valueInputRef.current : expectedInputRef.current;
    setShowGeneratorPicker(true);
  };

  const actionInfo = ACTION_TYPES.find(a => a.value === step.action);
  const ActionIcon = actionInfo?.icon || Settings;
  const categoryInfo = ACTION_CATEGORIES[actionInfo?.category as keyof typeof ACTION_CATEGORIES];

  const needsTarget = !['wait', 'screenshot', 'back', 'home', 'hide_keyboard', 'tap_xy', 'launch_app', 'close_app', 'reset_app'].includes(step.action);
  const needsValue = ['input', 'swipe', 'scroll', 'wait', 'tap_xy', 'wait_invisible'].includes(step.action);
  const needsExpected = ['assert_text', 'assert_contains'].includes(step.action);

  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden">
      {/* 步骤头部 */}
      <div 
        className="flex items-center gap-2 px-3 py-2 bg-gray-50 cursor-pointer hover:bg-gray-100"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <GripVertical size={16} className="text-gray-400 cursor-grab" />
        <span className="text-xs font-medium text-gray-400 w-6">#{index + 1}</span>
        
        <div className={`w-6 h-6 rounded flex items-center justify-center bg-${categoryInfo?.color || 'gray'}-100`}>
          <ActionIcon size={14} className={`text-${categoryInfo?.color || 'gray'}-600`} />
        </div>
        
        <span className="font-medium text-gray-900 flex-1">
          {actionInfo?.label || step.action}
          {step.description && (
            <span className="text-gray-500 font-normal ml-2">- {step.description}</span>
          )}
        </span>
        
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); onMoveUp(); }}
            disabled={isFirst}
            className="p-1 hover:bg-gray-200 rounded disabled:opacity-30"
            title="上移"
          >
            <ChevronDown size={14} className="rotate-180" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onMoveDown(); }}
            disabled={isLast}
            className="p-1 hover:bg-gray-200 rounded disabled:opacity-30"
            title="下移"
          >
            <ChevronDown size={14} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="p-1 hover:bg-red-100 rounded text-gray-400 hover:text-red-600"
            title="删除"
          >
            <Trash2 size={14} />
          </button>
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </div>

      {/* 步骤内容 */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* 动作类型 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">动作类型</label>
              <select
                value={step.action}
                onChange={(e) => onUpdate({ ...step, action: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
              >
                {Object.entries(ACTION_CATEGORIES).map(([catKey, catInfo]) => (
                  <optgroup key={catKey} label={catInfo.label}>
                    {ACTION_TYPES.filter(a => a.category === catKey).map(action => (
                      <option key={action.value} value={action.value}>
                        {action.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            {/* 描述 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">描述 (可选)</label>
              <input
                type="text"
                value={step.description || ''}
                onChange={(e) => onUpdate({ ...step, description: e.target.value || undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                placeholder="步骤描述"
              />
            </div>
          </div>

          {/* 目标选择器 */}
          {needsTarget && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                目标元素 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={step.target || ''}
                onChange={(e) => onUpdate({ ...step, target: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                placeholder="accessibility_id:login_button 或 xpath://button[@text='登录']"
              />
              <p className="text-xs text-gray-500 mt-1">
                支持: accessibility_id:, xpath:, id:, class:, text:
              </p>
            </div>
          )}

          {/* 输入值 */}
          {needsValue && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {step.action === 'wait' ? '等待时间 (秒)' : 
                 step.action === 'wait_invisible' ? '等待消失超时 (秒)' :
                 step.action === 'swipe' ? '滑动方向 (up/down/left/right)' :
                 step.action === 'scroll' ? '滚动方向 (up/down)' :
                 step.action === 'tap_xy' ? '点击坐标 (x,y)' : '输入值'}
              </label>
              <div className="relative">
                <input
                  ref={valueInputRef}
                  type={step.action === 'wait' || step.action === 'wait_invisible' ? 'number' : 'text'}
                  value={step.value || ''}
                  onChange={(e) => onUpdate({ ...step, value: e.target.value })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                  placeholder={
                    step.action === 'wait' ? '3' :
                    step.action === 'wait_invisible' ? '10' :
                    step.action === 'tap_xy' ? '200,450' :
                    step.action === 'swipe' ? 'up' :
                    step.action === 'scroll' ? 'down' :
                    '支持变量 ${username} / 内置生成器 ${random_email()} ${random_phone()} ${random_text(10)} ${uuid()} ${now(%Y%m%d)}'
                  }
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600"
                  title="插入内置生成器"
                  onClick={() => openPickerFor('value')}
                >
                  <Wand2 size={16} />
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                变量：${'{'}name{'}'}；内置：${'{'}random_email(){'}'}、${'{'}random_phone(){'}'}、${'{'}random_text(10){'}'}、${'{'}uuid(){'}'}、${'{'}now(%Y%m%d%H%M%S){'}'}
              </p>
            </div>
          )}

          {needsExpected && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {step.action === 'assert_text' ? '预期文本' : '应包含文本'}
              </label>
              <div className="relative">
                <input
                  ref={expectedInputRef}
                  type="text"
                  value={step.expected || ''}
                  onChange={(e) => onUpdate({ ...step, expected: e.target.value })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                  placeholder={step.action === 'assert_text' ? 'Hello' : '关键字'}
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600"
                  title="插入内置生成器"
                  onClick={() => openPickerFor('expected')}
                >
                  <Wand2 size={16} />
                </button>
              </div>
            </div>
          )}

          <GeneratorPicker
            open={showGeneratorPicker}
            onClose={() => setShowGeneratorPicker(false)}
            onPick={(example) => {
              const el = activeInputRef.current;
              if (el) {
                insertAtCursor(el, example);
                if (el === valueInputRef.current) onUpdate({ ...step, value: el.value });
                if (el === expectedInputRef.current) onUpdate({ ...step, expected: el.value });
              } else {
                // Fallback: append to value
                onUpdate({ ...step, value: (step.value || '') + example });
              }
              setShowGeneratorPicker(false);
            }}
          />

          {/* 高级选项 */}
          <div>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
            >
              <Settings size={14} />
              {showAdvanced ? '隐藏高级选项' : '显示高级选项'}
            </button>

            {showAdvanced && (
              <div className="mt-3 p-3 bg-gray-50 rounded-lg space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">超时 (秒)</label>
                    <input
                      type="number"
                      value={step.timeout || ''}
                      onChange={(e) => onUpdate({ ...step, timeout: e.target.value ? parseInt(e.target.value) : undefined })}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                      placeholder="30"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">重试次数</label>
                    <input
                      type="number"
                      value={step.retries || ''}
                      onChange={(e) => onUpdate({ ...step, retries: e.target.value ? parseInt(e.target.value) : undefined })}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                      placeholder="0"
                    />
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={step.screenshot || false}
                        onChange={(e) => onUpdate({ ...step, screenshot: e.target.checked || undefined })}
                        className="rounded border-gray-300"
                      />
                      执行后截图
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">条件执行 (if)</label>
                  <input
                    type="text"
                    value={step.conditions?.if || ''}
                    onChange={(e) => onUpdate({ 
                      ...step, 
                      conditions: { ...step.conditions, if: e.target.value || undefined }
                    })}
                    className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm font-mono"
                    placeholder="${platform} == 'android'"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// 主编辑器组件
export default function DSLEditor({
  initialValue,
  onChange,
  onValidate,
}: {
  initialValue?: DSLTestCase;
  onChange?: (dsl: DSLTestCase) => void;
  onValidate?: (dsl: DSLTestCase) => Promise<{ valid: boolean; errors?: string[] }>;
}) {
  const [testCase, setTestCase] = useState<DSLTestCase>(initialValue || {
    name: '新测试用例',
    description: '',
    tags: [],
    steps: [],
    variables: {},
  });
  
  const [activeTab, setActiveTab] = useState<'visual' | 'code'>('visual');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [newVarKey, setNewVarKey] = useState('');
  const [newVarValue, setNewVarValue] = useState('');

  // 更新测试用例
  const updateTestCase = useCallback((updates: Partial<DSLTestCase>) => {
    const updated = { ...testCase, ...updates };
    setTestCase(updated);
    onChange?.(updated);
  }, [testCase, onChange]);

  // 添加步骤
  const addStep = useCallback((section: 'setup' | 'steps' | 'teardown' = 'steps') => {
    const newStep: DSLStep = {
      id: generateId(),
      action: 'tap',
      target: '',
    };
    
    if (section === 'steps') {
      updateTestCase({ steps: [...testCase.steps, newStep] });
    } else if (section === 'setup') {
      updateTestCase({ setup: [...(testCase.setup || []), newStep] });
    } else {
      updateTestCase({ teardown: [...(testCase.teardown || []), newStep] });
    }
  }, [testCase, updateTestCase]);

  // 更新步骤
  const updateStep = useCallback((section: 'setup' | 'steps' | 'teardown', index: number, step: DSLStep) => {
    if (section === 'steps') {
      const newSteps = [...testCase.steps];
      newSteps[index] = step;
      updateTestCase({ steps: newSteps });
    } else if (section === 'setup') {
      const newSetup = [...(testCase.setup || [])];
      newSetup[index] = step;
      updateTestCase({ setup: newSetup });
    } else {
      const newTeardown = [...(testCase.teardown || [])];
      newTeardown[index] = step;
      updateTestCase({ teardown: newTeardown });
    }
  }, [testCase, updateTestCase]);

  // 删除步骤
  const deleteStep = useCallback((section: 'setup' | 'steps' | 'teardown', index: number) => {
    if (section === 'steps') {
      updateTestCase({ steps: testCase.steps.filter((_, i) => i !== index) });
    } else if (section === 'setup') {
      updateTestCase({ setup: (testCase.setup || []).filter((_, i) => i !== index) });
    } else {
      updateTestCase({ teardown: (testCase.teardown || []).filter((_, i) => i !== index) });
    }
  }, [testCase, updateTestCase]);

  // 移动步骤
  const moveStep = useCallback((section: 'setup' | 'steps' | 'teardown', index: number, direction: 'up' | 'down') => {
    const getArray = () => {
      if (section === 'steps') return [...testCase.steps];
      if (section === 'setup') return [...(testCase.setup || [])];
      return [...(testCase.teardown || [])];
    };
    
    const arr = getArray();
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= arr.length) return;
    
    [arr[index], arr[newIndex]] = [arr[newIndex], arr[index]];
    
    if (section === 'steps') updateTestCase({ steps: arr });
    else if (section === 'setup') updateTestCase({ setup: arr });
    else updateTestCase({ teardown: arr });
  }, [testCase, updateTestCase]);

  // 生成 JSON
  const dslJson = useMemo(() => {
    const output: any = {
      name: testCase.name,
    };
    if (testCase.description) output.description = testCase.description;
    if (testCase.tags?.length) output.tags = testCase.tags;
    if (Object.keys(testCase.variables || {}).length) output.variables = testCase.variables;
    const stripId = ({ id, ...rest }: any) => rest;
    if (testCase.setup?.length) output.setup = testCase.setup.map(stripId);
    output.steps = testCase.steps.map(stripId);
    if (testCase.teardown?.length) output.teardown = testCase.teardown.map(stripId);
    return JSON.stringify(output, null, 2);
  }, [testCase]);

  // 复制到剪贴板
  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(dslJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 验证 DSL
  const validate = async () => {
    if (onValidate) {
      const result = await onValidate(testCase);
      setValidationErrors(result.errors || []);
    } else {
      // 基本验证
      const errors: string[] = [];
      if (!testCase.name) errors.push('测试用例名称不能为空');
      if (testCase.steps.length === 0) errors.push('至少需要一个测试步骤');
      testCase.steps.forEach((step, i) => {
        const noTargetActions = ['wait', 'screenshot', 'back', 'home', 'hide_keyboard', 'tap_xy', 'launch_app', 'close_app', 'reset_app'];
        if (!noTargetActions.includes(step.action) && !step.target) {
          errors.push(`步骤 #${i + 1} 缺少目标元素`);
        }
      });
      setValidationErrors(errors);
    }
  };

  // 添加标签
  const addTag = () => {
    if (newTag && !testCase.tags?.includes(newTag)) {
      updateTestCase({ tags: [...(testCase.tags || []), newTag] });
      setNewTag('');
    }
  };

  // 添加变量
  const addVariable = () => {
    if (newVarKey && newVarValue) {
      updateTestCase({ 
        variables: { ...(testCase.variables || {}), [newVarKey]: newVarValue }
      });
      setNewVarKey('');
      setNewVarValue('');
    }
  };

  // 渲染步骤列表
  const renderStepList = (section: 'setup' | 'steps' | 'teardown', title: string) => {
    const steps = section === 'steps' ? testCase.steps : 
                  section === 'setup' ? (testCase.setup || []) : 
                  (testCase.teardown || []);
    
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-gray-900">{title}</h3>
          <button
            onClick={() => addStep(section)}
            className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
          >
            <Plus size={16} />
            添加步骤
          </button>
        </div>
        
        {steps.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
            <p className="text-gray-500 text-sm">暂无步骤</p>
            <button
              onClick={() => addStep(section)}
              className="mt-2 text-blue-600 hover:text-blue-800 text-sm"
            >
              + 添加第一个步骤
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {steps.map((step, index) => (
              <StepEditor
                key={step.id}
                step={step}
                index={index}
                onUpdate={(updated) => updateStep(section, index, updated)}
                onDelete={() => deleteStep(section, index)}
                onMoveUp={() => moveStep(section, index, 'up')}
                onMoveDown={() => moveStep(section, index, 'down')}
                isFirst={index === 0}
                isLast={index === steps.length - 1}
              />
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* 头部工具栏 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-4">
          <div className="flex bg-gray-200 rounded-lg p-0.5">
            <button
              onClick={() => setActiveTab('visual')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                activeTab === 'visual' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Eye size={16} className="inline mr-1.5" />
              可视化
            </button>
            <button
              onClick={() => setActiveTab('code')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                activeTab === 'code' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Code size={16} className="inline mr-1.5" />
              代码
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={validate}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-100"
          >
            <Check size={16} />
            验证
          </button>
          <button
            onClick={copyToClipboard}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-100"
          >
            {copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      </div>

      {/* 验证错误 */}
      {validationErrors.length > 0 && (
        <div className="px-4 py-2 bg-red-50 border-b border-red-200">
          <div className="flex items-start gap-2 text-red-700">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <div className="text-sm">
              {validationErrors.map((err, i) => (
                <div key={i}>{err}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 主内容区域 */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'visual' ? (
          <div className="p-4 space-y-6">
            {/* 基本信息 */}
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    用例名称 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={testCase.name}
                    onChange={(e) => updateTestCase({ name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="登录测试"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                  <input
                    type="text"
                    value={testCase.description || ''}
                    onChange={(e) => updateTestCase({ description: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="验证用户登录功能"
                  />
                </div>
              </div>

              {/* 标签 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">标签</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {testCase.tags?.map((tag, i) => (
                    <span key={i} className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                      {tag}
                      <button
                        onClick={() => updateTestCase({ tags: testCase.tags?.filter((_, j) => j !== i) })}
                        className="hover:text-blue-900"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addTag()}
                    className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                    placeholder="添加标签"
                  />
                  <button onClick={addTag} className="px-3 py-1.5 bg-gray-100 rounded-lg text-sm hover:bg-gray-200">
                    添加
                  </button>
                </div>
              </div>

              {/* 变量 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">变量</label>
                <div className="space-y-1 mb-2">
                  {Object.entries(testCase.variables || {}).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 text-sm bg-gray-50 px-3 py-1.5 rounded">
                      <code className="text-purple-600">${'{' + key + '}'}</code>
                      <span className="text-gray-400">=</span>
                      <span className="flex-1 text-gray-700">{value}</span>
                      <button
                        onClick={() => {
                          const { [key]: _, ...rest } = testCase.variables || {};
                          updateTestCase({ variables: rest });
                        }}
                        className="text-gray-400 hover:text-red-600"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newVarKey}
                    onChange={(e) => setNewVarKey(e.target.value)}
                    className="w-32 px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                    placeholder="变量名"
                  />
                  <input
                    type="text"
                    value={newVarValue}
                    onChange={(e) => setNewVarValue(e.target.value)}
                    className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                    placeholder="变量值"
                  />
                  <button onClick={addVariable} className="px-3 py-1.5 bg-gray-100 rounded-lg text-sm hover:bg-gray-200">
                    添加
                  </button>
                </div>
              </div>
            </div>

            {/* Setup 步骤 */}
            <div className="border-t pt-6">
              {renderStepList('setup', '前置步骤 (Setup)')}
            </div>

            {/* 主要测试步骤 */}
            <div className="border-t pt-6">
              {renderStepList('steps', '测试步骤')}
            </div>

            {/* Teardown 步骤 */}
            <div className="border-t pt-6">
              {renderStepList('teardown', '后置步骤 (Teardown)')}
            </div>
          </div>
        ) : (
          <div className="h-full">
            <pre className="h-full p-4 bg-gray-900 text-gray-100 text-sm font-mono overflow-auto">
              {dslJson}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
