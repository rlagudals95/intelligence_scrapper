import pino from 'pino';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '../..');
const logsDir = path.join(projectRoot, 'logs');

if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir, { recursive: true });
}

function getTimestamp(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${year}${month}${day}_${hours}${minutes}${seconds}`;
}

const timestamp = getTimestamp();
const logFile = path.join(logsDir, `scraper_${timestamp}.log`);

const streams: pino.StreamEntry[] = [];

if (process.env.LOG_TO_CONSOLE !== 'false') {
  streams.push({
    level: 'info',
    stream: pino.transport({
      target: 'pino-pretty',
      options: {
        colorize: true,
        translateTime: 'SYS:standard',
        ignore: 'pid,hostname',
      },
    }),
  });
}

if (process.env.LOG_TO_FILE !== 'false') {
  streams.push({
    level: 'debug',
    stream: fs.createWriteStream(logFile),
  });
}

export const logger = pino(
  {
    level: process.env.LOG_LEVEL || 'debug',
    formatters: {
      level: (label) => ({ level: label }),
    },
    timestamp: pino.stdTimeFunctions.isoTime,
  },
  pino.multistream(streams.length > 0 ? streams : [{ stream: process.stdout }])
);

export function getLogger(name?: string): pino.Logger {
  return name ? logger.child({ module: name }) : logger;
}

export { logFile };
