#!/usr/bin/env python3
"""
휴대폰 정책 스크래핑 메인 스크립트

사용법:
    python scrape_phones.py --list-url "https://..." --models "갤럭시S25,아이폰17"
    python scrape_phones.py --config scrape_config.json
"""
import asyncio
import argparse
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from src.core.config import SiteConfig
from src.core.browser import BrowserManager
from src.core.llm_client import LLMClient, LLMProvider
from src.utils.list_page_analyzer import ListPageAnalyzer
from src.utils.detail_page_analyzer import DetailPageAnalyzer
from src.utils.slack_notifier import SlackNotifier
from src.utils.logger import get_logger

logger = get_logger()


def get_llm_client():
    """LLM Client 생성"""
    import os
    
    if os.getenv("GEMINI_API_KEY"):
        provider = LLMProvider.GEMINI
        model = "gemini-2.5-flash"
        return LLMClient(provider=provider, model=model)
    elif os.getenv("OPENAI_API_KEY"):
        return LLMClient(provider=LLMProvider.OPENAI)
    elif os.getenv("ANTHROPIC_API_KEY"):
        return LLMClient(provider=LLMProvider.ANTHROPIC)
    else:
        raise ValueError("LLM API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")


def filter_products_by_models(products: List[Dict], target_models: List[str]) -> List[Dict]:
    """
    제품 리스트에서 특정 모델만 필터링
    
    Args:
        products: 전체 제품 리스트
        target_models: 찾고자 하는 모델명 리스트 (예: ["갤럭시S25", "아이폰17"])
        
    Returns:
        필터링된 제품 리스트
    """
    filtered = []
    
    for product in products:
        name = product.get('name', '').lower()
        
        for model in target_models:
            model_lower = model.lower()
            
            # 다양한 표기법 처리
            # 예: "갤럭시 S25", "갤럭시S25", "Galaxy S25" 등
            model_variants = [
                model_lower,
                model_lower.replace(' ', ''),
                model_lower.replace('갤럭시', 'galaxy'),
                model_lower.replace('아이폰', 'iphone'),
                model_lower.replace('s', ' s'),  # S25 -> " S25"
            ]
            
            if any(variant in name for variant in model_variants):
                filtered.append(product)
                logger.info(f"✅ 매칭: {product['name']} (찾는 모델: {model})")
                break
    
    return filtered


