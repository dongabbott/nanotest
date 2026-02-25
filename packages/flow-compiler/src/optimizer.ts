import { ExecutionPlan, ExecutionStep } from './types';

type OptimizationLevel = 'minimal' | 'standard' | 'aggressive';

export function optimizeExecutionPlan(
  plan: ExecutionPlan,
  level: OptimizationLevel = 'standard'
): ExecutionPlan {
  let optimizedPlan = { ...plan };

  // Apply optimizations based on level
  switch (level) {
    case 'aggressive':
      optimizedPlan = mergeSequentialSteps(optimizedPlan);
      optimizedPlan = maximizeParallelism(optimizedPlan);
      optimizedPlan = optimizeResourceUsage(optimizedPlan);
      optimizedPlan = eliminateRedundantWaits(optimizedPlan);
      break;
    case 'standard':
      optimizedPlan = maximizeParallelism(optimizedPlan);
      optimizedPlan = eliminateRedundantWaits(optimizedPlan);
      break;
    case 'minimal':
      optimizedPlan = eliminateRedundantWaits(optimizedPlan);
      break;
  }

  // Recalculate estimated duration after optimization
  optimizedPlan.estimatedDuration = calculateEstimatedDuration(optimizedPlan);

  return optimizedPlan;
}

/**
 * Merge sequential steps that can be combined
 */
function mergeSequentialSteps(plan: ExecutionPlan): ExecutionPlan {
  const steps = [...plan.steps];
  const merged: ExecutionStep[] = [];
  const skipIds = new Set<string>();

  for (const step of steps) {
    if (skipIds.has(step.id)) continue;

    // Find steps that only depend on this step
    const dependents = steps.filter(
      s => s.dependencies.length === 1 && s.dependencies[0] === step.id
    );

    // If there's exactly one dependent and it's of the same type, consider merging
    if (
      dependents.length === 1 &&
      dependents[0].type === step.type &&
      step.type === 'test_case'
    ) {
      const dependent = dependents[0];
      // Merge the steps
      const mergedStep: ExecutionStep = {
        ...step,
        config: {
          ...step.config,
          mergedSteps: [
            { id: step.id, config: step.config },
            { id: dependent.id, config: dependent.config },
          ],
        },
        timeout: (step.timeout || 0) + (dependent.timeout || 0),
      };
      merged.push(mergedStep);
      skipIds.add(dependent.id);

      // Update dependencies of steps that depended on the merged step
      for (const s of steps) {
        const depIndex = s.dependencies.indexOf(dependent.id);
        if (depIndex !== -1) {
          s.dependencies[depIndex] = step.id;
        }
      }
    } else {
      merged.push(step);
    }
  }

  return { ...plan, steps: merged };
}

/**
 * Maximize parallel execution where possible
 */
function maximizeParallelism(plan: ExecutionPlan): ExecutionPlan {
  const steps = [...plan.steps];
  const parallelGroups = { ...plan.parallelGroups };

  // Find steps that can run in parallel but aren't grouped
  const stepsByDepKey = new Map<string, ExecutionStep[]>();

  for (const step of steps) {
    if (step.parallelGroup) continue; // Already in a group

    const depKey = step.dependencies.sort().join(',');
    if (!stepsByDepKey.has(depKey)) {
      stepsByDepKey.set(depKey, []);
    }
    stepsByDepKey.get(depKey)!.push(step);
  }

  // Create new parallel groups
  let groupIndex = Object.keys(parallelGroups).length;
  for (const [, groupSteps] of stepsByDepKey) {
    if (groupSteps.length >= 2) {
      const groupId = `optimized_parallel_${groupIndex++}`;
      parallelGroups[groupId] = groupSteps.map(s => s.id);

      for (const step of groupSteps) {
        step.parallelGroup = groupId;
      }
    }
  }

  return { ...plan, steps, parallelGroups };
}

/**
 * Optimize resource usage by balancing parallel execution
 */
