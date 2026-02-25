import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Search,
  RefreshCw,
  X,
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  Loader2,
  Play,
  Square,
  Code,
  Crosshair,
} from 'lucide-react';
import { devicesApi } from '../services/api';

interface ElementNode {
  tag: string;
  attributes: Record<string, string>;
  children: ElementNode[];
  xpath: string;
}

interface ElementInspectorProps {
  onElementSelect?: (locator: { strategy: string; value: string }) => void;
  defaultServerUrl?: string;
}

function parseXmlToNodes(xmlString: string): ElementNode[] {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlString, 'text/xml');
  
  function domToNode(element: Element, parentXpath: string = ''): ElementNode {
    const tag = element.tagName;
    const attributes: Record<string, string> = {};
    
    for (let i = 0; i < element.attributes.length; i++) {
      const attr = element.attributes[i];
      attributes[attr.name] = attr.value;
    }
    
    const index = Array.from(element.parentNode?.children || []).indexOf(element) + 1;
    const xpath = parentXpath 
      ? `${parentXpath}/${tag}[${index}]`
      : `//${tag}[${index}]`;
    
    const children: ElementNode[] = [];
    element.childNodes.forEach((child) => {
      if (child.nodeType === Node.ELEMENT_NODE) {
        children.push(domToNode(child as Element, xpath));
      }
    });
    
    return { tag, attributes, children, xpath };
  }
  
  const nodes: ElementNode[] = [];
  doc.documentElement.childNodes.forEach((child) => {
    if (child.nodeType === Node.ELEMENT_NODE) {
      nodes.push(domToNode(child as Element, ''));
    }
  });
  
  return nodes;
}

function generateLocators(node: ElementNode): { strategy: string; value: string }[] {
  const locators: { strategy: string; value: string }[] = [];
  
  if (node.attributes['resource-id']) {
    locators.push({ strategy: 'id', value: node.attributes['resource-id'] });
  }
  
  if (node.attributes['accessibility-id'] || node.attributes['content-desc']) {
    locators.push({ 
      strategy: 'accessibility id', 
      value: node.attributes['accessibility-id'] || node.attributes['content-desc'] 
    });
  }
  
  if (node.attributes['text']) {
    locators.push({ strategy: 'text', value: node.attributes['text'] });
  }
  
  if (node.attributes['class']) {
    locators.push({ strategy: 'class', value: node.attributes['class'] });
  }
  
  locators.push({ strategy: 'xpath', value: node.xpath });
  
  return locators;
}

