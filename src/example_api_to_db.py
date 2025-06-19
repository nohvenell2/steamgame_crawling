import logging
from utils.logger import setup_logger
from fetch_steam_game_data import get_steam_game_info_api_sync
from single_game_crawler_minimal import get_steam_game_info_crawler_minimal_sync
from database.inserter import insert_steam_api_game_single, insert_steam_crawling_game_single

logger = logging.getLogger(__name__)

def test_data_to_db(ids):
    for game_id in ids:
        # api 데이터 수집
        data1 = get_steam_game_info_api_sync(game_id).get('data')
        # api 데이터 삽입
        insert_steam_api_game_single(data1) if data1 else None
        # 크롤링 데이터 수집
        data2 = get_steam_game_info_crawler_minimal_sync(game_id).get('data')
        # 크롤링 데이터 삽입
        insert_steam_crawling_game_single(data2) if data2 else None


if __name__ == "__main__":
    setup_logger("DEBUG")
    test_data_to_db(
        [
            15100, # 어쌔신크리드1
            812140, # 오딧세이
            3489700, # 스텔라 블레이드
            1284790, # 로그인 필수 게임
            238960, # poe - 지역락 게임
            1091500, # cp
            1222670, # sims
            1245620, # elden
            2456740, # inzoi
         ]
    )
