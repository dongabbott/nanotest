import OpenAI from 'openai';
import {
  AIAdapter,
  AIConfig,
  AIResponse,
  Message,
  VisionAnalysisRequest,
  VisionAnalysisResponse,
} from './types';

export class OpenAIAdapter implements AIAdapter {
  readonly provider = 'openai' as const;
  private client: OpenAI;
  private config: AIConfig;

  constructor(config: AIConfig) {
    this.config = config;
    this.client = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseUrl,
      timeout: config.timeout,
    });
  }

  async chat(messages: Message[]): Promise<AIResponse> {
    const response = await this.client.chat.completions.create({
      model: this.config.model,
      messages: messages.map((m) => ({
        role: m.role,
        content: m.content,
      })),
      max_tokens: this.config.maxTokens,
      temperature: this.config.temperature,
    });

    return {
      content: response.choices[0]?.message?.content || '',
      usage: response.usage
        ? {
            promptTokens: response.usage.prompt_tokens,
            completionTokens: response.usage.completion_tokens,
            totalTokens: response.usage.total_tokens,
          }
        : undefined,
      finishReason: response.choices[0]?.finish_reason || undefined,
    };
  }

  async complete(prompt: string): Promise<AIResponse> {
    return this.chat([{ role: 'user', content: prompt }]);
  }

  async analyzeImage(request: VisionAnalysisRequest): Promise<VisionAnalysisResponse> {
    const imageContent =
      request.format === 'url'
        ? { type: 'image_url' as const, image_url: { url: request.image as string } }
        : {
            type: 'image_url' as const,
            image_url: {
              url: `data:image/png;base64,${
                Buffer.isBuffer(request.image)
                  ? request.image.toString('base64')
                  : request.image
              }`,
            },
          };

    const response = await this.client.chat.completions.create({
      model: this.config.model.includes('vision') ? this.config.model : 'gpt-4-vision-preview',
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text: request.prompt },
            imageContent,
          ],
        },
      ],
      max_tokens: this.config.maxTokens,
    });

    const content = response.choices[0]?.message?.content || '';

    return {
      description: content,
      rawResponse: content,
    };
  }

  async generateTestSteps(description: string): Promise<string> {
    const systemPrompt = `You are an expert mobile test automation engineer. 
Given a test scenario description, generate a structured test case in JSON format following this schema:
- name: string
- steps: array of actions (tap, swipe, type, assert, wait, screenshot)
Each action should have appropriate selectors and parameters.
Return ONLY valid JSON, no explanations.`;

    const response = await this.chat([
      { role: 'system', content: systemPrompt },
      { role: 'user', content: description },
    ]);

    return response.content;
  }

  async analyzeScreenshot(
    image: string | Buffer,
    context?: string
  ): Promise<VisionAnalysisResponse> {
    const prompt = context
      ? `Analyze this mobile app screenshot. Context: ${context}. 
         Identify all interactive UI elements (buttons, inputs, links, etc.) with their approximate locations and text content.
         Return a JSON object with 'description' and 'elements' array.`
      : `Analyze this mobile app screenshot.
         Identify all interactive UI elements (buttons, inputs, links, etc.) with their approximate locations and text content.
         Return a JSON object with 'description' and 'elements' array.`;

    return this.analyzeImage({ image, prompt, format: 'base64' });
  }

  async suggestSelector(elementDescription: string, pageSource: string): Promise<string> {
    const prompt = `Given this UI element description: "${elementDescription}"
And this page source (XML/HTML):
${pageSource.substring(0, 8000)}

Suggest the best selector strategy and value. Return JSON:
{ "strategy": "id|xpath|accessibility_id|class_name", "value": "selector_value" }`;

    const response = await this.complete(prompt);
    return response.content;
  }
}
