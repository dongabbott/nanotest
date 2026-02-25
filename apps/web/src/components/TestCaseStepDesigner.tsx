// filepath: d:\project\nanotest\apps\web\src\components\TestCaseStepDesigner.tsx
import React, { useState, useCallback, useRef } from 'react';
import {
  MousePointer2,
  Type,
  ArrowUpDown,
  Clock,
  CheckCircle,
  Camera,
  Sparkles,
  Plus,
  Trash2,
  GripVertical,
  ChevronDown,
  ChevronRight,
  MoveUp,
  MoveDown,
  Copy,
  ClipboardPaste,
  MoreHorizontal,
  Undo2,
  Redo2,
  ChevronsUpDown,
  Search,
  Keyboard,
} from 'lucide-react';

// ============ 类型定义 ============

interface Selector {
  strategy: 'id' | 'xpath' | 'accessibility_id' | 'class_name' | 'ai_vision';
  value: string;
  timeout?: number;
}

interface BaseAction {
  id?: string;
  name?: string;
  description?: string;
  continueOnError?: boolean;
}

interface TapAction extends BaseAction {
  type: 'tap';
  selector: Selector;
  duration?: number;
}

interface SwipeAction extends BaseAction {
  type: 'swipe';
  direction: 'up' | 'down' | 'left' | 'right';
  distance?: number;
  duration?: number;
}

interface TypeAction extends BaseAction {
  type: 'type';
  selector: Selector;
  text: string;
  clearFirst?: boolean;
}

interface ScrollAction extends BaseAction {
  type: 'scroll';
  direction: 'up' | 'down' | 'left' | 'right';
  distance?: number;
}

interface WaitAction extends BaseAction {
  type: 'wait';
  duration?: number;
  selector?: Selector;
  condition?: 'visible' | 'hidden' | 'enabled' | 'disabled';
}

interface AssertAction extends BaseAction {
  type: 'assert';
  selector?: Selector;
  condition: 'exists' | 'not_exists' | 'visible' | 'text_equals' | 'text_contains' | 'enabled';
  expected?: string;
}

interface ScreenshotAction extends BaseAction {
  type: 'screenshot';
  name?: string;
  fullPage?: boolean;
}

interface AiAnalyzeAction extends BaseAction {
  type: 'ai_analyze';
  prompt: string;
  saveResult?: string;
}

type Action = TapAction | SwipeAction | TypeAction | ScrollAction | WaitAction | AssertAction | ScreenshotAction | AiAnalyzeAction;

export interface TestCaseDsl {
  version?: string;
  name: string;
  description?: string;
  tags?: string[];
  timeout?: number;
  retries?: number;
  setup?: Action[];
  steps: Action[];
  teardown?: Action[];
  variables?: Record<string, any>;
}

// ============ 常量 ============

const ACTION_TYPES: Record<string, { label: string; icon: any; color: string; description: string; shortcut?: string }> = {
  tap: { label: '点击', icon: MousePointer2, color: 'blue', description: '点击指定元素', shortcut: 'T' },
  swipe: { label: '滑动', icon: ArrowUpDown, color: 'purple', description: '滑动屏幕', shortcut: 'S' },
  type: { label: '输入', icon: Type, color: 'green', description: '在输入框中输入文本', shortcut: 'I' },
  scroll: { label: '滚动', icon: ArrowUpDown, color: 'indigo', description: '滚动页面', shortcut: 'R' },
  wait: { label: '等待', icon: Clock, color: 'yellow', description: '等待元素或时间', shortcut: 'W' },
  assert: { label: '断言', icon: CheckCircle, color: 'red', description: '验证条件是否满足', shortcut: 'A' },
  screenshot: { label: '截图', icon: Camera, color: 'pink', description: '截取屏幕截图', shortcut: 'C' },
  ai_analyze: { label: 'AI分析', icon: Sparkles, color: 'cyan', description: '使用AI分析屏幕', shortcut: 'X' },
};

const SELECTOR_STRATEGIES = [
  { value: 'id', label: 'ID' },
  { value: 'xpath', label: 'XPath' },
  { value: 'accessibility_id', label: '无障碍ID' },
  { value: 'class_name', label: '类名' },
  { value: 'ai_vision', label: 'AI视觉' },
];

const DIRECTIONS = [
  { value: 'up', label: '向上' },
  { value: 'down', label: '向下' },
  { value: 'left', label: '向左' },
  { value: 'right', label: '向右' },
];

