#!/usr/bin/env python3
"""
간단한 스크래핑 인터페이스
사이트명과 기종명만 입력하면 자동으로 스크래핑하고 슬랙으로 전송
"""
import asyncio
import argparse
import json
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

from scrape_phones import scrape_phones

# 사이트 URL 매핑
SITE_URLS = {
    "하이폰": {
        "삼성": "https://hi-phone.kr/index.php?channel=list&cate=103001000000",
        "아이폰": "https://hi-phone.kr/index.php?channel=list&cate=103002000000"
    },
    "딜리버리폰": {
        "삼성": "https://www.deliveryphone.co.kr/phone/list/2",
        "아이폰": "https://www.deliveryphone.co.kr/phone/list/3"
    },
    "성지폰": {
        "삼성": "https://sungjiphone.com/phone/list/2",
        "아이폰": "https://sungjiphone.com/phone/list/3"
    },
    "폰슐랭": {
        "삼성": "https://phonechelin.shop/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90",
        "아이폰": "https://phonechelin.shop/mshop/list?sst=c&cid=APPLE"
    },
    "엘지티샵": {
        "삼성": "https://lgtshop.co.kr/mshop/list?sst=c&cid=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90",
        "아이폰": "https://lgtshop.co.kr/mshop/list?sst=c&cid=APPLE"
    },
    "투게더몰": {
        "삼성": "https://uplustogethermall.com/section/samsung",
        "아이폰": "https://uplustogethermall.com/section/apple"
    }
}

# 기종 타입 판별 (삼성/아이폰)
def detect_phone_type(model: str) -> str:
    """기종명으로부터 삼성/아이폰 타입 판별"""
    model_lower = model.lower()
    
    # 아이폰 키워드
    if any(keyword in model_lower for keyword in ["아이폰", "iphone", "ip"]):
        return "아이폰"
    
    # 삼성 키워드 (기본값)
    return "삼성"


async def scrape_simple(
    sites: List[str],
    models: List[str],
    headless: bool = True,
    send_slack: bool = True
) -> List[Dict]:
    """
    간단한 스크래핑 인터페이스
    
    Args:
        sites: 사이트명 리스트 (예: ["하이폰", "딜리버리폰"])
        models: 기종명 리스트 (예: ["갤럭시S25", "아이폰17"])
        headless: 헤드리스 모드
        send_slack: 슬랙 전송 여부
        
    Returns:
        결과 리스트
    """
    print("\n" + "="*70)
    print("🚀 간단 스크래핑 시작")
    print("="*70)
    print(f"사이트: {', '.join(sites)}")
    print(f"기종: {', '.join(models)}")
    print("="*70 + "\n")
    
    results = []
    
    for site_name in sites:
        if site_name not in SITE_URLS:
            print(f"⚠️  알 수 없는 사이트: {site_name}")
            print(f"   지원 사이트: {', '.join(SITE_URLS.keys())}")
            continue
        
        # 각 기종별로 처리
        for model in models:
            phone_type = detect_phone_type(model)
            
            if phone_type not in SITE_URLS[site_name]:
                print(f"⚠️  {site_name}에서 {phone_type} 타입을 지원하지 않습니다.")
                continue
            
            list_url = SITE_URLS[site_name][phone_type]
            site_display_name = f"{site_name}_{phone_type}"
            
            print(f"\n{'='*70}")
            print(f"📱 [{site_name}] {model} 스크래핑 중...")
            print(f"{'='*70}\n")
            
            result = await scrape_phones(
                list_url=list_url,
                target_models=[model],
                site_name=site_display_name,
                headless=headless,
                send_slack=send_slack
            )
            
            results.append({
                "site": site_name,
                "model": model,
                "result": result
            })
            
            # 사이트 간 딜레이
            await asyncio.sleep(2)
    
    # 전체 요약
    print("\n" + "="*70)
    print("📊 전체 스크래핑 결과")
    print("="*70)
    
    success_count = sum(1 for r in results if r['result'].get('success'))
    total_products = sum(r['result'].get('product_count', 0) for r in results)
    total_policies = sum(r['result'].get('total_policies', 0) for r in results)
    
    print(f"성공: {success_count}/{len(results)} 작업")
    print(f"총 제품: {total_products}개")
    print(f"총 정책: {total_policies:,}개")
    
    for r in results:
        status = "✅" if r['result'].get('success') else "❌"
        print(f"{status} {r['site']} - {r['model']}: {r['result'].get('total_policies', 0)}개 정책")
    
    print("="*70 + "\n")
    
    return results


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="간단한 스크래핑: 사이트명과 기종명만 입력",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 하이폰에서 갤럭시S25 추출
  uv run python scrape_simple.py --sites 하이폰 --models 갤럭시S25
  
  # 여러 사이트에서 여러 기종 추출
  uv run python scrape_simple.py --sites 하이폰,딜리버리폰 --models 갤럭시S25,아이폰17
  
  # 설정 파일 사용
  uv run python scrape_simple.py --config simple_config.json

지원 사이트:
  하이폰, 딜리버리폰, 성지폰, 폰슐랭, 엘지티샵, 투게더몰
        """
    )
    
    parser.add_argument(
        "--sites",
        help="사이트명 (쉼표로 구분, 예: '하이폰,딜리버리폰')"
    )
    parser.add_argument(
        "--models",
        help="기종명 (쉼표로 구분, 예: '갤럭시S25,아이폰17')"
    )
    parser.add_argument(
        "--config",
        help="설정 파일 경로 (JSON)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="브라우저 표시"
    )
    parser.add_argument(
        "--no-slack",
        action="store_true",
        help="슬랙 알림 비활성화"
    )
    
    args = parser.parse_args()
    
    # 설정 파일 사용
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        sites = config.get('sites', [])
        models = config.get('models', [])
    # 명령줄 인자 사용
    elif args.sites and args.models:
        sites = [s.strip() for s in args.sites.split(',')]
        models = [m.strip() for m in args.models.split(',')]
    else:
        parser.print_help()
        return
    
    await scrape_simple(
        sites=sites,
        models=models,
        headless=not args.no_headless,
        send_slack=not args.no_slack
    )


if __name__ == "__main__":
    asyncio.run(main())

