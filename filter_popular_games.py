import requests
import csv
import time
import json
from typing import List, Dict, Set
from tqdm import tqdm

class SteamGameFilter:
    def __init__(self):
        self.steam_spy_base_url = "https://steamspy.com/api.php"
        self.steam_reviews_base_url = "https://store.steampowered.com/appreviews"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.filtered_games = set()
        
    def get_steam_spy_data(self, request_type: str, **params) -> Dict:
        """Steam Spy API 호출"""
        try:
            params_dict = {"request": request_type}
            params_dict.update(params)
            
            response = requests.get(self.steam_spy_base_url, params=params_dict, headers=self.headers)
            response.raise_for_status()
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Steam Spy API 오류: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"Steam Spy API 호출 실패: {str(e)}")
            return {}
    
    def get_game_review_count(self, app_id: int) -> int:
        """Steam Reviews API로 게임의 총 리뷰 수 확인"""
        try:
            url = f"{self.steam_reviews_base_url}/{app_id}"
            params = {
                "json": 1,
                "language": "all",
                "filter": "recent",
                "num_per_page": 1  # 리뷰 수만 확인하므로 1개만 요청
            }
            
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") == 1:
                    query_summary = data.get("query_summary", {})
                    return query_summary.get("total_reviews", 0)
            
            return 0
            
        except Exception as e:
            print(f"게임 {app_id} 리뷰 정보 조회 실패: {str(e)}")
            return 0
    
    def get_popular_games_from_steamspy(self) -> Set[int]:
        """Steam Spy에서 인기 게임들 수집"""
        popular_games = set()
        
        print("📊 Steam Spy에서 인기 게임 목록 수집 중...")
        
        # 1. 소유자 수 상위 100개 게임
        print("- 소유자 수 상위 100개 게임 수집...")
        top_owned = self.get_steam_spy_data("top100owned")
        if top_owned:
            for game_data in top_owned.values():
                if isinstance(game_data, dict) and "appid" in game_data:
                    popular_games.add(int(game_data["appid"]))
        
        # 2. 최근 2주 플레이어 수 상위 100개 게임
        print("- 최근 2주 플레이어 수 상위 100개 게임 수집...")
        top_2weeks = self.get_steam_spy_data("top100in2weeks")
        if top_2weeks:
            for game_data in top_2weeks.values():
                if isinstance(game_data, dict) and "appid" in game_data:
                    popular_games.add(int(game_data["appid"]))
        
        # 3. 평생 플레이어 수 상위 100개 게임
        print("- 평생 플레이어 수 상위 100개 게임 수집...")
        top_forever = self.get_steam_spy_data("top100forever")
        if top_forever:
            for game_data in top_forever.values():
                if isinstance(game_data, dict) and "appid" in game_data:
                    popular_games.add(int(game_data["appid"]))
        
        # 4. 인기 장르별 게임들 추가
        popular_genres = ["Action", "Adventure", "RPG", "Strategy", "Simulation", "Indie"]
        for genre in popular_genres:
            print(f"- {genre} 장르 게임 수집...")
            genre_games = self.get_steam_spy_data("genre", genre=genre)
            if genre_games:
                # 상위 50개만 선택 (너무 많으면 API 호출이 과도해짐)
                count = 0
                for game_data in genre_games.values():
                    if isinstance(game_data, dict) and "appid" in game_data:
                        popular_games.add(int(game_data["appid"]))
                        count += 1
                        if count >= 50:  # 장르당 최대 50개
                            break
            
            time.sleep(1)  # API 요청 간격 조절
        
        print(f"✅ Steam Spy에서 총 {len(popular_games)}개의 게임을 수집했습니다.")
        return popular_games
    
    def filter_games_by_reviews(self, game_ids: Set[int], min_reviews: int = 100) -> List[Dict]:
        """리뷰 수로 게임 필터링"""
        print(f"\n🔍 리뷰 수 {min_reviews}개 이상인 게임만 필터링 중...")
        
        filtered_games = []
        failed_games = []
        
        for app_id in tqdm(game_ids, desc="게임 리뷰 수 확인"):
            try:
                review_count = self.get_game_review_count(app_id)
                
                if review_count >= min_reviews:
                    filtered_games.append({
                        "app_id": app_id,
                        "review_count": review_count
                    })
                    print(f"✓ 게임 {app_id}: {review_count}개 리뷰 - 포함")
                else:
                    print(f"✗ 게임 {app_id}: {review_count}개 리뷰 - 제외")
                
                # API 요청 제한을 위한 대기
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ 게임 {app_id} 처리 실패: {str(e)}")
                failed_games.append(app_id)
                continue
        
        # 리뷰 수 순으로 정렬
        filtered_games.sort(key=lambda x: x["review_count"], reverse=True)
        
        print(f"\n✅ 총 {len(filtered_games)}개의 게임이 리뷰 수 {min_reviews}개 이상 조건을 만족합니다.")
        if failed_games:
            print(f"⚠️ {len(failed_games)}개 게임의 정보를 가져오지 못했습니다.")
        
        return filtered_games
    
    def save_to_csv(self, games_data: List[Dict], output_file: str):
        """필터링된 게임 목록을 CSV 파일로 저장"""
        print(f"\n💾 결과를 {output_file}에 저장 중...")
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                # 게임 ID만 저장 (기존 형식 유지)
                for game in games_data:
                    csvfile.write(f"{game['app_id']}\n")
            
            print(f"✅ {len(games_data)}개 게임 ID를 {output_file}에 저장했습니다.")
            
            # 추가로 상세 정보가 포함된 파일도 저장
            detailed_file = output_file.replace('.csv', '_detailed.csv')
            with open(detailed_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['app_id', 'review_count'])
                for game in games_data:
                    writer.writerow([game['app_id'], game['review_count']])
            
            print(f"✅ 상세 정보를 {detailed_file}에 저장했습니다.")
            
        except Exception as e:
            print(f"❌ 파일 저장 실패: {str(e)}")
    
    def run_filtering(self, min_reviews: int = 100, output_file: str = "data/steam_game_id_list.csv"):
        """전체 필터링 과정 실행"""
        print("🎮 Steam 게임 필터링 시작!")
        print(f"조건: 리뷰 수 {min_reviews}개 이상")
        print("-" * 50)
        
        # 1. Steam Spy에서 인기 게임 수집
        popular_games = self.get_popular_games_from_steamspy()
        
        if not popular_games:
            print("❌ 인기 게임 목록을 가져오는데 실패했습니다.")
            return
        
        # 2. 리뷰 수로 필터링
        filtered_games = self.filter_games_by_reviews(popular_games, min_reviews)
        
        if not filtered_games:
            print("❌ 조건을 만족하는 게임이 없습니다.")
            return
        
        # 3. CSV 파일로 저장
        self.save_to_csv(filtered_games, output_file)
        
        print("\n" + "="*50)
        print("🎯 필터링 완료!")
        print(f"📊 총 {len(filtered_games)}개의 인기 게임을 선별했습니다.")
        print(f"📄 결과 파일: {output_file}")
        print("="*50)

def main():
    """메인 실행 함수"""
    filter_manager = SteamGameFilter()
    
    # 사용자 설정
    MIN_REVIEWS = 100  # 최소 리뷰 수
    OUTPUT_FILE = "data/steam_game_id_list.csv"
    
    print("🎮 Steam 인기 게임 필터링 도구")
    print("=" * 50)
    print(f"최소 리뷰 수: {MIN_REVIEWS}개")
    print(f"출력 파일: {OUTPUT_FILE}")
    print("=" * 50)
    
    user_input = input("계속 진행하시겠습니까? (y/N): ")
    if user_input.lower() not in ['y', 'yes']:
        print("작업이 취소되었습니다.")
        return
    
    # 필터링 실행
    filter_manager.run_filtering(min_reviews=MIN_REVIEWS, output_file=OUTPUT_FILE)

if __name__ == "__main__":
    main() 