async def scrape_phones(
    list_url: str,
    target_models: List[str],
    site_name: str = None,
    headless: bool = True,
    send_slack: bool = True
) -> Dict[str, Any]:
    """
    휴대폰 정책 스크래핑 메인 함수
    
    Args:
        list_url: 리스트 페이지 URL
        target_models: 추출할 모델명 리스트
        site_name: 사이트 이름 (자동 추출)
        headless: 헤드리스 모드 여부
        send_slack: 슬랙 전송 여부
        
    Returns:
        스크래핑 결과 딕셔너리
    """
    start_time = time.time()
    
    # 사이트 이름 자동 추출
    if not site_name:
        from urllib.parse import urlparse
        site_name = urlparse(list_url).netloc.split('.')[0]
    
    print("\n" + "="*70)
    print(f"🚀 휴대폰 정책 스크래핑 시작")
    print("="*70)
    print(f"사이트: {site_name}")
    print(f"리스트 URL: {list_url}")
    print(f"찾을 모델: {', '.join(target_models)}")
    print("="*70 + "\n")
    
    # LLM 클라이언트
    llm_client = get_llm_client()
    list_analyzer = ListPageAnalyzer(llm_client)
    detail_analyzer = DetailPageAnalyzer(llm_client)
    
    results = []
    
    try:
        # 1단계: 리스트 페이지에서 URL 추출
        print(f"\n📋 [1단계] 제품 URL 추출 중...")
        
        config = SiteConfig(target_url=list_url, headless=headless, timeout=60000)
        
        async with BrowserManager(config) as browser:
            await browser.goto(list_url, wait_until="domcontentloaded")
            page = await browser.get_page()
            await asyncio.sleep(3)
            
            all_products = await list_analyzer.extract_product_urls(page, base_url=list_url)
            print(f"   전체 제품: {len(all_products)}개")
        
        # 2단계: 타겟 모델 필터링
        print(f"\n🔍 [2단계] 타겟 모델 필터링 중...")
        filtered_products = filter_products_by_models(all_products, target_models)
        print(f"   필터링 결과: {len(filtered_products)}개 제품")
        
        if not filtered_products:
            print("\n⚠️  일치하는 제품을 찾지 못했습니다.")
            print("   전체 제품 목록:")
            for p in all_products[:10]:
                print(f"   - {p['name']}")
            
            if send_slack:
                slack = SlackNotifier()
                await slack.send_scraping_result(
                    site_name=site_name,
                    success=False,
                    duration_seconds=time.time() - start_time,
                    error_message=f"타겟 모델을 찾지 못함: {', '.join(target_models)}"
                )
            
            return {
                "success": False,
                "site_name": site_name,
                "error": "타겟 모델을 찾지 못함"
            }
        
        # 3단계: 각 제품의 상세 페이지 분석
        print(f"\n🔍 [3단계] 상세 페이지 분석 중...")
        
        for idx, product in enumerate(filtered_products, 1):
            print(f"\n   [{idx}/{len(filtered_products)}] {product['name']}")
            print(f"      URL: {product['url']}")
            
            product_start = time.time()
            
            try:
                config = SiteConfig(target_url=product['url'], headless=headless, timeout=60000)
                
                async with BrowserManager(config) as browser:
                    await browser.goto(product['url'], wait_until="domcontentloaded")
                    page = await browser.get_page()
                    await asyncio.sleep(3)
                    
                    result = await detail_analyzer.analyze_detail_page(
                        page=page,
                        url=product['url'],
                        site_name=site_name
                    )
                    
                    policy_count = sum(len(p.policies) for p in result.products)
                    
                    print(f"      ✅ 정책 {policy_count}개 추출 완료 ({time.time() - product_start:.1f}초)")
                    
                    results.append({
                        "product_name": product['name'],
                        "url": product['url'],
                        "success": True,
                        "policy_count": policy_count,
                        "duration": time.time() - product_start,
                        "data": result
                    })
                    
            except Exception as e:
                print(f"      ❌ 오류: {e}")
                results.append({
                    "product_name": product['name'],
                    "url": product['url'],
                    "success": False,
                    "error": str(e),
                    "duration": time.time() - product_start
                })
        
        # 4단계: 결과 저장
        print(f"\n💾 [4단계] 결과 저장 중...")
        
        output_dir = Path("output/scraping")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{site_name}_{timestamp}.json"
        
        # JSON 저장
        output_data = {
            "site_name": site_name,
            "list_url": list_url,
            "target_models": target_models,
            "scraped_at": datetime.now().isoformat(),
            "total_duration": time.time() - start_time,
            "results": []
        }
        
        for result in results:
            if result['success']:
                output_data["results"].append({
                    "product_name": result['product_name'],
                    "url": result['url'],
                    "policy_count": result['policy_count'],
                    "duration": result['duration'],
                    "products": [p.model_dump(mode='json') for p in result['data'].products]
                })
            else:
                output_data["results"].append({
                    "product_name": result['product_name'],
                    "url": result['url'],
                    "error": result['error'],
                    "duration": result['duration']
                })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"   저장 완료: {output_file}")
        
        # 5단계: 결과 요약
        total_duration = time.time() - start_time
        success_count = sum(1 for r in results if r['success'])
        total_policies = sum(r.get('policy_count', 0) for r in results if r['success'])
        
        print("\n" + "="*70)
        print("📊 최종 결과")
        print("="*70)
        print(f"사이트: {site_name}")
        print(f"타겟 모델: {', '.join(target_models)}")
        print(f"처리 제품: {len(filtered_products)}개")
        print(f"성공: {success_count}개")
        print(f"총 정책: {total_policies:,}개")
        print(f"소요 시간: {total_duration:.1f}초")
        
        # LLM 사용량
        stats = llm_client.get_usage_stats()
        print(f"\nLLM 요청: {stats['request_count']}회")
        print(f"LLM 토큰: {stats['total_tokens']:,} tokens")
        print(f"LLM 비용: ${stats['total_cost_usd']:.4f} USD")
        print("="*70 + "\n")
        
        # 6단계: 슬랙 알림
        if send_slack:
            print("📤 슬랙 알림 전송 중...")
            slack = SlackNotifier()
            
            # 개별 제품 정책 상세 알림
            scraping_results = []
            for result in results:
                if result['success']:
                    # 각 제품의 정책을 슬랙으로 전송
                    for product in result['data'].products:
                        # CSV 파일 생성
                        csv_path = slack.save_policies_to_csv(
                            policies=product.policies,
                            output_dir=output_dir,
                            product_name=result['product_name'],
                            site_name=site_name
                        )
                        
                        # 슬랙으로 전송 (CSV 경로 포함)
                        # 상대 경로로 변환 (이미 상대 경로이므로 그대로 사용)
                        csv_relative_path = str(csv_path)
                        
                        await slack.send_policy_summary(
                            site_name=site_name,
                            product_name=result['product_name'],
                            policies=product.policies,
                            product_url=result['url'],
                            csv_file_path=csv_relative_path
                        )
                    scraping_results.append(result['data'])
            
            # 전체 요약 (비즈니스 친화적)
            if scraping_results:
                await slack.send_integration_summary(
                    scraping_results=scraping_results,
                    site_names=[site_name] * len(scraping_results)
                )
            
            print("   ✅ 슬랙 알림 전송 완료")
        
        return {
            "success": True,
            "site_name": site_name,
            "product_count": len(filtered_products),
            "success_count": success_count,
            "total_policies": total_policies,
            "duration": total_duration,
            "output_file": str(output_file)
        }
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
        if send_slack:
            slack = SlackNotifier()
            await slack.send_scraping_result(
                site_name=site_name,
                success=False,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )
        
        return {
            "success": False,
            "site_name": site_name,
            "error": str(e),
            "duration": time.time() - start_time
        }


