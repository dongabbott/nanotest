// filepath: d:\project\nanotest\packages\ai-adapter-sdk\src\adapters\anthropic.ts
import {
  AIAdapter,
  AIConfig,
  AIProvider,
  AIResponse,
  Message,
  VisionAnalysisRequest,
  VisionAnalysisResponse,
  DetectedElement,
} from '../types';

interface AnthropicMessage {
  role: 'user' | 'assistant';
  content: string | AnthropicContent[];
}

interface AnthropicContent {
  type: 'text' | 'image';
  text?: string;
  source?: {
    type: 'base64';
    media_type: string;
    data: string;
  };
}

interface AnthropicResponse {
  id: string;
  type: string;
  role: string;
  content: Array<{ type: string; text: string }>;
  model: string;
  stop_reason: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
  };
}

export class AnthropicAdapter implements AIAdapter {
  readonly provider: AIProvider = 'anthropic';
  private config: AIConfig;
  private baseUrl: string;

  constructor(config: AIConfig) {
    this.config = config;
    this.baseUrl = config.baseUrl || 'https://api.anthropic.com';
  }

  private async request(endpoint: string, body: Record<string, unknown>): Promise<AnthropicResponse> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout || 30000);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.config.apiKey || '',
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Anthropic API error: ${response.status} - ${error}`);
      }

      return response.json();
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private convertMessages(messages: Message[]): { system?: string; messages: AnthropicMessage[] } {
    let systemMessage: string | undefined;
    const anthropicMessages: AnthropicMessage[] = [];

    for (const msg of messages) {
      if (msg.role === 'system') {
        systemMessage = msg.content;
      } else {
        anthropicMessages.push({
          role: msg.role === 'assistant' ? 'assistant' : 'user',
          content: msg.content,
        });
      }
    }

    return { system: systemMessage, messages: anthropicMessages };
  }

  async chat(messages: Message[]): Promise<AIResponse> {
    const { system, messages: anthropicMessages } = this.convertMessages(messages);

    const response = await this.request('/v1/messages', {
      model: this.config.model,
      max_tokens: this.config.maxTokens || 4096,
      temperature: this.config.temperature || 0.7,
      system,
      messages: anthropicMessages,
    });

    return {
      content: response.content.map(c => c.text).join(''),
      usage: {
        promptTokens: response.usage.input_tokens,
        completionTokens: response.usage.output_tokens,
        totalTokens: response.usage.input_tokens + response.usage.output_tokens,
      },
      finishReason: response.stop_reason,
    };
  }

  async complete(prompt: string): Promise<AIResponse> {
    return this.chat([{ role: 'user', content: prompt }]);
  }

  async analyzeImage(request: VisionAnalysisRequest): Promise<VisionAnalysisResponse> {
    const imageContent = this.prepareImageContent(request);

    const response = await this.request('/v1/messages', {
      model: this.config.model,
      max_tokens: this.config.maxTokens || 4096,
      messages: [
        {
          role: 'user',
          content: [
            imageContent,
            { type: 'text', text: request.prompt },
          ],
        },
      ],
    });

    const rawResponse = response.content.map(c => c.text).join('');

    return {
      description: rawResponse,
      elements: this.parseElements(rawResponse),
      rawResponse,
    };
  }

  private prepareImageContent(request: VisionAnalysisRequest): AnthropicContent {
    let base64Data: string;
    let mediaType = 'image/png';

    if (Buffer.isBuffer(request.image)) {
      base64Data = request.image.toString('base64');
    } else if (request.format === 'base64') {
      base64Data = request.image;
    } else {
      // URL format - Anthropic requires base64, so we need to note this limitation
      throw new Error('Anthropic adapter requires base64 image data. URL format is not directly supported.');
    }

    return {
      type: 'image',
      source: {
        type: 'base64',
        media_type: mediaType,
        data: base64Data,
      },
    };
  }

  private parseElements(response: string): DetectedElement[] {
    const elements: DetectedElement[] = [];
    
    // Try to parse JSON from the response
    const jsonMatch = response.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[1]);
        if (Array.isArray(parsed.elements)) {
          return parsed.elements;
        }
      } catch {
        // Continue with empty elements
      }
    }

    return elements;
  }

  async generateTestSteps(description: string): Promise<string> {
    const prompt = `You are a mobile test automation expert. Generate test steps in JSON DSL format for the following test case description:

${description}

Output format:
{
  "name": "TestCaseName",
  "steps": [
    {"action": "launch_app", "params": {}},
    {"action": "tap", "target": "id=element_id"},
    {"action": "input", "target": "id=field_id", "value": "text"},
    {"action": "assert", "expr": "exists(id=element_id)"}
  ]
}

Available actions: launch_app, tap, input, swipe, scroll, wait, assert, screenshot

Generate only the JSON, no additional explanation.`;

    const response = await this.complete(prompt);
    return response.content;
  }

  async analyzeScreenshot(image: string | Buffer, context?: string): Promise<VisionAnalysisResponse> {
    const prompt = `Analyze this mobile app screenshot for UI testing purposes.

${context ? `Context: ${context}` : ''}

Please identify:
1. Key UI elements (buttons, text fields, labels, images)
2. Current screen state/name
3. Any potential issues (layout problems, accessibility concerns)
4. Suggested test assertions

Respond in this JSON format:
\`\`\`json
{
  "screenName": "string",
  "elements": [
    {
      "type": "button|text|input|image|other",
      "text": "visible text if any",
      "bounds": {"x": 0, "y": 0, "width": 100, "height": 50},
      "confidence": 0.95
    }
  ],
  "issues": ["list of potential issues"],
  "suggestedAssertions": ["exists(id=element)", "text_contains(id=label, 'expected')"]
}
\`\`\``;

    return this.analyzeImage({
      image,
      prompt,
      format: Buffer.isBuffer(image) ? 'base64' : 'base64',
    });
  }

  async suggestSelector(elementDescription: string, pageSource: string): Promise<string> {
    const prompt = `Given the following mobile app page source (XML) and element description, suggest the best selector strategy.

Element description: ${elementDescription}

Page source (truncated):
${pageSource.substring(0, 8000)}

Respond with only the selector in one of these formats:
- id=element_id
- xpath=//path/to/element
- accessibility_id=accessibility_label
- class=class_name

Choose the most stable and reliable selector.`;

    const response = await this.complete(prompt);
    return response.content.trim();
  }
}
