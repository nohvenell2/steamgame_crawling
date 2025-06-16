import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Optional

class SingleGameCrawler:
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
        except Exception:
            return None

    async def get_game_tags(self, app_id: int) -> List[str]:
        """게임 ID를 입력받아 태그 목록을 반환합니다."""
        url = f"{self.base_url}{app_id}"
        
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
                        
                        # 태그 추출
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
                    else:
                        return []
                        
        except Exception:
            return []


# 편의 함수
async def get_steam_game_tags(app_id: int) -> List[str]:
    """
    Steam 게임 ID를 입력받아 태그 목록을 반환하는 함수
    
    Args:
        app_id (int): Steam 게임 ID
        
    Returns:
        List[str]: 게임 태그 목록
        
    Example:
        tags = await get_steam_game_tags(1091500)  # Cyberpunk 2077
        print(tags)  # ['Cyberpunk', 'Open World', 'RPG', ...]
    """
    crawler = SingleGameCrawler()
    return await crawler.get_game_tags(app_id)


# 동기 버전 (asyncio.run 사용)
def get_steam_game_tags_sync(app_id: int) -> List[str]:
    """
    Steam 게임 ID를 입력받아 태그 목록을 반환하는 동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        
    Returns:
        List[str]: 게임 태그 목록
        
    Example:
        tags = get_steam_game_tags_sync(1091500)  # Cyberpunk 2077
        print(tags)  # ['Cyberpunk', 'Open World', 'RPG', ...]
    """
    return asyncio.run(get_steam_game_tags(app_id))


# 테스트용 메인 함수
async def main():
    # 테스트
    test_games = [
        (1091500, "Cyberpunk 2077"),
        (570, "Dota 2"),
        (730, "Counter-Strike 2")
    ]
    
    for app_id, title in test_games:
        tags = await get_steam_game_tags(app_id)
        print(f"{title} (ID: {app_id}): {tags}")


if __name__ == "__main__":
    print(get_steam_game_tags_sync(1284790))