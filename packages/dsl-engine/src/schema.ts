import { z } from 'zod';

// Action types supported by the DSL
export const ActionType = z.enum([
  'tap',
  'swipe',
  'type',
  'scroll',
  'wait',
  'assert',
  'screenshot',
  'ai_analyze',
  'conditional',
  'loop',
]);

// Element selector schema
export const SelectorSchema = z.object({
  strategy: z.enum(['id', 'xpath', 'accessibility_id', 'class_name', 'ai_vision']),
  value: z.string(),
  timeout: z.number().optional().default(10000),
});

// Base action schema
const BaseActionSchema = z.object({
  id: z.string().uuid().optional(),
  name: z.string().optional(),
  description: z.string().optional(),
  continueOnError: z.boolean().optional().default(false),
});

// Tap action
export const TapActionSchema = BaseActionSchema.extend({
  type: z.literal('tap'),
  selector: SelectorSchema,
  duration: z.number().optional(),
});

// Swipe action
export const SwipeActionSchema = BaseActionSchema.extend({
  type: z.literal('swipe'),
  direction: z.enum(['up', 'down', 'left', 'right']),
  distance: z.number().optional().default(0.5),
  duration: z.number().optional().default(500),
  startSelector: SelectorSchema.optional(),
});

// Type action
export const TypeActionSchema = BaseActionSchema.extend({
  type: z.literal('type'),
  selector: SelectorSchema,
  text: z.string(),
  clearFirst: z.boolean().optional().default(true),
});

// Scroll action
export const ScrollActionSchema = BaseActionSchema.extend({
  type: z.literal('scroll'),
  direction: z.enum(['up', 'down', 'left', 'right']),
  selector: SelectorSchema.optional(),
  distance: z.number().optional(),
});

// Wait action
export const WaitActionSchema = BaseActionSchema.extend({
  type: z.literal('wait'),
  duration: z.number().optional(),
  selector: SelectorSchema.optional(),
  condition: z.enum(['visible', 'hidden', 'enabled', 'disabled']).optional(),
});

// Assert action
export const AssertActionSchema = BaseActionSchema.extend({
  type: z.literal('assert'),
  selector: SelectorSchema.optional(),
  condition: z.enum(['exists', 'not_exists', 'visible', 'text_equals', 'text_contains', 'enabled']),
  expected: z.string().optional(),
});

// Screenshot action
export const ScreenshotActionSchema = BaseActionSchema.extend({
  type: z.literal('screenshot'),
  name: z.string().optional(),
  fullPage: z.boolean().optional().default(false),
});

// AI analyze action
export const AiAnalyzeActionSchema = BaseActionSchema.extend({
  type: z.literal('ai_analyze'),
  prompt: z.string(),
  saveResult: z.string().optional(),
});

// Conditional action
export const ConditionalActionSchema = BaseActionSchema.extend({
  type: z.literal('conditional'),
  condition: z.object({
    selector: SelectorSchema.optional(),
    check: z.enum(['exists', 'not_exists', 'visible', 'text_equals']),
    expected: z.string().optional(),
  }),
  thenActions: z.array(z.lazy(() => ActionSchema)),
  elseActions: z.array(z.lazy(() => ActionSchema)).optional(),
});

// Loop action
export const LoopActionSchema = BaseActionSchema.extend({
  type: z.literal('loop'),
  count: z.number().optional(),
  whileCondition: z.object({
    selector: SelectorSchema,
    check: z.enum(['exists', 'visible']),
  }).optional(),
  maxIterations: z.number().optional().default(100),
  actions: z.array(z.lazy(() => ActionSchema)),
});

// Union of all action types
export const ActionSchema: z.ZodType<any> = z.discriminatedUnion('type', [
  TapActionSchema,
  SwipeActionSchema,
  TypeActionSchema,
  ScrollActionSchema,
  WaitActionSchema,
  AssertActionSchema,
  ScreenshotActionSchema,
  AiAnalyzeActionSchema,
  ConditionalActionSchema as any,
  LoopActionSchema as any,
]);

// Test case DSL schema
export const TestCaseDslSchema = z.object({
  version: z.string().default('1.0'),
  name: z.string(),
  description: z.string().optional(),
  tags: z.array(z.string()).optional().default([]),
  timeout: z.number().optional().default(300000),
  retries: z.number().optional().default(0),
  setup: z.array(ActionSchema).optional().default([]),
  steps: z.array(ActionSchema),
  teardown: z.array(ActionSchema).optional().default([]),
  variables: z.record(z.string(), z.any()).optional().default({}),
});

// Type exports
export type ActionType = z.infer<typeof ActionType>;
export type Selector = z.infer<typeof SelectorSchema>;
export type Action = z.infer<typeof ActionSchema>;
export type TestCaseDsl = z.infer<typeof TestCaseDslSchema>;
export type TapAction = z.infer<typeof TapActionSchema>;
export type SwipeAction = z.infer<typeof SwipeActionSchema>;
export type TypeAction = z.infer<typeof TypeActionSchema>;
export type ScrollAction = z.infer<typeof ScrollActionSchema>;
export type WaitAction = z.infer<typeof WaitActionSchema>;
export type AssertAction = z.infer<typeof AssertActionSchema>;
export type ScreenshotAction = z.infer<typeof ScreenshotActionSchema>;
export type AiAnalyzeAction = z.infer<typeof AiAnalyzeActionSchema>;
export type ConditionalAction = z.infer<typeof ConditionalActionSchema>;
export type LoopAction = z.infer<typeof LoopActionSchema>;
