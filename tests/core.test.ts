import { describe, it, expect } from 'vitest';
import { SiteConfigSchema, createConfig, defaultConfigValues } from '../src/core/config.js';
import { StateManager } from '../src/core/state.js';

describe('SiteConfig', () => {
  it('should parse config with default values', () => {
    const config = SiteConfigSchema.parse({ targetUrl: 'https://example.com' });

    expect(config.targetUrl).toBe('https://example.com');
    expect(config.delayMin).toBe(1.0);
    expect(config.delayMax).toBe(3.0);
    expect(config.headless).toBe(true);
    expect(config.timeout).toBe(30000);
  });

  it('should reject invalid URL', () => {
    expect(() => SiteConfigSchema.parse({ targetUrl: 'not-a-url' })).toThrow();
  });

  it('should override default values', () => {
    const config = createConfig({
      targetUrl: 'https://example.com',
      delayMin: 2.0,
      delayMax: 5.0,
      headless: false,
    });

    expect(config.delayMin).toBe(2.0);
    expect(config.delayMax).toBe(5.0);
    expect(config.headless).toBe(false);
  });
});

describe('StateManager', () => {
  it('should track visited URLs', () => {
    const state = new StateManager();

    expect(state.isUrlVisited('https://example.com/1')).toBe(false);

    state.markUrlVisited('https://example.com/1');

    expect(state.isUrlVisited('https://example.com/1')).toBe(true);
    expect(state.isUrlVisited('https://example.com/2')).toBe(false);
  });

  it('should track visited states with hash', () => {
    const state = new StateManager();
    const url = 'https://example.com';
    const options1 = { carrier: 'SKT', plan: 'Plan A' };
    const options2 = { carrier: 'KT', plan: 'Plan B' };

    expect(state.isStateVisited(url, options1)).toBe(false);

    state.markStateVisited(url, options1);

    expect(state.isStateVisited(url, options1)).toBe(true);
    expect(state.isStateVisited(url, options2)).toBe(false);
  });

  it('should generate consistent hash', () => {
    const state = new StateManager();
    const url = 'https://example.com';
    const options = { carrier: 'SKT', plan: 'Plan A' };
    const optionsReordered = { plan: 'Plan A', carrier: 'SKT' };

    const hash1 = state.hashState(url, options);
    const hash2 = state.hashState(url, optionsReordered);

    expect(hash1).toBe(hash2);
  });

  it('should return correct stats', () => {
    const state = new StateManager();

    state.markUrlVisited('https://example.com/1');
    state.markUrlVisited('https://example.com/2');
    state.markStateVisited('https://example.com', { a: 1 });

    const stats = state.getStats();
    expect(stats.urlCount).toBe(2);
    expect(stats.stateCount).toBe(1);
  });
});
