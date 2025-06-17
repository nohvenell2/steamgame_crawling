import requests
from typing import Set, Optional

class SteamGameList:
    def __init__(self):
        self.steam_reviews_base_url = "https://store.steampowered.com/appreviews"
        self.steam_api_base_url = "http://api.steampowered.com/ISteamApps/GetAppList/v0002/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    def get_all_steam_games(self, limit: Optional[int] = None) -> Set[int]:
        """Steam API에서 모든 게임 목록을 가져옵니다."""
        try:
            print("📋 Steam API에서 게임 목록을 가져오는 중...")
            response = requests.get(self.steam_api_base_url, headers=self.headers)
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
                
                print(f"✅ 총 {len(game_ids)}개의 게임 ID를 가져왔습니다.")
                return game_ids
            else:
                print(f"Steam API 오류: {response.status_code}")
                return set()
                
        except Exception as e:
            print(f"Steam API 호출 실패: {str(e)}")
            return set()
if __name__ == "__main__":
    steam_game_list = SteamGameList()
    result = steam_game_list.get_all_steam_games(limit=100)
    print(result)