function optimizeResourceUsage(plan: ExecutionPlan): ExecutionPlan {
  const steps = [...plan.steps];
  const parallelGroups = { ...plan.parallelGroups };

  // Limit parallel groups to reasonable concurrency
  const MAX_CONCURRENCY = 10;

  for (const [groupId, stepIds] of Object.entries(parallelGroups)) {
    if (stepIds.length > MAX_CONCURRENCY) {
      // Split into smaller groups
      const chunks: string[][] = [];
      for (let i = 0; i < stepIds.length; i += MAX_CONCURRENCY) {
        chunks.push(stepIds.slice(i, i + MAX_CONCURRENCY));
      }

      // Update groups
      delete parallelGroups[groupId];
      chunks.forEach((chunk, i) => {
        const newGroupId = `${groupId}_chunk_${i}`;
        parallelGroups[newGroupId] = chunk;

        // Update steps
        for (const stepId of chunk) {
          const step = steps.find(s => s.id === stepId);
          if (step) {
            step.parallelGroup = newGroupId;
          }
        }
      });
    }
  }

  return { ...plan, steps, parallelGroups };
}

/**
 * Eliminate redundant wait steps
 */
function eliminateRedundantWaits(plan: ExecutionPlan): ExecutionPlan {
  const steps = plan.steps.filter(step => {
    if (step.type !== 'wait') return true;

    // Remove waits with zero duration and no waitForNodes
    if (!step.config.duration && !step.config.waitForNodes?.length) {
      return false;
    }

    // Remove waits that are immediately followed by end
    const dependentSteps = plan.steps.filter((s: ExecutionStep) =>
      s.dependencies.includes(step.id)
    );

    if (dependentSteps.length === 1 && dependentSteps[0].type === 'end') {
      // This wait is right before end and doesn't add value
      if (!step.config.duration && step.config.waitForNodes?.length === 1) {
        // Update the end step to depend on what the wait was waiting for
        const endStep = dependentSteps[0];
        const waitIdx = endStep.dependencies.indexOf(step.id);
        if (waitIdx !== -1) {
          endStep.dependencies.splice(waitIdx, 1, ...step.dependencies);
        }
        return false;
      }
    }

    return true;
  });

  // Update dependencies for removed steps
  const removedIds = new Set<string>(
    plan.steps.filter(s => !steps.includes(s)).map(s => s.id)
  );

  for (const step of steps) {
    step.dependencies = step.dependencies.filter((d: string) => !removedIds.has(d));
  }

  return { ...plan, steps };
}

/**
 * Calculate estimated duration based on critical path
 */
function calculateEstimatedDuration(plan: ExecutionPlan): number {
  const stepMap = new Map<string, ExecutionStep>(plan.steps.map(s => [s.id, s]));
  const durations = new Map<string, number>();

  // Calculate duration to reach each step
  for (const stepId of plan.criticalPath) {
    const step = stepMap.get(stepId);
    if (!step) continue;

    let maxDepDuration = 0;
    for (const depId of step.dependencies) {
      const depDuration = durations.get(depId) || 0;
      maxDepDuration = Math.max(maxDepDuration, depDuration);
    }

    durations.set(stepId, maxDepDuration + (step.timeout || 0));
  }

  // Return the maximum duration (time to complete the last step)
  return Math.max(...Array.from(durations.values()), 0);
}

/**
 * Analyze plan for potential improvements
 */
export interface OptimizationSuggestion {
  type: 'parallelization' | 'merge' | 'remove_wait' | 'reorder';
  description: string;
  affectedSteps: string[];
  estimatedImprovement?: number;
}

export function analyzePlan(plan: ExecutionPlan): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = [];

  // Check for sequential steps that could be parallelized
  const stepsByDepKey = new Map<string, ExecutionStep[]>();
  for (const step of plan.steps) {
    if (step.parallelGroup) continue;
    const depKey = step.dependencies.sort().join(',');
    if (!stepsByDepKey.has(depKey)) {
      stepsByDepKey.set(depKey, []);
    }
    stepsByDepKey.get(depKey)!.push(step);
  }

  for (const [, groupSteps] of stepsByDepKey) {
    if (groupSteps.length >= 2) {
      suggestions.push({
        type: 'parallelization',
        description: `${groupSteps.length} steps with same dependencies could run in parallel`,
        affectedSteps: groupSteps.map(s => s.id),
        estimatedImprovement: groupSteps.reduce((sum, s) => sum + (s.timeout || 0), 0) -
          Math.max(...groupSteps.map(s => s.timeout || 0)),
      });
    }
  }

  // Check for redundant waits
  for (const step of plan.steps) {
    if (step.type === 'wait' && !step.config.duration && !step.config.waitForNodes?.length) {
      suggestions.push({
        type: 'remove_wait',
        description: `Wait step "${step.id}" has no duration or wait conditions`,
        affectedSteps: [step.id],
      });
    }
  }

  return suggestions;
}
