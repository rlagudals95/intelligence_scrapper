import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';
import { GoogleGenerativeAI } from '@google/generative-ai';
import pRetry from 'p-retry';
import { getLogger } from '../utils/logger.js';

const logger = getLogger('LLMClient');

export type LLMProvider = 'openai' | 'anthropic' | 'gemini';

export interface LLMResponse {
  content: string;
  usage?: {
    inputTokens: number;
    outputTokens: number;
  };
}

export interface LLMClientOptions {
  provider?: LLMProvider;
  model?: string;
  maxRetries?: number;
  retryMinTimeout?: number;
  retryMaxTimeout?: number;
}

const DEFAULT_MODELS: Record<LLMProvider, string> = {
  openai: 'gpt-4o',
  anthropic: 'claude-sonnet-4-20250514',
  gemini: 'gemini-2.5-flash-preview-05-20',
};

export class LLMClient {
  private provider: LLMProvider;
  private model: string;
  private maxRetries: number;
  private retryMinTimeout: number;
  private retryMaxTimeout: number;

  private openai?: OpenAI;
  private anthropic?: Anthropic;
  private gemini?: GoogleGenerativeAI;

  private totalInputTokens = 0;
  private totalOutputTokens = 0;

  constructor(options: LLMClientOptions = {}) {
    this.provider = options.provider || this.detectProvider();
    this.model = options.model || DEFAULT_MODELS[this.provider];
    this.maxRetries = options.maxRetries ?? 3;
    this.retryMinTimeout = options.retryMinTimeout ?? 2000;
    this.retryMaxTimeout = options.retryMaxTimeout ?? 30000;

    this.initializeClient();

    logger.info({ provider: this.provider, model: this.model }, 'LLM client initialized');
  }

  private detectProvider(): LLMProvider {
    if (process.env.OPENAI_API_KEY) return 'openai';
    if (process.env.ANTHROPIC_API_KEY) return 'anthropic';
    if (process.env.GEMINI_API_KEY) return 'gemini';
    throw new Error('No LLM API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY');
  }

  private initializeClient(): void {
    switch (this.provider) {
      case 'openai':
        if (!process.env.OPENAI_API_KEY) {
          throw new Error('OPENAI_API_KEY not set');
        }
        this.openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
        break;

      case 'anthropic':
        if (!process.env.ANTHROPIC_API_KEY) {
          throw new Error('ANTHROPIC_API_KEY not set');
        }
        this.anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
        break;

      case 'gemini':
        if (!process.env.GEMINI_API_KEY) {
          throw new Error('GEMINI_API_KEY not set');
        }
        this.gemini = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
        break;
    }
  }

  async complete(systemPrompt: string, userPrompt: string): Promise<LLMResponse> {
    return pRetry(() => this._complete(systemPrompt, userPrompt), {
      retries: this.maxRetries,
      minTimeout: this.retryMinTimeout,
      maxTimeout: this.retryMaxTimeout,
      onFailedAttempt: (error) => {
        logger.warn(
          { attempt: error.attemptNumber, retriesLeft: error.retriesLeft, error: error.message },
          'LLM request failed, retrying...'
        );
      },
    });
  }

  async completeWithVision(
    systemPrompt: string,
    userPrompt: string,
    imageBase64: string
  ): Promise<LLMResponse> {
    return pRetry(() => this._completeWithVision(systemPrompt, userPrompt, imageBase64), {
      retries: this.maxRetries,
      minTimeout: this.retryMinTimeout,
      maxTimeout: this.retryMaxTimeout,
      onFailedAttempt: (error) => {
        logger.warn(
          { attempt: error.attemptNumber, retriesLeft: error.retriesLeft, error: error.message },
          'LLM vision request failed, retrying...'
        );
      },
    });
  }

  private async _complete(systemPrompt: string, userPrompt: string): Promise<LLMResponse> {
    switch (this.provider) {
      case 'openai':
        return this._completeOpenAI(systemPrompt, userPrompt);
      case 'anthropic':
        return this._completeAnthropic(systemPrompt, userPrompt);
      case 'gemini':
        return this._completeGemini(systemPrompt, userPrompt);
    }
  }

  private async _completeWithVision(
    systemPrompt: string,
    userPrompt: string,
    imageBase64: string
  ): Promise<LLMResponse> {
    switch (this.provider) {
      case 'openai':
        return this._completeOpenAIVision(systemPrompt, userPrompt, imageBase64);
      case 'anthropic':
        return this._completeAnthropicVision(systemPrompt, userPrompt, imageBase64);
      case 'gemini':
        return this._completeGeminiVision(systemPrompt, userPrompt, imageBase64);
    }
  }

  private async _completeOpenAI(systemPrompt: string, userPrompt: string): Promise<LLMResponse> {
    if (!this.openai) throw new Error('OpenAI client not initialized');

    const response = await this.openai.chat.completions.create({
      model: this.model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ],
    });

    const usage = response.usage;
    if (usage) {
      this.totalInputTokens += usage.prompt_tokens;
      this.totalOutputTokens += usage.completion_tokens;
    }

