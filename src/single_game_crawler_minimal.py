"""
Steam 게임 크롤링을 위한 최소한의 크롤러

이 모듈은 Steam API로 제공되지 않는 정보만 크롤링합니다:
- 사용자가 붙인 태그
- 리뷰 통계 (긍정 비율 등)
- 현지화된 가격 정보

반환 구조:
- 성공시: {'success': True, 'data': {...}}
- 실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}

가능한 에러 타입:
- 'age_verification_failed': 나이 인증 처리 실패
- 'invalid_game_page': 유효하지 않은 게임 페이지
- 'rate_limit_exceeded': 요청 제한 초과 (최대 재시도 초과)
- 'http_error': HTTP 에러 (404, 500 등)
- 'exception': 예외 발생 (네트워크 오류 등)
- 'unknown': 알 수 없는 오류

사용 예시:
```python
import asyncio
from single_game_crawler_minimal import get_minimal_steam_info, setup_logger

# 로거 설정 (선택사항)
setup_logger("INFO")

# 프로그램 실행
result = get_minimal_steam_info_sync(1091500)
print_minimal_info(result)
```
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
import re
from datetime import datetime
import logging

# 로거 유틸리티 import
from utils.logger import setup_logger

# 로거 설정
logger = logging.getLogger(__name__)

class MinimalGameCrawler:
    """Steam 게임 페이지에서 API로 제공되지 않는 핵심 정보만 크롤링"""
    
    def __init__(self):
        self.base_url = "https://store.steampowered.com/app/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def get_age_verification_cookies(self):
        """나이 인증을 우회하기 위한 쿠키를 생성합니다."""
        return {
            'birthtime': '1',
            'mature_content': '1',
            'lastagecheckage': '1-January-1970'
        }

    async def handle_age_check(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """나이 인증 페이지를 처리합니다."""
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    if 'agecheck' in html or 'agegate' in html:
                        logger.info("나이 인증 페이지 감지, 우회 중...")
                        form_data = {
                            'snr': '1_agecheck_agecheck__age-gate',
                            'ageDay': '1',
                            'ageMonth': 'January', 
                            'ageYear': '1990'
                        }
                        
                        async with session.post(url, data=form_data, headers=self.headers) as post_response:
                            if post_response.status == 200:
                                return await post_response.text()
                    
                    return html
        except Exception as e:
            logger.error(f"나이 인증 처리 중 오류: {str(e)}")
            return None

    def extract_user_tags(self, soup: BeautifulSoup) -> List[str]:
        """사용자가 붙인 태그를 추출합니다."""
        tags = []
        tag_selectors = [
            'a.app_tag',  # 가장 일반적인 사용자 태그
            '.popular_tags a',  # 인기 태그 섹션
            '.game_area_details_specs a'  # 상세 정보 섹션의 태그
        ]
        
        for selector in tag_selectors:
            tag_elements = soup.select(selector)
            if tag_elements:
                for tag in tag_elements:
                    tag_text = tag.get_text(strip=True)
                    # 빈 태그나 중복 제거
                    if tag_text and tag_text not in tags and len(tag_text) < 30:
                        tags.append(tag_text)
                break  # 첫 번째로 찾은 선택자만 사용
        
        return tags

    def extract_review_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """리뷰/평점 정보를 추출합니다."""
        review_info: Dict[str, Any] = {
            'recent_reviews': None,
            'all_reviews': None,
            'recent_review_count': None,
            'total_review_count': None,
            'recent_positive_percent': None,
            'total_positive_percent': None
        }
        
        try:
            # 리뷰 요약 정보 (Very Positive, Mixed, etc.)
            review_summaries = soup.select('.game_review_summary')
            if len(review_summaries) >= 2:
                review_info['recent_reviews'] = review_summaries[0].get_text(strip=True)
                review_info['all_reviews'] = review_summaries[1].get_text(strip=True)
            elif len(review_summaries) == 1:
                review_info['all_reviews'] = review_summaries[0].get_text(strip=True)
            
            # 상세 리뷰 통계
            review_sections = soup.select('.user_reviews_summary_row')
            
            for section in review_sections:
                section_text = section.get_text()
                
                # 최근 리뷰 섹션
                if 'Recent Reviews' in section_text or '최근 리뷰' in section_text:
                    # 리뷰 개수 추출
                    count_match = re.search(r'\((\d{1,3}(?:,\d{3})*)\)', section_text)
                    if count_match:
                        review_info['recent_review_count'] = count_match.group(1)
                    
                    # 긍정 비율 추출
                    percent_match = re.search(r'(\d+)%\s+of\s+the\s+\d+', section_text)
                    if percent_match:
                        review_info['recent_positive_percent'] = int(percent_match.group(1))
                
                # 전체 리뷰 섹션
                elif 'All Reviews' in section_text or '모든 리뷰' in section_text:
                    # 리뷰 개수 추출
                    count_match = re.search(r'\((\d{1,3}(?:,\d{3})*)\)', section_text)
                    if count_match:
                        review_info['total_review_count'] = count_match.group(1)
                    
                    # 긍정 비율 추출
                    percent_match = re.search(r'(\d+)%\s+of\s+the\s+\d+', section_text)
                    if percent_match:
                        review_info['total_positive_percent'] = int(percent_match.group(1))
            
            # 대안: 다른 방법으로 리뷰 통계 찾기
            if not review_info['total_review_count']:
                review_stats = soup.select('.responsive_reviewdesc')
                for stat in review_stats:
                    stat_text = stat.get_text()
                    
                    # "94% of the 123,456 user reviews" 패턴
                    match = re.search(r'(\d+)%\s+of\s+the\s+([\d,]+)\s+user\s+reviews', stat_text)
                    if match:
                        review_info['total_positive_percent'] = int(match.group(1))
                        review_info['total_review_count'] = match.group(2)
                        break
                        
        except Exception as e:
            logger.error(f"리뷰 정보 추출 중 오류: {e}")
        
        return review_info

    def extract_localized_price(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """현지화된 가격 정보를 추출합니다."""
        price_info = {
            'current_price': None,
            'original_price': None,
            'discount_percent': None,
            'is_free': False
        }
        
        try:
            # 무료 게임 확인
            free_elements = soup.select('.game_purchase_price')
            for elem in free_elements:
                text = elem.get_text(strip=True).lower()
                if 'free' in text or '무료' in text:
                    price_info['is_free'] = True
                    price_info['current_price'] = "Free"
                    return price_info
            
            # 현재 가격 (할인된 가격 포함)
            current_price_selectors = [
                '.game_purchase_price',      # 일반 가격
                '.discount_final_price'      # 할인된 최종 가격
            ]
            
            for selector in current_price_selectors:
                element = soup.select_one(selector)
                if element:
                    price_text = element.get_text(strip=True)
                    if price_text and price_text != '--' and price_text.lower() != 'free':
                        price_info['current_price'] = price_text
                        break
            
            # 원래 가격 (할인 전 가격)
            original_price_element = soup.select_one('.discount_original_price')
            if original_price_element:
                price_info['original_price'] = original_price_element.get_text(strip=True)
            
            # 할인율
            discount_element = soup.select_one('.discount_pct')
            if discount_element:
                discount_text = discount_element.get_text(strip=True)
                # "-50%" 형태에서 숫자만 추출
                discount_match = re.search(r'-(\d+)%', discount_text)
                if discount_match:
                    price_info['discount_percent'] = int(discount_match.group(1))
                    
        except Exception as e:
            logger.error(f"가격 정보 추출 중 오류: {e}")
        
        return price_info

    async def get_minimal_game_info(self, app_id: int, max_retries: int = 7) -> Dict[str, Any]:
        """
        게임 ID로 핵심 크롤링 정보만 추출합니다.
        
        Returns:
            Dict[str, Any]: 
                성공시: {'success': True, 'data': {...}}
                실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}
        """
        url = f"{self.base_url}{app_id}"
        logger.info(f"핵심 정보 크롤링 중: {url}")
        
        for attempt in range(max_retries + 1):
            try:
                jar = aiohttp.CookieJar(unsafe=True)
                async with aiohttp.ClientSession(cookie_jar=jar) as session:
                    cookies = self.get_age_verification_cookies()
                    
                    async with session.get(url, headers=self.headers, cookies=cookies) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # 나이 인증 처리
                            if 'agecheck' in response.url.path or 'agegate' in html.lower():
                                html = await self.handle_age_check(session, str(response.url))
                                if not html:
                                    return {
                                        'success': False,
                                        'error': 'age_verification_failed',
                                        'message': '나이 인증 처리 실패',
                                        'app_id': app_id
                                    }
                            
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # 게임 제목으로 유효성 확인
                            title_element = soup.select_one('.apphub_AppName, h1.pageheader, .game_title h1')
                            if not title_element:
                                logger.error(f"게임 ID {app_id}: 유효하지 않은 게임 페이지")
                                return {
                                    'success': False,
                                    'error': 'invalid_game_page',
                                    'message': '유효하지 않은 게임 페이지 (제목 요소 없음)',
                                    'app_id': app_id
                                }
                            
                            # 핵심 정보만 추출
                            minimal_info = {
                                'app_id': app_id,
                                'crawled_at': datetime.now().isoformat(),
                                'title': title_element.get_text(strip=True),
                                'user_tags': self.extract_user_tags(soup),
                                'review_info': self.extract_review_info(soup),
                                'localized_price': self.extract_localized_price(soup)
                            }
                            
                            return {
                                'success': True,
                                'data': minimal_info
                            }
                        
                        # 요청 제한 관련 오류
                        elif response.status in [429, 503, 502, 504]:
                            if attempt < max_retries:
                                delay = 2 * (2 ** attempt)  # 2초, 4초, 8초, 16초...
                                logger.warning(f"게임 ID {app_id}: HTTP {response.status} - {delay}초 후 재시도...")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                logger.error(f"게임 ID {app_id}: HTTP {response.status} - 최대 재시도 횟수 초과")
                                return {
                                    'success': False,
                                    'error': 'rate_limit_exceeded',
                                    'message': f'HTTP {response.status} - 최대 재시도 횟수 ({max_retries}) 초과',
                                    'app_id': app_id,
                                    'http_status': response.status
                                }
                        else:
                            logger.error(f"게임 ID {app_id}: HTTP {response.status} 오류")
                            return {
                                'success': False,
                                'error': 'http_error',
                                'message': f'HTTP {response.status} 오류',
                                'app_id': app_id,
                                'http_status': response.status
                            }
                            
            except Exception as e:
                if attempt < max_retries:
                    delay = 2 * (2 ** attempt)
                    logger.warning(f"게임 ID {app_id}: 오류 발생 - {delay}초 후 재시도... ({str(e)})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"게임 ID {app_id}: 크롤링 실패 - {str(e)}")
                    return {
                        'success': False,
                        'error': 'exception',
                        'message': f'최대 재시도 횟수 ({max_retries}) 초과 - {str(e)}',
                        'app_id': app_id,
                        'exception_type': type(e).__name__
                    }
        
        # 이론적으로 도달하지 않는 코드이지만 안전을 위해
        return {
            'success': False,
            'error': 'unknown',
            'message': '알 수 없는 오류',
            'app_id': app_id
        }


# 편의 함수들
async def get_minimal_steam_info(app_id: int, max_retries: int = 7) -> Dict[str, Any]:
    """
    Steam 게임 ID로 핵심 크롤링 정보만 가져오는 비동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        max_retries (int): 최대 재시도 횟수 (기본값: 7)
        
    Returns:
        Dict[str, Any]: 
            성공시: {'success': True, 'data': {...}}
            실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}
    """
    
    crawler = MinimalGameCrawler()
    return await crawler.get_minimal_game_info(app_id, max_retries)


def get_minimal_steam_info_sync(app_id: int, max_retries: int = 7) -> Dict[str, Any]:
    """
    Steam 게임 ID로 핵심 크롤링 정보만 가져오는 동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        max_retries (int): 최대 재시도 횟수 (기본값: 7)
        
    Returns:
        Dict[str, Any]: 
            성공시: {'success': True, 'data': {...}}
            실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}
    """
    return asyncio.run(get_minimal_steam_info(app_id, max_retries))


def print_minimal_info(result: Dict[str, Any]):
    """핵심 크롤링 결과를 보기 좋게 출력합니다."""
    if not result:
        print("결과가 없습니다.")
        return
    
    # 실패한 경우
    if not result.get('success', False):
        print(f"❌ 크롤링 실패 (ID: {result.get('app_id', 'Unknown')})")
        print(f"   오류 타입: {result.get('error', 'unknown')}")
        print(f"   오류 메시지: {result.get('message', '알 수 없는 오류')}")
        if 'http_status' in result:
            print(f"   HTTP 상태: {result['http_status']}")
        if 'exception_type' in result:
            print(f"   예외 타입: {result['exception_type']}")
        return
    
    # 성공한 경우
    info = result.get('data', {})
    print(f"=== {info.get('title', 'Unknown')} (ID: {info.get('app_id')}) ===")
    
    # 사용자 태그
    tags = info.get('user_tags', [])
    if tags:
        print(f"🏷️ 사용자 태그: {', '.join(tags[:10])}...")
        print(f"   (총 {len(tags)}개)")
    else:
        print("🏷️ 사용자 태그: 없음")
    
    # 리뷰 정보
    review_info = info.get('review_info', {})
    all_reviews = review_info.get('all_reviews')
    total_count = review_info.get('total_review_count')
    positive_percent = review_info.get('total_positive_percent')
    
    if all_reviews:
        print(f"⭐ 전체 리뷰: {all_reviews}")
        if total_count:
            print(f"   리뷰 수: {total_count}개")
        if positive_percent:
            print(f"   긍정 비율: {positive_percent}%")
    else:
        print("⭐ 리뷰 정보: 없음")
    
    # 현지화된 가격
    price_info = info.get('localized_price', {})
    current_price = price_info.get('current_price')
    original_price = price_info.get('original_price')
    discount = price_info.get('discount_percent')
    
    if current_price:
        print(f"💰 현재 가격: {current_price}")
        if original_price and discount:
            print(f"   원래 가격: {original_price} (할인: -{discount}%)")
    elif price_info.get('is_free'):
        print("💰 가격: 무료")
    else:
        print("💰 가격 정보: 없음")


async def main():
    """테스트 함수"""
    test_games = [
        (1091500, "Cyberpunk 2077"),
        (730, "Counter-Strike 2"),
        (238960, "Path of Exile"),
        (999999999, "Invalid Game")  # 존재하지 않는 게임으로 에러 테스트
    ]
    
    for app_id, expected_title in test_games:
        print(f"\n{'='*50}")
        print(f"테스트: {expected_title} (ID: {app_id})")
        print(f"{'='*50}")
        
        result = await get_minimal_steam_info(app_id)
        print_minimal_info(result)


if __name__ == "__main__":
    # 기본 로거 설정 (모듈을 직접 실행할 때만)
    setup_logger("INFO")
    
    # 테스트 실행
    asyncio.run(main()) 