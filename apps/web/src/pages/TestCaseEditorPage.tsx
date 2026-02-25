// filepath: d:\project\nanotest\apps\web\src\pages\TestCaseEditorPage.tsx
import React, { useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Editor, { OnMount } from '@monaco-editor/react';
import {
  Save,
  Play,
  Sparkles,
  ChevronLeft,
  AlertCircle,
  CheckCircle,
  Loader2,
  FileCode,
  Settings,
  Eye,
  Crosshair,
} from 'lucide-react';
import { testCasesApi } from '../services/api';
import ElementInspector from '../components/ElementInspector';

// DSL 语法示例模板
const DSL_TEMPLATE = `# Test Case: Login Flow
# Description: Verify user can login with valid credentials

@tags: smoke, login, critical
@priority: high

steps:
  - action: launch_app
    package: com.example.app
    
  - action: wait_for_element
    locator: 
      type: id
      value: "login_button"
    timeout: 10s
    
  - action: tap
    locator:
      type: id  
      value: "username_input"
      
  - action: input_text
    text: "testuser@example.com"
    
  - action: tap
    locator:
      type: id
      value: "password_input"
      
  - action: input_text
    text: "{{env.TEST_PASSWORD}}"
    
  - action: tap
    locator:
      type: id
      value: "login_button"
      
  - action: assert_visible
    locator:
      type: id
      value: "home_screen"
    message: "Login should navigate to home screen"

assertions:
  - type: element_exists
    locator:
      type: id
      value: "welcome_message"
  - type: text_contains
    locator:
      type: id
      value: "welcome_message"
    expected: "Welcome"
`;

// 自定义 DSL 语言配置
const DSL_LANGUAGE_CONFIG = {
  keywords: [
    'steps', 'action', 'locator', 'type', 'value', 'timeout', 'text',
    'assertions', 'expected', 'message', 'package', 'tags', 'priority'
  ],
  actions: [
    'launch_app', 'tap', 'long_press', 'swipe', 'input_text', 'clear_text',
    'wait_for_element', 'assert_visible', 'assert_not_visible', 'assert_text',
    'screenshot', 'scroll', 'back', 'home'
  ],
  locatorTypes: ['id', 'xpath', 'accessibility_id', 'class', 'text', 'partial_text'],
};

export default function TestCaseEditorPage() {
  const { projectId, caseId } = useParams<{ projectId: string; caseId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const editorRef = useRef<any>(null);
  
  const [dslContent, setDslContent] = useState('');
  const [caseName, setCaseName] = useState('');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [aiSuggestion, setAiSuggestion] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [showInspector, setShowInspector] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const isNewCase = caseId === 'new';

  // 获取测试用例数据
  const { data: testCase, isLoading } = useQuery({
    queryKey: ['testCase', caseId],
    queryFn: () => testCasesApi.get(caseId!),
    enabled: !isNewCase && !!caseId,
    onSuccess: (data: any) => {
      setDslContent(data.data?.dsl_content || '');
      setCaseName(data.data?.name || '');
    },
  });

  // 保存测试用例
  const saveMutation = useMutation({
    mutationFn: (data: { name: string; dsl_content: string }) => {
      if (isNewCase) {
        return testCasesApi.create(projectId!, data);
      }
      return testCasesApi.update(caseId!, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases', projectId] });
      if (isNewCase) {
        navigate(`/projects/${projectId}/cases`);
      }
    },
  });

  // 验证 DSL
  const validateDSL = useCallback((content: string) => {
    const errors: string[] = [];
    
    if (!content.trim()) {
      errors.push('DSL content cannot be empty');
      return errors;
    }

    // 基本语法检查
    const lines = content.split('\n');
    let hasSteps = false;
    let inSteps = false;
    
    lines.forEach((line, index) => {
      const trimmed = line.trim();
      
      if (trimmed.startsWith('steps:')) {
        hasSteps = true;
        inSteps = true;
      }
      
      if (trimmed.startsWith('- action:') && inSteps) {
        const actionMatch = trimmed.match(/- action:\s*(\w+)/);
        if (actionMatch) {
          const action = actionMatch[1];
          if (!DSL_LANGUAGE_CONFIG.actions.includes(action)) {
            errors.push(`Line ${index + 1}: Unknown action "${action}"`);
          }
        }
      }
      
      // 检查缩进
      if (trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('@')) {
        const indent = line.length - line.trimStart().length;
        if (indent % 2 !== 0) {
          errors.push(`Line ${index + 1}: Inconsistent indentation`);
        }
      }
    });

    if (!hasSteps) {
      errors.push('Missing required "steps:" section');
    }

    return errors;
  }, []);

  // Monaco 编辑器挂载
  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // 注册 DSL 语言
    monaco.languages.register({ id: 'nanotest-dsl' });

    // 语法高亮
    monaco.languages.setMonarchTokensProvider('nanotest-dsl', {
      tokenizer: {
        root: [
          [/#.*$/, 'comment'],
          [/@\w+:/, 'annotation'],
          [/\b(steps|assertions|action|locator|type|value|timeout|text|expected|message|package)\b:/, 'keyword'],
          [/\b(launch_app|tap|long_press|swipe|input_text|clear_text|wait_for_element|assert_visible|assert_not_visible|assert_text|screenshot|scroll|back|home)\b/, 'action'],
          [/\b(id|xpath|accessibility_id|class|text|partial_text)\b/, 'locator-type'],
          [/"[^"]*"/, 'string'],
          [/'[^']*'/, 'string'],
          [/\{\{[^}]+\}\}/, 'variable'],
          [/\d+[smh]?/, 'number'],
          [/-\s/, 'delimiter'],
        ],
      },
    });

    // 主题
    monaco.editor.defineTheme('nanotest-theme', {
      base: 'vs',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '6B7280', fontStyle: 'italic' },
        { token: 'annotation', foreground: '7C3AED' },
        { token: 'keyword', foreground: '2563EB', fontStyle: 'bold' },
        { token: 'action', foreground: '059669' },
        { token: 'locator-type', foreground: 'D97706' },
        { token: 'string', foreground: 'DC2626' },
        { token: 'variable', foreground: 'DB2777' },
        { token: 'number', foreground: '7C3AED' },
        { token: 'delimiter', foreground: '6B7280' },
      ],
      colors: {
        'editor.background': '#FAFAFA',
      },
    });

    monaco.editor.setTheme('nanotest-theme');

    // 自动补全
    monaco.languages.registerCompletionItemProvider('nanotest-dsl', {
      provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        const suggestions = [
          ...DSL_LANGUAGE_CONFIG.actions.map((action) => ({
            label: action,
            kind: monaco.languages.CompletionItemKind.Function,
            insertText: action,
            range,
            documentation: `Action: ${action}`,
          })),
          ...DSL_LANGUAGE_CONFIG.locatorTypes.map((type) => ({
            label: type,
            kind: monaco.languages.CompletionItemKind.Enum,
            insertText: type,
            range,
            documentation: `Locator type: ${type}`,
          })),
          {
            label: 'step-tap',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: [
              '- action: tap',
              '  locator:',
              '    type: ${1|id,xpath,accessibility_id|}',
              '    value: "${2:element_id}"',
            ].join('\n'),
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            range,
            documentation: 'Insert a tap action step',
          },
          {
            label: 'step-input',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: [
              '- action: input_text',
              '  locator:',
              '    type: ${1|id,xpath,accessibility_id|}',
              '    value: "${2:element_id}"',
              '  text: "${3:input text}"',
            ].join('\n'),
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            range,
            documentation: 'Insert an input text action step',
          },
          {
            label: 'step-assert',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: [
              '- action: assert_visible',
              '  locator:',
              '    type: ${1|id,xpath,accessibility_id|}',
              '    value: "${2:element_id}"',
              '  message: "${3:Assertion message}"',
            ].join('\n'),
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            range,
            documentation: 'Insert an assertion step',
          },
        ];

        return { suggestions };
      },
    });
  };

  // 处理编辑器内容变化
  const handleEditorChange = (value: string | undefined) => {
    const content = value || '';
    setDslContent(content);
    
    // 实时验证
    const errors = validateDSL(content);
    setValidationErrors(errors);
  };

  // AI 生成测试步骤
  const handleAIGenerate = async () => {
    setIsGenerating(true);
    setAiSuggestion('');
    
    try {
      // 模拟 AI 生成（实际应调用后端 AI 服务）
      await new Promise((resolve) => setTimeout(resolve, 2000));
      
      const suggestion = `# AI Generated suggestion based on your current steps:
# Consider adding error handling and additional assertions

  - action: wait_for_element
    locator:
      type: id
      value: "loading_indicator"
    timeout: 5s
    should_disappear: true
    
  - action: assert_not_visible
    locator:
      type: id
      value: "error_message"
    message: "No error should be displayed"
    
  - action: screenshot
    name: "verification_screenshot"`;
      
      setAiSuggestion(suggestion);
    } catch (error) {
      console.error('AI generation failed:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // 插入 AI 建议
  const insertAISuggestion = () => {
    if (aiSuggestion && editorRef.current) {
      const editor = editorRef.current;
      const position = editor.getPosition();
      editor.executeEdits('ai-suggestion', [
        {
          range: {
            startLineNumber: position.lineNumber,
            startColumn: position.column,
            endLineNumber: position.lineNumber,
            endColumn: position.column,
          },
          text: '\n' + aiSuggestion,
        },
      ]);
      setAiSuggestion('');
    }
  };

  // 保存
  const handleSave = () => {
    const errors = validateDSL(dslContent);
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }
    
    saveMutation.mutate({
      name: caseName || 'Untitled Test Case',
      dsl_content: dslContent,
    });
  };

  // 运行测试
  const handleRun = () => {
    // TODO: 实现运行测试功能
    console.log('Running test case...');
  };

  if (isLoading && !isNewCase) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="animate-spin text-blue-600" size={32} />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(`/projects/${projectId}/cases`)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ChevronLeft size={20} />
          </button>
          <div className="flex items-center gap-3">
            <FileCode className="text-blue-600" size={24} />
            <input
              type="text"
              value={caseName}
              onChange={(e) => setCaseName(e.target.value)}
              placeholder="Test Case Name"
              className="text-xl font-semibold bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1"
            />
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              showPreview ? 'bg-blue-100 text-blue-700' : 'hover:bg-gray-100'
            }`}
          >
            <Eye size={18} />
            <span>Preview</span>
          </button>
          
          <button
            onClick={() => setShowInspector(!showInspector)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              showInspector ? 'bg-green-100 text-green-700' : 'hover:bg-gray-100'
            }`}
          >
            <Crosshair size={18} />
            <span>元素检查</span>
          </button>
          
          <button
            onClick={handleAIGenerate}
            disabled={isGenerating}
            className="flex items-center gap-2 px-4 py-2 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition-colors disabled:opacity-50"
          >
            {isGenerating ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Sparkles size={18} />
            )}
            <span>AI Assist</span>
          </button>
          
          <button
            onClick={handleRun}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Play size={18} />
            <span>Run</span>
          </button>
          
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {saveMutation.isPending ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Save size={18} />
            )}
            <span>Save</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Editor */}
        <div className={`flex-1 flex flex-col ${showPreview ? 'w-1/2' : 'w-full'}`}>
          {/* Validation Errors */}
          {validationErrors.length > 0 && (
            <div className="bg-red-50 border-b border-red-200 px-4 py-2">
              <div className="flex items-start gap-2">
                <AlertCircle size={16} className="text-red-500 mt-0.5" />
                <div className="text-sm text-red-700">
                  {validationErrors.map((error, i) => (
                    <div key={i}>{error}</div>
                  ))}
                </div>
              </div>
            </div>
          )}
          
          {/* Monaco Editor */}
          <div className="flex-1">
            <Editor
              height="100%"
              defaultLanguage="nanotest-dsl"
              value={dslContent || (isNewCase ? DSL_TEMPLATE : '')}
              onChange={handleEditorChange}
              onMount={handleEditorMount}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                wordWrap: 'on',
                automaticLayout: true,
                tabSize: 2,
                scrollBeyondLastLine: false,
                folding: true,
                renderLineHighlight: 'all',
              }}
            />
          </div>
        </div>

        {/* Preview Panel */}
        {showPreview && (
          <div className="w-1/2 border-l border-gray-200 bg-gray-50 overflow-auto">
            <div className="p-4">
              <h3 className="font-semibold text-gray-900 mb-4">Step Preview</h3>
              <StepPreview dslContent={dslContent} />
            </div>
          </div>
        )}

        {/* AI Suggestion Panel */}
        {aiSuggestion && (
          <div className="w-80 border-l border-gray-200 bg-purple-50 flex flex-col">
            <div className="p-4 border-b border-purple-200">
              <div className="flex items-center gap-2 text-purple-700 font-medium">
                <Sparkles size={18} />
                <span>AI Suggestion</span>
              </div>
            </div>
            <div className="flex-1 p-4 overflow-auto">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
                {aiSuggestion}
              </pre>
            </div>
            <div className="p-4 border-t border-purple-200 flex gap-2">
              <button
                onClick={insertAISuggestion}
                className="flex-1 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors"
              >
                Insert
              </button>
              <button
                onClick={() => setAiSuggestion('')}
                className="px-4 py-2 border border-purple-300 rounded-lg hover:bg-purple-100 transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Element Inspector Panel */}
        {showInspector && (
          <div className="w-96 border-l border-gray-200 flex flex-col">
            <ElementInspector
              onElementSelect={(locator) => {
                const locatorText = `locator:\n      type: ${locator.strategy.replace(' ', '_')}\n      value: "${locator.value}"`;
                if (editorRef.current) {
                  const editor = editorRef.current;
                  const position = editor.getPosition();
                  editor.executeEdits('element-inspector', [
                    {
                      range: {
                        startLineNumber: position.lineNumber,
                        startColumn: position.column,
                        endLineNumber: position.lineNumber,
                        endColumn: position.column,
                      },
                      text: locatorText,
                    },
                  ]);
                }
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// Step Preview Component
function StepPreview({ dslContent }: { dslContent: string }) {
  const steps = parseDSLSteps(dslContent);

  if (steps.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No steps defined yet
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {steps.map((step, index) => (
        <div
          key={index}
          className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-sm transition-shadow"
        >
          <div className="flex items-center gap-3">
            <span className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-medium">
              {index + 1}
            </span>
            <div>
              <div className="font-medium text-gray-900">{step.action}</div>
              {step.locator && (
                <div className="text-sm text-gray-500">
                  {step.locator.type}: {step.locator.value}
                </div>
              )}
              {step.text && (
                <div className="text-sm text-gray-500">Text: {step.text}</div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// 简单的 DSL 解析器
function parseDSLSteps(content: string): Array<{
  action: string;
  locator?: { type: string; value: string };
  text?: string;
}> {
  const steps: Array<{
    action: string;
    locator?: { type: string; value: string };
    text?: string;
  }> = [];

  const lines = content.split('\n');
  let currentStep: any = null;
  let inLocator = false;

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith('- action:')) {
      if (currentStep) {
        steps.push(currentStep);
      }
      currentStep = {
        action: trimmed.replace('- action:', '').trim(),
      };
      inLocator = false;
    } else if (trimmed === 'locator:' && currentStep) {
      inLocator = true;
      currentStep.locator = { type: '', value: '' };
    } else if (trimmed.startsWith('type:') && inLocator && currentStep?.locator) {
      currentStep.locator.type = trimmed.replace('type:', '').trim();
    } else if (trimmed.startsWith('value:') && inLocator && currentStep?.locator) {
      currentStep.locator.value = trimmed.replace('value:', '').trim().replace(/"/g, '');
    } else if (trimmed.startsWith('text:') && currentStep) {
      currentStep.text = trimmed.replace('text:', '').trim().replace(/"/g, '');
      inLocator = false;
    }
  }

  if (currentStep) {
    steps.push(currentStep);
  }

  return steps;
}