const ASSERT_CONDITIONS = [
  { value: 'exists', label: '元素存在' },
  { value: 'not_exists', label: '元素不存在' },
  { value: 'visible', label: '元素可见' },
  { value: 'text_equals', label: '文本等于' },
  { value: 'text_contains', label: '文本包含' },
  { value: 'enabled', label: '元素启用' },
];

const WAIT_CONDITIONS = [
  { value: 'visible', label: '可见' },
  { value: 'hidden', label: '隐藏' },
  { value: 'enabled', label: '启用' },
  { value: 'disabled', label: '禁用' },
];

// ============ 工具函数 ============

const generateId = () => `step_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;

const createDefaultAction = (type: string): Action => {
  const id = generateId();
  const base = { id, continueOnError: false };
  
  switch (type) {
    case 'tap':
      return { ...base, type: 'tap', selector: { strategy: 'id', value: '' } };
    case 'swipe':
      return { ...base, type: 'swipe', direction: 'up', distance: 0.5, duration: 500 };
    case 'type':
      return { ...base, type: 'type', selector: { strategy: 'id', value: '' }, text: '', clearFirst: true };
    case 'scroll':
      return { ...base, type: 'scroll', direction: 'down' };
    case 'wait':
      return { ...base, type: 'wait', duration: 1000 };
    case 'assert':
      return { ...base, type: 'assert', condition: 'exists' };
    case 'screenshot':
      return { ...base, type: 'screenshot', fullPage: false };
    case 'ai_analyze':
      return { ...base, type: 'ai_analyze', prompt: '' };
    default:
      return { ...base, type: 'tap', selector: { strategy: 'id', value: '' } };
  }
};

// ============ 选择器编辑器 ============

function SelectorEditor({
  selector,
  onChange,
}: {
  selector: Selector;
  onChange: (selector: Selector) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-4 gap-2">
        <div>
          <label className="block text-xs text-gray-500 mb-1">定位方式</label>
          <select
            value={selector.strategy}
            onChange={(e) => onChange({ ...selector, strategy: e.target.value as Selector['strategy'] })}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {SELECTOR_STRATEGIES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="col-span-3">
          <label className="block text-xs text-gray-500 mb-1">定位值</label>
          <div className="relative">
            <input
              type="text"
              value={selector.value}
              onChange={(e) => onChange({ ...selector, value: e.target.value })}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-8"
              placeholder={selector.strategy === 'xpath' ? '//button[@text="登录"]' : '输入元素ID'}
            />
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600"
              title="元素选择器（即将支持）"
            >
              <Search size={14} />
            </button>
          </div>
        </div>
      </div>
      {selector.strategy === 'ai_vision' && (
        <p className="text-xs text-cyan-600 bg-cyan-50 px-2 py-1 rounded">
          💡 AI视觉定位将使用图像识别自动定位元素，请输入元素的描述文字
        </p>
      )}
    </div>
  );
}

// ============ 步骤编辑器 ============

function StepEditor({
  action,
  onChange,
}: {
  action: Action;
  onChange: (action: Action) => void;
}) {
  const renderFields = () => {
    switch (action.type) {
      case 'tap':
        return (
          <div className="space-y-3">
            <SelectorEditor
              selector={action.selector}
              onChange={(selector) => onChange({ ...action, selector })}
            />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">长按时长 (毫秒)</label>
                <input
                  type="number"
                  value={action.duration || ''}
                  onChange={(e) => onChange({ ...action, duration: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="留空为普通点击"
                />
              </div>
            </div>
          </div>
        );

      case 'swipe':
        return (
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-2">
              {DIRECTIONS.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  onClick={() => onChange({ ...action, direction: d.value as SwipeAction['direction'] })}
                  className={`px-3 py-2 text-sm rounded-lg border transition-all ${
                    action.direction === d.value
                      ? 'bg-purple-100 border-purple-400 text-purple-700 font-medium'
                      : 'border-gray-300 hover:border-purple-300 hover:bg-purple-50'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">滑动距离 (0-1)</label>
                <input
                  type="range"
                  min="0.1"
                  max="1"
                  step="0.1"
                  value={action.distance ?? 0.5}
                  onChange={(e) => onChange({ ...action, distance: Number(e.target.value) })}
                  className="w-full"
                />
                <div className="text-xs text-gray-400 text-center">{((action.distance ?? 0.5) * 100).toFixed(0)}%</div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">时长 (毫秒)</label>
                <input
                  type="number"
                  value={action.duration ?? 500}
                  onChange={(e) => onChange({ ...action, duration: Number(e.target.value) })}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        );

      case 'type':
        return (
          <div className="space-y-3">
            <SelectorEditor
              selector={action.selector}
              onChange={(selector) => onChange({ ...action, selector })}
            />
            <div>
              <label className="block text-xs text-gray-500 mb-1">输入文本</label>
              <textarea
                value={action.text}
                onChange={(e) => onChange({ ...action, text: e.target.value })}
                rows={2}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="要输入的文本内容，支持变量 ${变量名}"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={action.clearFirst ?? true}
                onChange={(e) => onChange({ ...action, clearFirst: e.target.checked })}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              输入前清空原有内容
            </label>
          </div>
        );

      case 'scroll':
        return (
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-2">
              {DIRECTIONS.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  onClick={() => onChange({ ...action, direction: d.value as ScrollAction['direction'] })}
                  className={`px-3 py-2 text-sm rounded-lg border transition-all ${
                    action.direction === d.value
                      ? 'bg-indigo-100 border-indigo-400 text-indigo-700 font-medium'
                      : 'border-gray-300 hover:border-indigo-300 hover:bg-indigo-50'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">滚动距离 (像素，留空为默认值)</label>
              <input
                type="number"
                value={action.distance || ''}
                onChange={(e) => onChange({ ...action, distance: e.target.value ? Number(e.target.value) : undefined })}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="默认滚动一屏"
              />
            </div>
          </div>
        );

      case 'wait':
        return (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">等待时长 (毫秒)</label>
                <input
                  type="number"
                  value={action.duration ?? 1000}
                  onChange={(e) => onChange({ ...action, duration: Number(e.target.value) })}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">等待条件</label>
                <select
                  value={action.condition || ''}
                  onChange={(e) => onChange({ ...action, condition: e.target.value as WaitAction['condition'] || undefined })}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">仅等待时间</option>
                  {WAIT_CONDITIONS.map((c) => (
                    <option key={c.value} value={c.value}>等待元素{c.label}</option>
                  ))}
                </select>
              </div>
            </div>
            {action.condition && (
              <SelectorEditor
                selector={action.selector || { strategy: 'id', value: '' }}
                onChange={(selector) => onChange({ ...action, selector })}
              />
            )}
          </div>
        );

      case 'assert':
        return (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">断言条件</label>
              <div className="grid grid-cols-3 gap-2">
                {ASSERT_CONDITIONS.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => onChange({ ...action, condition: c.value as AssertAction['condition'] })}
                    className={`px-2 py-1.5 text-xs rounded-lg border transition-all ${
                      action.condition === c.value
                        ? 'bg-red-100 border-red-400 text-red-700 font-medium'
                        : 'border-gray-300 hover:border-red-300 hover:bg-red-50'
                    }`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
            {(action.condition === 'text_equals' || action.condition === 'text_contains') && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">期望值</label>
                <input
                  type="text"
                  value={action.expected || ''}
                  onChange={(e) => onChange({ ...action, expected: e.target.value })}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="期望的文本内容"
                />
              </div>
            )}
            <SelectorEditor
              selector={action.selector || { strategy: 'id', value: '' }}
              onChange={(selector) => onChange({ ...action, selector })}
            />
          </div>
        );

      case 'screenshot':
        return (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">截图名称</label>
              <input
                type="text"
                value={action.name || ''}
                onChange={(e) => onChange({ ...action, name: e.target.value })}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="留空将自动生成"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={action.fullPage ?? false}
                onChange={(e) => onChange({ ...action, fullPage: e.target.checked })}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              截取完整页面（长截图）
            </label>
          </div>
        );

      case 'ai_analyze':
        return (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">AI 分析提示词</label>
              <textarea
                value={action.prompt}
                onChange={(e) => onChange({ ...action, prompt: e.target.value })}
                rows={3}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="描述需要AI分析的内容，例如：检查页面是否显示登录成功"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">结果变量名（可选）</label>
              <input
                type="text"
                value={action.saveResult || ''}
                onChange={(e) => onChange({ ...action, saveResult: e.target.value })}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="将分析结果保存到变量"
              />
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      {/* 步骤名称 */}
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">步骤名称（可选）</label>
          <input
            type="text"
            value={action.name || ''}
            onChange={(e) => onChange({ ...action, name: e.target.value })}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="给步骤起一个名字，方便识别"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer pt-5">
          <input
            type="checkbox"
            checked={action.continueOnError ?? false}
            onChange={(e) => onChange({ ...action, continueOnError: e.target.checked })}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          失败后继续
        </label>
      </div>
      
      {/* 具体字段 */}
      {renderFields()}
    </div>
  );
}

// ============ 步骤卡片 ============

function StepCard({
  action,
  index,
  isExpanded,
  isSelected,
  onToggle,
  onChange,
  onDelete,
  onMoveUp,
  onMoveDown,
  onDuplicate,
  onSelect,
  canMoveUp,
  canMoveDown,
  isDragging,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: {
  action: Action;
  index: number;
  isExpanded: boolean;
  isSelected: boolean;
  onToggle: () => void;
  onChange: (action: Action) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDuplicate: () => void;
  onSelect: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
  isDragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const actionType = ACTION_TYPES[action.type];
  const Icon = actionType?.icon || MousePointer2;

  const getStepSummary = () => {
    switch (action.type) {
      case 'tap':
        return action.selector.value ? `点击 ${action.selector.value}` : '点击元素';
      case 'swipe':
        return `向${action.direction === 'up' ? '上' : action.direction === 'down' ? '下' : action.direction === 'left' ? '左' : '右'}滑动`;
      case 'type':
        return action.text ? `输入 "${action.text.substring(0, 20)}${action.text.length > 20 ? '...' : ''}"` : '输入文本';
      case 'scroll':
        return `向${action.direction === 'up' ? '上' : action.direction === 'down' ? '下' : action.direction === 'left' ? '左' : '右'}滚动`;
      case 'wait':
        return action.condition ? `等待元素${action.condition}` : `等待 ${action.duration}ms`;
      case 'assert':
        return `断言: ${ASSERT_CONDITIONS.find(c => c.value === action.condition)?.label || action.condition}`;
      case 'screenshot':
        return action.name ? `截图: ${action.name}` : '截取屏幕';
      case 'ai_analyze':
        return action.prompt ? `AI: ${action.prompt.substring(0, 20)}...` : 'AI分析';
      default:
        return actionType?.label || '未知操作';
    }
  };

  const colorClasses: Record<string, { bg: string; text: string; border: string }> = {
    blue: { bg: 'bg-blue-100', text: 'text-blue-600', border: 'border-blue-200' },
    purple: { bg: 'bg-purple-100', text: 'text-purple-600', border: 'border-purple-200' },
    green: { bg: 'bg-green-100', text: 'text-green-600', border: 'border-green-200' },
    indigo: { bg: 'bg-indigo-100', text: 'text-indigo-600', border: 'border-indigo-200' },
    yellow: { bg: 'bg-yellow-100', text: 'text-yellow-600', border: 'border-yellow-200' },
    red: { bg: 'bg-red-100', text: 'text-red-600', border: 'border-red-200' },
    pink: { bg: 'bg-pink-100', text: 'text-pink-600', border: 'border-pink-200' },
    cyan: { bg: 'bg-cyan-100', text: 'text-cyan-600', border: 'border-cyan-200' },
  };

  const colors = colorClasses[actionType?.color || 'blue'];

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={`border rounded-lg bg-white transition-all ${
        isDragging ? 'opacity-50 scale-[0.98]' : ''
      } ${
        isExpanded ? 'ring-2 ring-blue-500 shadow-md' : 'hover:border-gray-400 hover:shadow-sm'
      } ${
        isSelected ? 'border-blue-400 bg-blue-50/30' : 'border-gray-200'
      }`}
    >
      {/* 头部 */}
      <div
        className="flex items-center gap-3 px-3 py-2.5 cursor-pointer select-none"
        onClick={onToggle}
      >
        <div 
          className="text-gray-400 cursor-grab active:cursor-grabbing hover:text-gray-600"
          onClick={(e) => e.stopPropagation()}
        >
          <GripVertical size={16} />
        </div>
        
        <div 
          className="flex items-center"
          onClick={(e) => { e.stopPropagation(); onSelect(); }}
        >
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => {}}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-2"
          />
        </div>
        
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${colors.bg}`}>
          <Icon size={16} className={colors.text} />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-gray-400">#{index + 1}</span>
            <span className="font-medium text-gray-900">{action.name || actionType?.label}</span>
            {action.continueOnError && (
              <span className="text-xs px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded">忽略错误</span>
            )}
          </div>
          <p className="text-sm text-gray-500 truncate">{getStepSummary()}</p>
        </div>

        <div className="flex items-center gap-0.5">
          <button
            onClick={(e) => { e.stopPropagation(); onMoveUp(); }}
            disabled={!canMoveUp}
            className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:hover:bg-transparent"
            title="上移 (Alt+↑)"
          >
            <MoveUp size={14} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onMoveDown(); }}
            disabled={!canMoveDown}
            className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:hover:bg-transparent"
            title="下移 (Alt+↓)"
          >
            <MoveDown size={14} />
          </button>
          
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setShowMenu(!showMenu); }}
              className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600"
            >
              <MoreHorizontal size={14} />
            </button>
            
            {showMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 w-36">
                  <button
                    onClick={(e) => { e.stopPropagation(); onDuplicate(); setShowMenu(false); }}
                    className="w-full px-3 py-1.5 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
                  >
                    <Copy size={14} />
                    复制步骤
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(); setShowMenu(false); }}
                    className="w-full px-3 py-1.5 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-2"
                  >
                    <Trash2 size={14} />
                    删除步骤
                  </button>
                </div>
              </>
            )}
          </div>
          
          {isExpanded ? (
            <ChevronDown size={16} className="text-gray-400 ml-1" />
          ) : (
            <ChevronRight size={16} className="text-gray-400 ml-1" />
          )}
        </div>
      </div>

      {/* 展开内容 */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-100">
          <StepEditor action={action} onChange={onChange} />
        </div>
      )}
    </div>
  );
}

