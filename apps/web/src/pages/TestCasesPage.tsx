import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, FileCode, Tag, X, Edit, Trash2, Eye, Code, Copy, Check, PanelRightOpen, PanelRightClose } from 'lucide-react';
import { testCasesApi } from '../services/api';
import TestCaseStepDesigner, { TestCaseDsl } from '../components/TestCaseStepDesigner';
import ElementInspector, { Selector } from '../components/ElementInspector';

// 创建/编辑测试用例弹窗
function TestCaseEditorModal({
  isOpen,
  onClose,
  projectId,
  editCase,
}: {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  editCase?: any;
}) {
  const [activeTab, setActiveTab] = useState<'visual' | 'code'>('visual');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [showInspector, setShowInspector] = useState(false);
  const [pendingSelector, setPendingSelector] = useState<Selector | null>(null);
  
  const [dsl, setDsl] = useState<TestCaseDsl>({
    name: '',
    description: '',
    tags: [],
    steps: [],
    variables: {},
  });

  const [codeContent, setCodeContent] = useState('{\n  "name": "",\n  "steps": []\n}');

  // 当 editCase 变化时，更新表单数据
  useEffect(() => {
    if (editCase?.dsl_content) {
      setDsl({
        name: editCase.name || '',
        description: editCase.dsl_content.description || '',
        tags: editCase.tags || [],
        steps: (editCase.dsl_content.steps || []).map((s: any, i: number) => ({
          ...s,
          id: s.id || `step_${i}_${Date.now()}`,
        })),
        variables: editCase.dsl_content.variables || {},
      });
      setCodeContent(JSON.stringify(editCase.dsl_content, null, 2));
    } else {
      // 新建时重置表单
      setDsl({
        name: '',
        description: '',
        tags: [],
        steps: [],
        variables: {},
      });
      setCodeContent('{\n  "name": "",\n  "steps": []\n}');
    }
    setError('');
    setActiveTab('visual');
  }, [editCase]);

  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: (data: { name: string; description?: string; dsl_content: any; tags?: string[] }) => {
      if (editCase) {
        return testCasesApi.update(editCase.id, data);
      }
      return testCasesApi.create(projectId, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases', projectId] });
      onClose();
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '保存测试用例失败');
    },
  });

  const resetForm = () => {
    setDsl({ name: '', description: '', tags: [], steps: [], variables: {} });
    setCodeContent('{\n  "name": "",\n  "steps": []\n}');
    setError('');
    setActiveTab('visual');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Guard: ignore submits not triggered by our explicit submit button.
    // Some nested buttons/components inside the form may accidentally trigger a submit.
    const nativeEvent: any = (e as any).nativeEvent;
    if (nativeEvent?.submitter && nativeEvent.submitter?.getAttribute) {
      const isOurSubmit = nativeEvent.submitter.getAttribute('data-submit') === 'true';
      if (!isOurSubmit) return;
    }

    let finalDsl: any;
    let finalName: string;
    let finalTags: string[];

    if (activeTab === 'visual') {
      if (!dsl.name.trim()) {
        setError('请输入测试用例名称');
        return;
      }
      if (dsl.steps.length === 0) {
        setError('请至少添加一个测试步骤');
        return;
      }
      finalName = dsl.name;
      finalTags = dsl.tags || [];
      finalDsl = {
        name: dsl.name,
        description: dsl.description,
        steps: dsl.steps.map(({ id, ...rest }) => rest),
        variables: dsl.variables,
      };
    } else {
      try {
        finalDsl = JSON.parse(codeContent);
        finalName = finalDsl.name || '未命名用例';
        finalTags = finalDsl.tags || [];
      } catch {
        setError('DSL 内容 JSON 格式错误');
        return;
      }
    }

    saveMutation.mutate({
      name: finalName,
      description: finalDsl?.description,
      dsl_content: finalDsl,
      tags: finalTags.length > 0 ? finalTags : undefined,
    });
  };

  // 同步可视化编辑到代码
  const syncToCode = () => {
    const json = {
      name: dsl.name,
      description: dsl.description,
      steps: dsl.steps.map(({ id, ...rest }) => rest),
      variables: dsl.variables,
    };
    setCodeContent(JSON.stringify(json, null, 2));
  };

  // 同步代码到可视化编辑
  const syncToVisual = () => {
    try {
      const parsed = JSON.parse(codeContent);
      setDsl({
        name: parsed.name || '',
        description: parsed.description || '',
        tags: parsed.tags || [],
        steps: (parsed.steps || []).map((s: any, i: number) => ({ ...s, id: s.id || `step_${i}` })),
        variables: parsed.variables || {},
      });
      setError('');
    } catch {
      setError('JSON 格式错误，无法同步到可视化模式');
    }
  };

  const handleTabChange = (tab: 'visual' | 'code') => {
    if (tab === 'code' && activeTab === 'visual') {
      syncToCode();
    } else if (tab === 'visual' && activeTab === 'code') {
      syncToVisual();
    }
    setActiveTab(tab);
  };

  const handleCopy = async () => {
    const json = activeTab === 'visual' 
      ? JSON.stringify({ name: dsl.name, description: dsl.description, steps: dsl.steps.map(({ id, ...rest }) => rest), variables: dsl.variables }, null, 2)
      : codeContent;
    await navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const addTag = () => {
    if (newTag.trim() && !dsl.tags?.includes(newTag.trim())) {
      setDsl({ ...dsl, tags: [...(dsl.tags || []), newTag.trim()] });
      setNewTag('');
    }
  };

  const removeTag = (index: number) => {
    setDsl({ ...dsl, tags: dsl.tags?.filter((_, i) => i !== index) });
  };

  // 处理从元素检查器选择的定位器
  const handleSelectElement = (selector: Selector) => {
    setPendingSelector(selector);
    // 提示用户已选择元素
    setTimeout(() => setPendingSelector(null), 3000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div
        className={`bg-white rounded-xl shadow-xl overflow-hidden flex flex-col transition-all duration-300 ${
          showInspector ? 'w-[95vw] h-[95vh] max-w-none' : 'w-full max-w-4xl max-h-[90vh]'
        }`}
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {editCase ? '编辑测试用例' : '创建测试用例'}
            </h2>
            <p className="text-sm text-gray-500">使用可视化设计器或直接编写 DSL 代码</p>
          </div>
          <div className="flex items-center gap-3">
            {/* 元素检查器开关 */}
            {activeTab === 'visual' && (
              <button
                type="button"
                onClick={() => setShowInspector(!showInspector)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  showInspector 
                    ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
                title={showInspector ? '关闭元素检查器' : '打开元素检查器'}
              >
                {showInspector ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
                <span className="hidden sm:inline">元素检查器</span>
              </button>
            )}
            {/* 模式切换 */}
            <div className="flex bg-gray-200 rounded-lg p-0.5">
              <button
                type="button"
                onClick={() => handleTabChange('visual')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  activeTab === 'visual' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Eye size={16} />
                可视化
              </button>
              <button
                type="button"
                onClick={() => handleTabChange('code')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  activeTab === 'code' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Code size={16} />
                代码
              </button>
            </div>
            <button
              type="button"
              onClick={handleCopy}
              className="p-2 hover:bg-gray-200 rounded-lg text-gray-500"
              title="复制 DSL"
            >
              {copied ? <Check size={18} className="text-green-600" /> : <Copy size={18} />}
            </button>
            <button 
              onClick={() => { onClose(); resetForm(); }} 
              className="p-2 hover:bg-gray-200 rounded-lg text-gray-400 hover:text-gray-600"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mx-6 mt-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* 待应用的选择器提示 */}
        {pendingSelector && (
          <div className="mx-6 mt-4 bg-green-50 border border-green-200 px-4 py-3 rounded-lg text-sm flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-green-700">已选择元素:</span>
              <code className="bg-green-100 px-2 py-0.5 rounded text-green-800 font-mono text-xs">
                {pendingSelector.strategy}: {pendingSelector.value}
              </code>
            </div>
            <button
              onClick={() => {
                navigator.clipboard.writeText(pendingSelector.value);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="text-green-600 hover:text-green-800 text-sm underline"
            >
              复制定位值
            </button>
          </div>
        )}

        {/* 内容区域 */}
        <form
          onSubmit={handleSubmit}
          className="flex-1 overflow-hidden flex flex-col"
          onKeyDown={(e) => {
            // Avoid Enter in inputs triggering submit implicitly while editing.
            if (e.key === 'Enter' && !(e.target instanceof HTMLTextAreaElement)) {
              const target = e.target as HTMLElement;
              const tag = target.tagName?.toLowerCase();
              if (tag === 'input') e.preventDefault();
            }
          }}
        >
          <div className="flex-1 overflow-hidden flex">
            {/* 左侧编辑区 */}
            <div className={`flex-1 overflow-auto p-6 ${showInspector && activeTab === 'visual' ? 'border-r border-gray-200' : ''}`}>
              {activeTab === 'visual' ? (
                <div className="space-y-6">
                  {/* 基本信息 */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        用例名称 <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={dsl.name}
                        onChange={(e) => setDsl({ ...dsl, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="例如：用户登录流程"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                      <input
                        type="text"
                        value={dsl.description || ''}
                        onChange={(e) => setDsl({ ...dsl, description: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="简要描述测试用例的目的"
                      />
                    </div>
                  </div>

                  {/* 标签 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">标签</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {dsl.tags?.map((tag, i) => (
                        <span 
                          key={i} 
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 text-blue-700 rounded-full text-sm"
                        >
                          <Tag size={12} />
                          {tag}
                          <button
                            type="button"
                            onClick={() => removeTag(i)}
                            className="ml-1 hover:text-blue-900"
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
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                        className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                        placeholder="输入标签后按回车添加"
                      />
                      <button 
                        type="button"
                        onClick={addTag} 
                        className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200"
                      >
                        添加
                      </button>
                    </div>
                  </div>

                  {/* 步骤设计器 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      测试步骤 <span className="text-red-500">*</span>
                    </label>
                    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 min-h-[300px]">
                      <TestCaseStepDesigner
                        dsl={dsl}
                        onChange={setDsl}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    DSL 代码 (JSON)
                  </label>
                  <textarea
                    value={codeContent}
                    onChange={(e) => setCodeContent(e.target.value)}
                    className="w-full h-[400px] px-4 py-3 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-gray-900 text-gray-100"
                    spellCheck={false}
                  />
                </div>
              )}
            </div>

            {/* 右侧元素检查器 */}
            {showInspector && activeTab === 'visual' && (
              <div className="w-[55%] flex-shrink-0 overflow-hidden">
                <ElementInspector
                  onSelectElement={handleSelectElement}
                  className="h-full rounded-none border-0"
                />
              </div>
            )}
          </div>

          {/* 底部操作栏 */}
          <div className="flex items-center justify-between gap-3 px-6 py-4 border-t bg-gray-50">
            <div className="text-sm text-gray-500">
              {activeTab === 'visual' && dsl.steps.length > 0 && (
                <span>共 {dsl.steps.length} 个步骤</span>
              )}
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { onClose(); resetForm(); }}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100"
              >
                取消
              </button>
              <button
                type="submit"
                data-submit="true"
                disabled={saveMutation.isPending}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {saveMutation.isPending ? '保存中...' : editCase ? '保存修改' : '创建用例'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function TestCasesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<any>(null);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['testCases', projectId],
    queryFn: () => testCasesApi.list(projectId!, 1, 50),
    enabled: !!projectId,
    refetchOnMount: 'always',
  });

  const deleteMutation = useMutation({
    mutationFn: (caseId: string) => testCasesApi.update(caseId, { status: 'archived' } as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases', projectId] });
    },
  });

  const testCases = data?.data?.items || [];

  const statusLabels: Record<string, string> = {
    active: '启用',
    draft: '草稿',
    archived: '已归档',
  };

  const handleEdit = (tc: any) => {
    setEditingCase(tc);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingCase(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">测试用例</h2>
          <p className="text-sm text-gray-500">使用可视化设计器创建和管理测试用例</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={18} />
          <span>新建用例</span>
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : testCases.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <FileCode size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无测试用例</h3>
          <p className="text-gray-500 mb-6">创建您的第一个测试用例来定义测试步骤</p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            创建用例
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">标签</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">步骤数</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">更新时间</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {testCases.map((tc: any) => (
                <tr key={tc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <FileCode size={18} className="text-gray-400" />
                      <div>
                        <span className="font-medium text-gray-900">{tc.name}</span>
                        {tc.dsl_content?.description && (
                          <p className="text-xs text-gray-500 mt-0.5">{tc.dsl_content.description}</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                      tc.status === 'active' ? 'bg-green-100 text-green-700' :
                      tc.status === 'draft' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {statusLabels[tc.status] || tc.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-1 flex-wrap">
                      {(tc.tags || []).slice(0, 3).map((tag: string) => (
                        <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded">
                          <Tag size={10} />
                          {tag}
                        </span>
                      ))}
                      {(tc.tags || []).length > 3 && (
                        <span className="text-xs text-gray-400">+{tc.tags.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {tc.dsl_content?.steps?.length || 0} 步
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(tc.updated_at).toLocaleDateString('zh-CN')}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button 
                        onClick={() => handleEdit(tc)}
                        className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-blue-600" 
                        title="编辑"
                      >
                        <Edit size={16} />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('确定要删除此用例吗？')) {
                            deleteMutation.mutate(tc.id);
                          }
                        }}
                        className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-red-600"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <TestCaseEditorModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        projectId={projectId!}
        editCase={editingCase}
      />
    </div>
  );
}
