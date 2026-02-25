import { v4 as uuidv4 } from 'uuid';
import {
  FlowDefinition,
  FlowNode,
  FlowEdge,
  ExecutionPlan,
  ExecutionStep,
  CompilationResult,
  CompilationError,
  CompilationWarning,
  FlowDefinitionSchema,
} from './types';
import { validateFlow } from './validator';
import { optimizeExecutionPlan } from './optimizer';

export class FlowCompiler {
  private flow: FlowDefinition;
  private errors: CompilationError[] = [];
  private warnings: CompilationWarning[] = [];
  private nodeMap: Map<string, FlowNode> = new Map();
  private edgeMap: Map<string, FlowEdge[]> = new Map(); // nodeId -> outgoing edges
  private incomingEdgeMap: Map<string, FlowEdge[]> = new Map(); // nodeId -> incoming edges

  constructor(flowDefinition: unknown) {
    // Validate and parse flow definition
    const parseResult = FlowDefinitionSchema.safeParse(flowDefinition);
    if (!parseResult.success) {
      throw new Error(`Invalid flow definition: ${parseResult.error.message}`);
    }
    this.flow = parseResult.data;
    this.buildMaps();
  }

  private buildMaps(): void {
    // Build node map
    for (const node of this.flow.nodes) {
      this.nodeMap.set(node.id, node);
    }

    // Build edge maps
    for (const edge of this.flow.edges) {
      // Outgoing edges
      if (!this.edgeMap.has(edge.source)) {
        this.edgeMap.set(edge.source, []);
      }
      this.edgeMap.get(edge.source)!.push(edge);

      // Incoming edges
      if (!this.incomingEdgeMap.has(edge.target)) {
        this.incomingEdgeMap.set(edge.target, []);
      }
      this.incomingEdgeMap.get(edge.target)!.push(edge);
    }
  }

  compile(options: CompileOptions = {}): CompilationResult {
    this.errors = [];
    this.warnings = [];

    // Step 1: Validate the flow
    const validationResult = validateFlow(this.flow);
    if (!validationResult.valid) {
      return {
        success: false,
        errors: validationResult.errors,
        warnings: validationResult.warnings,
      };
    }
    this.warnings.push(...(validationResult.warnings || []));

    // Step 2: Topological sort to determine execution order
    const sortResult = this.topologicalSort();
    if (!sortResult.success) {
      return {
        success: false,
        errors: this.errors,
        warnings: this.warnings,
      };
    }

    // Step 3: Build execution steps
    const steps = this.buildExecutionSteps(sortResult.order!);

    // Step 4: Identify parallel groups
    const parallelGroups = this.identifyParallelGroups(steps);

    // Step 5: Calculate critical path
    const criticalPath = this.calculateCriticalPath(steps);

    // Step 6: Build execution plan
    let plan: ExecutionPlan = {
      id: uuidv4(),
      flowId: this.flow.id,
      flowVersion: this.flow.version,
      steps,
      parallelGroups,
      criticalPath,
      estimatedDuration: this.estimateDuration(steps, criticalPath),
      variables: this.flow.variables || {},
    };

    // Step 7: Optimize if requested
    if (options.optimize !== false) {
      plan = optimizeExecutionPlan(plan, options.optimizationLevel || 'standard');
    }

    return {
      success: true,
      plan,
      warnings: this.warnings.length > 0 ? this.warnings : undefined,
    };
  }

  private topologicalSort(): { success: boolean; order?: string[] } {
    const visited = new Set<string>();
    const recursionStack = new Set<string>();
    const order: string[] = [];

    const visit = (nodeId: string): boolean => {
      if (recursionStack.has(nodeId)) {
        this.errors.push({
          code: 'CYCLE_DETECTED',
          message: `Cycle detected involving node: ${nodeId}`,
          nodeId,
        });
        return false;
      }

      if (visited.has(nodeId)) {
        return true;
      }

      visited.add(nodeId);
      recursionStack.add(nodeId);

      const outgoingEdges = this.edgeMap.get(nodeId) || [];
      for (const edge of outgoingEdges) {
        if (!visit(edge.target)) {
          return false;
        }
      }

      recursionStack.delete(nodeId);
      order.unshift(nodeId);
      return true;
    };

    // Find start node and begin traversal
    const startNode = this.flow.nodes.find(n => n.type === 'start');
    if (!startNode) {
      this.errors.push({
        code: 'NO_START_NODE',
        message: 'Flow must have a start node',
      });
      return { success: false };
    }

    if (!visit(startNode.id)) {
      return { success: false };
    }

    // Visit any unvisited nodes (disconnected components)
    for (const node of this.flow.nodes) {
      if (!visited.has(node.id)) {
        this.warnings.push({
          code: 'UNREACHABLE_NODE',
          message: `Node ${node.id} is not reachable from start`,
          nodeId: node.id,
          suggestion: 'Consider removing this node or connecting it to the flow',
        });
        if (!visit(node.id)) {
          return { success: false };
        }
      }
    }

    return { success: true, order };
  }

