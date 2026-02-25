import { ZodError } from 'zod';
import { TestCaseDslSchema, TestCaseDsl, Action } from './schema';

export interface ParseResult<T> {
  success: boolean;
  data?: T;
  errors?: ParseError[];
}

export interface ParseError {
  path: string;
  message: string;
  code: string;
}

export class DslParser {
  /**
   * Parse and validate a test case DSL definition
   */
  parse(input: unknown): ParseResult<TestCaseDsl> {
    try {
      const data = TestCaseDslSchema.parse(input);
      return { success: true, data };
    } catch (error) {
      if (error instanceof ZodError) {
        return {
          success: false,
          errors: error.errors.map((e) => ({
            path: e.path.join('.'),
            message: e.message,
            code: e.code,
          })),
        };
      }
      throw error;
    }
  }

  /**
   * Parse JSON string into test case DSL
   */
  parseJson(jsonString: string): ParseResult<TestCaseDsl> {
    try {
      const input = JSON.parse(jsonString);
      return this.parse(input);
    } catch (error) {
      if (error instanceof SyntaxError) {
        return {
          success: false,
          errors: [{ path: '', message: `Invalid JSON: ${error.message}`, code: 'invalid_json' }],
        };
      }
      throw error;
    }
  }

  /**
   * Validate a test case DSL without transformations
   */
  validate(input: unknown): ParseResult<void> {
    const result = this.parse(input);
    if (result.success) {
      return { success: true };
    }
    return { success: false, errors: result.errors };
  }

  /**
   * Extract all selectors from a test case for pre-validation
   */
  extractSelectors(testCase: TestCaseDsl): Array<{ path: string; selector: any }> {
    const selectors: Array<{ path: string; selector: any }> = [];

    const extractFromActions = (actions: Action[], basePath: string) => {
      actions.forEach((action, index) => {
        const path = `${basePath}[${index}]`;
        
        if ('selector' in action && action.selector) {
          selectors.push({ path: `${path}.selector`, selector: action.selector });
        }
        
        if ('startSelector' in action && action.startSelector) {
          selectors.push({ path: `${path}.startSelector`, selector: action.startSelector });
        }

        if (action.type === 'conditional') {
          if (action.condition?.selector) {
            selectors.push({ path: `${path}.condition.selector`, selector: action.condition.selector });
          }
          if (action.thenActions) {
            extractFromActions(action.thenActions, `${path}.thenActions`);
          }
          if (action.elseActions) {
            extractFromActions(action.elseActions, `${path}.elseActions`);
          }
        }

        if (action.type === 'loop') {
          if (action.whileCondition?.selector) {
            selectors.push({ path: `${path}.whileCondition.selector`, selector: action.whileCondition.selector });
          }
          if (action.actions) {
            extractFromActions(action.actions, `${path}.actions`);
          }
        }
      });
    };

    if (testCase.setup) extractFromActions(testCase.setup, 'setup');
    extractFromActions(testCase.steps, 'steps');
    if (testCase.teardown) extractFromActions(testCase.teardown, 'teardown');

    return selectors;
  }

  /**
   * Count total actions including nested ones
   */
  countActions(testCase: TestCaseDsl): number {
    const countInActions = (actions: Action[]): number => {
      return actions.reduce((count, action) => {
        let total = 1;
        if (action.type === 'conditional') {
          total += countInActions(action.thenActions || []);
          total += countInActions(action.elseActions || []);
        }
        if (action.type === 'loop') {
          total += countInActions(action.actions || []);
        }
        return count + total;
      }, 0);
    };

    return (
      countInActions(testCase.setup || []) +
      countInActions(testCase.steps) +
      countInActions(testCase.teardown || [])
    );
  }
}

export const parser = new DslParser();