// ============ 快捷添加工具栏 ============

function QuickAddToolbar({ onAdd }: { onAdd: (type: string) => void }) {
  return (
    <div className="flex items-center gap-1 p-2 bg-gray-50 rounded-lg border border-gray-200 overflow-x-auto">
      <span className="text-xs text-gray-500 mr-2 whitespace-nowrap">快捷添加:</span>
      {Object.entries(ACTION_TYPES).map(([type, config]) => {
        const Icon = config.icon;
        const colorClasses: Record<string, string> = {
          blue: 'hover:bg-blue-100 hover:text-blue-700',
          purple: 'hover:bg-purple-100 hover:text-purple-700',
          green: 'hover:bg-green-100 hover:text-green-700',
          indigo: 'hover:bg-indigo-100 hover:text-indigo-700',
          yellow: 'hover:bg-yellow-100 hover:text-yellow-700',
          red: 'hover:bg-red-100 hover:text-red-700',
          pink: 'hover:bg-pink-100 hover:text-pink-700',
          cyan: 'hover:bg-cyan-100 hover:text-cyan-700',
        };
        return (
          <button
            key={type}
            onClick={() => onAdd(type)}
            className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-gray-600 transition-colors whitespace-nowrap ${colorClasses[config.color]}`}
            title={`${config.description} (${config.shortcut})`}
          >
            <Icon size={14} />
            <span>{config.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ============ 添加步骤弹窗 ============

function AddStepModal({
  isOpen,
  onClose,
  onAdd,
  insertIndex,
}: {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (type: string) => void;
  insertIndex: number | null;
}) {
  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">
              {insertIndex !== null ? `在第 ${insertIndex + 1} 步后插入` : '添加测试步骤'}
            </h3>
            <p className="text-sm text-gray-500">选择要添加的操作类型</p>
          </div>
          <div className="p-4 grid grid-cols-2 gap-2">
            {Object.entries(ACTION_TYPES).map(([type, config]) => {
              const Icon = config.icon;
              const colorClasses: Record<string, { bg: string; hover: string; text: string }> = {
                blue: { bg: 'bg-blue-100', hover: 'hover:bg-blue-50 hover:border-blue-300', text: 'text-blue-600' },
                purple: { bg: 'bg-purple-100', hover: 'hover:bg-purple-50 hover:border-purple-300', text: 'text-purple-600' },
                green: { bg: 'bg-green-100', hover: 'hover:bg-green-50 hover:border-green-300', text: 'text-green-600' },
                indigo: { bg: 'bg-indigo-100', hover: 'hover:bg-indigo-50 hover:border-indigo-300', text: 'text-indigo-600' },
                yellow: { bg: 'bg-yellow-100', hover: 'hover:bg-yellow-50 hover:border-yellow-300', text: 'text-yellow-600' },
                red: { bg: 'bg-red-100', hover: 'hover:bg-red-50 hover:border-red-300', text: 'text-red-600' },
                pink: { bg: 'bg-pink-100', hover: 'hover:bg-pink-50 hover:border-pink-300', text: 'text-pink-600' },
                cyan: { bg: 'bg-cyan-100', hover: 'hover:bg-cyan-50 hover:border-cyan-300', text: 'text-cyan-600' },
              };
              const colors = colorClasses[config.color];
              return (
                <button
                  key={type}
                  onClick={() => { onAdd(type); onClose(); }}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 text-left transition-all ${colors.hover}`}
                >
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colors.bg}`}>
                    <Icon size={20} className={colors.text} />
                  </div>
                  <div>
                    <div className="font-medium text-gray-900">{config.label}</div>
                    <div className="text-xs text-gray-500">{config.description}</div>
                  </div>
                  {config.shortcut && (
                    <kbd className="ml-auto text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
                      {config.shortcut}
                    </kbd>
                  )}
                </button>
              );
            })}
          </div>
          <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 rounded-b-xl">
            <button
              onClick={onClose}
              className="w-full py-2 text-gray-600 hover:text-gray-900"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// ============ 主组件 ============

export interface TestCaseStepDesignerProps {
  dsl: TestCaseDsl;
  onChange: (dsl: TestCaseDsl) => void;
  compact?: boolean;
}

export default function TestCaseStepDesigner({
  dsl,
  onChange,
  compact = false,
}: TestCaseStepDesignerProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const [selectedSteps, setSelectedSteps] = useState<Set<number>>(new Set());
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [insertAfterIndex, setInsertAfterIndex] = useState<number | null>(null);
  const [clipboard, setClipboard] = useState<Action[]>([]);
  const [history, setHistory] = useState<Action[][]>([dsl.steps]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // 历史记录
  const pushHistory = useCallback((steps: Action[]) => {
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(steps);
    if (newHistory.length > 50) newHistory.shift();
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
  }, [history, historyIndex]);

  const undo = useCallback(() => {
    if (historyIndex > 0) {
      setHistoryIndex(historyIndex - 1);
      onChange({ ...dsl, steps: history[historyIndex - 1] });
    }
  }, [historyIndex, history, dsl, onChange]);

  const redo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      setHistoryIndex(historyIndex + 1);
      onChange({ ...dsl, steps: history[historyIndex + 1] });
    }
  }, [historyIndex, history, dsl, onChange]);

  // 步骤操作
  const handleToggleStep = (index: number) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSteps(newExpanded);
  };

  const handleSelectStep = (index: number) => {
    const newSelected = new Set(selectedSteps);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedSteps(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedSteps.size === dsl.steps.length) {
      setSelectedSteps(new Set());
    } else {
      setSelectedSteps(new Set(dsl.steps.map((_, i) => i)));
    }
  };

  const handleAddStep = useCallback((type: string, afterIndex?: number) => {
    const newAction = createDefaultAction(type);
    const newSteps = [...dsl.steps];
    const insertAt = afterIndex !== undefined ? afterIndex + 1 : newSteps.length;
    newSteps.splice(insertAt, 0, newAction);
    onChange({ ...dsl, steps: newSteps });
    pushHistory(newSteps);
    setExpandedSteps(new Set([insertAt]));
    setInsertAfterIndex(null);
  }, [dsl, onChange, pushHistory]);

  const handleUpdateStep = (index: number, action: Action) => {
    const newSteps = [...dsl.steps];
    newSteps[index] = action;
    onChange({ ...dsl, steps: newSteps });
  };

  const handleDeleteStep = (index: number) => {
    const newSteps = dsl.steps.filter((_, i) => i !== index);
    onChange({ ...dsl, steps: newSteps });
    pushHistory(newSteps);
    
    const newExpanded = new Set<number>();
    expandedSteps.forEach((i) => {
      if (i < index) newExpanded.add(i);
      else if (i > index) newExpanded.add(i - 1);
    });
    setExpandedSteps(newExpanded);
    
    const newSelected = new Set<number>();
    selectedSteps.forEach((i) => {
      if (i < index) newSelected.add(i);
      else if (i > index) newSelected.add(i - 1);
    });
    setSelectedSteps(newSelected);
  };

  const handleDeleteSelected = () => {
    if (selectedSteps.size === 0) return;
    const newSteps = dsl.steps.filter((_, i) => !selectedSteps.has(i));
    onChange({ ...dsl, steps: newSteps });
    pushHistory(newSteps);
    setSelectedSteps(new Set());
    setExpandedSteps(new Set());
  };

  const handleDuplicateStep = (index: number) => {
    const step = dsl.steps[index];
    const newStep = { ...JSON.parse(JSON.stringify(step)), id: generateId() };
    const newSteps = [...dsl.steps];
    newSteps.splice(index + 1, 0, newStep);
    onChange({ ...dsl, steps: newSteps });
    pushHistory(newSteps);
    setExpandedSteps(new Set([index + 1]));
  };

  const handleMoveStep = (fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= dsl.steps.length) return;
    const newSteps = [...dsl.steps];
    const [moved] = newSteps.splice(fromIndex, 1);
    newSteps.splice(toIndex, 0, moved);
    onChange({ ...dsl, steps: newSteps });
    pushHistory(newSteps);
    
    const newExpanded = new Set<number>();
    expandedSteps.forEach((i) => {
      if (i === fromIndex) newExpanded.add(toIndex);
      else if (fromIndex < toIndex && i > fromIndex && i <= toIndex) newExpanded.add(i - 1);
      else if (fromIndex > toIndex && i >= toIndex && i < fromIndex) newExpanded.add(i + 1);
      else newExpanded.add(i);
    });
    setExpandedSteps(newExpanded);
  };

  // 拖拽
  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleDragOver = (e: React.DragEvent, _index: number) => {
    e.preventDefault();
  };

  const handleDrop = (targetIndex: number) => {
    if (draggedIndex !== null && draggedIndex !== targetIndex) {
      handleMoveStep(draggedIndex, targetIndex);
    }
    setDraggedIndex(null);
  };

  // 复制粘贴
  const handleCopySelected = () => {
    const copied = dsl.steps.filter((_, i) => selectedSteps.has(i));
    setClipboard(copied);
  };

  const handlePaste = () => {
    if (clipboard.length === 0) return;
    const newSteps = clipboard.map(step => ({
      ...JSON.parse(JSON.stringify(step)),
      id: generateId(),
    }));
    const insertAt = selectedSteps.size > 0 
      ? Math.max(...Array.from(selectedSteps)) + 1 
      : dsl.steps.length;
    const allSteps = [...dsl.steps];
    allSteps.splice(insertAt, 0, ...newSteps);
    onChange({ ...dsl, steps: allSteps });
    pushHistory(allSteps);
  };

  // 快捷键
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 检查是否在输入框内
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.ctrlKey || e.metaKey) {
        if (e.key === 'z' && !e.shiftKey) {
          e.preventDefault();
          undo();
        } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
          e.preventDefault();
          redo();
        } else if (e.key === 'c') {
          e.preventDefault();
          handleCopySelected();
        } else if (e.key === 'v') {
          e.preventDefault();
          handlePaste();
        } else if (e.key === 'a') {
          e.preventDefault();
          handleSelectAll();
        }
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedSteps.size > 0) {
          e.preventDefault();
          handleDeleteSelected();
        }
      }

      // 快捷添加步骤
      Object.entries(ACTION_TYPES).forEach(([type, config]) => {
        if (config.shortcut && e.key.toUpperCase() === config.shortcut && !e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          handleAddStep(type);
        }
      });
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, handleCopySelected, handlePaste, handleSelectAll, handleDeleteSelected, selectedSteps, handleAddStep]);

  // 展开/折叠所有
  const handleExpandAll = () => {
    if (expandedSteps.size === dsl.steps.length) {
      setExpandedSteps(new Set());
    } else {
      setExpandedSteps(new Set(dsl.steps.map((_, i) => i)));
    }
  };

  return (
    <div ref={containerRef} className="flex flex-col h-full">
      {/* 工具栏 */}
      {!compact && (
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <button
              onClick={undo}
              disabled={historyIndex <= 0}
              className="p-1.5 hover:bg-gray-100 rounded text-gray-500 disabled:opacity-30"
              title="撤销 (Ctrl+Z)"
            >
              <Undo2 size={16} />
            </button>
            <button
              onClick={redo}
              disabled={historyIndex >= history.length - 1}
              className="p-1.5 hover:bg-gray-100 rounded text-gray-500 disabled:opacity-30"
              title="重做 (Ctrl+Y)"
            >
              <Redo2 size={16} />
            </button>
            <div className="w-px h-4 bg-gray-300 mx-1" />
            <button
              onClick={handleExpandAll}
              className="p-1.5 hover:bg-gray-100 rounded text-gray-500"
              title={expandedSteps.size === dsl.steps.length ? "折叠所有" : "展开所有"}
            >
              <ChevronsUpDown size={16} />
            </button>
          </div>
          
          <div className="flex items-center gap-2">
            {selectedSteps.size > 0 && (
              <>
                <span className="text-sm text-gray-500">已选 {selectedSteps.size} 项</span>
                <button
                  onClick={handleCopySelected}
                  className="p-1.5 hover:bg-gray-100 rounded text-gray-500"
                  title="复制 (Ctrl+C)"
                >
                  <Copy size={16} />
                </button>
                <button
                  onClick={handleDeleteSelected}
                  className="p-1.5 hover:bg-red-100 rounded text-red-500"
                  title="删除选中 (Delete)"
                >
                  <Trash2 size={16} />
                </button>
              </>
            )}
            {clipboard.length > 0 && (
              <button
                onClick={handlePaste}
                className="p-1.5 hover:bg-gray-100 rounded text-gray-500"
                title={`粘贴 ${clipboard.length} 个步骤 (Ctrl+V)`}
              >
                <ClipboardPaste size={16} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* 快捷添加工具栏 */}
      {!compact && <QuickAddToolbar onAdd={handleAddStep} />}

      {/* 步骤列表 */}
      <div className="flex-1 overflow-auto mt-3">
        {dsl.steps.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
            <div className="text-gray-400 mb-3">
              <MousePointer2 size={40} className="mx-auto" />
            </div>
            <h3 className="text-lg font-medium text-gray-700 mb-1">暂无测试步骤</h3>
            <p className="text-sm text-gray-500 mb-4">使用上方工具栏添加步骤，或按快捷键快速添加</p>
            <div className="flex items-center justify-center gap-2 text-xs text-gray-400">
              <Keyboard size={14} />
              <span>快捷键: T=点击, I=输入, S=滑动, W=等待, A=断言</span>
            </div>
            <button
              onClick={() => setShowAddModal(true)}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus size={16} className="inline mr-1" />
              添加第一个步骤
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {dsl.steps.map((action, index) => (
              <React.Fragment key={action.id || index}>
                <StepCard
                  action={action}
                  index={index}
                  isExpanded={expandedSteps.has(index)}
                  isSelected={selectedSteps.has(index)}
                  onToggle={() => handleToggleStep(index)}
                  onChange={(newAction) => handleUpdateStep(index, newAction)}
                  onDelete={() => handleDeleteStep(index)}
                  onMoveUp={() => handleMoveStep(index, index - 1)}
                  onMoveDown={() => handleMoveStep(index, index + 1)}
                  onDuplicate={() => handleDuplicateStep(index)}
                  onSelect={() => handleSelectStep(index)}
                  canMoveUp={index > 0}
                  canMoveDown={index < dsl.steps.length - 1}
                  isDragging={draggedIndex === index}
                  onDragStart={() => handleDragStart(index)}
                  onDragEnd={handleDragEnd}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDrop={() => handleDrop(index)}
                />
                {/* 插入点 */}
                <button
                  onClick={() => { setInsertAfterIndex(index); setShowAddModal(true); }}
                  className="w-full py-1 text-xs text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors opacity-0 hover:opacity-100"
                >
                  <Plus size={12} className="inline mr-1" />
                  在此处插入步骤
                </button>
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

      {/* 底部添加按钮 */}
      {dsl.steps.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <button
            onClick={() => { setInsertAfterIndex(null); setShowAddModal(true); }}
            className="flex items-center justify-center gap-2 w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-500 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all"
          >
            <Plus size={18} />
            <span>添加步骤</span>
          </button>
        </div>
      )}

      {/* 添加步骤弹窗 */}
      <AddStepModal
        isOpen={showAddModal}
        onClose={() => { setShowAddModal(false); setInsertAfterIndex(null); }}
        onAdd={(type) => handleAddStep(type, insertAfterIndex !== null ? insertAfterIndex : undefined)}
        insertIndex={insertAfterIndex}
      />
    </div>
  );
}

// 导出类型
export type { Action, TestCaseDsl as TestCaseDslType, Selector };