  private buildExecutionSteps(order: string[]): ExecutionStep[] {
    const steps: ExecutionStep[] = [];
    const nodeToStepId = new Map<string, string>();

    for (const nodeId of order) {
      const node = this.nodeMap.get(nodeId)!;
      const stepId = uuidv4();
      nodeToStepId.set(nodeId, stepId);

      // Get dependencies (steps that must complete before this one)
      const incomingEdges = this.incomingEdgeMap.get(nodeId) || [];
      const dependencies = incomingEdges
        .map(edge => nodeToStepId.get(edge.source))
        .filter((id): id is string => id !== undefined);

      const step: ExecutionStep = {
        id: stepId,
        nodeId: node.id,
        type: node.type,
        dependencies,
        config: this.buildStepConfig(node),
        timeout: node.config?.timeout || this.getDefaultTimeout(node.type),
        retries: node.config?.retries || 0,
      };

      // Handle parallel groups
      if (node.type === 'parallel_group') {
        step.parallelGroup = node.id;
      }

      steps.push(step);
    }

    return steps;
  }

  private buildStepConfig(node: FlowNode): Record<string, any> {
    const config: Record<string, any> = {
      nodeName: node.name,
      ...node.config,
    };

    switch (node.type) {
      case 'test_case':
        config.testCaseId = node.testCaseId;
        break;
      case 'conditional':
        config.condition = node.condition;
        break;
      case 'wait':
        config.duration = node.duration;
        config.waitForNodes = node.waitForNodes;
        break;
      case 'data_source':
        config.dataSourceType = node.dataSourceType;
        config.dataSourceConfig = node.dataSourceConfig;
        break;
      case 'parallel_group':
        config.maxConcurrency = node.maxConcurrency || 5;
        break;
    }

    return config;
  }

  private getDefaultTimeout(nodeType: string): number {
    const timeouts: Record<string, number> = {
      start: 1000,
      end: 1000,
      test_case: 300000, // 5 minutes
      parallel_group: 600000, // 10 minutes
      conditional: 5000,
      wait: 60000,
      data_source: 30000,
    };
    return timeouts[nodeType] || 60000;
  }

  private identifyParallelGroups(steps: ExecutionStep[]): Record<string, string[]> {
    const groups: Record<string, string[]> = {};

    // Find steps that can run in parallel (same dependencies)
    const dependencyGroups = new Map<string, ExecutionStep[]>();

    for (const step of steps) {
      const depKey = step.dependencies.sort().join(',');
      if (!dependencyGroups.has(depKey)) {
        dependencyGroups.set(depKey, []);
      }
      dependencyGroups.get(depKey)!.push(step);
    }

    // Create parallel groups for steps with same dependencies
    let groupIndex = 0;
    for (const [, groupSteps] of dependencyGroups) {
      if (groupSteps.length > 1) {
        const groupId = `parallel_${groupIndex++}`;
        groups[groupId] = groupSteps.map(s => s.id);

        // Mark steps as part of this parallel group
        for (const step of groupSteps) {
          if (!step.parallelGroup) {
            step.parallelGroup = groupId;
          }
        }
      }
    }

    return groups;
  }

  private calculateCriticalPath(steps: ExecutionStep[]): string[] {
    const stepMap = new Map(steps.map(s => [s.id, s]));
    const longestPath = new Map<string, number>();
    const pathPredecessor = new Map<string, string | null>();

    // Calculate longest path to each step
    for (const step of steps) {
      let maxPathLength = 0;
      let predecessor: string | null = null;

      for (const depId of step.dependencies) {
        const depPath = longestPath.get(depId) || 0;
        const depStep = stepMap.get(depId);
        const pathLength = depPath + (depStep?.timeout || 0);

        if (pathLength > maxPathLength) {
          maxPathLength = pathLength;
          predecessor = depId;
        }
      }

      longestPath.set(step.id, maxPathLength + (step.timeout || 0));
      pathPredecessor.set(step.id, predecessor);
    }

    // Find the end step with longest path
    let maxLength = 0;
    let endStepId: string | null = null;

    for (const step of steps) {
      if (step.type === 'end') {
        const length = longestPath.get(step.id) || 0;
        if (length > maxLength) {
          maxLength = length;
          endStepId = step.id;
        }
      }
    }

    // Reconstruct critical path
    const criticalPath: string[] = [];
    let current = endStepId;

    while (current) {
      criticalPath.unshift(current);
      current = pathPredecessor.get(current) || null;
    }

    return criticalPath;
  }

  private estimateDuration(steps: ExecutionStep[], criticalPath: string[]): number {
    const stepMap = new Map(steps.map(s => [s.id, s]));
    return criticalPath.reduce((total, stepId) => {
      const step = stepMap.get(stepId);
      return total + (step?.timeout || 0);
    }, 0);
  }
}

export interface CompileOptions {
  optimize?: boolean;
  optimizationLevel?: 'minimal' | 'standard' | 'aggressive';
  targetConcurrency?: number;
}

export function compileFlow(
  flowDefinition: unknown,
  options: CompileOptions = {}
): CompilationResult {
  try {
    const compiler = new FlowCompiler(flowDefinition);
    return compiler.compile(options);
  } catch (error) {
    return {
      success: false,
      errors: [{
        code: 'COMPILATION_ERROR',
        message: error instanceof Error ? error.message : 'Unknown error',
      }],
    };
  }
}