    return {
      content: response.choices[0]?.message?.content || '',
      usage: usage
        ? {
            inputTokens: usage.prompt_tokens,
            outputTokens: usage.completion_tokens,
          }
        : undefined,
    };
  }

  private async _completeOpenAIVision(
    systemPrompt: string,
    userPrompt: string,
    imageBase64: string
  ): Promise<LLMResponse> {
    if (!this.openai) throw new Error('OpenAI client not initialized');

    const response = await this.openai.chat.completions.create({
      model: this.model,
      messages: [
        { role: 'system', content: systemPrompt },
        {
          role: 'user',
          content: [
            {
              type: 'image_url',
              image_url: {
                url: `data:image/png;base64,${imageBase64}`,
                detail: 'high',
              },
            },
            { type: 'text', text: userPrompt },
          ],
        },
      ],
    });

    const usage = response.usage;
    if (usage) {
      this.totalInputTokens += usage.prompt_tokens;
      this.totalOutputTokens += usage.completion_tokens;
    }

    return {
      content: response.choices[0]?.message?.content || '',
      usage: usage
        ? {
            inputTokens: usage.prompt_tokens,
            outputTokens: usage.completion_tokens,
          }
        : undefined,
    };
  }

  private async _completeAnthropic(systemPrompt: string, userPrompt: string): Promise<LLMResponse> {
    if (!this.anthropic) throw new Error('Anthropic client not initialized');

    const response = await this.anthropic.messages.create({
      model: this.model,
      max_tokens: 4096,
      system: systemPrompt,
      messages: [{ role: 'user', content: userPrompt }],
    });

    this.totalInputTokens += response.usage.input_tokens;
    this.totalOutputTokens += response.usage.output_tokens;

    const textBlock = response.content.find((block) => block.type === 'text');
    const content = textBlock && 'text' in textBlock ? textBlock.text : '';

    return {
      content,
      usage: {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
      },
    };
  }

  private async _completeAnthropicVision(
    systemPrompt: string,
    userPrompt: string,
    imageBase64: string
  ): Promise<LLMResponse> {
    if (!this.anthropic) throw new Error('Anthropic client not initialized');

    const response = await this.anthropic.messages.create({
      model: this.model,
      max_tokens: 4096,
      system: systemPrompt,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: 'image/png',
                data: imageBase64,
              },
            },
            { type: 'text', text: userPrompt },
          ],
        },
      ],
    });

    this.totalInputTokens += response.usage.input_tokens;
    this.totalOutputTokens += response.usage.output_tokens;

    const textBlock = response.content.find((block) => block.type === 'text');
    const content = textBlock && 'text' in textBlock ? textBlock.text : '';

    return {
      content,
      usage: {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
      },
    };
  }

  private async _completeGemini(systemPrompt: string, userPrompt: string): Promise<LLMResponse> {
    if (!this.gemini) throw new Error('Gemini client not initialized');

    const model = this.gemini.getGenerativeModel({
      model: this.model,
      systemInstruction: systemPrompt,
    });

    const result = await model.generateContent(userPrompt);
    const response = result.response;
    const text = response.text();

    const usage = response.usageMetadata;

    if (usage) {
      this.totalInputTokens += usage.promptTokenCount || 0;
      this.totalOutputTokens += usage.candidatesTokenCount || 0;
    }

    return {
      content: text,
      usage: usage
        ? {
            inputTokens: usage.promptTokenCount || 0,
            outputTokens: usage.candidatesTokenCount || 0,
          }
        : undefined,
    };
  }

  private async _completeGeminiVision(
    systemPrompt: string,
    userPrompt: string,
    imageBase64: string
  ): Promise<LLMResponse> {
    if (!this.gemini) throw new Error('Gemini client not initialized');

    const model = this.gemini.getGenerativeModel({
      model: this.model,
      systemInstruction: systemPrompt,
    });

    const result = await model.generateContent([
      {
        inlineData: {
          mimeType: 'image/png',
          data: imageBase64,
        },
      },
      userPrompt,
    ]);

    const response = result.response;
    const text = response.text();

    const usage = response.usageMetadata;

    if (usage) {
      this.totalInputTokens += usage.promptTokenCount || 0;
      this.totalOutputTokens += usage.candidatesTokenCount || 0;
    }

    return {
      content: text,
      usage: usage
        ? {
            inputTokens: usage.promptTokenCount || 0,
            outputTokens: usage.candidatesTokenCount || 0,
          }
        : undefined,
    };
  }

  getTokenUsage(): { inputTokens: number; outputTokens: number; totalTokens: number } {
    return {
      inputTokens: this.totalInputTokens,
      outputTokens: this.totalOutputTokens,
      totalTokens: this.totalInputTokens + this.totalOutputTokens,
    };
  }

  resetTokenUsage(): void {
    this.totalInputTokens = 0;
    this.totalOutputTokens = 0;
  }

  getProvider(): LLMProvider {
    return this.provider;
  }

  getModel(): string {
    return this.model;
  }
}

export function createLLMClient(options?: LLMClientOptions): LLMClient {
  return new LLMClient(options);
}
