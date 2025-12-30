from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
import uvicorn
import os
import sys

# 프로젝트 루트를 path에 추가하여 import 가능하게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.services.phone_scraper_service import PhoneScraperService
from src.models.phase3_schemas import ScrapingResult

app = FastAPI(
    title="Phone Scrapper API",
    description="갤럭시 S25 및 아이폰 17 정책 통합 수집 API",
    version="1.0.0"
)

# 요청 데이터 모델 정의
class ScrapeRequest(BaseModel):
    site_url: str = Field(..., description="휴대폰 판매 사이트 메인 URL (예: https://hi-phone.kr/index.php?channel=list&cate=103001000000)")

scraper_service = PhoneScraperService()

@app.get("/")
async def root():
    return {"message": "Phone Scrapper API is running"}

@app.post("/scrape", response_model=List[ScrapingResult])
async def scrape_policies(request: ScrapeRequest):
    """
    사이트 URL을 입력받아 갤럭시 S25와 아이폰 17의 최신 정책을 추출합니다.
    (JSON Body를 통해 전체 URL을 안전하게 전달합니다.)
    """
    try:
        # 통합 파이프라인 실행
        results = await scraper_service.scrape_site(request.site_url)
        
        if not results:
            raise HTTPException(status_code=404, detail="해당 사이트에서 목표 모델 정책을 찾을 수 없습니다.")
            
        return results
        
    except Exception as e:
        import traceback
        error_msg = f"스크래핑 중 오류 발생: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    # 포트 8000에서 서버 실행
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
