import { z } from 'zod';

export const SiteConfigSchema = z.object({
  targetUrl: z.string().url(),
  listingUrl: z.string().url().optional(),
  delayMin: z.number().min(0).default(1.0),
  delayMax: z.number().min(0).default(3.0),
  userAgent: z
    .string()
    .default(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
  timeout: z.number().min(1000).default(30000),
  headless: z.boolean().default(true),
  viewportWidth: z.number().min(320).default(1280),
  viewportHeight: z.number().min(240).default(800),
  maxRetries: z.number().min(1).default(3),
  retryDelay: z.number().min(0).default(2),
  pruningThreshold: z.number().min(1).default(3),
  checkpointInterval: z.number().min(1).default(10),
  logLevel: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
  logToFile: z.boolean().default(true),
  logToConsole: z.boolean().default(true),
});

export type SiteConfig = z.infer<typeof SiteConfigSchema>;

export function createConfig(overrides: Partial<SiteConfig> & { targetUrl: string }): SiteConfig {
  return SiteConfigSchema.parse(overrides);
}

export const defaultConfigValues = {
  delayMin: 1.0,
  delayMax: 3.0,
  userAgent:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  timeout: 30000,
  headless: true,
  viewportWidth: 1280,
  viewportHeight: 800,
  maxRetries: 3,
  retryDelay: 2,
  pruningThreshold: 3,
  checkpointInterval: 10,
  logLevel: 'info' as const,
  logToFile: true,
  logToConsole: true,
};
