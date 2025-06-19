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
result = get_steam_game_info_sync(1091500)
print_game_info(result)
```
"""

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
import logging

# 로거 유틸리티 import
from utils.logger import setup_logger

# 로거 설정
logger = logging.getLogger(__name__)

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
        
        # 게임 짧은 설명
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

    def extract_detailed_description(self, soup: BeautifulSoup) -> str:
        """게임의 상세 설명을 추출합니다."""
        detailed_desc = ""
        
        try:
            # 방법 1: #game_area_description에서 추출
            game_area_desc = soup.select_one('#game_area_description')
            if game_area_desc:
                # "About This Game" 제목 제거하고 내용만 추출
                desc_text = game_area_desc.get_text(strip=True)
                # "About This Game" 문구 제거
                if desc_text.startswith('About This Game'):
                    desc_text = desc_text[len('About This Game'):].strip()
                if desc_text:
                    detailed_desc = desc_text
            
            # 방법 2: .game_area_description 클래스로 찾기
            if not detailed_desc:
                game_area_desc = soup.select_one('.game_area_description')
                if game_area_desc:
                    # 짧은 설명 요소는 제외하고 나머지 텍스트 추출
                    desc_copy = game_area_desc.__copy__()
                    # 짧은 설명 부분 제거
                    short_desc_elem = desc_copy.select_one('.game_description_snippet')
                    if short_desc_elem:
                        short_desc_elem.decompose()
                    
                    desc_text = desc_copy.get_text(strip=True)
                    if desc_text.startswith('About This Game'):
                        desc_text = desc_text[len('About This Game'):].strip()
                    if desc_text and len(desc_text) > 200:  # 충분히 긴 텍스트만
                        detailed_desc = desc_text
            
            # 방법 3: "About This Game" 제목 다음 컨텐츠 찾기
            if not detailed_desc:
                about_headers = soup.find_all(string=lambda text: text is not None and 'About This Game' in text)
                for header in about_headers:
                    parent = header.parent
                    if parent:
                        # 다음 형제 요소들에서 상세 설명 찾기
                        next_elem = parent.find_next_sibling()
                        while next_elem:
                            text = next_elem.get_text(strip=True)
                            if text and len(text) > 200:
                                detailed_desc = text
                                break
                            next_elem = next_elem.find_next_sibling()
                        
                        if detailed_desc:
                            break
            
            # 방법 4: 특정 컨테이너에서 가장 긴 텍스트 찾기
            if not detailed_desc:
                containers = soup.select('.tab_content, .game_page_autocollapse_ctn, .game_highlights')
                for container in containers:
                    text = container.get_text(strip=True)
                    if len(text) > 500 and len(text) > len(detailed_desc):
                        # 짧은 설명과 다른 경우만
                        short_desc = soup.select_one('.game_description_snippet')
                        if short_desc:
                            short_text = short_desc.get_text(strip=True)
                            if text != short_text and short_text not in text[:200]:
                                detailed_desc = text
            
            # 텍스트 정리
            if detailed_desc:
                # 불필요한 공백과 줄바꿈 정리
                detailed_desc = re.sub(r'\s+', ' ', detailed_desc).strip()
                # 너무 긴 경우 제한 (5000자)
                if len(detailed_desc) > 5000:
                    detailed_desc = detailed_desc[:5000] + "..."
                    
        except Exception as e:
            logger.error(f"상세 설명 추출 중 오류: {e}")
        
        return detailed_desc

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

    def extract_genres(self, soup: BeautifulSoup) -> List[str]:
        """게임 장르를 추출합니다."""
        genres = []
        
        try:
            # 방법 1: 게임 상세 정보에서 "Genre:" 라벨 다음의 링크들 찾기
            genre_section = soup.select_one('#genresAndManufacturer')
            if genre_section:
                # "Genre:" 텍스트가 있는 부분 찾기
                genre_text = genre_section.get_text()
                if 'Genre:' in genre_text:
                    genre_links = genre_section.select('a[href*="/genre/"]')
                    for link in genre_links:
                        genre_name = link.get_text(strip=True)
                        if genre_name and genre_name not in genres:
                            genres.append(genre_name)
            
            # 방법 2: 더 일반적인 방법으로 장르 링크 찾기
            if not genres:
                genre_links = soup.select('a[href*="/genre/"]')
                for link in genre_links:
                    # URL에서 장르명 추출
                    href = link.get('href')
                    if href and '/genre/' in href:
                        genre_name = link.get_text(strip=True)
                        # 개발사/퍼블리셔가 아닌 실제 장르인지 확인
                        if genre_name and len(genre_name) < 50 and genre_name not in genres:
                            # 일반적인 장르 키워드 필터링
                            common_genres = [
                                'Action', 'Adventure', 'RPG', 'Strategy', 'Simulation', 
                                'Sports', 'Racing', 'Puzzle', 'Platformer', 'Shooter',
                                'Fighting', 'Horror', 'Survival', 'Arcade', 'Casual',
                                'Indie', 'MMO', 'Multiplayer', 'Co-op', 'VR', 'Free to Play',
                                'Early Access'
                            ]
                            if any(common in genre_name for common in common_genres):
                                genres.append(genre_name)
                            elif genre_name in common_genres:
                                genres.append(genre_name)
            
            # 방법 3: details_block에서 "Genre:" 패턴으로 찾기
            if not genres:
                details_blocks = soup.select('.details_block')
                for block in details_blocks:
                    block_text = block.get_text()
                    if 'Genre:' in block_text:
                        # Genre: 다음의 링크들 찾기
                        genre_pattern = re.search(r'Genre:\s*(.+?)(?:\n|$)', block_text)
                        if genre_pattern:
                            genre_text = genre_pattern.group(1).strip()
                            # 쉼표로 구분된 장르들 분리
                            for genre in genre_text.split(','):
                                genre = genre.strip()
                                if genre and genre not in genres:
                                    genres.append(genre)
                        
                        # 블록 내의 장르 링크들도 찾기
                        genre_links = block.select('a[href*="/genre/"]')
                        for link in genre_links:
                            genre_name = link.get_text(strip=True)
                            if genre_name and genre_name not in genres:
                                genres.append(genre_name)
                        break
            
            # 방법 4: 전체 텍스트에서 "Genre:" 패턴 찾기
            if not genres:
                all_text = soup.get_text()
                genre_matches = re.findall(r'Genre[s]?[:\s]+([^\n\r]+)', all_text, re.IGNORECASE)
                for match in genre_matches:
                    match = match.strip()
                    # 쉼표나 기타 구분자로 분리
                    for genre in re.split(r'[,;/]', match):
                        genre = genre.strip()
                        if genre and len(genre) < 50 and genre not in genres:
                            genres.append(genre)
            
        except Exception as e:
            logger.error(f"장르 정보 추출 중 오류: {e}")
        
        # 중복 제거 및 정리
        unique_genres = []
        for genre in genres:
            if genre and genre not in unique_genres:
                unique_genres.append(genre)
        
        return unique_genres

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
            logger.error(f"개발사/퍼블리셔 추출 중 오류: {e}")
        
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
            logger.error(f"리뷰 정보 추출 중 오류: {e}")
        
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

    async def get_comprehensive_game_info(self, app_id: int, max_retries: int = 7) -> Dict[str, Any]:
        """
        게임 ID를 입력받아 모든 정보를 종합적으로 추출합니다.
        
        Returns:
            Dict[str, Any]: 
                성공시: {'success': True, 'data': {...}}
                실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}
        """
        url = f"{self.base_url}{app_id}"
        logger.info(f"종합 정보 추출 중: {url}")
        
        for attempt in range(max_retries + 1):
            try:
                jar = aiohttp.CookieJar(unsafe=True)
                async with aiohttp.ClientSession(cookie_jar=jar) as session:
                    cookies = self.get_age_verification_cookies()
                    
                    async with session.get(url, headers=self.headers, cookies=cookies) as response:
                        # 성공적인 응답
                        if response.status == 200:
                            html = await response.text()
                            
                            # 나이 인증 페이지로 리다이렉트된 경우 처리
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
                            
                            # 모든 정보 추출
                            game_info = {
                                'app_id': app_id,
                                'crawled_at': datetime.now().isoformat(),
                                **self.extract_basic_info(soup, app_id),
                                'detailed_description': self.extract_detailed_description(soup),
                                'tags': self.extract_tags(soup),
                                'genres': self.extract_genres(soup),
                                'price_info': self.extract_price_info(soup),
                                'developer_publisher': self.extract_developer_publisher(soup),
                                'release_date': self.extract_release_date(soup),
                                'review_info': self.extract_review_info(soup),
                                'header_images': self.extract_header_images(soup, app_id),
                                'system_requirements': self.extract_system_requirements(soup)
                            }
                            if not game_info.get('title') or game_info.get('title') == 'Unknown' :
                                logger.error(f"게임 ID {app_id}: 게임 정보 추출 불가능")
                                return {
                                    'success': False,
                                    'error': 'invalid_game_page',
                                    'message': '게임 정보 추출 불가능 (제목 없음)',
                                    'app_id': app_id
                                }
                            
                            logger.info(f"게임 ID {app_id}: 종합 정보 추출 성공 - {game_info['title']}")
                            return {
                                'success': True,
                                'data': game_info
                            }
                        
                        # 요청 제한 관련 상태 코드
                        elif response.status in [429, 503, 502, 504]:
                            if attempt < max_retries:
                                # 지수적으로 증가하는 딜레이 (2초, 4초, 8초, 16초, 32초, 64초, 128초)
                                delay = 2 * (2 ** attempt)
                                logger.warning(f"게임 ID {app_id}: HTTP {response.status} - {attempt + 1}회 실패, {delay}초 후 재시도...")
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
                        
                        # 기타 HTTP 에러
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
                if attempt < max_retries and "HTTP" in str(e) and any(code in str(e) for code in ["429", "503", "502", "504"]):
                    # 재시도 가능한 네트워크 오류
                    delay = 2 * (2 ** attempt)
                    logger.warning(f"게임 ID {app_id}: HTTP {response.status} - {attempt + 1}회 실패, {delay}초 후 재시도...")
                    await asyncio.sleep(delay)
                    continue
                elif attempt == max_retries:
                    logger.error(f"게임 ID {app_id}: 최대 재시도 횟수 초과 - {str(e)}")
                    return {
                        'success': False,
                        'error': 'exception',
                        'message': f'최대 재시도 횟수 ({max_retries}) 초과 - {str(e)}',
                        'app_id': app_id,
                        'exception_type': type(e).__name__
                    }
                else:
                    logger.error(f"게임 ID {app_id}: 종합 정보 추출 중 오류 - {str(e)}")
                    return {
                        'success': False,
                        'error': 'exception',
                        'message': f'종합 정보 추출 중 오류 - {str(e)}',
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
async def get_steam_game_info_crawler(app_id: int, max_retries: int = 7) -> Dict[str, Any]:
    """
    Steam 게임 ID를 입력받아 모든 정보를 반환하는 비동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        max_retries (int): 최대 재시도 횟수 (기본값: 7 - 총 대기시간 약 5분)
        
    Returns:
        Dict[str, Any]: 
            성공시: {'success': True, 'data': {...}}
            실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}
        
    Example:
        result = await get_steam_game_info(1091500)  # Cyberpunk 2077
        if result['success']:
            info = result['data']
            print(f"제목: {info['title']}")
            print(f"가격: {info['price_info']['current_price']}")
            print(f"태그: {info['tags']}")
        else:
            print(f"크롤링 실패: {result['error']} - {result['message']}")
    """
    crawler = ComprehensiveGameCrawler()
    return await crawler.get_comprehensive_game_info(app_id, max_retries)


def get_steam_game_info_crawler_sync(app_id: int, max_retries: int = 7) -> Dict[str, Any]:
    """
    Steam 게임 ID를 입력받아 모든 정보를 반환하는 동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        max_retries (int): 최대 재시도 횟수 (기본값: 7 - 총 대기시간 약 5분)
        
    Returns:
        Dict[str, Any]: 
            성공시: {'success': True, 'data': {...}}
            실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}
        
    Example:
        result = get_steam_game_info_sync(1091500)  # Cyberpunk 2077
        if result['success']:
            info = result['data']
            print(f"제목: {info['title']}")
            print(f"가격: {info['price_info']['current_price']}")
            print(f"태그: {info['tags']}")
        else:
            print(f"크롤링 실패: {result['error']} - {result['message']}")
    """
    return asyncio.run(get_steam_game_info_crawler(app_id, max_retries))


def save_game_info_json(result: Dict[str, Any], filename: Optional[str] = None) -> str:
    """게임 정보를 JSON 파일로 저장합니다."""
    if not result:
        raise ValueError("저장할 결과가 없습니다.")
    
    if not result.get('success', False):
        raise ValueError("실패한 결과는 저장할 수 없습니다.")
    
    game_info = result['data']
    
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
    
    logger.info(f"게임 정보가 저장되었습니다: {file_path}")
    return str(file_path)


def save_multiple_games_csv(results: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
    """여러 게임 정보를 CSV 파일로 저장합니다."""
    if not results:
        raise ValueError("저장할 결과가 없습니다.")
    
    # 성공한 결과만 필터링
    successful_results = [result for result in results if result.get('success', False)]
    
    if not successful_results:
        raise ValueError("성공한 결과가 없어 저장할 수 없습니다.")
    
    games_info = [result['data'] for result in successful_results]
    
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
        'app_id', 'title', 'description', 'detailed_description', 'current_price', 'original_price', 
        'discount_percent', 'is_free', 'developer', 'publisher', 'release_date',
        'all_reviews', 'total_review_count', 'total_positive_percent',
        'tags', 'genres', 'header_image', 'crawled_at'
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
                'detailed_description': game_info.get('detailed_description', '')[:500] + '...' if len(game_info.get('detailed_description', '')) > 500 else game_info.get('detailed_description', ''),
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
                'genres': ', '.join(game_info.get('genres', [])),
                'header_image': game_info.get('header_images', [''])[0] if game_info.get('header_images') else '',
                'crawled_at': game_info.get('crawled_at', '')
            }
            writer.writerow(row)
    
    logger.info(f"{len(games_info)}개 게임 정보가 CSV로 저장되었습니다: {file_path}")
    return str(file_path)


def load_game_info_json(file_path: str) -> Dict[str, Any]:
    """JSON 파일에서 게임 정보를 불러옵니다."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_game_info(result: Dict[str, Any]):
    """게임 정보를 보기 좋게 출력합니다."""
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
    game_info = result.get('data', {})
    print(f"=== {game_info.get('title', 'Unknown')} (ID: {game_info.get('app_id')}) ===")
    print(f"📝 짧은 설명: {game_info.get('description', 'N/A')[:100]}...")
    
    detailed_desc = game_info.get('detailed_description', '')
    if detailed_desc:
        print(f"📄 상세 설명: {detailed_desc[:200]}...")
        print(f"   (총 {len(detailed_desc)} 문자)")
    else:
        print(f"📄 상세 설명: N/A")
    
    print(f"💰 가격: {game_info.get('price_info', {}).get('current_price', 'N/A')}")
    print(f"👨‍💻 개발사: {game_info.get('developer_publisher', {}).get('developer', 'N/A')}")
    print(f"🏢 퍼블리셔: {game_info.get('developer_publisher', {}).get('publisher', 'N/A')}")
    print(f"📅 출시일: {game_info.get('release_date', 'N/A')}")
    print(f"⭐ 전체 리뷰: {game_info.get('review_info', {}).get('all_reviews', 'N/A')}")
    print(f"🎮 장르: {', '.join(game_info.get('genres', [])[:5]) or 'N/A'}")
    print(f"🏷️ 태그: {', '.join(game_info.get('tags', [])[:5])}...")
    print(f"🖼️ 헤더 이미지: {game_info.get('header_images', ['N/A'])[0]}")


async def main(save=False):
    # 로거 설정
    setup_logger("INFO")
    
    # 테스트
    test_games = [
        (1091500, "Cyberpunk 2077"),
        (2456740, "inZOI"),
        (570, "Dota 2"),
        (730, "Counter-Strike 2"),
        (203770,"CK2"),
        (1771300,"KCD2")
    ]
    
    all_results = []
    
    for app_id, expected_title in test_games:
        print(f"\n{'='*50}")
        print(f"테스트 중: {expected_title} (ID: {app_id})")
        print(f"{'='*50}")
        
        result = await get_steam_game_info_crawler(app_id)
        print_game_info(result)
        
        if result.get('success', False) and save:
            # 개별 게임 정보를 JSON으로 저장
            save_game_info_json(result)
        
        all_results.append(result)
    
    # 모든 게임 정보를 CSV로 저장
    if all_results and save:
        successful_count = len([r for r in all_results if r.get('success', False)])
        if successful_count > 0:
            save_multiple_games_csv(all_results, "test_games.csv")
            print(f"\n📊 총 {successful_count}개 게임 정보 수집 완료!")
            print("💾 개별 JSON 파일과 통합 CSV 파일이 data/game_info/ 폴더에 저장되었습니다.")
        else:
            print("⚠️ 저장할 성공한 결과가 없습니다.")


if __name__ == "__main__":
    asyncio.run(main(save=False))