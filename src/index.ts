// Phone Scraper V2 - TypeScript Version
// Main entry point

export * from './core/index.js';
export * from './models/index.js';
export * from './crawlers/index.js';
export * from './services/index.js';
export * from './utils/index.js';

import { getLogger } from './utils/logger.js';

const logger = getLogger('main');

logger.info('Phone Scraper V2 (TypeScript) loaded');
