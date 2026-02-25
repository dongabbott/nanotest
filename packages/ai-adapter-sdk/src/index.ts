import { AIAdapter, AIConfig, AIConfigSchema, CreateAdapterOptions } from './types';
import { OpenAIAdapter } from './adapters/openai';
import { AnthropicAdapter } from './adapters/anthropic';

export * from './types';
export { OpenAIAdapter } from './adapters/openai';
export { AnthropicAdapter } from './adapters/anthropic';

/**
 * Create an AI adapter based on the configuration
 */
export function createAdapter(options: CreateAdapterOptions): AIAdapter {
  const config = AIConfigSchema.parse(options);

  switch (config.provider) {
    case 'openai':
    case 'azure-openai':
      return new OpenAIAdapter(config);
    case 'anthropic':
      return new AnthropicAdapter(config);
    case 'local':
      // TODO: Implement local LLM adapter
      throw new Error('Local adapter not yet implemented');
    default:
      throw new Error(`Unknown provider: ${config.provider}`);
  }
}

/**
 * Create an OpenAI adapter with default settings
 */
export function createOpenAIAdapter(apiKey: string, model = 'gpt-4-turbo-preview'): AIAdapter {
  return createAdapter({
    provider: 'openai',
    apiKey,
    model,
  });
}

/**
 * Utility to wrap adapter calls with retry logic
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  retries = 3,
  delay = 1000
): Promise<T> {
  let lastError: Error | undefined;

  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (i < retries - 1) {
        await new Promise((resolve) => setTimeout(resolve, delay * (i + 1)));
      }
    }
  }

  throw lastError;
}
