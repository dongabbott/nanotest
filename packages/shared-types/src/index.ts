// Common types shared across NanoTest packages

export interface TestCase {
  id: string;
  name: string;
  description?: string;
  projectId: string;
  steps: TestStep[];
  tags?: string[];
  priority?: 'low' | 'medium' | 'high' | 'critical';
  status?: 'draft' | 'active' | 'deprecated';
  createdAt?: string;
  updatedAt?: string;
}

export interface TestStep {
  id: string;
  order: number;
  action: string;
  target?: string;
  value?: string;
  expectedResult?: string;
  screenshot?: boolean;
}

export interface TestRun {
  id: string;
  projectId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  startedAt?: string;
  completedAt?: string;
  results?: TestResult[];
  environment?: Record<string, string>;
}

export interface TestResult {
  id: string;
  testCaseId: string;
  testRunId: string;
  status: 'passed' | 'failed' | 'skipped' | 'error';
  duration?: number;
  error?: string;
  screenshots?: string[];
  logs?: string[];
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface User {
  id: string;
  email: string;
  name?: string;
  role?: 'admin' | 'user' | 'viewer';
}

// Execution context types
export interface ExecutionContext {
  runId: string;
  projectId: string;
  environment: Record<string, string>;
  variables: Record<string, unknown>;
  secrets?: Record<string, string>;
}

// Event types for real-time updates
export interface ExecutionEvent {
  type: 'step_started' | 'step_completed' | 'step_failed' | 'run_completed';
  timestamp: string;
  runId: string;
  stepId?: string;
  data?: Record<string, unknown>;
}
