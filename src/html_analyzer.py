import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Optional
import json

class SteamHTMLAnalyzer:
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

    async def fetch_and_analyze_game_page(self, app_id: int):
        """게임 페이지를 가져와서 HTML 구조를 분석합니다."""
        url = f"{self.base_url}{app_id}"
        print(f"분석 중인 게임 URL: {url}")
        
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
                                print("나이 인증 우회 실패")
                                return
                        
                        print(f"HTML 길이: {len(html)} 문자")
                        
                        # BeautifulSoup으로 파싱
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # 다양한 정보 추출 시도
                        self.analyze_game_info(soup)
                        
                        # HTML을 파일로 저장 (분석용)
                        with open(f"data/cyberpunk_html.html", 'w', encoding='utf-8') as f:
                            f.write(html)
                        print("HTML 파일 저장 완료: data/cyberpunk_html.html")
                        
                    else:
                        print(f"HTTP 오류: {response.status}")
                        
        except Exception as e:
            print(f"페이지 가져오기 중 오류: {str(e)}")

    def analyze_game_info(self, soup: BeautifulSoup):
        """HTML에서 추출 가능한 모든 정보를 분석합니다."""
        print("\n=== Steam 게임 페이지 정보 분석 ===\n")
        
        # 1. 게임 제목
        print("1. 게임 제목:")
        title_selectors = [
            'div.apphub_AppName',
            'h1.pageheader', 
            '.game_title h1',
            '#appHubAppName',
            '.apphub_AppName'
        ]
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                print(f"   - {selector}: '{element.get_text(strip=True)}'")
        
        # 2. 게임 태그
        print("\n2. 게임 태그:")
        tag_selectors = [
            'a.app_tag',
            '.popular_tags a',
            '.game_area_details_specs a'
        ]
        for selector in tag_selectors:
            elements = soup.select(selector)
            if elements:
                tags = [tag.get_text(strip=True) for tag in elements[:5]]  # 처음 5개만
                print(f"   - {selector}: {tags}")
        
        # 3. 가격 정보
        print("\n3. 가격 정보:")
        price_selectors = [
            '.game_purchase_price',
            '.discount_final_price',
            '.discount_original_price',
            '.game_area_purchase_game .price'
        ]
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                print(f"   - {selector}: '{element.get_text(strip=True)}'")
        
        # 4. 개발사/퍼블리셔
        print("\n4. 개발사/퍼블리셔:")
        dev_pub_selectors = [
            '.dev_row .summary',
            '.glance_ctn_responsive_left .dev_row',
            '.details_block .summary'
        ]
        for selector in dev_pub_selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements[:3]:  # 처음 3개만
                    print(f"   - {selector}: '{elem.get_text(strip=True)}'")
        
        # 5. 출시일
        print("\n5. 출시일:")
        release_selectors = [
            '.release_date .date',
            '.game_area_release_date .date'
        ]
        for selector in release_selectors:
            element = soup.select_one(selector)
            if element:
                print(f"   - {selector}: '{element.get_text(strip=True)}'")
        
        # 6. 게임 설명
        print("\n6. 게임 설명:")
        desc_selectors = [
            '.game_description_snippet',
            '.game_area_description .game_description_snippet'
        ]
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                desc = element.get_text(strip=True)[:200] + "..." if len(element.get_text(strip=True)) > 200 else element.get_text(strip=True)
                print(f"   - {selector}: '{desc}'")
        
        # 7. 시스템 요구사항
        print("\n7. 시스템 요구사항:")
        sys_req_selectors = [
            '.game_area_sys_req',
            '.sysreq_contents'
        ]
        for selector in sys_req_selectors:
            element = soup.select_one(selector)
            if element:
                req_text = element.get_text(strip=True)[:100] + "..." if len(element.get_text(strip=True)) > 100 else element.get_text(strip=True)
                print(f"   - {selector}: '{req_text}'")
        
        # 8. 평점/리뷰
        print("\n8. 평점/리뷰:")
        review_selectors = [
            '.game_review_summary',
            '.user_reviews_summary_row',
            '.summary .nonresponsive_hidden'
        ]
        for selector in review_selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements[:2]:  # 처음 2개만
                    print(f"   - {selector}: '{elem.get_text(strip=True)}'")
        
        # 9. 스크린샷/미디어
        print("\n9. 스크린샷/미디어:")
        media_selectors = [
            '.highlight_screenshot img',
            '.game_area_screenshot img'
        ]
        for selector in media_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"   - {selector}: {len(elements)}개 이미지 발견")
                for img in elements[:2]:  # 처음 2개만
                    src = img.get('src', '')
                    if src:
                        print(f"     * {src}")
        
        # 10. DLC/추가 콘텐츠
        print("\n10. DLC/추가 콘텐츠:")
        dlc_selectors = [
            '.game_area_dlc_section',
            '.dlc_page_purchase_dlc'
        ]
        for selector in dlc_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"   - {selector}: {len(elements)}개 DLC 섹션 발견")
        
        # 11. 언어 지원
        print("\n11. 언어 지원:")
        lang_selectors = [
            '.game_language_options',
            '.game_area_details_specs .name'
        ]
        for selector in lang_selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements[:3]:  # 처음 3개만
                    text = elem.get_text(strip=True)
                    if '언어' in text or 'Language' in text:
                        print(f"   - {selector}: '{text}'")
        
        # 12. 모든 클래스와 ID 분석
        print("\n12. 주요 클래스/ID 분석:")
        
        # 가장 많이 사용되는 클래스들
        all_classes = []
        for element in soup.find_all(class_=True):
            all_classes.extend(element.get('class', []))
        
        from collections import Counter
        common_classes = Counter(all_classes).most_common(10)
        print("   - 가장 많이 사용되는 클래스:")
        for class_name, count in common_classes:
            print(f"     * .{class_name}: {count}회")
        
        # ID가 있는 요소들
        elements_with_id = soup.find_all(id=True)
        print(f"   - ID가 있는 요소: {len(elements_with_id)}개")
        for elem in elements_with_id[:5]:  # 처음 5개만
            print(f"     * #{elem.get('id')}: {elem.name}")

async def main():
    analyzer = SteamHTMLAnalyzer()
    
    # Cyberpunk 2077 분석
    cyberpunk_id = 1091500
    await analyzer.fetch_and_analyze_game_page(cyberpunk_id)

if __name__ == "__main__":
    asyncio.run(main()) 