import * as fs from 'fs';
import * as path from 'path';
import { getLogger } from './logger.js';

const logger = getLogger('SelectorCache');

export interface SelectorCacheEntry {
  product_card_selectors: string[];  // 후보 셀렉터 배열 (우선순위순)
  product_name_selectors: string[];
  detail_link_selectors: string[];
  carrier_selectors: string[];
  join_type_selectors: string[];
  storage_selectors: string[];
  pricing_selectors: {
    retail_price: string[];
    public_subsidy: string[];
    installment: string[];
    monthly_payment: string[];
  };
  last_updated: string;
  last_verified_at: string;        // 마지막 성공 시각
  success_count: number;
  fail_count: number;
  consecutive_fails: number;       // 연속 실패 횟수 (성공 시 0 리셋)
  consecutive_soft_fails: number;  // 선택 필드 연속 실패
  disabled_until?: string;         // 일시 비활성화 시각 (ISO8601)
  quality_score: number;           // 품질 점수 (0-100)
}

// 연속 실패 임계값: 이 값 이상이면 캐시 무효화
const CONSECUTIVE_FAIL_THRESHOLD = 3;

export interface SelectorCache {
  [siteKey: string]: SelectorCacheEntry;
}

const CACHE_DIR = 'checkpoints';
const CACHE_FILE = 'selector-cache.json';

export class SelectorCacheManager {
  private cache: SelectorCache = {};
  private cacheFilePath: string;

  constructor() {
    this.cacheFilePath = path.join(process.cwd(), CACHE_DIR, CACHE_FILE);
    this.load();
  }

  /**
   * URL에서 사이트 키 추출 (도메인 기반)
   */
  private getSiteKey(url: string): string {
    try {
      const urlObj = new URL(url);
      return urlObj.hostname.replace('www.', '');
    } catch {
      return url;
    }
  }

  /**
   * 캐시에서 셀렉터 후보들 가져오기
   * 연속 실패 임계값 초과 또는 비활성화 시간 내면 null 반환
   */
  get(url: string): SelectorCacheEntry | null {
    const siteKey = this.getSiteKey(url);
    const entry = this.cache[siteKey];

    if (!entry) {
      logger.info({ siteKey }, 'Cache miss');
      return null;
    }

    // 일시 비활성화 체크
    if (entry.disabled_until) {
      const disabledUntil = new Date(entry.disabled_until);
      if (new Date() < disabledUntil) {
        logger.warn({ siteKey, disabledUntil: entry.disabled_until }, 'Cache disabled until');
        return null;
      }
    }

    // 연속 실패 임계값 체크 - 캐시 무효화
    if (entry.consecutive_fails >= CONSECUTIVE_FAIL_THRESHOLD) {
      logger.warn(
        { siteKey, consecutiveFails: entry.consecutive_fails },
        'Cache invalidated due to consecutive failures, forcing LLM re-analysis'
      );
      return null;
    }

    logger.info({ siteKey, selectors: entry.product_card_selectors.length }, 'Cache hit');
    return entry;
  }

  /**
   * 셀렉터 캐시 저장/업데이트
   */
  set(url: string, entry: Partial<SelectorCacheEntry>): void {
    const siteKey = this.getSiteKey(url);
    const existing = this.cache[siteKey];
    const now = new Date().toISOString();

    this.cache[siteKey] = {
      product_card_selectors: entry.product_card_selectors || existing?.product_card_selectors || [],
      product_name_selectors: entry.product_name_selectors || existing?.product_name_selectors || [],
      detail_link_selectors: entry.detail_link_selectors || existing?.detail_link_selectors || [],
      carrier_selectors: entry.carrier_selectors || existing?.carrier_selectors || [],
      join_type_selectors: entry.join_type_selectors || existing?.join_type_selectors || [],
      storage_selectors: entry.storage_selectors || existing?.storage_selectors || [],
      pricing_selectors: entry.pricing_selectors || existing?.pricing_selectors || {
        retail_price: [],
        public_subsidy: [],
        installment: [],
        monthly_payment: [],
      },
      last_updated: now,
      last_verified_at: now,
      success_count: (existing?.success_count || 0) + 1,
      fail_count: existing?.fail_count || 0,
      consecutive_fails: 0,  // 성공 시 연속 실패 리셋
      consecutive_soft_fails: existing?.consecutive_soft_fails || 0,
      quality_score: entry.quality_score || existing?.quality_score || 80,
    };

    // 비활성화 해제
    delete this.cache[siteKey].disabled_until;

    this.save();
    logger.info({ siteKey }, 'Cache updated');
  }