function ElementTreeNode({ 
  node, 
  depth = 0,
  onSelect,
  selectedXpath,
}: { 
  node: ElementNode; 
  depth?: number;
  onSelect: (node: ElementNode) => void;
  selectedXpath: string | null;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children.length > 0;
  const isSelected = selectedXpath === node.xpath;
  
  return (
    <div>
      <div
        className={`flex items-center gap-1 py-1 px-2 cursor-pointer hover:bg-blue-50 rounded ${
          isSelected ? 'bg-blue-100' : ''
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(node)}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="p-0.5 hover:bg-gray-200 rounded"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : (
          <span className="w-5" />
        )}
        
        <span className="text-xs font-mono text-gray-600">{node.tag}</span>
        
        {node.attributes['resource-id'] && (
          <span className="text-xs text-blue-600 ml-1 truncate max-w-[100px]">
            @{node.attributes['resource-id'].split('/').pop()}
          </span>
        )}
        
        {node.attributes['text'] && (
          <span className="text-xs text-gray-500 ml-1 truncate max-w-[80px]">
            "{node.attributes['text']}"
          </span>
        )}
      </div>
      
      {expanded && hasChildren && (
        <div>
          {node.children.map((child, index) => (
            <ElementTreeNode
              key={`${child.xpath}-${index}`}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
              selectedXpath={selectedXpath}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ElementInspector({ 
  onElementSelect,
  defaultServerUrl = 'http://localhost:4723',
}: ElementInspectorProps) {
  const [serverUrl, setServerUrl] = useState(defaultServerUrl);
  const [capabilities, setCapabilities] = useState(`{
  "platformName": "Android",
  "appium:deviceName": "Android Emulator",
  "appium:automationName": "UiAutomator2"
}`);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<ElementNode | null>(null);
  const [pageSource, setPageSource] = useState<string>('');
  const [screenshot, setScreenshot] = useState<string>('');
  const [copiedLocator, setCopiedLocator] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  
  const startSessionMutation = useMutation({
    mutationFn: () => devicesApi.startSession(serverUrl, JSON.parse(capabilities)),
    onSuccess: (response) => {
      if (response.data?.success) {
        setSessionId(response.data.session_id);
      }
    },
  });
  
  const getPageSourceMutation = useMutation({
    mutationFn: () => devicesApi.getPageSource(sessionId!),
    onSuccess: (response) => {
      if (response.data?.success) {
        setPageSource(response.data.source || '');
        setScreenshot(response.data.screenshot || '');
      }
    },
  });
  
  const stopSessionMutation = useMutation({
    mutationFn: () => devicesApi.stopSession(sessionId!),
    onSuccess: () => {
      setSessionId(null);
      setPageSource('');
      setScreenshot('');
      setSelectedNode(null);
    },
  });
  
  const elementTree = pageSource ? parseXmlToNodes(pageSource) : [];
  
  const filteredNodes = searchTerm 
    ? elementTree.filter(node => {
        const searchLower = searchTerm.toLowerCase();
        return node.tag.toLowerCase().includes(searchLower) ||
          Object.values(node.attributes).some(v => v.toLowerCase().includes(searchLower));
      })
    : elementTree;
  
  const handleCopyLocator = async (locator: { strategy: string; value: string }) => {
    const code = `driver.find_element(AppiumBy.${locator.strategy.replace(' ', '_')}, "${locator.value}")`;
    await navigator.clipboard.writeText(code);
    setCopiedLocator(`${locator.strategy}-${locator.value}`);
    setTimeout(() => setCopiedLocator(null), 2000);
  };
  
  const handleSelectElement = (node: ElementNode) => {
    setSelectedNode(node);
  };
  
  const handleUseLocator = (locator: { strategy: string; value: string }) => {
    if (onElementSelect) {
      onElementSelect(locator);
    }
  };
  
  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Crosshair size={18} />
            元素检查器
          </h3>
          {sessionId && (
            <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">
              已连接
            </span>
          )}
        </div>
        
        {!sessionId ? (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Appium 服务器地址</label>
              <input
                type="text"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="http://localhost:4723"
              />
            </div>
            
            <div>
              <label className="block text-xs text-gray-500 mb-1">Capabilities (JSON)</label>
              <textarea
                value={capabilities}
                onChange={(e) => setCapabilities(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
              />
            </div>
            
            <button
              onClick={() => startSessionMutation.mutate()}
              disabled={startSessionMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {startSessionMutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Play size={16} />
              )}
              连接设备
            </button>
            
            {startSessionMutation.isError && (
              <p className="text-xs text-red-600">
                {(startSessionMutation.error as any)?.response?.data?.message || '连接失败'}
              </p>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => getPageSourceMutation.mutate()}
              disabled={getPageSourceMutation.isPending}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
            >
              {getPageSourceMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              刷新页面
            </button>
            
            <button
              onClick={() => stopSessionMutation.mutate()}
              disabled={stopSessionMutation.isPending}
              className="px-3 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50"
            >
              <Square size={14} />
            </button>
          </div>
        )}
      </div>
      
      {screenshot && (
        <div className="p-4 border-b border-gray-200">
          <img
            src={`data:image/png;base64,${screenshot}`}
            alt="Device Screenshot"
            className="w-full rounded border border-gray-200"
          />
        </div>
      )}
      
      {pageSource && (
        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="p-2 border-b border-gray-200">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="搜索元素..."
                className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="flex-1 overflow-auto">
            {filteredNodes.map((node, index) => (
              <ElementTreeNode
                key={`${node.xpath}-${index}`}
                node={node}
                onSelect={handleSelectElement}
                selectedXpath={selectedNode?.xpath || null}
              />
            ))}
          </div>
        </div>
      )}
      
      {selectedNode && (
        <div className="p-4 border-t border-gray-200 bg-gray-50 max-h-64 overflow-auto">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-gray-900">元素属性</h4>
            <button
              onClick={() => setSelectedNode(null)}
              className="p-1 hover:bg-gray-200 rounded"
            >
              <X size={14} />
            </button>
          </div>
          
          <div className="space-y-1 mb-3">
            {Object.entries(selectedNode.attributes).slice(0, 8).map(([key, value]) => (
              <div key={key} className="flex text-xs">
                <span className="text-gray-500 w-24 truncate">{key}:</span>
                <span className="text-gray-900 truncate flex-1" title={value}>{value}</span>
              </div>
            ))}
            {Object.keys(selectedNode.attributes).length > 8 && (
              <div className="text-xs text-gray-400">
                +{Object.keys(selectedNode.attributes).length - 8} 更多属性...
              </div>
            )}
          </div>
          
          <h4 className="text-sm font-medium text-gray-900 mb-2">定位器</h4>
          <div className="space-y-1">
            {generateLocators(selectedNode).map((locator, index) => (
              <div
                key={`${locator.strategy}-${index}`}
                className="flex items-center gap-2 p-2 bg-white rounded border border-gray-200 text-xs"
              >
                <span className="text-blue-600 font-medium">{locator.strategy}:</span>
                <code className="flex-1 truncate text-gray-700">{locator.value}</code>
                <button
                  onClick={() => handleCopyLocator(locator)}
                  className="p-1 hover:bg-gray-100 rounded"
                  title="复制代码"
                >
                  {copiedLocator === `${locator.strategy}-${locator.value}` ? (
                    <Check size={12} className="text-green-600" />
                  ) : (
                    <Copy size={12} />
                  )}
                </button>
                {onElementSelect && (
                  <button
                    onClick={() => handleUseLocator(locator)}
                    className="p-1 hover:bg-blue-100 rounded text-blue-600"
                    title="使用此定位器"
                  >
                    <Code size={12} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
