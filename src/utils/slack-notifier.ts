import axios from 'axios';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { Phase3ScrapingResult, Policy } from '../models/phase3-schemas.js';
import { getLogger } from './logger.js';

const logger = getLogger('SlackNotifier');
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '../..');

export class SlackNotifier {
  private webhookUrl: string | null;

  constructor() {
    this.webhookUrl = process.env.SLACK_WEBHOOK_URL || null;
  }

  /**
   * Send message to Slack
   */
  async sendMessage(message: string): Promise<void> {
    if (!this.webhookUrl || process.env.NO_SLACK === '1') {
      logger.info('Slack disabled, skipping notification');
      return;
    }

    try {
      await axios.post(this.webhookUrl, { text: message });
      logger.info('Slack message sent');
    } catch (error) {
      logger.error({ error }, 'Failed to send Slack message');
    }
  }

  /**
   * Save policies to CSV file
   */
  savePoliciesToCsv(policies: Policy[], siteName: string, productName: string): string {
    const csvDir = path.join(projectRoot, 'output', 'scraping', 'csv');
    if (!fs.existsSync(csvDir)) {
      fs.mkdirSync(csvDir, { recursive: true });
    }

    const timestamp = this.getTimestamp();
    const safeProductName = productName.replace(/[/\\?%*:|"<>]/g, '_').slice(0, 50);
    const fileName = `${siteName}_${safeProductName}_${timestamp}.csv`;
    const filePath = path.join(csvDir, fileName);

    // UTF-8 BOM for Excel compatibility
    const BOM = '\uFEFF';
    const headers = [
      '통신사',
      '가입유형',
      '할인유형',
      '요금제명',
      '월요금',
      '출고가',
      '공시지원금',
      '추가할인',
      '최종가',
      '월할부금',
    ].join(',');

    const rows = policies.map((p) =>
      [
        p.carrier,
        p.joinType,
        p.discountType,
        `"${p.plan.name}"`,
        p.plan.monthlyFee,
        p.pricing.retailPrice,
        p.pricing.publicSubsidy || 0,
        p.pricing.additionalDiscount || 0,
        p.pricing.finalPrice,
        p.pricing.monthlyInstallment || 0,
      ].join(',')
    );

    const content = BOM + headers + '\n' + rows.join('\n');
    fs.writeFileSync(filePath, content, 'utf8');

    logger.info({ filePath, count: policies.length }, 'CSV saved');
    return filePath;
  }

  /**
   * Save scraping result to JSON file
   */
  saveResultToJson(result: Phase3ScrapingResult, siteName: string): string {
    const jsonDir = path.join(projectRoot, 'output', 'scraping');
    if (!fs.existsSync(jsonDir)) {
      fs.mkdirSync(jsonDir, { recursive: true });
    }

    const timestamp = this.getTimestamp();
    const fileName = `${siteName}_${timestamp}.json`;
    const filePath = path.join(jsonDir, fileName);

    fs.writeFileSync(filePath, JSON.stringify(result, null, 2), 'utf8');

    logger.info({ filePath }, 'JSON saved');
    return filePath;
  }

  /**
   * Notify scraping completion
   */
  async notifyScrapingComplete(
    result: Phase3ScrapingResult,
    csvPaths: string[]
  ): Promise<void> {
    const totalPolicies = result.products.reduce((sum, p) => sum + p.policies.length, 0);

    const message = [
      '📱 *스크래핑 완료!*',
      '',
      `🏪 사이트: ${result.source.siteName}`,
      `📦 제품 수: ${result.products.length}`,
      `📋 총 정책 수: ${totalPolicies}`,
      `⏰ 시간: ${result.capturedAt}`,
      '',
      `📁 CSV 파일: ${csvPaths.length}개 생성`,
    ].join('\n');

    await this.sendMessage(message);
  }

  /**
   * Notify error
   */
  async notifyError(siteName: string, error: string): Promise<void> {
    const message = [
      '❌ *스크래핑 오류 발생*',
      '',
      `🏪 사이트: ${siteName}`,
      `🚨 오류: ${error}`,
      `⏰ 시간: ${new Date().toISOString()}`,
    ].join('\n');

    await this.sendMessage(message);
  }

  private getTimestamp(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    return `${year}${month}${day}_${hours}${minutes}${seconds}`;
  }
}

export function createSlackNotifier(): SlackNotifier {
  return new SlackNotifier();
}
