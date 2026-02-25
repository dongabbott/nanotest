import {
  FlowDefinition,
  FlowNode,
  FlowEdge,
  CompilationError,
  CompilationWarning,
} from './types';

export interface ValidationResult {
  valid: boolean;
  errors?: CompilationError[];
  warnings?: CompilationWarning[];
}

export function validateFlow(flow: FlowDefinition): ValidationResult {
  const errors: CompilationError[] = [];
  const warnings: CompilationWarning[] = [];
  const nodeIds = new Set(flow.nodes.map(n => n.id));

  // Validate nodes
  validateNodes(flow.nodes, errors, warnings);

  // Validate edges
  validateEdges(flow.edges, nodeIds, errors, warnings);

  // Validate flow structure
  validateFlowStructure(flow, errors, warnings);

  return {
    valid: errors.length === 0,
    errors: errors.length > 0 ? errors : undefined,
    warnings: warnings.length > 0 ? warnings : undefined,
  };
}

function validateNodes(
  nodes: FlowNode[],
  errors: CompilationError[],
  warnings: CompilationWarning[]
): void {
  const nodeIds = new Set<string>();
  let startCount = 0;
  let endCount = 0;

  for (const node of nodes) {
    // Check for duplicate node IDs
    if (nodeIds.has(node.id)) {
      errors.push({
        code: 'DUPLICATE_NODE_ID',
        message: `Duplicate node ID: ${node.id}`,
        nodeId: node.id,
      });
    }
    nodeIds.add(node.id);

    // Count start and end nodes
    if (node.type === 'start') startCount++;
    if (node.type === 'end') endCount++;

    // Validate node-specific requirements
    validateNodeByType(node, errors, warnings);
  }

  // Must have exactly one start node
  if (startCount === 0) {
    errors.push({
      code: 'NO_START_NODE',
      message: 'Flow must have exactly one start node',
    });
  } else if (startCount > 1) {
    errors.push({
      code: 'MULTIPLE_START_NODES',
      message: `Flow has ${startCount} start nodes, but must have exactly one`,
    });
  }

  // Must have at least one end node
  if (endCount === 0) {
    errors.push({
      code: 'NO_END_NODE',
      message: 'Flow must have at least one end node',
    });
  }
}

function validateNodeByType(
  node: FlowNode,
  errors: CompilationError[],
  warnings: CompilationWarning[]
): void {
  switch (node.type) {
    case 'test_case':
      if (!node.testCaseId) {
        errors.push({
          code: 'MISSING_TEST_CASE_ID',
          message: `Test case node "${node.name}" must have a testCaseId`,
          nodeId: node.id,
        });
      }
      break;

    case 'conditional':
      if (!node.condition?.expression) {
        errors.push({
          code: 'MISSING_CONDITION',
          message: `Conditional node "${node.name}" must have a condition expression`,
          nodeId: node.id,
        });
      }
      break;

    case 'wait':
      if (!node.duration && (!node.waitForNodes || node.waitForNodes.length === 0)) {
        warnings.push({
          code: 'WAIT_NO_CRITERIA',
          message: `Wait node "${node.name}" has no duration or waitForNodes specified`,
          nodeId: node.id,
          suggestion: 'Add either duration or waitForNodes to the wait node',
        });
      }
      break;

    case 'data_source':
      if (!node.dataSourceType) {
        errors.push({
          code: 'MISSING_DATA_SOURCE_TYPE',
          message: `Data source node "${node.name}" must specify dataSourceType`,
          nodeId: node.id,
        });
      }
      break;

    case 'parallel_group':
      if (node.maxConcurrency !== undefined && node.maxConcurrency < 1) {
        errors.push({
          code: 'INVALID_CONCURRENCY',
          message: `Parallel group "${node.name}" maxConcurrency must be at least 1`,
          nodeId: node.id,
        });
      }
      break;
  }
}