async def scrape_batch(
    batch_config_path: str,
    headless: bool = True,
    send_slack: bool = True
) -> List[Dict[str, Any]]:
    """
    여러 사이트를 배치로 스크래핑
    
    Args:
        batch_config_path: 배치 설정 파일 경로
        headless: 헤드리스 모드 여부
        send_slack: 슬랙 전송 여부
        
    Returns:
        각 사이트별 결과 리스트
    """
    with open(batch_config_path, 'r', encoding='utf-8') as f:
        batch_config = json.load(f)
    
    sites = batch_config.get('sites', [])
    
    if not sites:
        print("⚠️  배치 설정 파일에 사이트가 없습니다.")
        return []
    
    print("\n" + "="*70)
    print(f"🚀 배치 스크래핑 시작: {len(sites)}개 사이트")
    print("="*70 + "\n")
    
    results = []
    
    for idx, site_config in enumerate(sites, 1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{len(sites)}] {site_config.get('site_name', 'Unknown')}")
        print(f"{'='*70}\n")
        
        result = await scrape_phones(
            list_url=site_config['list_url'],
            target_models=site_config.get('models', []),
            site_name=site_config.get('site_name'),
            headless=headless,
            send_slack=send_slack
        )
        
        results.append(result)
        
        # 사이트 간 딜레이 (서버 부하 방지)
        if idx < len(sites):
            print(f"\n⏳ 다음 사이트로 이동하기 전 대기 중... (3초)")
            await asyncio.sleep(3)
    
    # 전체 요약
    print("\n" + "="*70)
    print("📊 배치 스크래핑 전체 결과")
    print("="*70)
    
    success_count = sum(1 for r in results if r.get('success'))
    total_products = sum(r.get('product_count', 0) for r in results)
    total_policies = sum(r.get('total_policies', 0) for r in results)
    
    print(f"성공: {success_count}/{len(sites)} 사이트")
    print(f"총 제품: {total_products}개")
    print(f"총 정책: {total_policies:,}개")
    
    for result in results:
        status = "✅" if result.get('success') else "❌"
        print(f"{status} {result.get('site_name', 'Unknown')}: {result.get('total_policies', 0)}개 정책")
    
    print("="*70 + "\n")
    
    return results


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="휴대폰 정책 스크래핑")
    parser.add_argument("--list-url", help="리스트 페이지 URL")
    parser.add_argument("--models", help="찾을 모델명 (쉼표로 구분, 예: '갤럭시S25,아이폰17')")
    parser.add_argument("--config", help="단일 사이트 설정 파일 경로 (JSON)")
    parser.add_argument("--batch-config", help="배치 스크래핑 설정 파일 경로 (JSON)")
    parser.add_argument("--site-name", help="사이트 이름 (선택)")
    parser.add_argument("--no-headless", action="store_true", help="브라우저 표시")
    parser.add_argument("--no-slack", action="store_true", help="슬랙 알림 비활성화")
    
    args = parser.parse_args()
    
    # 배치 모드
    if args.batch_config:
        await scrape_batch(
            batch_config_path=args.batch_config,
            headless=not args.no_headless,
            send_slack=not args.no_slack
        )
        return
    
    # 설정 파일 사용
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        list_url = config.get('list_url')
        target_models = config.get('models', [])
        site_name = config.get('site_name')
    # 명령줄 인자 사용
    elif args.list_url and args.models:
        list_url = args.list_url
        target_models = [m.strip() for m in args.models.split(',')]
        site_name = args.site_name
    else:
        parser.print_help()
        return
    
    await scrape_phones(
        list_url=list_url,
        target_models=target_models,
        site_name=site_name,
        headless=not args.no_headless,
        send_slack=not args.no_slack
    )


if __name__ == "__main__":
    asyncio.run(main())

