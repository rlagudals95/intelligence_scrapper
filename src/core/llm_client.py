"""
LLM Client (Phase 2)
OpenAI, Anthropic, Gemini API 통합
"""
import os
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import asyncio

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

from ..utils.logger import get_logger

logger = get_logger()

# Gemini import (optional)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class LLMProvider(str, Enum):
    """LLM 제공자"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class LLMClient:
    """LLM API 클라이언트 (통합)"""
    load_dotenv()
    
    def __init__(
        self,
        provider: LLMProvider = LLMProvider.OPENAI,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.1
    ):
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # 사용량 추적
        self.total_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0
        
        # API 키 설정
        if api_key:
            self.api_key = api_key
        elif provider == LLMProvider.OPENAI:
            self.api_key = os.getenv("OPENAI_API_KEY")
        elif provider == LLMProvider.GEMINI:
            self.api_key = os.getenv("GEMINI_API_KEY")
        else:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            raise ValueError(f"{provider.value.upper()}_API_KEY 환경변수가 설정되지 않았습니다")
        
        # 모델 설정
        if model:
            self.model = model
        elif provider == LLMProvider.OPENAI:
            self.model = "gpt-4o"  # 또는 "gpt-4o-mini"
        elif provider == LLMProvider.GEMINI:
            self.model = "gemini-3.0-flash-preview"  # 최신 모델
        else:
            self.model = "claude-3-5-sonnet-20241022"
        
        # 클라이언트 초기화
        if provider == LLMProvider.OPENAI:
            self.client = AsyncOpenAI(api_key=self.api_key)
        elif provider == LLMProvider.GEMINI:
            if not GEMINI_AVAILABLE:
                raise ImportError("google-generativeai 패키지가 설치되지 않았습니다. pip install google-generativeai")
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
        else:
            self.client = AsyncAnthropic(api_key=self.api_key)
        
        logger.info(
            "LLM Client 초기화",
            provider=provider.value,
            model=self.model
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    async def complete(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        LLM 완성 요청
        
        Args:
            prompt: 사용자 프롬프트
            system_message: 시스템 메시지 (선택)
            temperature: 온도 (선택, 기본값 사용)
            max_tokens: 최대 토큰 (선택, 기본값 사용)
            response_format: 응답 형식 (OpenAI JSON mode 등)
            
        Returns:
            str: LLM 응답 텍스트
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        self.request_count += 1
        
        try:
            if self.provider == LLMProvider.OPENAI:
                response_text = await self._openai_complete(
                    prompt, system_message, temp, max_tok, response_format
                )
            elif self.provider == LLMProvider.GEMINI:
                response_text = await self._gemini_complete(
                    prompt, system_message, temp, max_tok, response_format
                )
            else:
                response_text = await self._anthropic_complete(
                    prompt, system_message, temp, max_tok
                )
            
            logger.info(
                "LLM 요청 완료",
                provider=self.provider.value,
                request_count=self.request_count,
                response_length=len(response_text)
            )
            
            return response_text
            
        except Exception as e:
            logger.error(
                "LLM 요청 실패",
                provider=self.provider.value,
                error=str(e)
            )
            raise
    
    async def _openai_complete(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, Any]]
    ) -> str:
        """OpenAI API 호출"""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # JSON mode (OpenAI 전용)
        if response_format:
            kwargs["response_format"] = response_format
        
        response = await self.client.chat.completions.create(**kwargs)
        
        # 토큰 사용량 추적
        if hasattr(response, 'usage'):
            self.total_tokens += response.usage.total_tokens
            # GPT-4o 대략적 가격 (input: $2.5/1M, output: $10/1M)
            cost = (
                response.usage.prompt_tokens * 2.5 / 1_000_000 +
                response.usage.completion_tokens * 10 / 1_000_000
            )
            self.total_cost += cost
        
        return response.choices[0].message.content
    
    async def _anthropic_complete(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Anthropic API 호출"""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        if system_message:
            kwargs["system"] = system_message
        
        response = await self.client.messages.create(**kwargs)
        
        # 토큰 사용량 추적
        if hasattr(response, 'usage'):
            self.total_tokens += response.usage.input_tokens + response.usage.output_tokens
            # Claude 대략적 가격 (input: $3/1M, output: $15/1M)
            cost = (
                response.usage.input_tokens * 3 / 1_000_000 +
                response.usage.output_tokens * 15 / 1_000_000
            )
            self.total_cost += cost
        
        return response.content[0].text
    
    async def _gemini_complete(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, Any]]
    ) -> str:
        """Gemini API 호출"""
        # 시스템 메시지와 프롬프트 결합
        full_prompt = prompt
        if system_message:
            full_prompt = f"{system_message}\n\n{prompt}"
        
        # JSON mode 처리
        if response_format and response_format.get("type") == "json_object":
            full_prompt += "\n\n**중요: 응답은 반드시 유효한 JSON 형식이어야 합니다.**"
        
        # Generation config
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        # JSON mode 설정 (Gemini 2.0부터 지원)
        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"
        
        # 비동기 호출
        response = await asyncio.to_thread(
            self.client.generate_content,
            full_prompt,
            generation_config=generation_config
        )
        
        # 토큰 사용량 추적 (Gemini는 무료/저렴)
        if hasattr(response, 'usage_metadata'):
            self.total_tokens += (
                response.usage_metadata.prompt_token_count +
                response.usage_metadata.candidates_token_count
            )
            # Gemini Flash는 무료 또는 매우 저렴 (가격 추정: $0.001/1K tokens)
            cost = self.total_tokens * 0.001 / 1000
            self.total_cost = cost
        
        return response.text
    
    async def _gemini_vision(
        self,
        prompt: str,
        image_url: str,
        system_message: Optional[str]
    ) -> str:
        """Gemini Vision API"""
        # 시스템 메시지와 프롬프트 결합
        full_prompt = prompt
        if system_message:
            full_prompt = f"{system_message}\n\n{prompt}"
        
        # data URL 파싱
        if image_url.startswith("data:image/"):
            parts = image_url.split(";base64,")
            if len(parts) == 2:
                import base64
                image_data = base64.b64decode(parts[1])
                
                # Gemini에 이미지 전달
                import PIL.Image
                import io
                image = PIL.Image.open(io.BytesIO(image_data))
                
                # 비동기 호출
                response = await asyncio.to_thread(
                    self.client.generate_content,
                    [full_prompt, image]
                )
                
                # 토큰 추적
                if hasattr(response, 'usage_metadata'):
                    self.total_tokens += (
                        response.usage_metadata.prompt_token_count +
                        response.usage_metadata.candidates_token_count
                    )
                
                return response.text
            else:
                raise ValueError("잘못된 data URL 형식")
        else:
            raise ValueError("Gemini는 data URL 형식만 지원합니다")
    
    async def complete_with_vision(
        self,
        prompt: str,
        image_url: str,
        system_message: Optional[str] = None
    ) -> str:
        """
        비전 기능 사용 (이미지 포함)
        
        Args:
            prompt: 텍스트 프롬프트
            image_url: 이미지 URL (data:image/... 또는 http://...)
            system_message: 시스템 메시지
            
        Returns:
            str: LLM 응답
        """
        if self.provider == LLMProvider.OPENAI:
            return await self._openai_vision(prompt, image_url, system_message)
        elif self.provider == LLMProvider.GEMINI:
            return await self._gemini_vision(prompt, image_url, system_message)
        else:
            return await self._anthropic_vision(prompt, image_url, system_message)
    
    async def _openai_vision(
        self,
        prompt: str,
        image_url: str,
        system_message: Optional[str]
    ) -> str:
        """OpenAI 비전 API"""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        })
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        
        if hasattr(response, 'usage'):
            self.total_tokens += response.usage.total_tokens
        
        return response.choices[0].message.content
    
    async def _anthropic_vision(
        self,
        prompt: str,
        image_url: str,
        system_message: Optional[str]
    ) -> str:
        """Anthropic 비전 API"""
        # image_url이 data URL인 경우 파싱
        if image_url.startswith("data:image/"):
            media_type, base64_data = image_url.split(";base64,")
            media_type = media_type.replace("data:", "")
        else:
            raise ValueError("Anthropic는 data URL 형식만 지원합니다")
        
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        
        if system_message:
            kwargs["system"] = system_message
        
        response = await self.client.messages.create(**kwargs)
        
        if hasattr(response, 'usage'):
            self.total_tokens += response.usage.input_tokens + response.usage.output_tokens
        
        return response.content[0].text
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """사용량 통계 반환"""
        return {
            "provider": self.provider.value,
            "model": self.model,
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 4)
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.total_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0