function validateEdges(
  edges: FlowEdge[],
  nodeIds: Set<string>,
  errors: CompilationError[],
  warnings: CompilationWarning[]
): void {
  const edgeIds = new Set<string>();
  const edgeKeys = new Set<string>();

  for (const edge of edges) {
    // Check for duplicate edge IDs
    if (edgeIds.has(edge.id)) {
      errors.push({
        code: 'DUPLICATE_EDGE_ID',
        message: `Duplicate edge ID: ${edge.id}`,
        edgeId: edge.id,
      });
    }
    edgeIds.add(edge.id);

    // Check for duplicate edges (same source and target)
    const edgeKey = `${edge.source}->${edge.target}`;
    if (edgeKeys.has(edgeKey)) {
      warnings.push({
        code: 'DUPLICATE_EDGE',
        message: `Multiple edges from "${edge.source}" to "${edge.target}"`,
        suggestion: 'Consider merging these edges or using different conditions',
      });
    }
    edgeKeys.add(edgeKey);

    // Validate source node exists
    if (!nodeIds.has(edge.source)) {
      errors.push({
        code: 'INVALID_EDGE_SOURCE',
        message: `Edge "${edge.id}" references non-existent source node: ${edge.source}`,
        edgeId: edge.id,
      });
    }

    // Validate target node exists
    if (!nodeIds.has(edge.target)) {
      errors.push({
        code: 'INVALID_EDGE_TARGET',
        message: `Edge "${edge.id}" references non-existent target node: ${edge.target}`,
        edgeId: edge.id,
      });
    }

    // Validate self-loops
    if (edge.source === edge.target) {
      errors.push({
        code: 'SELF_LOOP',
        message: `Edge "${edge.id}" creates a self-loop on node "${edge.source}"`,
        edgeId: edge.id,
        nodeId: edge.source,
      });
    }

    // Validate conditional edges have expressions
    if (edge.condition === 'on_condition' && !edge.conditionExpression) {
      errors.push({
        code: 'MISSING_EDGE_CONDITION',
        message: `Edge "${edge.id}" has condition type "on_condition" but no expression`,
        edgeId: edge.id,
      });
    }
  }
}

function validateFlowStructure(
  flow: FlowDefinition,
  errors: CompilationError[],
  warnings: CompilationWarning[]
): void {
  const nodeMap = new Map(flow.nodes.map(n => [n.id, n]));
  const outgoingEdges = new Map<string, FlowEdge[]>();
  const incomingEdges = new Map<string, FlowEdge[]>();

  // Build edge maps
  for (const edge of flow.edges) {
    if (!outgoingEdges.has(edge.source)) {
      outgoingEdges.set(edge.source, []);
    }
    outgoingEdges.get(edge.source)!.push(edge);

    if (!incomingEdges.has(edge.target)) {
      incomingEdges.set(edge.target, []);
    }
    incomingEdges.get(edge.target)!.push(edge);
  }

  // Validate start node has no incoming edges
  for (const node of flow.nodes) {
    if (node.type === 'start') {
      const incoming = incomingEdges.get(node.id) || [];
      if (incoming.length > 0) {
        errors.push({
          code: 'START_HAS_INCOMING',
          message: `Start node "${node.id}" should not have incoming edges`,
          nodeId: node.id,
        });
      }
    }

    // Validate end node has no outgoing edges
    if (node.type === 'end') {
      const outgoing = outgoingEdges.get(node.id) || [];
      if (outgoing.length > 0) {
        errors.push({
          code: 'END_HAS_OUTGOING',
          message: `End node "${node.id}" should not have outgoing edges`,
          nodeId: node.id,
        });
      }
    }

    // Validate conditional nodes have multiple outgoing edges
    if (node.type === 'conditional') {
      const outgoing = outgoingEdges.get(node.id) || [];
      if (outgoing.length < 2) {
        warnings.push({
          code: 'CONDITIONAL_SINGLE_PATH',
          message: `Conditional node "${node.name}" has only ${outgoing.length} outgoing edge(s)`,
          nodeId: node.id,
          suggestion: 'Conditional nodes typically should have at least 2 outgoing paths',
        });
      }
    }

    // Check for orphan nodes (no edges at all, except start/end)
    if (node.type !== 'start' && node.type !== 'end') {
      const incoming = incomingEdges.get(node.id) || [];
      const outgoing = outgoingEdges.get(node.id) || [];

      if (incoming.length === 0 && outgoing.length === 0) {
        errors.push({
          code: 'ORPHAN_NODE',
          message: `Node "${node.name}" (${node.id}) has no connections`,
          nodeId: node.id,
        });
      } else if (incoming.length === 0) {
        warnings.push({
          code: 'NO_INCOMING_EDGES',
          message: `Node "${node.name}" has no incoming edges and may be unreachable`,
          nodeId: node.id,
        });
      } else if (outgoing.length === 0) {
        // Node is not start or end, so having no outgoing edges means dead end
        warnings.push({
          code: 'NO_OUTGOING_EDGES',
          message: `Node "${node.name}" has no outgoing edges (dead end)`,
          nodeId: node.id,
          suggestion: 'Connect this node to an end node or another node',
        });
      }
    }
  }

  // Validate wait nodes reference existing nodes
  for (const node of flow.nodes) {
    if (node.type === 'wait' && node.waitForNodes) {
      for (const waitNodeId of node.waitForNodes) {
        if (!nodeMap.has(waitNodeId)) {
          errors.push({
            code: 'INVALID_WAIT_REFERENCE',
            message: `Wait node "${node.name}" references non-existent node: ${waitNodeId}`,
            nodeId: node.id,
          });
        }
      }
    }
  }
}
