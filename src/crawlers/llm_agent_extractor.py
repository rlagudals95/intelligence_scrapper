"""
Phase 3B: LLM Agent 기반 정책 추출
사이트 구조와 무관하게 LLM이 추론하여 옵션 클릭 및 정책 수집
"""
import json
import asyncio
import hashlib
import datetime
import base64
import time
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

from ..core.llm_client import LLMClient
from ..utils.logger import get_logger
from ..models.phase3_schemas import (
    ScrapingResult,
    Product,
    Policy,
    MobilePlan,
    PricingDetails,
    SourceInfo,
    JoinType,
    DiscountType,
    parse_storage
)

logger = get_logger()


class LLMAgentExtractor:
    """
    LLM Agent 기반 정책 추출기
    
    특징:
    - 사이트별 특수 셀렉터 불필요
    - LLM이 화면을 보고 옵션 위치 파악
    - 텍스트 기반으로 요소 클릭
    - 범용적으로 모든 사이트 지원
    """
    
    # 요금제 필터 조건 (기종별 통신사별 가입유형별 요금제명 + 월요금)
    PLAN_FILTERS = {
        "GALAXY_S25": {
            "SKT": {
                "번호이동": [
                    {"name": "5GX 프라임", "fee": 89000},
                    {"name": "5GX 레귤러플러스", "fee": 79000},
                    {"name": "5GX 레귤러", "fee": 69000},
                ],
                "기기변경": [
                    {"name": "5GX 프라임", "fee": 89000},
                    {"name": "5GX 레귤러플러스", "fee": 79000},
                    {"name": "5GX 레귤러", "fee": 69000},
                ]
            },
            "KT": {
                "번호이동": [
                    {"name": "스페셜", "fee": 100000},
                    {"name": "베이직", "fee": 80000},
                    {"name": "5G 심플 30GB", "fee": 61000},
                ],
                "기기변경": [
                    {"name": "스페셜", "fee": 100000},
                    {"name": "베이직", "fee": 80000},
                    {"name": "5G 심플 30GB", "fee": 61000},
                ]
            },
            "LGU": {
                "번호이동": [
                    {"name": "5G 프리미어 에센셜", "fee": 85000},
                    {"name": "5G 심플+", "fee": 61000},
                ],
                "기기변경": [
                    {"name": "5G 프리미어 에센셜", "fee": 85000},
                    {"name": "5G 심플+", "fee": 61000},
                ]
            }
        },
        "IPHONE17": {
            "SKT": {
                "번호이동": [
                    {"name": "5GX 프라임", "fee": 89000},
                    {"name": "5GX 레귤러플러스", "fee": 79000},
                    {"name": "5GX 레귤러", "fee": 69000},
                ],
                "기기변경": [
                    {"name": "5GX 프라임", "fee": 89000},
                    {"name": "5GX 레귤러플러스", "fee": 79000},
                    {"name": "5GX 레귤러", "fee": 69000},
                ]
            },
            "KT": {
                "번호이동": [
                    {"name": "스페셜", "fee": 100000},
                    {"name": "베이직", "fee": 80000},
                    {"name": "5G 심플 30GB", "fee": 61000},
                ],
                "기기변경": [
                    {"name": "스페셜", "fee": 100000},
                    {"name": "베이직", "fee": 80000},
                    {"name": "5G 심플 30GB", "fee": 61000},
                ]
            },
            "LGU": {
                "번호이동": [
                    {"name": "5G 프리미어 에센셜", "fee": 85000},
                    {"name": "5G 심플+", "fee": 61000},
                ],
                "기기변경": [
                    {"name": "5G 프리미어 에센셜", "fee": 85000},
                    {"name": "5G 심플+", "fee": 61000},
                ]
            }
        }
    }
    
    def __init__(self, llm_client: LLMClient, model_name: str = "IPHONE17"):
        self.llm = llm_client
        self.model_name = model_name  # 기종명 (GALAXY_S25 또는 IPHONE17)
        self.available_plans = []  # 추출된 요금제 리스트 (월요금 포함)
        logger.info(f"🤖 LLMAgentExtractor 초기화 (기종: {model_name})")
    
    async def analyze_available_options(self, page: Page) -> Dict[str, Any]:
        """
        LLM이 화면을 보고 선택 가능한 옵션 파악
        
        2단계 분석:
        1. 기본 옵션 분석 (용량, 색상, 통신사, 가입유형)
        2. 요금제 드롭다운 열고 요금제 추출
        
        Args:
            page: Playwright Page 객체
            
        Returns:
            옵션 정보 dict
        """
        logger.info("="*70)
        logger.info("📊 LLM Agent: 옵션 분석 시작")
        logger.info("="*70)
        
        # Phase 1: 기본 옵션 분석
        logger.info("\n[Phase 1] 기본 옵션 분석")
        
        # 저해상도 스크린샷 (최적화)
        screenshot_bytes = await page.screenshot(
            full_page=False,
            quality=60,  # JPEG 품질 60%
            type='jpeg'
        )
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
        image_url = f"data:image/jpeg;base64,{screenshot_base64}"
        
        # 옵션 관련 HTML만 추출 (범용적)
        html = await page.evaluate("""
            () => {
                // 옵션 키워드가 포함된 영역 찾기 (클래스명 사용 안 함)
                const allDivs = document.querySelectorAll('div, section, article');
                let optionHTML = '';
                
                for (const div of allDivs) {
                    const text = div.textContent;
                    // 옵션 관련 키워드
                    if (text.includes('용량') || text.includes('색상') || 
                        text.includes('통신사') || text.includes('가입') ||
                        text.includes('요금제') || text.includes('GB')) {
                        optionHTML = div.outerHTML;
                        break;  // 첫 번째 매칭 영역
                    }
                }
                
                return optionHTML ? optionHTML.substring(0, 20000) : document.body.innerHTML.substring(0, 20000);
            }
        """)
        
        logger.info(f"   스크린샷: {len(screenshot_base64)} bytes (JPEG 60%)")
        logger.info(f"   HTML: {len(html)} bytes")
        
        # LLM 프롬프트
        prompt = f"""
이미지와 HTML을 분석하여 **중요한** 옵션만 파악하세요.

# 스크린샷 분석

이미지를 보고 다음 옵션 UI를 찾으세요:

## 필수 옵션 (반드시 찾아야 함)

1. **용량/저장공간** (storage):
   - 256GB, 512GB, 1TB 같은 텍스트가 있는 버튼/탭/라디오
   - 반드시 추출

2. **색상** (color):
   - 색상 이름이나 색상 선택 버튼
   - 있으면 추출, 없으면 빈 리스트

3. **통신사** (carrier):
   - SKT, KT, LG U+, LGU 같은 통신사 선택 UI
   - "사용중인 통신사" 또는 "사용하실 통신사" 라벨 확인
   - 반드시 추출

4. **가입유형** (join_type):
   - "번호이동", "기기변경", "신규가입" 버튼/탭
   - 있으면 추출
   - 또는 "사용중인 통신사"와 "사용하실 통신사"의 조합으로 판단
     * 같은 통신사 → 기기변경
     * 다른 통신사 → 번호이동

5. **요금제** (plan):
   - 요금제 선택 드롭다운/버튼/리스트
   - **모든 요금제 이름**을 나열하세요 (예: "5GX 프리미엄", "5GX 레귤러플러스", "5G 슈퍼플랜")
   - 요금제가 여러 개 보이면 모두 추출하세요
   - 있으면 추출, 없으면 빈 리스트
   - 보통 요금제명 옆에 월요금이 표시됨 (예: "109,000원/월")

## 무시할 옵션 (추출하지 마세요)

- ❌ **할부개월**: 24개월, 30개월, 36개월 → 무시
- ❌ **추가할인**: 통신사 가족결합, 복지할인, 제휴카드 → 무시
- ❌ **할인방법**: 공시지원금, 선택약정 → 무시 (공시지원금 기준으로만 수집)

# HTML 참고
{html[:5000]}

# 응답 형식 (JSON)
{{
  "storage": ["256GB", "512GB", "1TB"],
  "color": ["코스믹 오렌지", "딥 블루", "실버"],
  "carrier": ["SKT", "KT", "LGU"],
  "join_type": ["번호이동", "기기변경"],
  "plan": ["5GX 프리미엄", "5GX 레귤러플러스", "5G 슈퍼플랜"]
}}

**주의:**
- 이미지에서 실제로 보이는 텍스트를 정확히 추출
- 통신사: "LG U+" 또는 "LGU" 형태 그대로 반환
- 옵션이 없으면 빈 리스트 []
- 할부개월, 추가할인은 제외!

**JSON만 출력하세요.**
"""
        
        try:
            logger.info("   🤖 LLM 기본 옵션 분석 중...")
            
            response = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=image_url,
                system_message="당신은 UI 분석 전문가입니다. 이미지를 보고 선택 가능한 옵션을 파악합니다."
            )
            
            # JSON 추출
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            options = json.loads(response)
            logger.info("   ✅ 기본 옵션 분석 완료")
            
        except Exception as e:
            logger.error(f"기본 옵션 분석 실패: {e}")
            options = {}
        
        # Phase 2: 요금제 드롭다운 열고 요금제 추출
        logger.info("\n[Phase 2] 요금제 분석")
        
        plans_extracted = []
        try:
            # 요금제 드롭다운 버튼 찾기
            bill_view_btn = page.locator('.bill-view, button.bill-view, .plan-dropdown-btn')
            count = await bill_view_btn.count()
            
            if count > 0:
                logger.info(f"   🔽 요금제 드롭다운 버튼 발견")
                try:
                    await bill_view_btn.first.click(force=True, timeout=2000)
                    await asyncio.sleep(0.3)  # 1초 → 0.3초
                    logger.info(f"   ✅ 드롭다운 열림")
                except Exception as e:
                    logger.debug(f"   드롭다운 클릭 실패: {e}")
            
            # JavaScript로 요금제 + 월요금 추출 (범용적, 키워드 기반)
            plans_with_fees = await page.evaluate("""
                () => {
                    const plans = [];
                    
                    // 모든 요소에서 요금제 패턴 찾기
                    const allElements = document.querySelectorAll('li, option, div, span, p');
                    
                    allElements.forEach(elem => {
                        const text = elem.textContent.trim();
                        
                        // 요금제명 패턴 (5GX, 5G, LTE 등)
                        if (text.match(/5GX|5G|LTE|프리미|슈퍼|레귤러|초이스|스페셜|베이직|에센셜/) && 
                            text.length < 100) {  // 너무 긴 텍스트 제외
                            
                            // 월요금 패턴 찾기 (콤마 있거나 없거나)
                            const feeMatch = text.match(/(\\d{1,3}),?(\\d{3})\\s*원/);
                            
                            if (feeMatch) {
                                // 요금제명 추출
                                const planName = text.split(/\\d{1,3},?\\d{3}\\s*원/)[0]
                                    .replace(/월/g, '')
                                    .trim();
                                
                                if (planName.length > 2 && planName.length < 30) {
                                    const fee = parseInt(feeMatch[1].replace(',', '') + feeMatch[2]);
                                    plans.push({
                                        name: planName,
                                        monthly_fee: fee
                                    });
                                }
                            }
                        }
                    });
                    
                    // 중복 제거
                    const uniquePlans = [];
                    const seenKeys = new Set();
                    
                    plans.forEach(plan => {
                        const key = plan.name + '_' + plan.monthly_fee;
                        if (!seenKeys.has(key)) {
                            seenKeys.add(key);
                            uniquePlans.push(plan);
                        }
                    });
                    
                    return uniquePlans;
                }
            """)
            
            if plans_with_fees:
                # 요금제명 리스트로 변환 (기존 호환성)
                options["plan"] = [p["name"] for p in plans_with_fees]
                # 월요금 정보도 저장
                self.available_plans = plans_with_fees
                
                logger.info(f"   📋 추출된 요금제 (월요금 포함): {len(plans_with_fees)}개")
                for plan in plans_with_fees[:5]:
                    logger.info(f"      • {plan['name']} ({plan['monthly_fee']:,}원/월)")
            else:
                logger.info(f"   ⚠️  요금제를 찾을 수 없음")
                options["plan"] = []
                self.available_plans = []
                
        except Exception as e:
            logger.debug(f"   요금제 추출 실패: {e}")
        
        # 결과 요약
        logger.info("\n✅ 전체 옵션 분석 완료")
        for opt_type, values in options.items():
            if values:
                logger.info(f"   {opt_type}: {len(values)}개 - {values[:3]}{'...' if len(values) > 3 else ''}")
            else:
                logger.info(f"   {opt_type}: (없음)")
        
        return options
    
    async def click_option(
        self,
        page: Page,
        option_type: str,
        option_value: str
    ) -> bool:
        """
        텍스트 기반으로 옵션 클릭
        
        Args:
            page: Playwright Page 객체
            option_type: 옵션 타입 (예: "storage")
            option_value: 클릭할 값 (예: "512GB")
            
        Returns:
            성공 여부
        """
        logger.info(f"  🎯 클릭 시도: {option_type} = {option_value}")
        
        try:
            # 텍스트로 요소 찾기 (Playwright 내장 기능)
            # 여러 전략 시도
            
            # 전략 1: 정확한 텍스트 매칭
            locator = page.get_by_text(option_value, exact=True)
            count = await locator.count()
            
            if count > 0:
                logger.info(f"     전략 1: 정확한 텍스트 매칭 ({count}개 발견)")
                # 클릭 가능한 요소 찾기 (버튼, 라벨 등)
                for i in range(count):
                    elem = locator.nth(i)
                    tag = await elem.evaluate("el => el.tagName.toLowerCase()")
                    
                    if tag in ["button", "a", "label", "div"]:
                        try:
                            await elem.click(force=True, timeout=3000)
                            logger.info(f"     ✅ 클릭 성공: {tag}")
                            return True
                        except:
                            continue
            
            # 전략 2: 부분 텍스트 매칭
            locator = page.get_by_text(option_value, exact=False)
            count = await locator.count()
            
            if count > 0:
                logger.info(f"     전략 2: 부분 텍스트 매칭 ({count}개 발견)")
                elem = locator.first
                tag = await elem.evaluate("el => el.tagName.toLowerCase()")
                
                try:
                    await elem.click(force=True, timeout=3000)
                    logger.info(f"     ✅ 클릭 성공: {tag}")
                    return True
                except:
                    pass
            
            # 전략 3: Role 기반 (버튼, 라디오 등)
            for role in ["button", "radio", "tab", "option"]:
                try:
                    locator = page.get_by_role(role, name=option_value)
                    count = await locator.count()
                    if count > 0:
                        logger.info(f"     전략 3: Role '{role}' ({count}개 발견)")
                        await locator.first.click(force=True, timeout=3000)
                        logger.info(f"     ✅ 클릭 성공")
                        return True
                except:
                    continue
            
            logger.warning(f"     ⚠️  클릭 실패: {option_value}를 찾을 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"     ❌ 클릭 오류: {e}")
            return False
    
    async def extract_pricing_from_screen(self, page: Page) -> Dict[str, Any]:
        """
        현재 화면에서 가격 정보 추출 (Vision API)
        
        최적화:
        - 저해상도 스크린샷 (품질 낮춤)
        - 가격 관련 HTML만 추출 (범용적)
        
        Args:
            page: Playwright Page 객체
            
        Returns:
            가격 정보 dict
        """
        # 전체 화면 스크린샷 (저해상도로 최적화)
        screenshot_bytes = await page.screenshot(
            full_page=False,
            quality=50,  # JPEG 품질 50% (파일 크기 대폭 감소)
            type='jpeg'  # PNG 대신 JPEG 사용
        )
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
        image_url = f"data:image/jpeg;base64,{screenshot_base64}"
        
        logger.debug(f"   📸 스크린샷: {len(screenshot_base64)} bytes (JPEG 50%)")
        
        # 가격 관련 HTML만 추출 (범용적, 클래스명 사용 안 함)
        pricing_html = await page.evaluate("""
            () => {
                // 가격 키워드가 포함된 모든 요소 찾기
                const allElements = document.querySelectorAll('dl, div, table, ul');
                let html = '';
                let count = 0;
                
                allElements.forEach(elem => {
                    const text = elem.textContent;
                    // 가격 관련 키워드 확인
                    if (text.includes('출고가') || text.includes('지원금') || 
                        text.includes('할부') || text.includes('요금') || 
                        text.includes('납부') || text.includes('월')) {
                        html += elem.outerHTML + '\\n';
                        count++;
                        if (count >= 15) return;  // 최대 15개
                    }
                });
                
                return html.substring(0, 5000);  // 최대 5000자
            }
        """)
        
        prompt = f"""
이미지와 HTML을 분석하여 휴대폰 가격 정보를 추출하세요.

# 이미지 분석
스크린샷에서 다음을 찾으세요:
- 출고가
- 공시지원금 또는 추가지원금
- 할부원금
- 월 납부금액
- 요금제 정보

# HTML 참고
{pricing_html[:3000]}

# 응답 (JSON)
{{
  "retail_price": 1980000,
  "public_subsidy": 0,
  "additional_subsidy": -550000,
  "installment_principal": 1430000,
  "monthly_payment": 63314,
  "final_price": 145064,
  "plan_name": "5GX 프리미엄",
  "plan_monthly_fee": 109000
}}

**이미지에서 본 실제 값을 반환하세요. JSON만 출력.**
"""
        
        try:
            response = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=image_url,
                system_message="가격 정보를 정확히 추출하세요."
            )
            
            # JSON 추출
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            response = response.strip()
            
            pricing = json.loads(response)
            
            logger.info("   ✅ 가격 추출 완료")
            if pricing.get('retail_price'):
                logger.info(f"      출고가: {pricing['retail_price']:,}원")
            if pricing.get('installment_principal'):
                logger.info(f"      할부원금: {pricing['installment_principal']:,}원")
            if pricing.get('final_price'):
                logger.info(f"      월납부: {pricing['final_price']:,}원")
            
            return pricing
            
        except Exception as e:
            logger.error(f"   ❌ 가격 추출 실패: {e}")
            return {}
    
    async def collect_all_policies(
        self,
        page: Page,
        url: str,
        site_name: str = "Unknown",
        max_combinations: int = 30
    ) -> ScrapingResult:
        """
        모든 옵션 조합에 대한 정책 수집
        
        Args:
            page: Playwright Page 객체
            url: 페이지 URL
            site_name: 사이트 이름
            max_combinations: 최대 조합 수
            
        Returns:
            ScrapingResult
        """
        logger.info("="*70)
        logger.info("🚀 LLM Agent 기반 정책 수집 시작")
        logger.info("="*70)
        logger.info(f"사이트: {site_name}")
        logger.info(f"URL: {url}")
        logger.info(f"최대 조합: {max_combinations}")
        logger.info("="*70 + "\n")
        
        # Step 1: 선택 가능한 옵션 분석
        logger.info("[Step 1] 옵션 분석")
        step1_start = time.time()
        available_options = await self.analyze_available_options(page)
        logger.info(f"   ⏱️ Step 1 완료: {time.time() - step1_start:.2f}초")
        
        if not available_options:
            logger.warning("⚠️  옵션을 찾을 수 없습니다")
            return ScrapingResult(
                source=SourceInfo(site=site_name, url=url),
                products=[]
            )
        
        # Step 2: 경우의 수 계산
        logger.info("\n[Step 2] 경우의 수 계산")
        total_combinations = 1
        for opt_type, values in available_options.items():
            if values:
                total_combinations *= len(values)
                logger.info(f"   {opt_type}: {len(values)}개 → 누적: {total_combinations}개")
        
        logger.info(f"\n   💡 이론적 총 조합: {total_combinations}개")
        
        # Step 3: 요금제 필터링 (조건에 맞는 요금제만)
        logger.info("\n[Step 3] 요금제 필터링")
        logger.info(f"   기종: {self.model_name}")
        logger.info(f"   추출된 요금제: {len(self.available_plans)}개")
        
        filtered_plans = self._filter_plans_by_model(available_options)
        
        logger.info(f"   📋 조건에 맞는 요금제: {len(filtered_plans)}개")
        for plan_info in filtered_plans[:5]:
            logger.info(f"      • {plan_info['name']} ({plan_info['monthly_fee']:,}원/월)")
        
        # Step 4: 가지치기 전략 적용
        logger.info("\n[Step 4] 가지치기 전략 적용")
        pruned_options = self._apply_pruning_strategy(available_options)
        
        # 최종 조합 계산 (요금제 포함)
        final_combinations = len(filtered_plans) if filtered_plans else 1
        for opt_type, values in pruned_options.items():
            if values:
                final_combinations *= len(values)
        
        logger.info(f"   ✂️  가지치기 후: {final_combinations}개")
        
        if final_combinations > max_combinations:
            logger.warning(f"   ⚠️  최대 조합 수 제한: {max_combinations}개")
        
        # Step 5: 조합 생성 (요금제 포함)
        logger.info("\n[Step 5] 조합 생성")
        from itertools import product as itertools_product
        
        combinations = []
        
        # 기본 옵션 조합 (용량, 색상, 통신사, 가입유형)
        base_keys = list(pruned_options.keys())
        base_values = [pruned_options[k] for k in base_keys if pruned_options[k]]
        base_keys = [k for k in base_keys if pruned_options[k]]
        
        if not base_keys:
            logger.warning("   ⚠️  유효한 옵션 없음")
            return ScrapingResult(source=SourceInfo(site=site_name, url=url), products=[])
        
        # 각 기본 조합에 대해 요금제 추가
        for base_combo_values in itertools_product(*base_values):
            base_combo = dict(zip(base_keys, base_combo_values))
            
            # 이 조합의 통신사와 가입유형에 맞는 요금제 필터링
            carrier = base_combo.get("carrier", "")
            join_type = base_combo.get("join_type", "")
            
            # 조건에 맞는 요금제 찾기
            matching_plans = [
                p for p in filtered_plans
                if self._is_plan_valid_for_combo(p, carrier, join_type)
            ]
            
            if matching_plans:
                # 각 요금제별로 조합 생성
                for plan_info in matching_plans[:3]:  # 최대 3개
                    combo = base_combo.copy()
                    combo["plan"] = plan_info["name"]
                    combinations.append(combo)
            else:
                # 요금제 정보 없으면 기본 조합만
                combinations.append(base_combo)
            
            if len(combinations) >= max_combinations:
                break
        
        logger.info(f"   ✅ 생성된 조합: {len(combinations)}개")
        for idx, combo in enumerate(combinations[:5], 1):
            logger.info(f"      [{idx}] {combo}")
        if len(combinations) > 5:
            logger.info(f"      ... 외 {len(combinations) - 5}개")
        
        # Step 5: 각 조합별 정책 수집
        logger.info("\n[Step 5] 정책 수집 시작")
        logger.info("="*70)
        
        collected_data = []
        
        for idx, combo in enumerate(combinations, 1):
            combo_start = time.time()
            print(f"\n[{idx}/{len(combinations)}] 조합 시작: {combo} - {time.strftime('%H:%M:%S')}")
            logger.info(f"\n[{idx}/{len(combinations)}] 조합: {combo}")
            
            try:
                # 옵션 선택
                click_start = time.time()
                click_success_count = 0
                for opt_type, opt_value in combo.items():
                    try:
                        success = await self.click_option(page, opt_type, opt_value)
                        if success:
                            click_success_count += 1
                        else:
                            logger.warning(f"   ⚠️  클릭 실패: {opt_type}={opt_value}")
                    except Exception as e:
                        logger.warning(f"   ⚠️  클릭 오류: {opt_type}={opt_value}, {e}")
                
                click_time = time.time() - click_start
                print(f"   ⏱️ 옵션 클릭: {click_time:.2f}초 ({click_success_count}/{len(combo)}개 성공)")
                logger.info(f"   옵션 클릭: {click_time:.2f}초")
                
                # 화면 업데이트 대기 (최적화: 2초 → 0.5초)
                await asyncio.sleep(0.5)
                
                # 가격 추출
                pricing_start = time.time()
                print(f"   💰 가격 추출 시작...")
                logger.info(f"   가격 추출 시도...")
                pricing = await self.extract_pricing_from_screen(page)
                pricing_time = time.time() - pricing_start
                print(f"   ⏱️ 가격 추출: {pricing_time:.2f}초")
                logger.info(f"   가격 추출: {pricing_time:.2f}초")
                
                if pricing and pricing.get('retail_price'):
                    collected_data.append({
                        "combo": combo,
                        "pricing": pricing
                    })
                    combo_total = time.time() - combo_start
                    print(f"   ✅ 정책 수집 완료 (총 {combo_total:.2f}초)\n")
                    logger.info(f"   ✅ 정책 수집 완료 (총 {combo_total:.2f}초)")
                else:
                    print(f"   ⚠️  가격 추출 실패\n")
                    logger.warning(f"   ⚠️  가격 추출 실패 또는 데이터 없음: {pricing}")
                
            except Exception as e:
                logger.error(f"   ❌ 조합 처리 실패: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        logger.info("\n" + "="*70)
        logger.info(f"✅ 정책 수집 완료: {len(collected_data)}개")
        logger.info("="*70 + "\n")
        
        # Step 6: Phase 3 스키마로 변환
        logger.info("[Step 6] 스키마 변환")
        result = self._convert_to_schema(collected_data, url, site_name)
        
        logger.info(f"   ✅ 변환 완료: {len(result.products)}개 제품, {sum(len(p.policies) for p in result.products)}개 정책\n")
        
        return result
    
    def _filter_plans_by_model(self, options: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        기종에 맞는 요금제만 필터링
        
        조건: 요금제명 + 월요금 모두 확인
        - SKT 번호이동: "5GX 프라임" (89000), "5GX 레귤러플러스" (79000), "5GX 레귤러" (69000)
        - KT 번호이동: "스페셜" (100000), "베이직" (80000), "5G 심플 30GB" (61000)
        - LGU 번호이동: "5G 프리미어 에센셜" (85000), "5G 심플+" (61000)
        
        Returns:
            필터링된 요금제 리스트 [{"name": "요금제명", "monthly_fee": 89000}, ...]
        """
        if not self.available_plans:
            return []
        
        if self.model_name not in self.PLAN_FILTERS:
            # 필터 조건 없으면 모두 허용
            return self.available_plans
        
        # 모든 허용된 요금제 (이름 + 월요금) 수집
        model_filters = self.PLAN_FILTERS[self.model_name]
        all_allowed_plans = []
        
        for carrier_filters in model_filters.values():
            for plan_list in carrier_filters.values():
                all_allowed_plans.extend(plan_list)
        
        # 중복 제거
        unique_allowed = {(p["name"], p["fee"]) for p in all_allowed_plans}
        
        # 추출된 요금제 중 조건에 맞는 것만 필터링
        filtered = []
        for plan in self.available_plans:
            plan_name = plan["name"]
            plan_fee = plan["monthly_fee"]
            
            # 이름 유사도 검사 (부분 일치)
            for allowed_name, allowed_fee in unique_allowed:
                # 월요금이 일치하고 이름이 유사하면 허용
                if plan_fee == allowed_fee:
                    # 이름 부분 일치 확인 (공백/특수문자 무시)
                    plan_name_clean = plan_name.replace(" ", "").replace("+", "")
                    allowed_name_clean = allowed_name.replace(" ", "").replace("+", "")
                    
                    if (allowed_name_clean in plan_name_clean or 
                        plan_name_clean in allowed_name_clean):
                        filtered.append(plan)
                        break
        
        return filtered
    
    def _is_plan_valid_for_combo(
        self,
        plan_info: Dict[str, Any],
        carrier: str,
        join_type: str
    ) -> bool:
        """
        요금제가 특정 조합에 유효한지 확인 (요금제명 + 월요금)
        
        Args:
            plan_info: 요금제 정보 {"name": "5GX 프라임", "monthly_fee": 89000}
            carrier: 통신사 (SKT, KT, LGU)
            join_type: 가입유형 (번호이동, 기기변경)
            
        Returns:
            유효 여부
        """
        if self.model_name not in self.PLAN_FILTERS:
            # 필터 조건 없으면 모두 허용
            return True
        
        model_filters = self.PLAN_FILTERS[self.model_name]
        
        # 통신사 정규화
        carrier_normalized = carrier.upper()
        if "LG" in carrier_normalized:
            carrier_normalized = "LGU"
        
        if carrier_normalized not in model_filters:
            return False
        
        carrier_filters = model_filters[carrier_normalized]
        
        # 가입유형 정규화
        join_normalized = "번호이동" if "번호이동" in join_type else "기기변경"
        
        if join_normalized not in carrier_filters:
            return False
        
        # 허용된 요금제 리스트 (이름 + 월요금)
        allowed_plans = carrier_filters[join_normalized]
        
        # 요금제 이름과 월요금 모두 확인
        plan_name = plan_info.get("name", "")
        plan_fee = plan_info.get("monthly_fee", 0)
        
        # 이름 정규화 (공백, +, 특수문자 제거)
        plan_name_clean = plan_name.replace(" ", "").replace("+", "").upper()
        
        for allowed in allowed_plans:
            allowed_name_clean = allowed["name"].replace(" ", "").replace("+", "").upper()
            allowed_fee = allowed["fee"]
            
            # 월요금 일치 + 이름 부분 일치
            if plan_fee == allowed_fee:
                if (allowed_name_clean in plan_name_clean or 
                    plan_name_clean in allowed_name_clean):
                    return True
        
        return False
    
    def _apply_pruning_strategy(self, options: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        가지치기 전략 적용
        
        조합에 포함할 옵션:
        - 용량: 첫 번째만 (최저 용량)
        - 색상: 첫 번째만 (가격 동일)
        - 통신사: 모두 (SKT, KT, LGU)
        - 가입유형: 모두 (번호이동, 기기변경)
        
        조합에서 제외:
        - 요금제: 조합 생성에서 제외 (각 조합에서 현재 요금제만 사용)
        - 할부개월: 무시
        - 추가할인: 무시
        - 할인방법: 무시
        
        Args:
            options: 원본 옵션 목록
            
        Returns:
            가지치기된 옵션 목록
        """
        pruned = {}
        
        for opt_type, values in options.items():
            if not values:
                continue
            
            if opt_type == "storage":
                # 용량: 첫 번째만 (최저 용량)
                pruned[opt_type] = [values[0]]
                logger.info(f"   ✅ {opt_type}: 첫 번째만 (최저 용량) (1/{len(values)}개)")
                
            elif opt_type == "color":
                # 색상: 첫 번째만 (가격 동일)
                pruned[opt_type] = [values[0]]
                logger.info(f"   ✅ {opt_type}: 첫 번째만 (1/{len(values)}개)")
                
            elif opt_type == "carrier":
                # 통신사: 모두 테스트 (중요!)
                pruned[opt_type] = values
                logger.info(f"   ✅ {opt_type}: 모두 ({len(values)}개)")
                
            elif opt_type == "join_type":
                # 가입유형: 모두 테스트 (중요!)
                pruned[opt_type] = values
                logger.info(f"   ✅ {opt_type}: 모두 ({len(values)}개)")
                
            elif opt_type == "plan":
                # 요금제: 조합에서 제외 (현재 선택된 요금제 사용)
                logger.info(f"   💡 {opt_type}: 조합 제외 (현재 요금제 사용) ({len(values)}개 발견)")
                # pruned에 추가하지 않음
            
            else:
                # 나머지 옵션 무시 (installment, discount 등)
                logger.info(f"   ❌ {opt_type}: 무시 ({len(values)}개)")
        
        return pruned
    
    def _convert_to_schema(
        self,
        collected_data: List[Dict[str, Any]],
        url: str,
        site_name: str
    ) -> ScrapingResult:
        """수집 데이터를 Phase 3 스키마로 변환"""
        
        # 용량별로 그룹화
        products_by_storage: Dict[str, List[Dict]] = {}
        
        for data in collected_data:
            combo = data["combo"]
            storage = combo.get("storage", "Unknown")
            
            if storage not in products_by_storage:
                products_by_storage[storage] = []
            products_by_storage[storage].append(data)
        
        # Product 생성
        products = []
        
        for storage, policies_data in products_by_storage.items():
            policies = []
            
            for data in policies_data:
                combo = data["combo"]
                pricing = data["pricing"]
                
                # Policy ID 생성
                policy_id = hashlib.md5(str(combo).encode()).hexdigest()[:16]
                
                # JoinType 파싱
                join_type_str = combo.get("join_type", "")
                if "번호이동" in join_type_str:
                    join_type = JoinType.NUMBER_TRANSFER
                elif "신규" in join_type_str or "신규가입" in join_type_str:
                    join_type = JoinType.NEW_SUBSCRIPTION
                else:
                    join_type = JoinType.DEVICE_CHANGE
                
                # Carrier 정규화
                carrier_str = combo.get("carrier", "Unknown")
                if "LG" in carrier_str.upper():
                    carrier = "LGU"
                else:
                    carrier = carrier_str.upper()
                
                policy = Policy(
                    policy_id=policy_id,
                    carrier=carrier,
                    mno_join_type=join_type,
                    mobile_plan=MobilePlan(
                        name=pricing.get("plan_name", "알 수 없음"),
                        monthly_fee=pricing.get("plan_monthly_fee", 0) or 0
                    ),
                    discount_type=DiscountType.PUBLIC_SUBSIDY,
                    pricing=PricingDetails(
                        mno_retail_price=pricing.get("retail_price"),
                        public_subsidy=pricing.get("public_subsidy"),
                        discount=pricing.get("additional_subsidy"),
                        sku_installment_fee=pricing.get("installment_principal"),
                        monthly_payment=pricing.get("monthly_payment")
                    )
                )
                
                policies.append(policy)
            
            # Product 생성
            product_id = hashlib.md5(f"{site_name}_{storage}".encode()).hexdigest()[:16]
            
            product = Product(
                product_id=product_id,
                sku_code="Unknown Model",  # TODO: 모델명 추출
                sku_storage=parse_storage(storage),
                policies=policies
            )
            
            products.append(product)
        
        return ScrapingResult(
            captured_at=datetime.datetime.now(),
            source=SourceInfo(site=site_name, url=url),
            products=products
        )

