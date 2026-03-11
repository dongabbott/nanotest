import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Monitor,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  MousePointer2,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  Smartphone,
  ZoomIn,
  ZoomOut,
  Crosshair,
} from 'lucide-react';
import { devicesApi } from '../services/api';
import { CreateSessionModal } from './devices';

// ============ 类型定义 ============

interface ElementNode {
  tag: string;
  attributes: Record<string, string>;
  children: ElementNode[];
  bounds?: { x: number; y: number; width: number; height: number };
  xpath?: string;
}

interface Selector {
  strategy: 'id' | 'xpath' | 'accessibility_id' | 'class_name';
  value: string;
}

interface SessionInfo {
  session_id: string;
  device_udid: string;
  device_name?: string;
  platform: string;
  platform_version?: string;
  package_name?: string;
  app_name?: string;
  server_url: string;
  status: string;
}

interface ElementInspectorProps {
  onSelectElement?: (selector: Selector) => void;
  className?: string;
  // When provided, ElementInspector can show a "Create Session" entry point.
  devices?: { udid: string; status: string }[];
}

// ============ XML 解析器 ============

function parseXmlToElements(xmlString: string): ElementNode | null {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlString, 'text/xml');
    
    const parseError = doc.querySelector('parsererror');
    if (parseError) {
      console.error('XML parse error:', parseError.textContent);
      return null;
    }

    const parseNode = (node: Element, parentXpath: string = ''): ElementNode => {
      const tag = node.tagName;
      const attributes: Record<string, string> = {};
      
      for (const attr of Array.from(node.attributes)) {
        attributes[attr.name] = attr.value;
      }

      // 计算 xpath
      const siblings = parentXpath 
        ? Array.from(node.parentElement?.children || []).filter(n => n.tagName === tag)
        : [node];
      const index = siblings.indexOf(node) + 1;
      const xpath = `${parentXpath}/${tag}${siblings.length > 1 ? `[${index}]` : ''}`;

      // 解析 bounds (Android: "left,top][right,bottom", iOS: 直接有 x,y,width,height)
      let bounds: ElementNode['bounds'];
      if (attributes['bounds']) {
        const match = attributes['bounds'].match(/\[(\d+),(\d+)\]\[(\d+),(\d+)\]/);
        if (match) {
          const [, left, top, right, bottom] = match.map(Number);
          bounds = { x: left, y: top, width: right - left, height: bottom - top };
        }
      } else if (attributes['x'] && attributes['y'] && attributes['width'] && attributes['height']) {
        bounds = {
          x: parseInt(attributes['x'], 10),
          y: parseInt(attributes['y'], 10),
          width: parseInt(attributes['width'], 10),
          height: parseInt(attributes['height'], 10),
        };
      }

      const children: ElementNode[] = [];
      for (const child of Array.from(node.children)) {
        children.push(parseNode(child, xpath));
      }

      return { tag, attributes, children, bounds, xpath };
    };

    return parseNode(doc.documentElement);
  } catch (e) {
    console.error('Failed to parse XML:', e);
    return null;
  }
}

// ============ 获取元素的最佳定位器 ============

function getBestSelectors(node: ElementNode, platform: string): Selector[] {
  const selectors: Selector[] = [];
  const attrs = node.attributes;

  if (platform === 'android') {
    // Android 优先级: resource-id > content-desc > xpath
    if (attrs['resource-id']) {
      selectors.push({ strategy: 'id', value: attrs['resource-id'] });
    }
    if (attrs['content-desc']) {
      selectors.push({ strategy: 'accessibility_id', value: attrs['content-desc'] });
    }
    if (attrs['class']) {
      selectors.push({ strategy: 'class_name', value: attrs['class'] });
    }
  } else {
    // iOS 优先级: name > label > accessibility-id > xpath
    if (attrs['name']) {
      selectors.push({ strategy: 'accessibility_id', value: attrs['name'] });
    }
    if (attrs['label']) {
      selectors.push({ strategy: 'accessibility_id', value: attrs['label'] });
    }
    if (attrs['type']) {
      selectors.push({ strategy: 'class_name', value: attrs['type'] });
    }
  }

  // 始终添加 XPath 作为备选
  if (node.xpath) {
    selectors.push({ strategy: 'xpath', value: node.xpath });
  }

  return selectors;
}

