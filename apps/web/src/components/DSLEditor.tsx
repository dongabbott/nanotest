import { useState, useCallback, useMemo } from 'react';
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
  Settings
} from 'lucide-react';

// DSL 步骤类型定义
interface DSLStep {
  id: string;
  action: string;
  target?: string;
  value?: string;
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
  { value: 'input', label: '输入文本', icon: Type, category: 'input' },
  { value: 'clear', label: '清空输入', icon: Type, category: 'input' },
  { value: 'assert_visible', label: '断言可见', icon: Eye, category: 'assertion' },
  { value: 'assert_text', label: '断言文本', icon: Type, category: 'assertion' },
  { value: 'assert_exists', label: '断言存在', icon: Check, category: 'assertion' },
  { value: 'wait', label: '等待', icon: Clock, category: 'control' },
  { value: 'wait_for', label: '等待元素', icon: Clock, category: 'control' },
  { value: 'screenshot', label: '截图', icon: Image, category: 'utility' },
  { value: 'back', label: '返回', icon: RotateCcw, category: 'navigation' },
  { value: 'home', label: '主页', icon: Smartphone, category: 'navigation' },
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

  const actionInfo = ACTION_TYPES.find(a => a.value === step.action);
  const ActionIcon = actionInfo?.icon || Settings;
  const categoryInfo = ACTION_CATEGORIES[actionInfo?.category as keyof typeof ACTION_CATEGORIES];

  const needsTarget = !['wait', 'screenshot', 'back', 'home'].includes(step.action);
  const needsValue = ['input', 'swipe', 'scroll', 'wait', 'assert_text'].includes(step.action);

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
                 step.action === 'assert_text' ? '预期文本' :
                 step.action === 'swipe' ? '滑动方向 (up/down/left/right)' : '输入值'}
              </label>
              <input
                type={step.action === 'wait' ? 'number' : 'text'}
                value={step.value || ''}
                onChange={(e) => onUpdate({ ...step, value: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                placeholder={step.action === 'wait' ? '3' : '输入值或变量 ${username}'}
              />
            </div>
          )}

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
    if (testCase.setup?.length) {
      output.setup = testCase.setup.map(({ id, ...rest }) => rest);
    }
    output.steps = testCase.steps.map(({ id, ...rest }) => rest);
    if (testCase.teardown?.length) {
      output.teardown = testCase.teardown.map(({ id, ...rest }) => rest);
    }
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
        if (!['wait', 'screenshot', 'back', 'home'].includes(step.action) && !step.target) {
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
