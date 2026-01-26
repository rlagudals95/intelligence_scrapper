import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';
import { getLogger } from '../utils/logger.js';

const logger = getLogger('StateManager');
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '../..');

interface StateData {
  visitedUrls: string[];
  visitedStates: string[];
  lastUpdated: string;
}

export class StateManager {
  private visitedUrls: Set<string> = new Set();
  private visitedStates: Set<string> = new Set();
  private checkpointPath: string;

  constructor(checkpointDir?: string) {
    const dir = checkpointDir || path.join(projectRoot, 'checkpoints');
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    this.checkpointPath = path.join(dir, 'state.json');
  }

  hashState(url: string, options: Record<string, unknown>): string {
    const sortedOptions = Object.keys(options)
      .sort()
      .reduce(
        (acc, key) => {
          acc[key] = options[key];
          return acc;
        },
        {} as Record<string, unknown>
      );

    const data = JSON.stringify({ url, options: sortedOptions });
    return crypto.createHash('sha256').update(data).digest('hex');
  }

  markUrlVisited(url: string): void {
    this.visitedUrls.add(url);
    logger.debug({ url }, 'URL marked as visited');
  }

  isUrlVisited(url: string): boolean {
    return this.visitedUrls.has(url);
  }

  markStateVisited(url: string, options: Record<string, unknown>): void {
    const hash = this.hashState(url, options);
    this.visitedStates.add(hash);
    logger.debug({ url, hash }, 'State marked as visited');
  }

  isStateVisited(url: string, options: Record<string, unknown>): boolean {
    const hash = this.hashState(url, options);
    return this.visitedStates.has(hash);
  }

  save(): void {
    const data: StateData = {
      visitedUrls: Array.from(this.visitedUrls),
      visitedStates: Array.from(this.visitedStates),
      lastUpdated: new Date().toISOString(),
    };

    fs.writeFileSync(this.checkpointPath, JSON.stringify(data, null, 2), 'utf-8');
    logger.info({ path: this.checkpointPath }, 'State saved to checkpoint');
  }

  load(): boolean {
    if (!fs.existsSync(this.checkpointPath)) {
      logger.info('No checkpoint file found, starting fresh');
      return false;
    }

    try {
      const content = fs.readFileSync(this.checkpointPath, 'utf-8');
      const data: StateData = JSON.parse(content);

      this.visitedUrls = new Set(data.visitedUrls);
      this.visitedStates = new Set(data.visitedStates);

      logger.info(
        {
          urlCount: this.visitedUrls.size,
          stateCount: this.visitedStates.size,
          lastUpdated: data.lastUpdated,
        },
        'State loaded from checkpoint'
      );

      return true;
    } catch (error) {
      logger.error({ error }, 'Failed to load checkpoint');
      return false;
    }
  }

  clear(): void {
    this.visitedUrls.clear();
    this.visitedStates.clear();
    logger.info('State cleared');
  }

  getStats(): { urlCount: number; stateCount: number } {
    return {
      urlCount: this.visitedUrls.size,
      stateCount: this.visitedStates.size,
    };
  }

  getVisitedUrls(): string[] {
    return Array.from(this.visitedUrls);
  }
}
