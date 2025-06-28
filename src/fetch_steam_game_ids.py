"""
Steam 게임 ID 목록 수집 모듈

Steam API를 사용하여 Steam 플랫폼에서 사용 가능한 모든 게임의 ID 목록을 가져오는 단순한 모듈입니다.
다른 크롤링 모듈에서 게임 ID가 필요할 때 사용할 수 있는 기본 데이터를 제공합니다.

주요 기능:
- Steam GetAppList API를 통한 전체 게임 ID 수집
- 선택적 제한 옵션 (테스트용)
- 중복 제거된 게임 ID Set 반환

사용 예시:
```python
from fetch_steam_game_ids import get_all_steam_games

# 전체 게임 ID 가져오기
all_game_ids = get_all_steam_games()
print(f"총 {len(all_game_ids)}개의 게임 ID")

# 제한된 개수만 가져오기 (테스트용)
limited_ids = get_all_steam_games(limit=100)
```
"""

import requests
from typing import Set, Optional
import logging
from utils.logger import setup_logger

# 로거 설정
logger = logging.getLogger(__name__)

def get_all_steam_games(limit: Optional[int] = None) -> Set[int]:
    """Steam API에서 모든 게임 목록을 가져옵니다."""
    steam_api_base_url = "http://api.steampowered.com/ISteamApps/GetAppList/v0002/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        logger.info("[API] Steam API에서 게임 목록을 가져오는 중...")
        response = requests.get(steam_api_base_url, headers=headers)
        response.raise_for_status()
        
        if response.status_code == 200:
            data = response.json()
            apps = data.get('applist', {}).get('apps', [])
            
            game_ids = set()
            for app in apps:
                app_id = app.get('appid')
                if app_id:
                    game_ids.add(int(app_id))
                    
                    # 제한이 설정된 경우 해당 수만큼만 가져오기
                    if limit and len(game_ids) >= limit:
                        break
            
            logger.info(f"총 {len(game_ids)}개의 게임 ID를 가져왔습니다.")
            return game_ids
        else:
            logger.error(f"Steam API 오류: {response.status_code}")
            return set()
            
    except Exception as e:
        logger.error(f"Steam API 호출 실패: {str(e)}")
        return set()


if __name__ == "__main__":
<<<<<<< HEAD
    steam_game_list = SteamGameList()
    result = steam_game_list.get_all_steam_games(limit=10)
=======
    setup_logger("INFO")
    result = get_all_steam_games(limit=10)
>>>>>>> feature/integrate-latest-with-db
    print(result)