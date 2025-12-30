"""
Phase 3B: 화면 기반 정책 추출
HTML에서 직접 가격 정보를 추출
"""
import json
import asyncio
import hashlib
import datetime
from itertools import product
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

from ..core.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.prompts import (
    SCREEN_PAGE_STRUCTURE_SYSTEM,
    format_screen_page_structure_prompt,
    SCREEN_EXTRACT_PRICING_SYSTEM,
    format_screen_extract_pricing_prompt
)
from ..models.phase3_schemas import (
    ScrapingResult,
    Product,
    Policy,
    MobilePlan,
    PricingDetails,
    SourceInfo,
    StorageType,
    JoinType,
    DiscountType,
    parse_storage
)

logger = get_logger()


class ScreenExtractor:
    """
    화면 기반 정책 추출기
    
    LLM을 사용하여:
    1. 페이지 구조 분석 (옵션 UI, 가격 영역 식별)
    2. 가격 정보 추출
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        logger.info("🖥️ ScreenExtractor 초기화")
    
    async def analyze_page_structure(self, page: Page) -> Dict[str, Any]:
        """
        페이지 구조 분석: 옵션 UI와 가격 영역 식별
        
        Args:
            page: Playwright Page 객체
            
        Returns:
            구조 정보 dict
        """
        logger.info("="*70)
        logger.info("📊 페이지 구조 분석 시작")
        logger.info("="*70)
        
        # HTML 가져오기
        html = await page.content()
        logger.info(f"HTML 크기: {len(html):,} bytes")
        
        # LLM으로 분석
        prompt = format_screen_page_structure_prompt(html)
        
        try:
            logger.info("🤖 LLM 분석 중...")
            
            response = await self.llm.complete(
                prompt=prompt,
                system_message=SCREEN_PAGE_STRUCTURE_SYSTEM,
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            structure = json.loads(response)
            
            logger.info("✅ 구조 분석 완료")
            logger.info(f"   옵션: {list(structure.get('options', {}).keys())}")
            logger.info(f"   가격: {len(structure.get('pricing', {}))}개 필드")
            
            return structure
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return {"options": {}, "pricing": {}}
        except Exception as e:
            logger.error(f"구조 분석 실패: {e}")
            return {"options": {}, "pricing": {}}
    
    async def extract_pricing(self, page: Page, use_vision: bool = True) -> Dict[str, Any]:
        """
        현재 화면에서 가격 정보 추출
        
        Args:
            page: Playwright Page 객체
            use_vision: Vision API 사용 여부 (스크린샷 + HTML 분석)
            
        Returns:
            가격 정보 dict
        """
        logger.info("💰 가격 정보 추출 중...")
        
        if use_vision:
            # Vision API 사용 (스크린샷 + HTML)
            return await self._extract_pricing_with_vision(page)
        else:
            # HTML만 사용
            return await self._extract_pricing_from_html(page)
    
    async def _extract_pricing_from_html(self, page: Page) -> Dict[str, Any]:
        """HTML만 사용하여 가격 추출"""
        html = await page.content()
        
        prompt = format_screen_extract_pricing_prompt(html)
        
        try:
            response = await self.llm.complete(
                prompt=prompt,
                system_message=SCREEN_EXTRACT_PRICING_SYSTEM,
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            pricing = json.loads(response)
            
            logger.info("✅ 가격 추출 완료 (HTML)")
            self._log_pricing(pricing)
            
            return pricing
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return {}
        except Exception as e:
            logger.error(f"가격 추출 실패: {e}")
            return {}
    
    async def _extract_pricing_with_vision(self, page: Page) -> Dict[str, Any]:
        """스크린샷과 HTML을 함께 사용하여 가격 추출"""
        import base64
        
        # 스크린샷 캡처
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
        
        # 가격 영역 HTML 추출 (전체 HTML은 너무 큼)
        # JavaScript로 현재 표시된 가격 영역만 추출
        pricing_html = await page.evaluate("""
            () => {
                // 가격 표시 영역 찾기
                const priceBox = document.querySelector('.mobile-price-box, .calc-bill-box, .price-area, .price-info');
                if (priceBox) {
                    return priceBox.outerHTML;
                }
                
                // 전체 body에서 가격 관련 dl 태그들만 추출
                const dls = document.querySelectorAll('dl');
                let html = '';
                dls.forEach(dl => {
                    const text = dl.textContent;
                    if (text.includes('출고가') || text.includes('지원금') || text.includes('할부') || 
                        text.includes('요금') || text.includes('납부')) {
                        html += dl.outerHTML + '\\n';
                    }
                });
                return html;
            }
        """)
        
        logger.info(f"   가격 HTML 추출: {len(pricing_html)} bytes")
        
        # Vision API 프롬프트
        prompt = f"""
