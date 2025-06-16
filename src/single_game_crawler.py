import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
import re
from datetime import datetime
import json
import csv
import os
from pathlib import Path

class ComprehensiveGameCrawler:
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
                        print("나이 인증 페이지 감지, 우회 중...")
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
            print(f"나이 인증 처리 중 오류: {str(e)}")
            return None

    def extract_basic_info(self, soup: BeautifulSoup, app_id: int) -> Dict[str, Any]:
        """기본 게임 정보를 추출합니다."""
        info = {}
        
        # 게임 제목
        title_selectors = [
            'div.apphub_AppName',
            'h1.pageheader',
            '.game_title h1',
            '#appHubAppName'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                info['title'] = element.get_text(strip=True)
                break
        
        if 'title' not in info:
            info['title'] = "Unknown"
        
        # 게임 설명
        desc_selectors = [
            '.game_description_snippet',
            '.game_area_description .game_description_snippet'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                info['description'] = element.get_text(strip=True)
                break
        
        if 'description' not in info:
            info['description'] = ""
        
        return info

    def extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """게임 태그를 추출합니다."""
        tags = []
        tag_selectors = [
            'a.app_tag',
            '.popular_tags a',
            '.game_area_details_specs a'
        ]
        
        for selector in tag_selectors:
            tag_elements = soup.select(selector)
            if tag_elements:
                for tag in tag_elements:
                    tag_text = tag.get_text(strip=True)
                    if tag_text and tag_text not in tags:
                        tags.append(tag_text)
                break
        
        return tags

    def extract_price_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """가격 정보를 추출합니다."""
        price_info = {
            'current_price': None,
            'original_price': None,
            'discount_percent': None,
            'is_free': False
        }
        
        # 무료 게임 확인
        free_elements = soup.select('.game_purchase_price')
        for elem in free_elements:
            text = elem.get_text(strip=True).lower()
            if 'free' in text or '무료' in text:
                price_info['is_free'] = True
                price_info['current_price'] = "Free"
                return price_info
        
        # 현재 가격
        current_price_selectors = [
            '.game_purchase_price',
            '.discount_final_price'
        ]
        
        for selector in current_price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                if price_text and price_text != '--':
                    price_info['current_price'] = price_text
                    break
        
        # 원래 가격 (할인 시)
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
        
        return price_info

    def extract_developer_publisher(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """개발사/퍼블리셔 정보를 추출합니다."""
        dev_pub_info: Dict[str, Any] = {
            'developer': None,
            'publisher': None
        }
        
        # 개발사/퍼블리셔 정보 추출 - 다양한 방법 시도
        try:
            # 방법 1: 게임 상세 정보에서 찾기
            details_specs = soup.select('.game_area_details_specs .summary')
            
            for i, spec in enumerate(details_specs):
                text = spec.get_text(strip=True).lower()
                
                # 다음 요소가 있는지 확인
                if i + 1 < len(details_specs):
                    next_spec = details_specs[i + 1]
                    value = next_spec.get_text(strip=True)
                    
                    if 'developer' in text:
                        dev_pub_info['developer'] = value
                    elif 'publisher' in text:
                        dev_pub_info['publisher'] = value
            
            # 방법 2: dev_row 클래스로 찾기
            if not dev_pub_info['developer'] or not dev_pub_info['publisher']:
                dev_rows = soup.select('.dev_row')
                for row in dev_rows:
                    summary = row.select_one('.summary')
                    if summary:
                        summary_text = summary.get_text(strip=True).lower()
                        if 'developer' in summary_text:
                            dev_link = row.select_one('a')
                            if dev_link:
                                dev_pub_info['developer'] = dev_link.get_text(strip=True)
                        elif 'publisher' in summary_text:
                            pub_link = row.select_one('a')
                            if pub_link:
                                dev_pub_info['publisher'] = pub_link.get_text(strip=True)
            
            # 방법 3: 링크 href 속성으로 찾기
            if not dev_pub_info['developer']:
                dev_elements = soup.select('a[href*="developer"]')
                if dev_elements:
                    dev_pub_info['developer'] = dev_elements[0].get_text(strip=True)
            
            if not dev_pub_info['publisher']:
                pub_elements = soup.select('a[href*="publisher"]')
                if pub_elements:
                    dev_pub_info['publisher'] = pub_elements[0].get_text(strip=True)
            
            # 방법 4: 게임 정보 블록에서 직접 찾기
            if not dev_pub_info['developer'] or not dev_pub_info['publisher']:
                # 모든 텍스트에서 "Developer:" 또는 "Publisher:" 패턴 찾기
                all_text = soup.get_text()
                
                # Developer 패턴 찾기
                dev_match = re.search(r'Developer[:\s]+([^\n\r]+)', all_text, re.IGNORECASE)
                if dev_match and not dev_pub_info['developer']:
                    dev_pub_info['developer'] = dev_match.group(1).strip()
                
                # Publisher 패턴 찾기
                pub_match = re.search(r'Publisher[:\s]+([^\n\r]+)', all_text, re.IGNORECASE)
                if pub_match and not dev_pub_info['publisher']:
                    dev_pub_info['publisher'] = pub_match.group(1).strip()
            
            # 방법 5: 특정 클래스명으로 찾기
            if not dev_pub_info['developer'] or not dev_pub_info['publisher']:
                # 다른 가능한 선택자들
                possible_selectors = [
                    '.glance_ctn .summary',
                    '.details_block .summary',
                    '.game_area_details .summary'
                ]
                
                for selector in possible_selectors:
                    elements = soup.select(selector)
                    for i, elem in enumerate(elements):
                        text = elem.get_text(strip=True).lower()
                        if 'developer' in text and i + 1 < len(elements):
                            if not dev_pub_info['developer']:
                                dev_pub_info['developer'] = elements[i + 1].get_text(strip=True)
                        elif 'publisher' in text and i + 1 < len(elements):
                            if not dev_pub_info['publisher']:
                                dev_pub_info['publisher'] = elements[i + 1].get_text(strip=True)
                    
                    if dev_pub_info['developer'] and dev_pub_info['publisher']:
                        break
                        
        except Exception as e:
            print(f"개발사/퍼블리셔 추출 중 오류: {e}")
        
        return dev_pub_info

    def extract_release_date(self, soup: BeautifulSoup) -> Optional[str]:
        """출시일을 추출합니다."""
        release_selectors = [
            '.release_date .date',
            '.game_area_release_date .date'
        ]
        
        for selector in release_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        return None

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
        
        # 리뷰 요약 정보
        review_summaries = soup.select('.game_review_summary')
        if len(review_summaries) >= 2:
            review_info['recent_reviews'] = review_summaries[0].get_text(strip=True)
            review_info['all_reviews'] = review_summaries[1].get_text(strip=True)
        elif len(review_summaries) == 1:
            review_info['all_reviews'] = review_summaries[0].get_text(strip=True)
        
        # 상세 리뷰 통계 - 더 정확한 추출
        try:
            # 리뷰 통계 정보가 있는 섹션 찾기
            review_sections = soup.select('.user_reviews_summary_row')
            
            for section in review_sections:
                section_text = section.get_text()
                
                # 최근 리뷰 섹션
                if 'Recent Reviews' in section_text or '최근 리뷰' in section_text:
                    # 괄호 안의 숫자 추출 (리뷰 개수)
                    count_match = re.search(r'\((\d{1,3}(?:,\d{3})*)\)', section_text)
                    if count_match:
                        review_info['recent_review_count'] = count_match.group(1)
                    
                    # 퍼센트 추출 - 더 정확한 패턴
                    percent_match = re.search(r'(\d+)%\s+of\s+the\s+\d+', section_text)
                    if percent_match:
                        review_info['recent_positive_percent'] = int(percent_match.group(1))
                
                # 전체 리뷰 섹션
                elif 'All Reviews' in section_text or '모든 리뷰' in section_text:
                    # 괄호 안의 숫자 추출 (리뷰 개수)
                    count_match = re.search(r'\((\d{1,3}(?:,\d{3})*)\)', section_text)
                    if count_match:
                        review_info['total_review_count'] = count_match.group(1)
                    
                    # 퍼센트 추출 - 더 정확한 패턴
                    percent_match = re.search(r'(\d+)%\s+of\s+the\s+\d+', section_text)
                    if percent_match:
                        review_info['total_positive_percent'] = int(percent_match.group(1))
            
            # 추가 시도: 다른 선택자로 리뷰 통계 찾기
            if not review_info['total_review_count']:
                # 리뷰 통계를 담고 있는 다른 요소들 시도
                review_stats = soup.select('.responsive_reviewdesc')
                for stat in review_stats:
                    stat_text = stat.get_text()
                    
                    # "94% of the 123,456 user reviews" 패턴 찾기
                    match = re.search(r'(\d+)%\s+of\s+the\s+([\d,]+)\s+user\s+reviews', stat_text)
                    if match:
                        review_info['total_positive_percent'] = int(match.group(1))
                        review_info['total_review_count'] = match.group(2)
                        break
                        
        except Exception as e:
            print(f"리뷰 정보 추출 중 오류: {e}")
        
        return review_info

    def extract_header_images(self, soup: BeautifulSoup, app_id: int) -> List[str]:
        """헤더 이미지를 추출합니다."""
        header_images = []
        
        # HTML에서 헤더 이미지 찾기
        header_selectors = [
            '.game_header_image_full',
            '.game_header_image img',
            '.page_header_image img'
        ]
        
        for selector in header_selectors:
            elements = soup.select(selector)
            for elem in elements:
                src = elem.get('src', '')
                if src and src not in header_images:
                    header_images.append(src)
        
        # Steam의 표준 헤더 이미지 URL 패턴 추가
        standard_header_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg"
        if standard_header_url not in header_images:
            header_images.append(standard_header_url)
        
        return header_images

    def extract_system_requirements(self, soup: BeautifulSoup) -> Dict[str, str]:
        """시스템 요구사항을 추출합니다."""
        sys_req = {
            'minimum': '',
            'recommended': ''
        }
        
        sys_req_sections = soup.select('.game_area_sys_req')
        for section in sys_req_sections:
            text = section.get_text()
            if 'Minimum' in text or '최소' in text:
                sys_req['minimum'] = text.strip()
            elif 'Recommended' in text or '권장' in text:
                sys_req['recommended'] = text.strip()
        
        return sys_req

    async def get_comprehensive_game_info(self, app_id: int) -> Dict[str, Any]:
        """게임 ID를 입력받아 모든 정보를 종합적으로 추출합니다."""
        url = f"{self.base_url}{app_id}"
        print(f"종합 정보 추출 중: {url}")
        
        try:
            jar = aiohttp.CookieJar(unsafe=True)
            async with aiohttp.ClientSession(cookie_jar=jar) as session:
                cookies = self.get_age_verification_cookies()
                
                async with session.get(url, headers=self.headers, cookies=cookies) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # 나이 인증 페이지로 리다이렉트된 경우 처리
                        if 'agecheck' in response.url.path or 'agegate' in html.lower():
                            html = await self.handle_age_check(session, str(response.url))
                            if not html:
                                return {}
                        
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # 모든 정보 추출
                        game_info = {
                            'app_id': app_id,
                            'crawled_at': datetime.now().isoformat(),
                            **self.extract_basic_info(soup, app_id),
                            'tags': self.extract_tags(soup),
                            'price_info': self.extract_price_info(soup),
                            'developer_publisher': self.extract_developer_publisher(soup),
                            'release_date': self.extract_release_date(soup),
                            'review_info': self.extract_review_info(soup),
                            'header_images': self.extract_header_images(soup, app_id),
                            'system_requirements': self.extract_system_requirements(soup)
                        }
                        
                        return game_info
                    else:
                        print(f"HTTP 오류: {response.status}")
                        return {}
                        
        except Exception as e:
            print(f"종합 정보 추출 중 오류: {str(e)}")
            return {}


# 편의 함수들
async def get_steam_game_info(app_id: int) -> Dict[str, Any]:
    """
    Steam 게임 ID를 입력받아 모든 정보를 반환하는 비동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        
    Returns:
        Dict[str, Any]: 게임의 모든 정보
        
    Example:
        info = await get_steam_game_info(1091500)  # Cyberpunk 2077
        print(f"제목: {info['title']}")
        print(f"가격: {info['price_info']['current_price']}")
        print(f"태그: {info['tags']}")
    """
    crawler = ComprehensiveGameCrawler()
    return await crawler.get_comprehensive_game_info(app_id)


def get_steam_game_info_sync(app_id: int) -> Dict[str, Any]:
    """
    Steam 게임 ID를 입력받아 모든 정보를 반환하는 동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        
    Returns:
        Dict[str, Any]: 게임의 모든 정보
        
    Example:
        info = get_steam_game_info_sync(1091500)  # Cyberpunk 2077
        print(f"제목: {info['title']}")
        print(f"가격: {info['price_info']['current_price']}")
        print(f"태그: {info['tags']}")
    """
    return asyncio.run(get_steam_game_info(app_id))


def save_game_info_json(game_info: Dict[str, Any], filename: Optional[str] = None) -> str:
    """게임 정보를 JSON 파일로 저장합니다."""
    if not game_info:
        raise ValueError("저장할 게임 정보가 없습니다.")
    
    # 파일명 생성
    if not filename:
        app_id = game_info.get('app_id', 'unknown')
        title = game_info.get('title', 'unknown').replace('/', '_').replace('\\', '_')
        # 파일명에 사용할 수 없는 문자 제거
        safe_title = re.sub(r'[<>:"|?*]', '', title)[:50]
        filename = f"game_{app_id}_{safe_title}.json"
    
    # 저장 디렉토리 생성
    save_dir = Path("data/game_info")
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 파일 경로
    file_path = save_dir / filename
    
    # JSON으로 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(game_info, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 게임 정보가 저장되었습니다: {file_path}")
    return str(file_path)


def save_multiple_games_csv(games_info: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
    """여러 게임 정보를 CSV 파일로 저장합니다."""
    if not games_info:
        raise ValueError("저장할 게임 정보가 없습니다.")
    
    # 파일명 생성
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"games_info_{timestamp}.csv"
    
    # 저장 디렉토리 생성
    save_dir = Path("data/game_info")
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 파일 경로
    file_path = save_dir / filename
    
    # CSV 헤더 정의
    headers = [
        'app_id', 'title', 'description', 'current_price', 'original_price', 
        'discount_percent', 'is_free', 'developer', 'publisher', 'release_date',
        'all_reviews', 'total_review_count', 'total_positive_percent',
        'tags', 'header_image', 'crawled_at'
    ]
    
    # CSV로 저장
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for game_info in games_info:
            # 데이터 평탄화
            row = {
                'app_id': game_info.get('app_id', ''),
                'title': game_info.get('title', ''),
                'description': game_info.get('description', '')[:200] + '...' if len(game_info.get('description', '')) > 200 else game_info.get('description', ''),
                'current_price': game_info.get('price_info', {}).get('current_price', ''),
                'original_price': game_info.get('price_info', {}).get('original_price', ''),
                'discount_percent': game_info.get('price_info', {}).get('discount_percent', ''),
                'is_free': game_info.get('price_info', {}).get('is_free', False),
                'developer': game_info.get('developer_publisher', {}).get('developer', ''),
                'publisher': game_info.get('developer_publisher', {}).get('publisher', ''),
                'release_date': game_info.get('release_date', ''),
                'all_reviews': game_info.get('review_info', {}).get('all_reviews', ''),
                'total_review_count': game_info.get('review_info', {}).get('total_review_count', ''),
                'total_positive_percent': game_info.get('review_info', {}).get('total_positive_percent', ''),
                'tags': ', '.join(game_info.get('tags', [])),
                'header_image': game_info.get('header_images', [''])[0] if game_info.get('header_images') else '',
                'crawled_at': game_info.get('crawled_at', '')
            }
            writer.writerow(row)
    
    print(f"✅ {len(games_info)}개 게임 정보가 CSV로 저장되었습니다: {file_path}")
    return str(file_path)


def load_game_info_json(file_path: str) -> Dict[str, Any]:
    """JSON 파일에서 게임 정보를 불러옵니다."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_game_info(game_info: Dict[str, Any]):
    """게임 정보를 보기 좋게 출력합니다."""
    if not game_info:
        print("게임 정보를 찾을 수 없습니다.")
        return
    
    print(f"\n=== {game_info.get('title', 'Unknown')} (ID: {game_info.get('app_id')}) ===")
    print(f"📝 설명: {game_info.get('description', 'N/A')[:100]}...")
    print(f"💰 가격: {game_info.get('price_info', {}).get('current_price', 'N/A')}")
    print(f"👨‍💻 개발사: {game_info.get('developer_publisher', {}).get('developer', 'N/A')}")
    print(f"🏢 퍼블리셔: {game_info.get('developer_publisher', {}).get('publisher', 'N/A')}")
    print(f"📅 출시일: {game_info.get('release_date', 'N/A')}")
    print(f"⭐ 전체 리뷰: {game_info.get('review_info', {}).get('all_reviews', 'N/A')}")
    print(f"🏷️ 태그: {', '.join(game_info.get('tags', [])[:5])}...")
    print(f"🖼️ 헤더 이미지: {game_info.get('header_images', ['N/A'])[0]}")


async def main():
    # 테스트
    test_games = [
        #(1091500, "Cyberpunk 2077"),
        #(570, "Dota 2"),
        #(730, "Counter-Strike 2")
        (1284790,'unable')

    ]
    
    all_games_info = []
    
    for app_id, expected_title in test_games:
        print(f"\n{'='*50}")
        print(f"테스트 중: {expected_title} (ID: {app_id})")
        print(f"{'='*50}")
        
        game_info = await get_steam_game_info(app_id)
        print_game_info(game_info)
        
        if game_info:
            # 개별 게임 정보를 JSON으로 저장
            save_game_info_json(game_info)
            all_games_info.append(game_info)
    
    # 모든 게임 정보를 CSV로 저장
    if all_games_info:
        save_multiple_games_csv(all_games_info, "test_games.csv")
        
        print(f"\n📊 총 {len(all_games_info)}개 게임 정보 수집 완료!")
        print("💾 개별 JSON 파일과 통합 CSV 파일이 data/game_info/ 폴더에 저장되었습니다.")


if __name__ == "__main__":
    asyncio.run(main()) 