  /**
   * 성공 기록: 연속 실패 리셋 + 성공 횟수 증가
   */
  recordSuccess(url: string, qualityScore?: number): void {
    const siteKey = this.getSiteKey(url);
    const entry = this.cache[siteKey];

    if (entry) {
      entry.success_count++;
      entry.consecutive_fails = 0;  // 성공 시 연속 실패 리셋
      entry.last_verified_at = new Date().toISOString();
      if (qualityScore !== undefined) {
        entry.quality_score = qualityScore;
      }
      delete entry.disabled_until;  // 비활성화 해제
      this.save();
      logger.debug({ siteKey, successCount: entry.success_count }, 'Success recorded');
    }
  }

  /**
   * 성공한 셀렉터를 우선순위로 올리기
   */
  promoteSelector(url: string, selectorType: keyof Omit<SelectorCacheEntry, 'pricing_selectors' | 'last_updated' | 'success_count' | 'fail_count'>, workingSelector: string): void {
    const siteKey = this.getSiteKey(url);
    const entry = this.cache[siteKey];

    if (!entry) return;

    const selectors = entry[selectorType] as string[];
    const index = selectors.indexOf(workingSelector);

    if (index > 0) {
      // 동작하는 셀렉터를 맨 앞으로 이동
      selectors.splice(index, 1);
      selectors.unshift(workingSelector);
      this.save();
      logger.debug({ siteKey, selectorType, workingSelector }, 'Selector promoted');
    } else if (index === -1) {
      // 새로운 셀렉터 추가
      selectors.unshift(workingSelector);
      this.save();
      logger.debug({ siteKey, selectorType, workingSelector }, 'New selector added');
    }
  }

  /**
   * 실패 카운트 증가 (연속 실패 추적)
   */
  recordFailure(url: string): void {
    const siteKey = this.getSiteKey(url);
    const entry = this.cache[siteKey];

    if (entry) {
      entry.fail_count++;
      entry.consecutive_fails++;
      entry.last_updated = new Date().toISOString();

      // 연속 실패 임계값 도달 시 로그
      if (entry.consecutive_fails >= CONSECUTIVE_FAIL_THRESHOLD) {
        logger.warn(
          { siteKey, consecutiveFails: entry.consecutive_fails },
          'Consecutive fail threshold reached, cache will be invalidated on next access'
        );
      }

      this.save();
      logger.debug(
        { siteKey, consecutiveFails: entry.consecutive_fails, totalFails: entry.fail_count },
        'Failure recorded'
      );
    }
  }

  /**
   * Soft fail 기록 (선택 필드 실패)
   */
  recordSoftFailure(url: string): void {
    const siteKey = this.getSiteKey(url);
    const entry = this.cache[siteKey];

    if (entry) {
      entry.consecutive_soft_fails++;

      // soft fail도 3회 연속 시 재분석 필요
      if (entry.consecutive_soft_fails >= CONSECUTIVE_FAIL_THRESHOLD) {
        logger.warn(
          { siteKey, consecutiveSoftFails: entry.consecutive_soft_fails },
          'Consecutive soft fail threshold reached'
        );
        // 선택 필드 soft fail은 전체 캐시 무효화 대신 경고만
      }

      this.save();
    }
  }

  /**
   * 캐시 일시 비활성화 (지정 시간 동안)
   */
  disableTemporarily(url: string, durationMinutes: number = 30): void {
    const siteKey = this.getSiteKey(url);
    const entry = this.cache[siteKey];

    if (entry) {
      const disabledUntil = new Date();
      disabledUntil.setMinutes(disabledUntil.getMinutes() + durationMinutes);
      entry.disabled_until = disabledUntil.toISOString();
      this.save();
      logger.info({ siteKey, disabledUntil: entry.disabled_until }, 'Cache temporarily disabled');
    }
  }

  /**
   * 캐시 파일에서 로드
   */
  private load(): void {
    try {
      if (fs.existsSync(this.cacheFilePath)) {
        const data = fs.readFileSync(this.cacheFilePath, 'utf8');
        this.cache = JSON.parse(data);
        logger.info({ entries: Object.keys(this.cache).length }, 'Selector cache loaded');
      }
    } catch (error) {
      logger.warn({ error }, 'Failed to load selector cache, starting fresh');
      this.cache = {};
    }
  }

  /**
   * 캐시 파일에 저장
   */
  private save(): void {
    try {
      if (!fs.existsSync(CACHE_DIR)) {
        fs.mkdirSync(CACHE_DIR, { recursive: true });
      }
      fs.writeFileSync(this.cacheFilePath, JSON.stringify(this.cache, null, 2), 'utf8');
    } catch (error) {
      logger.warn({ error }, 'Failed to save selector cache');
    }
  }

  /**
   * 캐시 초기화
   */
  clear(): void {
    this.cache = {};
    this.save();
    logger.info('Selector cache cleared');
  }
}

// 싱글톤 인스턴스
let cacheInstance: SelectorCacheManager | null = null;

export function getSelectorCache(): SelectorCacheManager {
  if (!cacheInstance) {
    cacheInstance = new SelectorCacheManager();
  }
  return cacheInstance;
}
