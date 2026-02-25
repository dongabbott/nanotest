// filepath: d:\project\nanotest\packages\flow-compiler\src\types.ts
import { z } from 'zod';

// Node types in the flow DAG
export const FlowNodeType = z.enum([
  'start',
  'end',
  'test_case',
  'parallel_group',
  'conditional',
  'wait',
  'data_source',
]);

// Edge condition types
export const EdgeConditionType = z.enum([
  'always',
  'on_success',
  'on_failure',
  'on_condition',
]);

// Flow node schema
export const FlowNodeSchema = z.object({
  id: z.string(),
  type: FlowNodeType,
  name: z.string(),
  config: z.record(z.any()).optional(),
  position: z.object({
    x: z.number(),
    y: z.number(),
  }).optional(),
  // For test_case nodes
  testCaseId: z.string().optional(),
  // For parallel_group nodes
  maxConcurrency: z.number().optional(),
  // For conditional nodes
  condition: z.object({
    expression: z.string(),
    variables: z.array(z.string()).optional(),
  }).optional(),
  // For wait nodes
  duration: z.number().optional(),
  waitForNodes: z.array(z.string()).optional(),
  // For data_source nodes
  dataSourceType: z.enum(['csv', 'json', 'database', 'api']).optional(),
  dataSourceConfig: z.record(z.any()).optional(),
});

// Flow edge schema
export const FlowEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  condition: EdgeConditionType.optional().default('always'),
  conditionExpression: z.string().optional(),
  label: z.string().optional(),
});

// Complete flow definition schema
export const FlowDefinitionSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  version: z.string().default('1.0'),
  nodes: z.array(FlowNodeSchema),
  edges: z.array(FlowEdgeSchema),
  variables: z.record(z.any()).optional(),
  timeout: z.number().optional().default(3600000), // 1 hour default
  retryPolicy: z.object({
    maxRetries: z.number().default(0),
    retryDelay: z.number().default(1000),
    retryOn: z.array(z.enum(['failure', 'timeout', 'error'])).optional(),
  }).optional(),
});

// Execution plan types
export const ExecutionStepSchema = z.object({
  id: z.string(),
  nodeId: z.string(),
  type: FlowNodeType,
  dependencies: z.array(z.string()), // Step IDs that must complete before this step
  parallelGroup: z.string().optional(), // Group ID for parallel execution
  config: z.record(z.any()),
  timeout: z.number().optional(),
  retries: z.number().optional(),
});

export const ExecutionPlanSchema = z.object({
  id: z.string(),
  flowId: z.string(),
  flowVersion: z.string(),
  steps: z.array(ExecutionStepSchema),
  parallelGroups: z.record(z.array(z.string())), // Group ID -> Step IDs
  criticalPath: z.array(z.string()), // Step IDs in critical path
  estimatedDuration: z.number().optional(),
  variables: z.record(z.any()),
});

// Type exports
export type FlowNodeType = z.infer<typeof FlowNodeType>;
export type EdgeConditionType = z.infer<typeof EdgeConditionType>;
export type FlowNode = z.infer<typeof FlowNodeSchema>;
export type FlowEdge = z.infer<typeof FlowEdgeSchema>;
export type FlowDefinition = z.infer<typeof FlowDefinitionSchema>;
export type ExecutionStep = z.infer<typeof ExecutionStepSchema>;
export type ExecutionPlan = z.infer<typeof ExecutionPlanSchema>;

// Compilation result
export interface CompilationResult {
  success: boolean;
  plan?: ExecutionPlan;
  errors?: CompilationError[];
  warnings?: CompilationWarning[];
}

export interface CompilationError {
  code: string;
  message: string;
  nodeId?: string;
  edgeId?: string;
}

export interface CompilationWarning {
  code: string;
  message: string;
  nodeId?: string;
  suggestion?: string;
}
