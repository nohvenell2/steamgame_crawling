import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Optional
import time

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

    async def get_game_tags_with_retry(self, app_id: int, max_retries: int = 7) -> List[str]:
        """재시도 로직이 포함된 게임 태그 추출 함수"""
        url = f"{self.base_url}{app_id}"
        
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
                        
                        # 요청 제한 관련 상태 코드
                        elif response.status in [429, 503, 502, 504]:
                            if attempt < max_retries:
                                # 지수적으로 증가하는 딜레이 (10초, 20초, 40초, 80초, 160초, 320초, 640초)
                                delay = 2 * (2 ** attempt)
                                print(f"  ⚠️  게임 ID {app_id}: HTTP {response.status} - {attempt + 1}회 실패, {delay}초 후 재시도...")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                print(f"  ❌ 게임 ID {app_id}: HTTP {response.status} - 최대 재시도 횟수 초과")
                                raise Exception(f"HTTP {response.status}: 최대 재시도 횟수({max_retries})를 초과했습니다. 요청이 지속적으로 거부되고 있습니다.")
                        
                        # 기타 HTTP 에러
                        else:
                            print(f"  ❌ 게임 ID {app_id}: HTTP {response.status} 오류")
                            return []
                            
            except Exception as e:
                if attempt < max_retries and "HTTP" in str(e) and any(code in str(e) for code in ["429", "503", "502", "504"]):
                    # 재시도 가능한 네트워크 오류
                    delay = 10 * (2 ** attempt)
                    print(f"  ⚠️  게임 ID {app_id}: 네트워크 오류 - {attempt + 1}회 실패, {delay}초 후 재시도... ({str(e)})")
                    await asyncio.sleep(delay)
                    continue
                elif attempt == max_retries:
                    print(f"  ❌ 게임 ID {app_id}: 최대 재시도 횟수 초과 - {str(e)}")
                    raise Exception(f"최대 재시도 횟수({max_retries})를 초과했습니다. 마지막 오류: {str(e)}")
                else:
                    print(f"  ❌ 게임 ID {app_id}: 크롤링 오류 - {str(e)}")
                    return []
        
        return []

    async def get_game_tags(self, app_id: int) -> List[str]:
        """기존 호환성을 위한 래퍼 함수"""
        return await self.get_game_tags_with_retry(app_id)


# 편의 함수
async def get_steam_game_tags(app_id: int, max_retries: int = 7) -> List[str]:
    """
    Steam 게임 ID를 입력받아 태그 목록을 반환하는 함수
    
    Args:
        app_id (int): Steam 게임 ID
        max_retries (int): 최대 재시도 횟수 (기본값: 7 - 총 대기시간 약 5분)
        
    Returns:
        List[str]: 게임 태그 목록
        
    Example:
        tags = await get_steam_game_tags(1091500)  # Cyberpunk 2077
        print(tags)  # ['Cyberpunk', 'Open World', 'RPG', ...]
    """
    crawler = SingleGameCrawler()
    return await crawler.get_game_tags_with_retry(app_id, max_retries)


# 동기 버전 (asyncio.run 사용)
def get_steam_game_tags_sync(app_id: int, max_retries: int = 7) -> List[str]:
    """
    Steam 게임 ID를 입력받아 태그 목록을 반환하는 동기 함수
    
    Args:
        app_id (int): Steam 게임 ID
        max_retries (int): 최대 재시도 횟수 (기본값: 7 - 총 대기시간 약 5분)
        
    Returns:
        List[str]: 게임 태그 목록
        
    Example:
        tags = get_steam_game_tags_sync(1091500)  # Cyberpunk 2077
        print(tags)  # ['Cyberpunk', 'Open World', 'RPG', ...]
    """
    return asyncio.run(get_steam_game_tags(app_id, max_retries))


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
    print(get_steam_game_tags_sync(1284790)) # 로그인 필요 게임
    #print(get_steam_game_tags_sync(1245620)) # 로그인이 필요없는 나이제한 게임