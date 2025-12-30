"""
API Monitor: 네트워크 요청/응답 모니터링
Playwright로 모든 API 호출을 캡처하고 분석
"""
import time
import json
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, Response

from ..utils.logger import get_logger
from ..core.llm_client import LLMClient

logger = get_logger()


class APIMonitor:
    """
    API 호출 모니터링 및 응답 캡처
    
    Phase 3A에서 사용: API 기반 정책 추출
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.api_calls: List[Dict[str, Any]] = []
        self.is_monitoring = False
        self.llm_client = llm_client
        logger.info("📡 APIMonitor 초기화")
    
    def start_monitoring(self, page: Page):
        """
        네트워크 모니터링 시작
        
        Args:
            page: Playwright Page 객체
        """
        if self.is_monitoring:
            logger.warning("⚠️  이미 모니터링 중입니다")
            return
        
        logger.info("="*70)
        logger.info("📡 API 모니터링 시작")
        logger.info("="*70)
        
        async def handle_response(response: Response):
            """응답 핸들러"""
            url = response.url
            method = response.request.method
            status = response.status
            
            # 리소스 파일 제외
            if not self._is_potential_api(url):
                return
            
            # 응답 타입 확인
            content_type = response.headers.get('content-type', '')
            
            try:
                # JSON 응답만 저장
                if 'application/json' in content_type:
                    data = await response.json()
                    
                    api_call = {
                        'url': url,
                        'method': method,
                        'status': status,
                        'content_type': content_type,
                        'data': data,
                        'timestamp': time.time()
                    }
                    
                    self.api_calls.append(api_call)
                    
                    logger.info(f"📡 캡처: {method} {status} {url[:80]}")
                    
            except Exception as e:
                logger.debug(f"응답 파싱 실패: {url[:60]} - {str(e)}")
        
        page.on("response", handle_response)
        self.is_monitoring = True
        logger.info("✅ 모니터링 활성화\n")
    
    def _is_potential_api(self, url: str) -> bool:
        """
        잠재적 API 요청인지 판단
        
        Args:
            url: 요청 URL
            
        Returns:
            bool: API일 가능성이 있으면 True
        """
        url_lower = url.lower()
        
        # 제외할 패턴
        exclude = [
            '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
            '.woff', '.woff2', '.ttf', '.ico',
            'google-analytics', 'gtag', 'facebook'
        ]
        
        return not any(pattern in url_lower for pattern in exclude)
    
    def get_captured_apis(self, within_seconds: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        캡처된 API 호출 목록 반환
        
        Args:
            within_seconds: 최근 N초 이내의 API만 반환
            
        Returns:
            API 호출 정보 리스트
        """
        if within_seconds is None:
            return self.api_calls
        
        now = time.time()
        return [
            api for api in self.api_calls
            if now - api['timestamp'] <= within_seconds
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """API 호출 통계"""
        return {
            'total_calls': len(self.api_calls),
            'unique_urls': len(set(api['url'] for api in self.api_calls)),
            'methods': {
                'GET': sum(1 for api in self.api_calls if api['method'] == 'GET'),
                'POST': sum(1 for api in self.api_calls if api['method'] == 'POST'),
            }
        }
    
    def print_summary(self):
        """API 호출 요약 출력"""
        stats = self.get_stats()
        
        logger.info("="*70)
        logger.info("📊 API 모니터링 요약")
        logger.info("="*70)
        logger.info(f"총 API 호출: {stats['total_calls']}개")
        logger.info(f"고유 URL: {stats['unique_urls']}개")
        logger.info(f"GET: {stats['methods']['GET']}개, POST: {stats['methods']['POST']}개")
        
        if self.api_calls:
            logger.info(f"\n최근 API (최대 5개):")
            for api in self.api_calls[-5:]:
                logger.info(f"  • {api['method']} {api['url'][:70]}")
        else:
            logger.warning("\n⚠️  캡처된 API 없음")
        
        logger.info("="*70 + "\n")
    
    async def analyze_api_with_llm(self, api_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM을 사용하여 API 응답이 정책 관련 정보를 포함하는지 분석
        
        Args:
            api_call: API 호출 정보
            
        Returns:
            분석 결과 dict
        """
        if not self.llm_client:
            logger.warning("LLM Client가 설정되지 않았습니다")
            return {
                "is_relevant": False,
                "contains": [],
                "confidence": 0.0,
                "reason": "LLM Client 없음"
            }
        
        # API 응답 데이터 준비
        url = api_call['url']
        data = api_call['data']
        data_str = json.dumps(data, ensure_ascii=False, indent=2)[:3000]  # 최대 3000자
        
        # LLM 프롬프트
        prompt = f"""
다음 API 응답을 분석하여, 이것이 휴대폰 가격/정책 정보를 포함하는지 판단하세요.

# API URL
{url}

# API 응답 데이터 (JSON)
{data_str}

# 질문
이 API 응답에 다음 정보 중 하나라도 포함되어 있나요?
- 휴대폰 가격 (출고가, 할인가, 최종가)
- 지원금 (공시지원금, 추가지원금)
- 요금제 정보 (이름, 월 요금)
- 할부 정보 (할부원금, 월 할부금)
- 옵션 정보 (용량, 색상, 통신사, 가입유형)
- 부가서비스/보험 정보

# 응답 형식 (JSON)
{{
  "is_relevant": true,  // 또는 false
  "contains": ["가격", "공시지원금", "요금제"],  // 포함된 정보 타입
  "confidence": 0.95,  // 확신도 (0.0 ~ 1.0)
  "reason": "이 API는 휴대폰의 출고가, 공시지원금 및 선택된 요금제에 따른 월 할부금을 포함하고 있습니다."
}}

**JSON만 출력하세요. 설명 없이.**
"""
        
        system_message = "당신은 API 응답 분석 전문가입니다. 주어진 API 응답에서 휴대폰 정책 관련 정보를 정확히 식별하고 판단합니다."
        
        try:
            logger.info(f"🤖 LLM 분석 중: {url[:60]}...")
            
            response_text = await self.llm_client.complete(
                prompt=prompt,
                system_message=system_message,
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            result = json.loads(response_text)
            logger.info(f"✅ 분석 완료: relevant={result.get('is_relevant')}, confidence={result.get('confidence'):.2f}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return {
                "is_relevant": False,
                "contains": [],
                "confidence": 0.0,
                "reason": f"JSON 파싱 실패: {e}"
            }
        except Exception as e:
            logger.error(f"LLM 분석 중 오류: {e}")
            return {
                "is_relevant": False,
                "contains": [],
                "confidence": 0.0,
                "reason": f"LLM 오류: {e}"
            }
    
    async def find_relevant_apis_with_llm(self) -> List[Dict[str, Any]]:
        """
        LLM을 사용하여 정책 관련 API 식별
        
        Returns:
            관련 API 목록 (분석 결과 포함)
        """
        if not self.api_calls:
            logger.info("분석할 API 없음")
            return []
        
        if not self.llm_client:
            logger.warning("LLM Client가 설정되지 않음. LLM 분석 건너뜀")
            return []
        
        logger.info(f"\n🤖 LLM으로 {len(self.api_calls)}개 API 분석 시작...")
        logger.info("="*70)
        
        relevant_apis = []
        
        for idx, api_call in enumerate(self.api_calls, 1):
            logger.info(f"\n[{idx}/{len(self.api_calls)}] 분석 중: {api_call['url'][:70]}")
            
            analysis = await self.analyze_api_with_llm(api_call)
            
            if analysis.get("is_relevant", False):
                # 분석 결과를 API 정보에 추가
                api_call['llm_analysis'] = analysis
                relevant_apis.append(api_call)
                
                logger.info(f"✅ 정책 관련 API 발견!")
                logger.info(f"   포함 정보: {', '.join(analysis.get('contains', []))}")
                logger.info(f"   확신도: {analysis.get('confidence'):.2f}")
                logger.info(f"   이유: {analysis.get('reason', 'N/A')}")
            else:
                logger.debug(f"❌ 관련 없음: {analysis.get('reason', 'N/A')}")
        
        logger.info("\n" + "="*70)
        logger.info(f"🎯 분석 완료: 총 {len(relevant_apis)}개 정책 관련 API 발견")
        logger.info("="*70 + "\n")
        
        return relevant_apis