이미지와 HTML을 함께 분석하여 휴대폰 가격 정보를 추출하세요.

# 이미지 분석
스크린샷에서 다음 정보를 시각적으로 확인하세요:
- 출고가
- 공시지원금 또는 추가 지원금
- 할부원금
- 월 통신요금  
- 월 납부금액 (A+B)
- 요금제 이름 및 월요금

# HTML 데이터
{pricing_html}

# 추출 방법
1. 이미지에서 각 가격의 위치와 금액을 확인
2. HTML에서 해당 금액을 찾기
3. 정확한 숫자 추출

# 출력 (JSON)
{{
  "retail_price": <이미지와 HTML에서 확인한 실제 출고가>,
  "public_subsidy": <공시지원금 (없으면 null)>,
  "additional_subsidy": <추가 지원금 (마이너스 가능, 없으면 null)>,
  "installment_principal": <할부원금>,
  "monthly_payment": <월 할부금>,
  "final_price": <월 납부금액 (A+B 합계)>,
  "plan_name": "<요금제 이름>",
  "plan_monthly_fee": <요금제 월요금>
}}

**이미지에서 본 정확한 숫자를 반환하세요. 콤마 제거, 정수로 변환. JSON만 출력.**
"""
        
        try:
            image_url = f"data:image/png;base64,{screenshot_base64}"
            
            logger.info("   Vision API 호출 중...")
            response = await self.llm.complete_with_vision(
                prompt=prompt,
                image_url=image_url,
                system_message=SCREEN_EXTRACT_PRICING_SYSTEM
            )
            
            logger.info(f"   Vision API 응답 받음: {len(response)} chars")
            logger.debug(f"   응답 내용: {response[:200]}...")
            
            # JSON 추출
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            pricing = json.loads(response)
            
            logger.info("✅ 가격 추출 완료 (Vision)")
            self._log_pricing(pricing)
            
            return pricing
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"응답 내용: {response[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Vision 가격 추출 실패: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to HTML only
            logger.warning("Fallback: HTML만 사용하여 재시도...")
            return await self._extract_pricing_from_html(page)
    
    def _log_pricing(self, pricing: Dict[str, Any]):
        """가격 정보 로깅"""
        if pricing.get('retail_price'):
            logger.info(f"   출고가: {pricing['retail_price']:,}원")
        if pricing.get('public_subsidy'):
            logger.info(f"   공시지원금: {pricing['public_subsidy']:,}원")
        if pricing.get('additional_subsidy'):
            logger.info(f"   추가지원금: {pricing['additional_subsidy']:,}원")
        if pricing.get('installment_principal'):
            logger.info(f"   할부원금: {pricing['installment_principal']:,}원")
        if pricing.get('monthly_payment'):
            logger.info(f"   월 할부금: {pricing['monthly_payment']:,}원")
        if pricing.get('final_price'):
            logger.info(f"   최종가: {pricing['final_price']:,}원")
        if pricing.get('plan_name'):
            logger.info(f"   요금제: {pricing['plan_name']} ({pricing.get('plan_monthly_fee', 0):,}원/월)")
    
    async def select_option(
        self,
        page: Page,
        option_type: str,
        option_value: str,
        structure: Dict[str, Any]
    ) -> bool:
        """
        특정 옵션 선택
        
        Args:
            page: Playwright Page 객체
            option_type: 옵션 타입 (예: "storage", "carrier")
            option_value: 선택할 값 (예: "256GB", "SKT")
            structure: 페이지 구조 정보
            
        Returns:
            성공 여부
        """
        option_info = structure.get("options", {}).get(option_type)
        if not option_info:
            logger.warning(f"옵션 정보 없음: {option_type}")
            return False
        
        selector = option_info.get("selector")
        option_ui_type = option_info.get("type")
        
        logger.info(f"  [{option_type}] {option_value} 선택 중... (type: {option_ui_type})")
        
        try:
            if option_ui_type == "select":
                # Select 드롭다운
                await page.select_option(selector, label=option_value)
                
            elif option_ui_type == "radio":
                # Radio 버튼
                # value 또는 label로 찾기
                radio = page.locator(f"{selector}[value='{option_value}']").first
                if await radio.count() == 0:
                    # label로 찾기
                    radio = page.locator(f"{selector}").filter(has_text=option_value).first
                await radio.check()
                
            elif option_ui_type in ["button", "tab"]:
                # 버튼 또는 탭
                button = page.locator(selector).filter(has_text=option_value).first
                if await button.count() > 0:
                    await button.click()
                else:
                    logger.warning(f"버튼을 찾을 수 없음: {option_value}")
                    return False
                
            elif option_ui_type == "swatch":
                # 색상 스와치
                swatch = page.locator(selector).filter(has_text=option_value).first
                if await swatch.count() > 0:
                    await swatch.click()
                else:
                    logger.warning(f"스와치를 찾을 수 없음: {option_value}")
                    return False
            
            # 화면 업데이트 대기
            await asyncio.sleep(1)
            logger.info(f"  ✅ {option_type} 선택 완료")
            return True
            
        except Exception as e:
            logger.error(f"옵션 선택 실패: {option_type}={option_value}, 오류: {e}")
            return False
    
    async def get_available_options(
        self,
        page: Page,
        structure: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        현재 페이지에서 선택 가능한 옵션 목록 추출
        
        Args:
            page: Playwright Page 객체
            structure: 페이지 구조 정보
            
        Returns:
            옵션 타입별 값 목록
        """
        logger.info("📋 선택 가능한 옵션 추출 중...")
        
        available = {}
        options_info = structure.get("options", {})
        
        for option_type, option_info in options_info.items():
            selector = option_info.get("selector")
            ui_type = option_info.get("type")
            
            try:
                if ui_type == "select":
                    # Select 옵션
                    options = await page.locator(f"{selector} option").all_text_contents()
                    # 빈 값 제거
                    options = [opt.strip() for opt in options if opt.strip()]
                    
                elif ui_type == "radio":
                    # Radio 옵션 (라벨 텍스트 추출)
                    radios = await page.locator(selector).all()
                    options = []
                    for radio in radios:
                        # value 또는 인접한 label 텍스트 추출
                        text = await radio.get_attribute("value")
                        if not text:
                            # 라벨 찾기
                            label = page.locator(f"label[for='{await radio.get_attribute('id')}']")
                            if await label.count() > 0:
                                text = await label.text_content()
                        if text:
                            options.append(text.strip())
                    
                elif ui_type in ["button", "tab", "swatch"]:
                    # 버튼/탭/스와치
                    elements = await page.locator(selector).all()
                    options = []
                    for elem in elements:
                        text = await elem.text_content()
                        if text:
                            options.append(text.strip())
                
                if options:
                    available[option_type] = options
                    logger.info(f"  {option_type}: {options}")
                    
            except Exception as e:
                logger.warning(f"옵션 추출 실패: {option_type}, 오류: {e}")
        
        return available
    
    async def extract_with_options(
        self,
        page: Page,
        options: Dict[str, str],
        structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        특정 옵션 조합에 대한 가격 추출
        
        Args:
            page: Playwright Page 객체
            options: 옵션 조합 (예: {"storage": "256GB", "carrier": "SKT"})
            structure: 페이지 구조 정보
            
        Returns:
            가격 정보 dict (옵션 정보 포함)
        """
        logger.info(f"\n🎯 옵션 조합: {options}")
        
        # 각 옵션 선택
        for option_type, option_value in options.items():
            success = await self.select_option(page, option_type, option_value, structure)
            if not success:
                logger.warning(f"옵션 선택 실패: {option_type}={option_value}")
        
        # 화면 업데이트 대기
        await asyncio.sleep(2)
        
        # 가격 추출
        pricing = await self.extract_pricing(page)
        
        # 옵션 정보 추가
        result = {
            "options": options,
            "pricing": pricing
        }
        
        return result
    
    def generate_option_combinations(
        self,
        available_options: Dict[str, List[str]],
        max_combinations: int = 50
    ) -> List[Dict[str, str]]:
        """
        모든 옵션 조합 생성 (가지치기 포함)
        
        Args:
            available_options: 옵션 타입별 값 목록
            max_combinations: 최대 조합 수
            
        Returns:
            옵션 조합 리스트
        """
        logger.info(f"\n📊 옵션 조합 생성 중...")
        logger.info(f"   입력: {available_options}")
        logger.info(f"   최대 조합 수: {max_combinations}")
        
        # 가지치기 전략 적용
        pruned_options = {}
        
        for option_type, values in available_options.items():
            if option_type == "storage":
                # 용량: 모두 테스트
                pruned_options[option_type] = values
            elif option_type == "color":
                # 색상: 첫 번째만 (가격 동일)
                pruned_options[option_type] = [values[0]] if values else []
            elif option_type == "carrier":
                # 통신사: 모두 테스트
                pruned_options[option_type] = values
            elif option_type == "join_type":
                # 가입유형: 모두 테스트
                pruned_options[option_type] = values
            elif option_type == "plan":
                # 요금제: 상위 3개만
                pruned_options[option_type] = values[:3] if len(values) > 3 else values
            elif option_type == "installment":
                # 할부: 24개월만
                if "24" in str(values):
                    pruned_options[option_type] = ["24개월"]
                else:
                    pruned_options[option_type] = [values[0]] if values else []
        
        logger.info(f"   가지치기 후: {pruned_options}")
        
        # 조합 생성
        if not pruned_options:
            return []
        
        keys = list(pruned_options.keys())
        values = [pruned_options[k] for k in keys]
        
        combinations = []
        for combo_values in product(*values):
            combo = dict(zip(keys, combo_values))
            combinations.append(combo)
            
            if len(combinations) >= max_combinations:
                logger.warning(f"⚠️  최대 조합 수 도달: {max_combinations}")
                break
        
        logger.info(f"✅ 총 {len(combinations)}개 조합 생성됨")
        return combinations
    
    async def collect_all_policies(
        self,
        page: Page,
        url: str,
        site_name: str = "Unknown",
        max_combinations: int = 50
    ) -> ScrapingResult:
        """
        모든 옵션 조합에 대한 정책 수집 및 Phase3 스키마로 변환
        
        Args:
            page: Playwright Page 객체
            url: 페이지 URL
            site_name: 사이트 이름
            max_combinations: 최대 조합 수
            
        Returns:
            ScrapingResult (Phase 3 스키마)
        """
        logger.info("="*70)
        logger.info("🚀 전체 정책 수집 시작")
        logger.info("="*70)
        logger.info(f"URL: {url}")
        logger.info(f"사이트: {site_name}")
        logger.info("="*70 + "\n")
        
        # 1. 페이지 구조 분석
        structure = await self.analyze_page_structure(page)
        
        # 2. 선택 가능한 옵션 추출
        available_options = await self.get_available_options(page, structure)
        
        if not available_options:
            logger.warning("⚠️  선택 가능한 옵션이 없습니다")
            return ScrapingResult(
                source=SourceInfo(site=site_name, url=url),
                products=[]
            )
        
        # 3. 옵션 조합 생성
        combinations = self.generate_option_combinations(available_options, max_combinations)
        
        if not combinations:
            logger.warning("⚠️  생성된 조합이 없습니다")
            return ScrapingResult(
                source=SourceInfo(site=site_name, url=url),
                products=[]
            )
        
        # 4. 각 조합별 정책 수집
        logger.info(f"\n🔄 {len(combinations)}개 조합 처리 시작...")
        logger.info("="*70)
        
        collected_data = []
        
        for idx, combo in enumerate(combinations, 1):
            logger.info(f"\n[{idx}/{len(combinations)}] 조합 처리 중")
            
            try:
                result = await self.extract_with_options(page, combo, structure)
                collected_data.append(result)
                
            except Exception as e:
                logger.error(f"조합 처리 실패: {combo}, 오류: {e}")
                continue
        
        logger.info("\n" + "="*70)
        logger.info(f"✅ 정책 수집 완료: {len(collected_data)}개")
        logger.info("="*70 + "\n")
        
        # 5. Phase 3 스키마로 변환
        scraping_result = self._convert_to_phase3_schema(
            collected_data,
            url,
            site_name
        )
        
        return scraping_result
    
    def _convert_to_phase3_schema(
        self,
        collected_data: List[Dict[str, Any]],
        url: str,
        site_name: str
    ) -> ScrapingResult:
        """
        수집된 데이터를 Phase 3 스키마로 변환
        
        Args:
            collected_data: 수집된 데이터 리스트
            url: 페이지 URL
            site_name: 사이트 이름
            
        Returns:
            ScrapingResult
        """
        logger.info("🔄 Phase 3 스키마로 변환 중...")
        
        # 제품별로 그룹화 (storage 기준)
        products_by_storage: Dict[str, List[Dict[str, Any]]] = {}
        
        for data in collected_data:
            options = data.get("options", {})
            storage = options.get("storage", "Unknown")
            
            if storage not in products_by_storage:
                products_by_storage[storage] = []
            products_by_storage[storage].append(data)
        
        # Product 생성
        products = []
        
        for storage, policies_data in products_by_storage.items():
            # Policy 생성
            policies = []
            
            for data in policies_data:
                options = data.get("options", {})
                pricing_data = data.get("pricing", {})
                
                # Policy ID 생성 (옵션 조합 해시)
                policy_id = self._generate_hash(str(options))
                
                # 가입 유형 파싱
                join_type_str = options.get("join_type", "기기변경")
                try:
                    if "번호이동" in join_type_str:
                        join_type = JoinType.NUMBER_TRANSFER
                    elif "신규가입" in join_type_str:
                        join_type = JoinType.NEW_SUBSCRIPTION
                    else:
                        join_type = JoinType.DEVICE_CHANGE
                except:
                    join_type = JoinType.DEVICE_CHANGE
                
                # 할인 타입 파싱 (기본값: 공시지원금)
                discount_type = DiscountType.PUBLIC_SUBSIDY
                
                # Policy 생성
                policy = Policy(
                    policy_id=policy_id,
                    carrier=options.get("carrier", "Unknown"),
                    mno_join_type=join_type,
                    mobile_plan=MobilePlan(
                        name=pricing_data.get("plan_name", "알 수 없음"),
                        monthly_fee=pricing_data.get("plan_monthly_fee", 0) or 0
                    ),
                    discount_type=discount_type,
                    pricing=PricingDetails(
                        mno_retail_price=pricing_data.get("retail_price"),
                        public_subsidy=pricing_data.get("public_subsidy"),
                        discount=pricing_data.get("additional_subsidy"),
                        sku_installment_fee=pricing_data.get("installment_principal"),
                        monthly_payment=pricing_data.get("monthly_payment")
                    ),
                    addons=[]  # TODO: 부가서비스 추출
                )
                
                policies.append(policy)
            
            # Product ID 생성
            product_id = self._generate_hash(f"{site_name}_{storage}")
            
            # Product 생성
            product = Product(
                product_id=product_id,
                sku_code=f"Unknown Model",  # TODO: 모델명 추출
                sku_storage=parse_storage(storage),
                policies=policies
            )
            
            products.append(product)
        
        # ScrapingResult 생성
        result = ScrapingResult(
            captured_at=datetime.datetime.now(),
            source=SourceInfo(site=site_name, url=url),
            products=products
        )
        
        logger.info(f"✅ 변환 완료: {len(products)}개 제품, 총 {sum(len(p.policies) for p in products)}개 정책")
        
        return result
    
    def _generate_hash(self, text: str) -> str:
        """문자열 해시 생성"""
        return hashlib.md5(text.encode()).hexdigest()[:16]

