import { z } from 'zod';

// Provider types
export type AIProvider = 'openai' | 'anthropic' | 'azure-openai' | 'local';

// Configuration schema
export const AIConfigSchema = z.object({
  provider: z.enum(['openai', 'anthropic', 'azure-openai', 'local']),
  apiKey: z.string().optional(),
  baseUrl: z.string().url().optional(),
  model: z.string(),
  maxTokens: z.number().optional().default(4096),
  temperature: z.number().min(0).max(2).optional().default(0.7),
  timeout: z.number().optional().default(30000),
});

export type AIConfig = z.infer<typeof AIConfigSchema>;

// Message types
export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

// Response types
export interface AIResponse {
  content: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
  finishReason?: string;
}

// Vision analysis types
export interface VisionAnalysisRequest {
  image: string | Buffer;
  prompt: string;
  format?: 'base64' | 'url';
}

export interface VisionAnalysisResponse {
  description: string;
  elements?: DetectedElement[];
  rawResponse: string;
}

export interface DetectedElement {
  type: string;
  text?: string;
  bounds?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  confidence: number;
}

// Abstract adapter interface
export interface AIAdapter {
  readonly provider: AIProvider;
  
  chat(messages: Message[]): Promise<AIResponse>;
  complete(prompt: string): Promise<AIResponse>;
  analyzeImage(request: VisionAnalysisRequest): Promise<VisionAnalysisResponse>;
  
  // Test-specific methods
  generateTestSteps(description: string): Promise<string>;
  analyzeScreenshot(image: string | Buffer, context?: string): Promise<VisionAnalysisResponse>;
  suggestSelector(elementDescription: string, pageSource: string): Promise<string>;
}

// Adapter creation options
export interface CreateAdapterOptions extends AIConfig {
  retries?: number;
  retryDelay?: number;
}
