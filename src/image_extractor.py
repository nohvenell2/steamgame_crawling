import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Optional

class SteamImageExtractor:
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

    def extract_header_image(self, soup: BeautifulSoup, app_id: int) -> List[str]:
        """Steam 게임 페이지에서 헤더 이미지만 추출합니다."""
        header_images = []
        
        print("헤더 이미지 추출:")
        
        # 1. HTML에서 헤더 이미지 찾기
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
                    print(f"   - 페이지 헤더 이미지: {src}")
        
        # 2. Steam의 표준 헤더 이미지 URL 패턴 추가
        standard_header_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg"
        if standard_header_url not in header_images:
            header_images.append(standard_header_url)
            print(f"   - 표준 헤더 이미지: {standard_header_url}")
        
        return header_images

    async def get_game_header_image(self, app_id: int) -> List[str]:
        """게임 ID를 입력받아 헤더 이미지 URL을 반환합니다."""
        url = f"{self.base_url}{app_id}"
        print(f"헤더 이미지 추출 중: {url}")
        
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
                                return []
                        
                        soup = BeautifulSoup(html, 'html.parser')
                        return self.extract_header_image(soup, app_id)
                    else:
                        print(f"HTTP 오류: {response.status}")
                        return []
                        
        except Exception as e:
            print(f"헤더 이미지 추출 중 오류: {str(e)}")
            return []


# 편의 함수
async def get_steam_game_header_image(app_id: int) -> List[str]:
    """
    Steam 게임 ID를 입력받아 헤더 이미지 URL 목록을 반환하는 함수
    
    Args:
        app_id (int): Steam 게임 ID
        
    Returns:
        List[str]: 헤더 이미지 URL 목록
        
    Example:
        images = await get_steam_game_header_image(1091500)  # Cyberpunk 2077
        print(images[0])  # 첫 번째 헤더 이미지 URL
    """
    extractor = SteamImageExtractor()
    return await extractor.get_game_header_image(app_id)


# 동기 버전
def get_steam_game_header_image_sync(app_id: int) -> List[str]:
    """
    Steam 게임 ID를 입력받아 헤더 이미지 URL 목록을 반환하는 동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        
    Returns:
        List[str]: 헤더 이미지 URL 목록
        
    Example:
        images = get_steam_game_header_image_sync(1091500)  # Cyberpunk 2077
        print(images[0])  # 첫 번째 헤더 이미지 URL
    """
    return asyncio.run(get_steam_game_header_image(app_id))


async def main():
    extractor = SteamImageExtractor()
    
    # 테스트 게임 ID
    test_id = 2456740
    header_images = await extractor.get_game_header_image(test_id)
    
    # 결과 출력
    print(f"\n=== 추출된 헤더 이미지 ===")
    print(f"총 {len(header_images)}개의 헤더 이미지 발견")
    
    for i, image_url in enumerate(header_images, 1):
        print(f"{i}. {image_url}")
    
    if header_images:
        print(f"\n메인 헤더 이미지: {header_images[0]}")

if __name__ == "__main__":
    asyncio.run(main()) 