// ============ 元素树节点组件 ============

function ElementTreeNode({
  node,
  depth,
  platform,
  selectedNode,
  hoveredNode,
  expandedNodes,
  onSelect,
  onHover,
  onToggleExpand,
}: {
  node: ElementNode;
  depth: number;
  platform: string;
  selectedNode: ElementNode | null;
  hoveredNode: ElementNode | null;
  expandedNodes: Set<string>;
  onSelect: (node: ElementNode) => void;
  onHover: (node: ElementNode | null) => void;
  onToggleExpand: (xpath: string) => void;
}) {
  const hasChildren = node.children.length > 0;
  const isExpanded = node.xpath ? expandedNodes.has(node.xpath) : false;
  const isSelected = selectedNode?.xpath === node.xpath;
  const isHovered = hoveredNode?.xpath === node.xpath;

  // 获取显示名称
  const getDisplayName = () => {
    const attrs = node.attributes;
    if (platform === 'android') {
      if (attrs['text']) return `"${attrs['text'].substring(0, 20)}${attrs['text'].length > 20 ? '...' : ''}"`;
      if (attrs['content-desc']) return `[${attrs['content-desc'].substring(0, 15)}]`;
      if (attrs['resource-id']) {
        const id = attrs['resource-id'].split('/').pop() || attrs['resource-id'];
        return `#${id}`;
      }
    } else {
      if (attrs['label']) return `"${attrs['label'].substring(0, 20)}${attrs['label'].length > 20 ? '...' : ''}"`;
      if (attrs['name']) return `[${attrs['name'].substring(0, 15)}]`;
      if (attrs['value']) return `"${attrs['value'].substring(0, 15)}..."`;
    }
    return '';
  };

  const displayName = getDisplayName();

  return (
    <div>
      <div
        className={`flex items-center gap-1 px-2 py-1 cursor-pointer text-sm hover:bg-blue-50 rounded transition-colors ${
          isSelected ? 'bg-blue-100 text-blue-800' : isHovered ? 'bg-gray-100' : ''
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={() => onSelect(node)}
        onMouseEnter={() => onHover(node)}
        onMouseLeave={() => onHover(null)}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (node.xpath) onToggleExpand(node.xpath);
            }}
            className="p-0.5 hover:bg-gray-200 rounded"
          >
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : (
          <span className="w-5" />
        )}
        <span className="text-purple-600 font-mono">{node.tag}</span>
        {displayName && (
          <span className="text-gray-500 truncate max-w-[150px]">{displayName}</span>
        )}
      </div>
      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child, index) => (
            <ElementTreeNode
              key={child.xpath || index}
              node={child}
              depth={depth + 1}
              platform={platform}
              selectedNode={selectedNode}
              hoveredNode={hoveredNode}
              expandedNodes={expandedNodes}
              onSelect={onSelect}
              onHover={onHover}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ============ 属性面板组件 ============

function AttributesPanel({
  node,
  platform,
  onUseSelector,
}: {
  node: ElementNode;
  platform: string;
  onUseSelector: (selector: Selector) => void;
}) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const selectors = getBestSelectors(node, platform);

  const handleCopy = async (value: string, key: string) => {
    await navigator.clipboard.writeText(value);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <div className="space-y-4">
      {/* 推荐定位器 */}
      {selectors.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">推荐定位器</h4>
          <div className="space-y-1.5">
            {selectors.map((sel, i) => (
              <div
                key={i}
                className="flex items-center gap-2 p-2 bg-green-50 border border-green-200 rounded-lg group"
              >
                <span className="text-xs font-medium text-green-700 bg-green-100 px-1.5 py-0.5 rounded">
                  {sel.strategy}
                </span>
                <code className="flex-1 text-xs text-green-800 truncate font-mono">
                  {sel.value}
                </code>
                <button
                  onClick={() => handleCopy(sel.value, `sel-${i}`)}
                  className="p-1 hover:bg-green-200 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  title="复制"
                >
                  {copiedKey === `sel-${i}` ? <Check size={12} className="text-green-600" /> : <Copy size={12} className="text-green-600" />}
                </button>
                <button
                  onClick={() => onUseSelector(sel)}
                  className="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  使用
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 所有属性 */}
      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">元素属性</h4>
        <div className="space-y-1 max-h-[200px] overflow-auto">
          {Object.entries(node.attributes).map(([key, value]) => (
            <div
              key={key}
              className="flex items-center gap-2 px-2 py-1.5 hover:bg-gray-50 rounded text-sm group"
            >
              <span className="text-gray-500 font-medium min-w-[100px]">{key}:</span>
              <span className="flex-1 text-gray-800 truncate font-mono text-xs">{value}</span>
              <button
                onClick={() => handleCopy(value, key)}
                className="p-1 hover:bg-gray-200 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                title="复制"
              >
                {copiedKey === key ? <Check size={12} className="text-green-600" /> : <Copy size={12} className="text-gray-400" />}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============ 截图视图组件 ============

function ScreenshotView({
  screenshot,
  elementTree,
  selectedNode,
  hoveredNode,
  onSelectNode,
  onHoverNode,
}: {
  screenshot: string;
  elementTree: ElementNode | null;
  selectedNode: ElementNode | null;
  hoveredNode: ElementNode | null;
  onSelectNode: (node: ElementNode | null) => void;
  onHoverNode: (node: ElementNode | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [inspectMode, setInspectMode] = useState(false);

  // 计算缩放后的实际显示尺寸
  const displayWidth = imageSize.width * scale;
  const displayHeight = imageSize.height * scale;

  // 收集所有有 bounds 的元素
  const collectElementsWithBounds = useCallback((node: ElementNode): ElementNode[] => {
    const result: ElementNode[] = [];
    if (node.bounds && node.bounds.width > 0 && node.bounds.height > 0) {
      result.push(node);
    }
    for (const child of node.children) {
      result.push(...collectElementsWithBounds(child));
    }
    return result;
  }, []);

  const elementsWithBounds = elementTree ? collectElementsWithBounds(elementTree) : [];

  // Detect the actual device coordinate space from the root element's bounds.
  // XML bounds use device-pixel coordinates; the screenshot's naturalWidth/Height
  // is typically identical, but on some devices (e.g. with nav-bar cropping or
  // display scaling) they may differ. We compute a ratio to bridge the two.
  const deviceSize = useMemo(() => {
    if (elementTree?.bounds) {
      return {
        width: elementTree.bounds.x + elementTree.bounds.width,
        height: elementTree.bounds.y + elementTree.bounds.height,
      };
    }
    // Fallback: assume screenshot pixels == device pixels
    return imageSize;
  }, [elementTree, imageSize]);

  // Ratio: screenshot-pixel / device-pixel  (usually ≈ 1)
  const sx = imageSize.width > 0 && deviceSize.width > 0 ? imageSize.width / deviceSize.width : 1;
  const sy = imageSize.height > 0 && deviceSize.height > 0 ? imageSize.height / deviceSize.height : 1;

  // 处理图片加载获取实际尺寸
  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
    
    // 自动适应容器
    if (containerRef.current) {
      const containerWidth = containerRef.current.clientWidth - 32;
      const containerHeight = containerRef.current.clientHeight - 32;
      const scaleX = containerWidth / img.naturalWidth;
      const scaleY = containerHeight / img.naturalHeight;
      setScale(Math.min(scaleX, scaleY, 1));
    }
  };

  // 点击截图区域找到对应元素
  const handleScreenClick = (e: React.MouseEvent) => {
    if (!inspectMode || !elementTree) return;

    const rect = e.currentTarget.getBoundingClientRect();
    // Convert click position to screenshot-pixel coordinates
    const imgX = (e.clientX - rect.left) / scale;
    const imgY = (e.clientY - rect.top) / scale;

    // Convert screenshot-pixel → device-pixel (for matching against XML bounds)
    const devX = imgX / sx;
    const devY = imgY / sy;

    // 找到包含该点的最小元素
    let bestMatch: ElementNode | null = null;
    let bestArea = Infinity;

    for (const el of elementsWithBounds) {
      if (!el.bounds) continue;
      const { x: bx, y: by, width: bw, height: bh } = el.bounds;
      if (devX >= bx && devX <= bx + bw && devY >= by && devY <= by + bh) {
        const area = bw * bh;
        if (area < bestArea) {
          bestArea = area;
          bestMatch = el;
        }
      }
    }

    if (bestMatch) {
      onSelectNode(bestMatch);
    }
  };

  // 鼠标悬停时高亮元素
  const handleScreenMouseMove = (e: React.MouseEvent) => {
    if (!inspectMode || !elementTree) {
      onHoverNode(null);
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const imgX = (e.clientX - rect.left) / scale;
    const imgY = (e.clientY - rect.top) / scale;
    const devX = imgX / sx;
    const devY = imgY / sy;

    let bestMatch: ElementNode | null = null;
    let bestArea = Infinity;

    for (const el of elementsWithBounds) {
      if (!el.bounds) continue;
      const { x: bx, y: by, width: bw, height: bh } = el.bounds;
      if (devX >= bx && devX <= bx + bw && devY >= by && devY <= by + bh) {
        const area = bw * bh;
        if (area < bestArea) {
          bestArea = area;
          bestMatch = el;
        }
      }
    }

    onHoverNode(bestMatch);
  };

  // 计算元素在截图上的显示位置（CSS px）
  // bounds(device-pixel) → ×sx/sy → screenshot-pixel → ×scale → display-pixel
  const getElementPosition = (node: ElementNode) => {
    if (!node.bounds || imageSize.width === 0) return null;
    return {
      left: node.bounds.x * sx * scale,
      top: node.bounds.y * sy * scale,
      width: node.bounds.width * sx * scale,
      height: node.bounds.height * sy * scale,
    };
  };

  return (
    <div ref={containerRef} className="relative h-full flex flex-col bg-gray-900">
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setInspectMode(!inspectMode)}
            className={`p-1.5 rounded transition-colors ${
              inspectMode ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
            title="元素选择模式"
          >
            <Crosshair size={16} />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setScale(Math.max(0.25, scale - 0.25))}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title="缩小"
          >
            <ZoomOut size={16} />
          </button>
          <span className="text-xs text-gray-400 w-12 text-center">{Math.round(scale * 100)}%</span>
          <button
            onClick={() => setScale(Math.min(2, scale + 0.25))}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title="放大"
          >
            <ZoomIn size={16} />
          </button>
        </div>
      </div>

      {/* 截图区域 */}
      <div className="flex-1 overflow-auto p-4 flex items-center justify-center">
        <div
          className={`relative ${inspectMode ? 'cursor-crosshair' : 'cursor-default'}`}
          style={{ width: displayWidth, height: displayHeight }}
          onClick={handleScreenClick}
          onMouseMove={handleScreenMouseMove}
        >
          <img
            src={`data:image/png;base64,${screenshot}`}
            alt="Device Screenshot"
            className="w-full h-full"
            onLoad={handleImageLoad}
            draggable={false}
          />
          
          {/* 高亮选中/悬停的元素 */}
          {(selectedNode || hoveredNode) && (
            <>
              {hoveredNode && hoveredNode !== selectedNode && (() => {
                const pos = getElementPosition(hoveredNode);
                if (!pos) return null;
                return (
                  <div
                    className="absolute border-2 border-yellow-400 bg-yellow-400/20 pointer-events-none"
                    style={{
                      left: pos.left,
                      top: pos.top,
                      width: pos.width,
                      height: pos.height,
                    }}
                  />
                );
              })()}
              {selectedNode && (() => {
                const pos = getElementPosition(selectedNode);
                if (!pos) return null;
                return (
                  <div
                    className="absolute border-2 border-blue-500 bg-blue-500/20 pointer-events-none"
                    style={{
                      left: pos.left,
                      top: pos.top,
                      width: pos.width,
                      height: pos.height,
                    }}
                  />
                );
              })()}
            </>
          )}
        </div>
      </div>

      {inspectMode && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-full shadow-lg">
          点击截图选择元素
        </div>
      )}
    </div>
  );
}

