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
from .smart_plan_extractor import SmartPlanExtractor

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
        
        # Phase 0: 요금제 드롭다운 열기 (확실하게!)
        logger.info("\n[Phase 0] 요금제 드롭다운 열기")
        print("\n[Phase 0] 요금제 드롭다운 열기")
        
        # 전략 1: "월" + 숫자 패턴이 있는 모든 요소 클릭
        try:
            plan_boxes = page.locator('*:has-text("월"):has-text("원")')
            count = await plan_boxes.count()
            print(f"   '월'+'원' 요소: {count}개")
            logger.info(f"   '월'+'원' 요소: {count}개")
            
            for i in range(min(count, 10)):
                try:
                    elem = plan_boxes.nth(i)
                    text = await elem.text_content(timeout=500)
                    
                    # "월 109,000원" 같은 패턴이 있으면 클릭
                    if "월" in text and "원" in text and len(text) < 300:
                        await elem.click(force=True, timeout=500)
                        await asyncio.sleep(0.2)
                        print(f"   ✅ 클릭 {i+1}: {text[:30]}...")
                except:
                    pass
        except Exception as e:
            logger.debug(f"   전략 1 실패: {e}")
        
        # 전략 2: ▼ 버튼 클릭
        try:
            dropdown_btns = page.locator('*:has-text("▼")')
            count = await dropdown_btns.count()
            print(f"   ▼ 버튼: {count}개")
            
            for i in range(min(count, 5)):
                try:
                    await dropdown_btns.nth(i).click(force=True, timeout=500)
                    await asyncio.sleep(0.2)
                except:
                    pass
        except:
            pass
        
        # 충분한 대기 (드롭다운이 완전히 열릴 때까지)
        await asyncio.sleep(2)
        print("   ⏸️  드롭다운 대기 완료\n")
        
        # Phase 1: 기본 옵션 분석
        logger.info("[Phase 1] 기본 옵션 분석")
        
        # 스크린샷 (타임아웃 처리)
        screenshot_base64 = None
        try:
            screenshot_bytes = await page.screenshot(
                full_page=False,
                quality=60,
                type='jpeg',
                timeout=10000  # 10초 타임아웃
            )
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
            logger.info(f"   📸 스크린샷 캡처 성공")
        except Exception as e:
            logger.warning(f"   ⚠️ 스크린샷 실패 (HTML만 사용): {e}")
        
        image_url = f"data:image/jpeg;base64,{screenshot_base64}" if screenshot_base64 else None
        
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
        
        if screenshot_base64:
            logger.info(f"   스크린샷: {len(screenshot_base64)} bytes (JPEG 60%)")
        else:
            logger.info(f"   스크린샷: 실패 (HTML만 사용)")
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
            
            if image_url:
                # Vision API 사용
                response = await self.llm.complete_with_vision(
                    prompt=prompt,
                    image_url=image_url,
                    system_message="당신은 UI 분석 전문가입니다. 이미지를 보고 선택 가능한 옵션을 파악합니다."
                )
            else:
                # HTML만 사용
                response = await self.llm.complete(
                    prompt=prompt,
                    system_message="당신은 UI 분석 전문가입니다. HTML을 분석하여 선택 가능한 옵션을 파악합니다.",
                    response_format={"type": "json_object"}
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
            import traceback
            traceback.print_exc()
            options = {}
        
        # Phase 2: SmartPlanExtractor로 요금제 추출
        logger.info("\n[Phase 2] 요금제 추출 (Smart)")
        print("\n[Phase 2] 요금제 추출 (Smart)")
        
        plans_with_fees = []
        
        try:
            smart_extractor = SmartPlanExtractor(self.llm)
            plans_with_fees = await smart_extractor.extract_all_plans(page)
            
        except Exception as e:
            logger.error(f"   ❌ Smart 추출 실패: {e}")
            
            # Fallback: JavaScript로 시도
            logger.info(f"   🔄 Fallback: JavaScript")
            
            try:
                plans_with_fees = await page.evaluate("""
                () => {
                    const plans = [];
                    
                    // 모든 li, option 요소에서 요금제 찾기 (visible 체크 제거!)
                    const planElements = document.querySelectorAll('li, option, tr');
                    
                    planElements.forEach(elem => {
                        const text = elem.textContent.trim();
                        
                        // 요금제 패턴: 짧고 + "월" + 숫자 + 키워드
                        if (text.length < 300 && text.includes('월') &&
                            text.match(/프리미|프라임|레귤러|레규러|스페셜|베이직|심플|슬림|에센셜/i)) {
                            
                            // 월요금 패턴
                            const feeMatch = text.match(/(\\d{1,3}),?(\\d{3})\\s*원/);
                            
                            if (feeMatch) {
                                const fee = parseInt(feeMatch[1].replace(',', '') + feeMatch[2]);
                                
                                // 범위 체크
                                if (fee < 40000 || fee > 150000) return;
                                
                                // 요금제명 추출
                                let planName = text.split(/월\\s*(\\d{1,3}),?(\\d{3})\\s*원/)[0]
                                    .replace(/\\(.*?\\)/g, '')  // 괄호 제거
                                    .trim();
                                
                                if (planName.length >= 2 && planName.length < 30) {
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
                    const seen = new Set();
                    
                    plans.forEach(plan => {
                        const key = plan.name + '_' + plan.monthly_fee;
                        if (!seen.has(key)) {
                            seen.add(key);
                            uniquePlans.push(plan);
                        }
                    });
                    
                    return uniquePlans;
                }
                """)
                
                logger.info(f"   ✅ JavaScript 추출: {len(plans_with_fees)}개")
                
            except Exception as e2:
                logger.error(f"   ❌ JavaScript도 실패: {e2}")
        
        # 최종 요금제 저장
        if plans_with_fees:
            # 요금제명 리스트로 변환
            options["plan"] = [p["name"] for p in plans_with_fees]
            # 월요금 정보도 저장
            self.available_plans = plans_with_fees
            
            logger.info(f"   📋 최종 추출된 요금제: {len(plans_with_fees)}개")
            for plan in plans_with_fees[:10]:
                logger.info(f"      • {plan['name']} ({plan['monthly_fee']:,}원/월)")
        else:
            logger.warning(f"   ⚠️  요금제를 찾을 수 없음")
            options["plan"] = []
            self.available_plans = []
        
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
            option_type: 옵션 타입 (예: "storage", "plan")
            option_value: 클릭할 값 (예: "512GB", "5GX 프라임")
            
        Returns:
            성공 여부
        """
        logger.info(f"  🎯 클릭 시도: {option_type} = {option_value}")
        
        # plan_fee는 클릭하지 않음 (디버깅 정보일 뿐)
        if option_type == "plan_fee":
            return True
        
        try:
            # 요금제 클릭은 더 세심하게 (핵심 키워드만 사용)
            if option_type == "plan":
                logger.info(f"     📋 요금제 선택: '{option_value}'")
                print(f"     📋 요금제 선택: '{option_value}'")
                
                # Step 1: 요금제 드롭다운/팝업 열기 (Phase 0 방식 - 가장 확실함)
                logger.info(f"     [Step 1] 드롭다운 열기 (Phase 0 방식)")
                print(f"     [Step 1] 드롭다운 열기 (Phase 0 방식)")
                
                # 먼저 팝업이 이미 열려있는지 확인
                popup_check = page.locator('.popup.popup-detail.popup-price, .popup-detail, .popup')
                popup_count_before = await popup_check.count()
                logger.info(f"     🔍 [DEBUG] 팝업 열기 전 팝업 개수: {popup_count_before}")
                print(f"     🔍 [DEBUG] 팝업 열기 전 팝업 개수: {popup_count_before}")
                
                dropdown_opened = False
                
                # 팝업이 이미 열려있으면 스킵
                if popup_count_before > 0:
                    logger.info(f"     ✅ 팝업이 이미 열려있음")
                    print(f"     ✅ 팝업이 이미 열려있음")
                    dropdown_opened = True
                else:
                    # 전략 1: Vision API로 현재 선택된 요금제 버튼 찾기 (SmartPlanExtractor 방식)
                    logger.info(f"     전략 1: Vision API로 버튼 찾기 (SmartPlanExtractor 방식)")
                    print(f"     전략 1: Vision API로 버튼 찾기 (SmartPlanExtractor 방식)")
                    vision_success = False
                    try:
                        import base64
                        screenshot = await page.screenshot(full_page=False, quality=60, type='jpeg')
                        screenshot_b64 = base64.b64encode(screenshot).decode()
                        img_url = f"data:image/jpeg;base64,{screenshot_b64}"
                        
                        button_prompt = """
이 화면에서 "요금제" 선택 박스/버튼을 찾으세요.

보통:
- "요금제" 라벨
- 현재 선택된 요금제명 + 월요금
- 드롭다운 아이콘 (▼)

예: "프리미엄(OTT 택1) 월 109,000원 ▼" 또는 "프라임 월 89,000원 ▼"

현재 선택된 요금제의 **정확한 텍스트 일부**를 반환:

JSON:
{"button_text": "프리미엄"}

**클릭할 버튼을 찾을 수 있는 키워드만 반환하세요.**
"""
                        
                        resp = await self.llm.complete_with_vision(
                            prompt=button_prompt,
                            image_url=img_url,
                            system_message="요금제 드롭다운 버튼을 찾으세요."
                        )
                        
                        resp = resp.strip()
                        if "```" in resp:
                            resp = resp.split("```")[1] if "```json" not in resp else resp.split("```json")[1].split("```")[0]
                        resp = resp.strip()
                        
                        button_info = json.loads(resp)
                        button_text = button_info.get("button_text", "")
                        
                        logger.info(f"     🎯 Vision으로 찾은 버튼 키워드: '{button_text}'")
                        print(f"     🎯 Vision으로 찾은 버튼 키워드: '{button_text}'")
                        
                        if button_text:
                            # 버튼 클릭 시도 (타임아웃 짧게 설정)
                            try:
                                await page.get_by_text(button_text, exact=False).first.click(force=True, timeout=2000)
                                await asyncio.sleep(1)  # SmartPlanExtractor와 동일
                                logger.info(f"     ✅ Vision 버튼 클릭 완료")
                                print(f"     ✅ Vision 버튼 클릭 완료")
                                
                                # 팝업 확인
                                popup_count_after = await popup_check.count()
                                if popup_count_after > 0:
                                    logger.info(f"     ✅ 팝업 열림 확인: {popup_count_after}개")
                                    print(f"     ✅ 팝업 열림 확인: {popup_count_after}개")
                                    dropdown_opened = True
                                    vision_success = True
                                else:
                                    logger.warning(f"     ⚠️  Vision 버튼 클릭했지만 팝업이 열리지 않음")
                                    print(f"     ⚠️  Vision 버튼 클릭했지만 팝업이 열리지 않음")
                            except Exception as click_error:
                                logger.warning(f"     ⚠️  Vision으로 찾은 버튼 클릭 실패: {click_error}")
                                print(f"     ⚠️  Vision으로 찾은 버튼 클릭 실패: {click_error}")
                    except Exception as e:
                        logger.warning(f"     ⚠️ Vision 버튼 찾기 실패: {e}")
                        print(f"     ⚠️ Vision 버튼 찾기 실패: {e}")
                    
                    # 전략 2: Vision API 실패 시 "월" + "원" 패턴으로 Fallback (Phase 0 방식)
                    if not vision_success:
                        logger.info(f"     전략 2: '월'+'원' 패턴 클릭 (Fallback - Phase 0 방식)")
                        print(f"     전략 2: '월'+'원' 패턴 클릭 (Fallback - Phase 0 방식)")
                        try:
                            plan_boxes = page.locator('*:has-text("월"):has-text("원")')
                            count = await plan_boxes.count()
                            logger.info(f"     '월'+'원' 요소: {count}개")
                            print(f"     '월'+'원' 요소: {count}개")
                            
                            # Phase 0처럼 모든 요소를 클릭 (팝업 확인은 나중에)
                            clicked_count = 0
                            for i in range(min(count, 10)):
                                try:
                                    elem = plan_boxes.nth(i)
                                    text = await elem.text_content(timeout=500)
                                    
                                    # "월 109,000원" 같은 패턴이 있으면 클릭
                                    if text and "월" in text and "원" in text and len(text) < 300:
                                        await elem.click(force=True, timeout=500)
                                        await asyncio.sleep(0.2)  # Phase 0과 동일
                                        clicked_count += 1
                                        logger.info(f"     ✅ 클릭 {clicked_count}: {text[:30]}...")
                                        print(f"     ✅ 클릭 {clicked_count}: {text[:30]}...")
                                except:
                                    pass
                            
                            logger.info(f"     총 {clicked_count}개 요소 클릭 완료")
                            print(f"     총 {clicked_count}개 요소 클릭 완료")
                            
                            # Phase 0처럼 충분한 대기 후 팝업 확인
                            await asyncio.sleep(2)  # Phase 0과 동일한 대기 시간
                            popup_count_after = await popup_check.count()
                            logger.info(f"     🔍 [DEBUG] 팝업 열기 후 팝업 개수: {popup_count_after}")
                            print(f"     🔍 [DEBUG] 팝업 열기 후 팝업 개수: {popup_count_after}")
                            
                            if popup_count_after > 0:
                                logger.info(f"     ✅ 팝업 열림 확인: {popup_count_after}개")
                                print(f"     ✅ 팝업 열림 확인: {popup_count_after}개")
                                dropdown_opened = True
                        except Exception as e:
                            logger.debug(f"     전략 2 실패: {e}")
                    
                    # 전략 3: Fallback - ▼ 버튼 클릭 (SmartPlanExtractor와 동일)
                    if not dropdown_opened:
                        logger.info(f"     전략 3: ▼ 버튼 클릭 (Fallback)")
                        print(f"     전략 3: ▼ 버튼 클릭 (Fallback)")
                        try:
                            btns = await page.locator('*:has-text("▼")').all()
                            logger.info(f"     ▼ 버튼: {len(btns)}개")
                            print(f"     ▼ 버튼: {len(btns)}개")
                            
                            for btn in btns[:3]:
                                try:
                                    await btn.click(force=True, timeout=500)
                                    await asyncio.sleep(0.2)  # SmartPlanExtractor와 동일
                                except:
                                    pass
                            
                            # 팝업 확인
                            await asyncio.sleep(0.5)
                            popup_count_after = await popup_check.count()
                            if popup_count_after > 0:
                                logger.info(f"     ✅ 팝업 열림 확인: {popup_count_after}개")
                                print(f"     ✅ 팝업 열림 확인: {popup_count_after}개")
                                dropdown_opened = True
                        except Exception as e:
                            logger.debug(f"     전략 3 실패: {e}")
                    
                    # 대기 시간 (Vision 성공 시 1.5초, Fallback 사용 시 이미 2초 대기했으므로 추가 불필요)
                    if vision_success:
                        await asyncio.sleep(1.5)  # SmartPlanExtractor와 동일한 대기 시간
                
                # 추가 대기 (이미 위에서 2초 대기했으므로 추가 대기 불필요)
                if dropdown_opened:
                    logger.info(f"     ✅ 드롭다운 열기 성공")
                    print(f"     ✅ 드롭다운 열기 성공")
                else:
                    logger.warning(f"     ⚠️  드롭다운 열기 실패, 그래도 진행 시도")
                    print(f"     ⚠️  드롭다운 열기 실패, 그래도 진행 시도")
                
                # Step 2: 열린 팝업/드롭다운에서 특정 요금제 선택
                logger.info(f"     [Step 2] 요금제 '{option_value}' 선택")
                print(f"     [Step 2] 요금제 '{option_value}' 선택")
                
                # 요금제명 정리 (괄호 제거)
                plan_name_clean = option_value.split('(')[0].strip()  # "프리미엄(OTT 택1)" → "프리미엄"
                
                logger.info(f"     검색할 요금제명: '{plan_name_clean}'")
                print(f"     검색할 요금제명: '{plan_name_clean}'")
                
                selected = False
                
                # 전략 1: 팝업 테이블의 <tr> 요소에서 정확히 일치하는 것 찾기
                try:
                    # 팝업이 열려있는지 확인
                    popup = page.locator('.popup.popup-detail.popup-price, .popup-detail, .popup')
                    popup_count = await popup.count()
                    popup_visible = popup_count > 0
                    
                    logger.info(f"     🔍 [DEBUG] 팝업 개수: {popup_count}, visible: {popup_visible}")
                    print(f"     🔍 [DEBUG] 팝업 개수: {popup_count}, visible: {popup_visible}")
                    
                    if popup_visible:
                        logger.info(f"     팝업 발견, 테이블에서 정확히 일치하는 요금제 검색")
                        print(f"     팝업 발견, 테이블에서 정확히 일치하는 요금제 검색")
                        
                        # 모든 tr 요소를 순회하면서 정확히 일치하는 것 찾기
                        all_trs = popup.locator('tr')
                        tr_count = await all_trs.count()
                        logger.info(f"     총 tr 요소: {tr_count}개")
                        print(f"     총 tr 요소: {tr_count}개")
                        
                        for i in range(tr_count):
                            try:
                                tr_elem = all_trs.nth(i)
                                
                                # td.name의 텍스트 확인
                                name_td = tr_elem.locator('td.name').first
                                name_text = await name_td.text_content(timeout=500)
                                
                                if not name_text:
                                    continue
                                
                                # 정확히 일치하는지 확인 (공백 정리)
                                name_text_clean = name_text.strip()
                                plan_name_clean_stripped = plan_name_clean.strip()
                                
                                logger.info(f"     🔍 [DEBUG] tr[{i}] name_text: '{name_text_clean}' vs 찾는 값: '{plan_name_clean_stripped}'")
                                print(f"     🔍 [DEBUG] tr[{i}] name_text: '{name_text_clean}' vs 찾는 값: '{plan_name_clean_stripped}'")
                                
                                # 정확히 일치하는지 확인
                                if name_text_clean == plan_name_clean_stripped:
                                    logger.info(f"     ✅ 정확히 일치하는 요금제 발견!")
                                    print(f"     ✅ 정확히 일치하는 요금제 발견!")
                                    
                                    # onclick 속성이 있으면 JavaScript로 실행
                                    onclick = await tr_elem.get_attribute('onclick')
                                    logger.info(f"     🔍 [DEBUG] onclick 속성 존재: {onclick is not None}")
                                    print(f"     🔍 [DEBUG] onclick 속성 존재: {onclick is not None}")
                                    
                                    if onclick:
                                        logger.info(f"     🔍 [DEBUG] onclick 전체 코드: {onclick}")
                                        print(f"     🔍 [DEBUG] onclick 전체 코드: {onclick}")
                                        
                                        # 방법 1: tr 요소를 직접 클릭 (onclick이 자동 실행됨) - 가장 간단하고 확실함
                                        try:
                                            logger.info(f"     🔍 [DEBUG] tr 요소 직접 클릭 시도 (onclick 자동 실행)")
                                            print(f"     🔍 [DEBUG] tr 요소 직접 클릭 시도 (onclick 자동 실행)")
                                            await tr_elem.click(force=True, timeout=2000)
                                            await asyncio.sleep(0.8)  # onclick 실행 및 팝업 닫기 대기
                                            
                                            logger.info(f"     ✅ 요금제 선택 성공 (tr 클릭): {name_text_clean}")
                                            print(f"     ✅ 요금제 선택 성공 (tr 클릭): {name_text_clean}")
                                            selected = True
                                            break
                                        except Exception as e:
                                            logger.warning(f"     ⚠️  tr 클릭 실패, onclick 코드 직접 실행 시도: {e}")
                                            print(f"     ⚠️  tr 클릭 실패, onclick 코드 직접 실행 시도: {e}")
                                            
                                            # 방법 2: onclick 코드를 직접 실행 (fallback)
                                            try:
                                                logger.info(f"     🔍 [DEBUG] onclick 코드 직접 실행")
                                                print(f"     🔍 [DEBUG] onclick 코드 직접 실행")
                                                await page.wait_for_function(
                                                    "typeof jQuery !== 'undefined' && typeof select_option === 'function'",
                                                    timeout=5000
                                                )
                                                result = await page.evaluate(f"""
                                                    (function() {{
                                                        try {{
                                                            {onclick}
                                                            return {{ success: true }};
                                                        }} catch (e) {{
                                                            return {{ success: false, error: e.toString() }};
                                                        }}
                                                    }})();
                                                """)
                                                await asyncio.sleep(0.5)
                                                
                                                if result.get('success'):
                                                    logger.info(f"     ✅ onclick 실행 완료")
                                                    print(f"     ✅ onclick 실행 완료")
                                                    selected = True
                                                    break
                                                else:
                                                    logger.warning(f"     ⚠️  onclick 실행 실패: {result.get('error')}")
                                                    print(f"     ⚠️  onclick 실행 실패: {result.get('error')}")
                                            except Exception as e2:
                                                logger.warning(f"     ⚠️  onclick 코드 실행 실패: {e2}")
                                                print(f"     ⚠️  onclick 코드 실행 실패: {e2}")
                                    else:
                                        logger.info(f"     🔍 [DEBUG] onclick 속성 없음, 직접 클릭 시도")
                                        print(f"     🔍 [DEBUG] onclick 속성 없음, 직접 클릭 시도")
                                        await tr_elem.click(force=True, timeout=2000)
                                        await asyncio.sleep(0.8)
                                        selected = True
                                        break
                                    
                                    if selected:
                                        break
                            except Exception as e:
                                logger.debug(f"     tr 요소 {i} 처리 실패: {e}")
                                continue
                        
                        if not selected:
                            logger.warning(f"     ⚠️  정확히 일치하는 요금제를 찾을 수 없음")
                            print(f"     ⚠️  정확히 일치하는 요금제를 찾을 수 없음")
                    else:
                        logger.warning(f"     ⚠️  팝업이 열려있지 않음!")
                        print(f"     ⚠️  팝업이 열려있지 않음!")
                except Exception as e:
                    logger.debug(f"     팝업 테이블 전략 실패: {e}")
                
                if selected:
                    await asyncio.sleep(0.5)
                    logger.info(f"     ✅ 요금제 선택 완료")
                    print(f"     ✅ 요금제 선택 완료")
                    return True
                else:
                    logger.warning(f"     ❌ 요금제 '{option_value}'를 찾을 수 없음")
                    print(f"     ❌ 요금제 '{option_value}'를 찾을 수 없음")
                    return False
            
            # 일반 옵션 클릭
            # 전략 1: 정확한 텍스트 매칭
            locator = page.get_by_text(option_value, exact=True)
            count = await locator.count()
            
            if count > 0:
                logger.info(f"     전략 1: 정확한 텍스트 매칭 ({count}개 발견)")
                # 클릭 가능한 요소 찾기
                for i in range(min(count, 3)):
                    elem = locator.nth(i)
                    tag = await elem.evaluate("el => el.tagName.toLowerCase()")
                    
                    if tag in ["button", "a", "label", "div", "li"]:
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
                
                try:
                    await elem.click(force=True, timeout=3000)
                    logger.info(f"     ✅ 클릭 성공")
                    return True
                except:
                    pass
            
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
        # 전체 화면 스크린샷 (저해상도로 최적화, 타임아웃 처리)
        try:
            screenshot_bytes = await page.screenshot(
                full_page=False,
                quality=50,  # JPEG 품질 50%
                type='jpeg',
                timeout=10000  # 10초 타임아웃
            )
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
            image_url = f"data:image/jpeg;base64,{screenshot_base64}"
            logger.debug(f"   📸 스크린샷: {len(screenshot_base64)} bytes (JPEG 50%)")
        except Exception as e:
            logger.warning(f"   ⚠️ 스크린샷 실패, HTML만 사용: {e}")
            # HTML 기반 추출로 fallback
            return await self._extract_pricing_from_html_only(page)
        
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
            
            logger.debug(f"   Vision API 응답 길이: {len(response)} chars")
            
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
            
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ JSON 파싱 실패: {e}")
            logger.error(f"   응답 내용: {response[:300]}")
            return {}
        except Exception as e:
            logger.error(f"   ❌ 가격 추출 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}
    
    async def _extract_pricing_from_html_only(self, page: Page) -> Dict[str, Any]:
        """HTML만 사용하여 가격 추출 (스크린샷 실패 시 fallback)"""
        try:
            pricing_html = await page.evaluate("""
                () => {
                    const dls = document.querySelectorAll('dl, div, table');
                    let html = '';
                    let count = 0;
                    
                    dls.forEach(elem => {
                        const text = elem.textContent;
                        if (text.includes('출고가') || text.includes('지원금') || 
                            text.includes('할부') || text.includes('요금') || text.includes('납부')) {
                            html += elem.outerHTML + '\\n';
                            count++;
                            if (count >= 15) return;
                        }
                    });
                    return html.substring(0, 8000);
                }
            """)
            
            prompt = f"""
HTML에서 가격 정보를 추출하세요:

{pricing_html}

출력 (JSON):
{{
  "retail_price": 1155000,
  "public_subsidy": -500000,
  "additional_subsidy": -190000,
  "installment_principal": 465000,
  "monthly_payment": 19375,
  "final_price": 129586,
  "plan_name": "프리미엄",
  "plan_monthly_fee": 109000
}}

HTML에서 실제 값을 추출하세요. JSON만 출력.
"""
            
            response = await self.llm.complete(
                prompt=prompt,
                system_message="HTML에서 가격 정보를 정확히 추출하세요.",
                response_format={"type": "json_object"}
            )
            
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"HTML 가격 추출 실패: {e}")
            return {}
    
    async def extract_model_name(self, page: Page) -> str:
        """
        페이지에서 기종명 추출
        
        Returns:
            "GALAXY_S25" 또는 "IPHONE_17" 형식
        """
        try:
            # 페이지 제목과 HTML 텍스트에서 기종명 추출
            title = await page.title()
            
            # 간단한 패턴 매칭
            text_to_check = title.upper()
            
            # 갤럭시 패턴
            if "S25" in text_to_check or "S 25" in text_to_check:
                return "GALAXY_S25"
            elif "S24" in text_to_check or "S 24" in text_to_check:
                return "GALAXY_S24"
            
            # 아이폰 패턴
            if "17" in text_to_check and ("IPHONE" in text_to_check or "아이폰" in title):
                return "IPHONE_17"
            elif "16" in text_to_check and ("IPHONE" in text_to_check or "아이폰" in title):
                return "IPHONE_16"
            
            # LLM으로 추출 시도
            logger.info("   🤖 LLM으로 기종명 추출 시도...")
            
            html_snippet = await page.evaluate("""
                () => {
                    const h1 = document.querySelector('h1, .product-title, .model-name');
                    return h1 ? h1.textContent : document.title;
                }
            """)
            
            prompt = f"""
다음 텍스트에서 휴대폰 기종명을 추출하세요:

{title}
{html_snippet}

추출 규칙:
- 갤럭시 S25 → "GALAXY_S25"
- 아이폰 17 → "IPHONE_17"
- 갤럭시 S24 → "GALAXY_S24"
- 아이폰 16 → "IPHONE_16"

형식: "GALAXY_S25" 또는 "IPHONE_17"만 출력하세요.
"""
            
            response = await self.llm.complete(
                prompt=prompt,
                system_message="기종명을 정확히 추출하세요.",
                max_tokens=20
            )
            
            model_name = response.strip().replace('"', '').replace("'", "")
            
            if "GALAXY" in model_name or "IPHONE" in model_name:
                return model_name
            
        except Exception as e:
            logger.debug(f"기종명 추출 실패: {e}")
        
        return "UNKNOWN_MODEL"
    
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
        
        # Step 0: 기종명 사용 (이미 초기화 시 설정됨)
        logger.info("[Step 0] 기종명 확인")
        sku_code = self.model_name  # 이미 __init__에서 설정된 값 사용
        logger.info(f"   📱 기종명: {sku_code}\n")
        
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
        print(f"\n[Step 3] 요금제 필터링")
        print(f"   기종: {self.model_name}")
        print(f"   추출된 요금제: {len(self.available_plans)}개")
        
        for plan in self.available_plans[:8]:
            print(f"      - {plan['name']} ({plan['monthly_fee']:,}원/월)")
        
        filtered_plans = self._filter_plans_by_model(available_options)
        
        print(f"\n   ✂️ 필터링 후: {len(filtered_plans)}개")
        logger.info(f"   📋 조건에 맞는 요금제: {len(filtered_plans)}개")
        
        for plan_info in filtered_plans[:8]:
            print(f"      ✅ {plan_info['name']} ({plan_info['monthly_fee']:,}원/월)")
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
        
        # 각 기본 조합에 대해 조건에 맞는 요금제만 추가
        for base_combo_values in itertools_product(*base_values):
            base_combo = dict(zip(base_keys, base_combo_values))
            
            # 이 조합의 통신사와 가입유형
            carrier = base_combo.get("carrier", "")
            join_type = base_combo.get("join_type", "")
            
            # 알뜰폰은 제외
            if "알뜰" in carrier:
                logger.debug(f"   ⏭️  알뜰폰 조합 건너뛰기: {carrier}")
                continue
            
            # 조건에 맞는 요금제만 찾기 (엄격)
            matching_plans = []
            for plan in filtered_plans:
                if self._is_plan_valid_for_combo(plan, carrier, join_type):
                    matching_plans.append(plan)
                    logger.debug(f"   ✅ 매칭: {carrier}/{join_type} - {plan['name']} ({plan['monthly_fee']:,}원)")
            
            if matching_plans:
                # 조건에 맞는 요금제만 조합 생성 (최대 3개)
                for plan_info in matching_plans[:3]:
                    combo = base_combo.copy()
                    combo["plan"] = plan_info["name"]
                    combo["plan_fee"] = plan_info["monthly_fee"]  # 디버깅용
                    combinations.append(combo)
                    logger.debug(f"   📌 조합 추가 (요금제 필터): {combo}")
            else:
                # 조건에 맞는 요금제가 없으면 조합 스킵
                logger.warning(f"   ⚠️  {carrier}/{join_type} - 조건 맞는 요금제 없음, 조합 스킵")
                logger.debug(f"   ⏭️  조합 건너뛰기: {base_combo}")
                continue
            
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
            # plan이 없는 조합은 스킵
            if "plan" not in combo or not combo.get("plan"):
                logger.warning(f"   ⚠️  [{idx}/{len(combinations)}] plan이 없는 조합 스킵: {combo}")
                print(f"   ⚠️  [{idx}/{len(combinations)}] plan이 없는 조합 스킵")
                continue
            
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
                
                # 가격 데이터 검증 (완화)
                if pricing:
                    # retail_price가 없어도 다른 필드가 있으면 수집
                    has_data = any([
                        pricing.get('retail_price'),
                        pricing.get('installment_principal'),
                        pricing.get('final_price'),
                        pricing.get('plan_name')
                    ])
                    
                    if has_data:
                        collected_data.append({
                            "combo": combo,
                            "pricing": pricing
                        })
                        combo_total = time.time() - combo_start
                        print(f"   ✅ 정책 수집 완료 (총 {combo_total:.2f}초)")
                        logger.info(f"   ✅ 정책 수집 완료")
                    else:
                        print(f"   ⚠️  가격 데이터 없음")
                        print(f"      추출된 데이터: {pricing}")
                        logger.warning(f"   ⚠️  가격 데이터 없음: {pricing}")
                else:
                    print(f"   ❌ 가격 추출 완전 실패 (null)")
                    logger.error(f"   ❌ 가격 추출 실패: pricing is None")
                
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
        result = self._convert_to_schema(collected_data, url, site_name, sku_code)
        
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
        요금제가 특정 조합에 유효한지 확인 (월요금 우선, 이름은 유연하게)
        
        매칭 전략:
        1. 월요금이 조건에 맞는지 확인 (필수)
        2. 요금제 이름은 핵심 키워드만 확인 (유연)
           - "5GX 레귤러플러스" ↔ "레귤러플러스" ✅
           - "5G 프리미어 에센셜" ↔ "프리미어" ✅
        
        Args:
            plan_info: 요금제 정보 {"name": "레귤러플러스", "monthly_fee": 79000}
            carrier: 통신사 (SKT, KT, LGU)
            join_type: 가입유형 (번호이동, 기기변경)
            
        Returns:
            유효 여부
        """
        if self.model_name not in self.PLAN_FILTERS:
            return True
        
        model_filters = self.PLAN_FILTERS[self.model_name]
        
        # 통신사 정규화
        carrier_normalized = carrier.upper()
        if "LG" in carrier_normalized or "LGU" in carrier_normalized:
            carrier_normalized = "LGU"
        if "알뜰" in carrier:
            return False  # 알뜰폰 제외
        
        if carrier_normalized not in model_filters:
            return False
        
        carrier_filters = model_filters[carrier_normalized]
        
        # 가입유형 정규화
        join_normalized = "번호이동" if "번호이동" in join_type else "기기변경"
        
        if join_normalized not in carrier_filters:
            return False
        
        # 허용된 요금제 리스트
        allowed_plans = carrier_filters[join_normalized]
        
        plan_name = plan_info.get("name", "")
        plan_fee = plan_info.get("monthly_fee", 0)
        
        # 이름 정규화 (공백, 숫자, 특수문자, 5G/5GX 접두어 제거)
        plan_name_clean = (plan_name
                          .replace("5GX", "").replace("5G", "")
                          .replace("LTE", "").replace(" ", "")
                          .replace("+", "").replace("플러스", "플러스")
                          .upper())
        
        # 월요금 기준 필터링
        for allowed in allowed_plans:
            allowed_fee = allowed["fee"]
            
            # 1차: 월요금 일치 확인 (필수)
            if plan_fee != allowed_fee:
                continue
            
            # 2차: 이름 유연 매칭 (선택)
            allowed_name = allowed["name"]
            allowed_name_clean = (allowed_name
                                 .replace("5GX", "").replace("5G", "")
                                 .replace("LTE", "").replace(" ", "")
                                 .replace("+", "")
                                 .upper())
            
            # 유연한 매칭:
            # - "레귤러플러스" ↔ "레귤러플러스" ✅
            # - "레귤러플러스" ↔ "레규러플러스" ✅ (오타)
            # - "프라임" ↔ "프라임플러스" ✅
            # - "레귤러" ↔ "레귤러플러스" ✅
            
            # 핵심 키워드만 추출 (플러스 제거)
            plan_core = plan_name_clean.replace("플러스", "").replace("PLUS", "")
            allowed_core = allowed_name_clean.replace("플러스", "").replace("PLUS", "")
            
            # 매칭 조건 (여러 전략)
            if (allowed_name_clean == plan_name_clean or          # 완전 일치
                allowed_name_clean in plan_name_clean or          # 부분 일치 1
                plan_name_clean in allowed_name_clean or          # 부분 일치 2
                allowed_core in plan_core or                      # 핵심 키워드 1
                plan_core in allowed_core or                      # 핵심 키워드 2
                (len(allowed_core) >= 2 and allowed_core in plan_name_clean) or  # 짧은 키워드
                (len(plan_core) >= 2 and plan_core in allowed_name_clean)):      # 짧은 키워드 역방향
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
        site_name: str,
        sku_code: str = "UNKNOWN_MODEL"
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
                
                # plan_name이 None이거나 빈 문자열이면 기본값 사용
                plan_name = pricing.get("plan_name")
                if not plan_name or plan_name is None:
                    plan_name = "알 수 없음"
                
                policy = Policy(
                    policy_id=policy_id,
                    carrier=carrier,
                    mno_join_type=join_type,
                    mobile_plan=MobilePlan(
                        name=plan_name,
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
            product_id = hashlib.md5(f"{site_name}_{sku_code}_{storage}".encode()).hexdigest()[:16]
            
            product = Product(
                product_id=product_id,
                sku_code=sku_code,  # 추출된 기종명 사용
                sku_storage=parse_storage(storage),
                policies=policies
            )
            
            products.append(product)
        
        return ScrapingResult(
            captured_at=datetime.datetime.now(),
            source=SourceInfo(site=site_name, url=url),
            products=products
        )