// ============ 主组件 ============

export default function ElementInspector({ onSelectElement, className = '', devices = [] }: ElementInspectorProps) {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [elementTree, setElementTree] = useState<ElementNode | null>(null);
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<ElementNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<ElementNode | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'tree' | 'attributes'>('tree');
  const [isCreateSessionOpen, setIsCreateSessionOpen] = useState(false);

  // 获取活跃 Sessions（含 expired，后端会自动恢复）
  const { data: sessionsData, isLoading: loadingSessions, refetch: refetchSessions } = useQuery({
    queryKey: ['appiumSessions'],
    queryFn: () => devicesApi.listSessions(),
    refetchInterval: 10000,
  });

  const sessions: SessionInfo[] = (sessionsData?.data?.sessions || []).filter(
    (s: SessionInfo) => s.status === 'active' || s.status === 'expired' || s.status === 'disconnected'
  );

  const selectedSession = sessions.find(s => s.session_id === selectedSessionId);

  // 刷新页面源码
  const refreshMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      const result = await devicesApi.performSessionAction(sessionId, 'source');
      const screenshotResult = await devicesApi.performSessionAction(sessionId, 'screenshot');
      return {
        source: result.data?.data?.source,
        screenshot: screenshotResult.data?.data?.screenshot,
      };
    },
    onSuccess: (data) => {
      if (data.source) {
        const tree = parseXmlToElements(data.source);
        setElementTree(tree);
        // 自动展开根节点
        if (tree?.xpath) {
          setExpandedNodes(new Set([tree.xpath]));
        }
      }
      if (data.screenshot) {
        setScreenshot(data.screenshot);
      }
      setSelectedNode(null);
    },
  });

  // 选择 Session 时自动刷新
  useEffect(() => {
    if (selectedSessionId) {
      refreshMutation.mutate(selectedSessionId);
    }
  }, [selectedSessionId]);

  // 展开/折叠节点
  const handleToggleExpand = (xpath: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(xpath)) {
      newExpanded.delete(xpath);
    } else {
      newExpanded.add(xpath);
    }
    setExpandedNodes(newExpanded);
  };

  // 选择元素时自动展开父节点
  const handleSelectNode = (node: ElementNode | null) => {
    setSelectedNode(node);
    if (node?.xpath) {
      // 展开所有父节点
      const parts = node.xpath.split('/').filter(Boolean);
      const newExpanded = new Set(expandedNodes);
      let path = '';
      for (const part of parts) {
        path += '/' + part;
        newExpanded.add(path);
      }
      setExpandedNodes(newExpanded);
    }
  };

  // 使用选择器
  const handleUseSelector = (selector: Selector) => {
    onSelectElement?.(selector);
  };

  if (sessions.length === 0 && !loadingSessions) {
    return (
      <>
        <div className={`flex flex-col items-center justify-center h-full bg-gray-50 rounded-lg border-2 border-dashed border-gray-300 p-6 ${className}`}>
          <Smartphone size={48} className="text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-700 mb-2">无活跃会话</h3>
          <p className="text-sm text-gray-500 text-center mb-4">
            请先创建一个 Appium Session，然后返回此处选择元素
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetchSessions()}
              className="flex items-center gap-2 px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded-lg"
            >
              <RefreshCw size={16} />
              刷新列表
            </button>
            <button
              onClick={() => setIsCreateSessionOpen(true)}
              disabled={devices.length === 0}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              title={devices.length === 0 ? '没有可用设备，无法创建 Session' : '创建新的 Appium Session'}
            >
              创建 Session
            </button>
          </div>
        </div>

        <CreateSessionModal
          isOpen={isCreateSessionOpen}
          onClose={() => {
            setIsCreateSessionOpen(false);
            refetchSessions();
          }}
          devices={devices as any}
        />
      </>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-white rounded-lg border border-gray-200 overflow-hidden ${className}`}>
      {/* 头部 - Session 选择器 */}
      <div className="flex items-center gap-3 px-4 py-3 border-b bg-gray-50">
        <Monitor size={18} className="text-gray-500" />
        <select
          value={selectedSessionId || ''}
          onChange={(e) => setSelectedSessionId(e.target.value || null)}
          className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">选择设备会话...</option>
          {sessions.map((session) => (
            <option key={session.session_id} value={session.session_id}>
              {session.device_name || session.device_udid} ({session.platform}) - {session.app_name || session.package_name || '未知应用'}
            </option>
          ))}
        </select>
        <button
          onClick={() => selectedSessionId && refreshMutation.mutate(selectedSessionId)}
          disabled={!selectedSessionId || refreshMutation.isPending}
          className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg disabled:opacity-50"
          title="刷新界面"
        >
          <RefreshCw size={18} className={refreshMutation.isPending ? 'animate-spin' : ''} />
        </button>
      </div>

      {!selectedSessionId ? (
        <div className="flex-1 flex items-center justify-center text-gray-400">
          <div className="text-center">
            <MousePointer2 size={40} className="mx-auto mb-3 opacity-50" />
            <p>请选择一个设备会话</p>
          </div>
        </div>
      ) : refreshMutation.isPending && !screenshot ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 size={32} className="mx-auto mb-3 animate-spin text-blue-500" />
            <p className="text-gray-500">正在加载设备界面...</p>
          </div>
        </div>
      ) : refreshMutation.isError ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-red-500">
            <AlertCircle size={40} className="mx-auto mb-3" />
            <p>加载失败，请重试</p>
            <button
              onClick={() => refreshMutation.mutate(selectedSessionId)}
              className="mt-3 px-4 py-2 text-sm bg-red-50 text-red-600 rounded-lg hover:bg-red-100"
            >
              重试
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* 左侧 - 截图 */}
          <div className="w-[55%] border-r border-gray-200 min-h-0">
            {screenshot ? (
              <ScreenshotView
                screenshot={screenshot}
                elementTree={elementTree}
                selectedNode={selectedNode}
                hoveredNode={hoveredNode}
                onSelectNode={handleSelectNode}
                onHoverNode={setHoveredNode}
              />
            ) : (
              <div className="h-full flex items-center justify-center bg-gray-100">
                <p className="text-gray-400">无截图</p>
              </div>
            )}
          </div>

          {/* 右侧 - 元素树 & 属性 */}
          <div className="w-[45%] flex flex-col min-h-0">
            {/* Tab 切换 */}
            <div className="flex border-b border-gray-200 flex-shrink-0">
              <button
                onClick={() => setActiveTab('tree')}
                className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${
                  activeTab === 'tree'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                元素树
              </button>
              <button
                onClick={() => setActiveTab('attributes')}
                className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${
                  activeTab === 'attributes'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                属性 {selectedNode && '✓'}
              </button>
            </div>

            {/* 内容区域 */}
            <div className="flex-1 overflow-auto min-h-0">
              {activeTab === 'tree' ? (
                elementTree ? (
                  <div className="py-2">
                    <ElementTreeNode
                      node={elementTree}
                      depth={0}
                      platform={selectedSession?.platform || 'android'}
                      selectedNode={selectedNode}
                      hoveredNode={hoveredNode}
                      expandedNodes={expandedNodes}
                      onSelect={handleSelectNode}
                      onHover={setHoveredNode}
                      onToggleExpand={handleToggleExpand}
                    />
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400">
                    <p>无元素数据</p>
                  </div>
                )
              ) : selectedNode ? (
                <div className="p-4">
                  <AttributesPanel
                    node={selectedNode}
                    platform={selectedSession?.platform || 'android'}
                    onUseSelector={handleUseSelector}
                  />
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <MousePointer2 size={32} className="mx-auto mb-2 opacity-50" />
                    <p>请在左侧选择一个元素</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export type { Selector, ElementNode };
