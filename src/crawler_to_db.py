"""Steam Game Crawler to Database

single_game_crawler의 크롤링 기능과 database.inserter를 연결하여
크롤링한 데이터를 바로 데이터베이스에 저장하는 모듈
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# 크롤링 모듈 import
from single_game_crawler import get_steam_game_info, ComprehensiveGameCrawler
from database.inserter import GameInserter
from database.connection import test_connection

# 로거 설정
logger = logging.getLogger(__name__)


class CrawlerToDatabase:
    """크롤링 데이터를 바로 데이터베이스에 저장하는 클래스"""
    
    def __init__(self, max_retries: int = 7):
        self.max_retries = max_retries
        self.crawler = ComprehensiveGameCrawler()
    
    async def crawl_and_save_game(self, app_id: int) -> bool:
        """단일 게임을 크롤링하고 데이터베이스에 저장"""
        try:
            logger.info(f"게임 {app_id} 크롤링 시작")
            
            # 크롤링 실행
            game_info = await get_steam_game_info(app_id, self.max_retries)
            
            if not game_info:
                logger.warning(f"게임 {app_id}: 크롤링 데이터 없음")
                return False
            
            # 데이터베이스에 저장
            with GameInserter() as inserter:
                success = inserter.insert_game_from_dict(game_info)
                
            if success:
                logger.info(f"✅ 게임 {app_id} ({game_info.get('title', 'Unknown')}) DB 저장 완료")
                return True
            else:
                logger.error(f"❌ 게임 {app_id} DB 저장 실패")
                return False
                
        except Exception as e:
            logger.error(f"게임 {app_id} 처리 중 오류: {e}")
            return False
    
    async def crawl_and_save_multiple_games(
        self, 
        app_ids: List[int], 
        delay_between_requests: float = 2.0
    ) -> Dict[str, int]:
        """여러 게임을 순차적으로 크롤링하고 저장"""
        results = {
            'success': 0,
            'failed': 0,
            'total': len(app_ids)
        }
        
        logger.info(f"총 {len(app_ids)}개 게임 크롤링 시작")
        
        for i, app_id in enumerate(app_ids, 1):
            logger.info(f"진행률: {i}/{len(app_ids)} ({i/len(app_ids)*100:.1f}%)")
            
            # 크롤링 및 저장
            success = await self.crawl_and_save_game(app_id)
            
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
            
            # 요청 간 딜레이 (API 부하 방지)
            if i < len(app_ids):  # 마지막이 아니면 딜레이
                logger.debug(f"{delay_between_requests}초 대기 중...")
                await asyncio.sleep(delay_between_requests)
        
        logger.info(f"배치 크롤링 완료: 성공 {results['success']}개, 실패 {results['failed']}개")
        return results
    
    async def crawl_and_save_from_file(self, file_path: str) -> Dict[str, int]:
        """파일에서 게임 ID 목록을 읽어서 크롤링 및 저장"""
        try:
            app_ids = []
            file_path_obj = Path(file_path)
            
            if file_path_obj.suffix == '.txt':
                # 텍스트 파일에서 한 줄씩 읽기
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and line.isdigit():
                            app_ids.append(int(line))
            
            elif file_path_obj.suffix == '.csv':
                # CSV 파일에서 읽기 (첫 번째 컬럼이 app_id라고 가정)
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)  # 헤더 스킵
                    for row in reader:
                        if row and row[0].isdigit():
                            app_ids.append(int(row[0]))
            
            else:
                raise ValueError("지원되지 않는 파일 형식입니다. .txt 또는 .csv 파일을 사용하세요.")
            
            logger.info(f"파일에서 {len(app_ids)}개 게임 ID 읽음: {file_path_obj}")
            
            if not app_ids:
                logger.warning("파일에서 유효한 게임 ID를 찾을 수 없습니다.")
                return {'success': 0, 'failed': 0, 'total': 0}
            
            # 크롤링 및 저장 실행
            return await self.crawl_and_save_multiple_games(app_ids)
            
        except Exception as e:
            logger.error(f"파일 처리 중 오류: {e}")
            return {'success': 0, 'failed': 0, 'total': 0}


# 편의 함수들
async def crawl_single_game_to_db(app_id: int, max_retries: int = 7) -> bool:
    """단일 게임을 크롤링해서 바로 DB에 저장하는 편의 함수"""
    crawler_db = CrawlerToDatabase(max_retries)
    return await crawler_db.crawl_and_save_game(app_id)


async def crawl_multiple_games_to_db(
    app_ids: List[int], 
    max_retries: int = 7,
    delay: float = 2.0
) -> Dict[str, int]:
    """여러 게임을 크롤링해서 바로 DB에 저장하는 편의 함수"""
    crawler_db = CrawlerToDatabase(max_retries)
    return await crawler_db.crawl_and_save_multiple_games(app_ids, delay)


def crawl_single_game_to_db_sync(app_id: int, max_retries: int = 7) -> bool:
    """단일 게임을 크롤링해서 바로 DB에 저장하는 동기 함수"""
    return asyncio.run(crawl_single_game_to_db(app_id, max_retries))


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """로깅 설정"""
    log_level = getattr(logging, level.upper())
    
    # 로그 포맷
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택사항)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


async def main():
    """메인 함수 - 테스트 및 예시"""
    # 로깅 설정
    setup_logging("INFO")
    
    print("🎯 Steam 게임 크롤러 → 데이터베이스 저장 시스템")
    print("=" * 60)
    
    # 데이터베이스 연결 테스트
    print("1. 데이터베이스 연결 테스트...")
    if test_connection():
        print("   ✅ 데이터베이스 연결 성공!")
    else:
        print("   ❌ 데이터베이스 연결 실패!")
        print("   환경변수(.env)를 확인하고 MySQL 서버가 실행 중인지 확인하세요.")
        return
    
    # 크롤링 및 저장 테스트
    print("\n2. 테스트 게임 크롤링 및 저장...")
    
    test_games = [
        (1091500, "Cyberpunk 2077"),
        (570, "Dota 2"),
        (730, "Counter-Strike 2")
    ]
    
    crawler_db = CrawlerToDatabase()
    
    # 개별 테스트
    for app_id, expected_title in test_games:
        print(f"\n📥 크롤링 중: {expected_title} (ID: {app_id})")
        success = await crawler_db.crawl_and_save_game(app_id)
        
        if success:
            print(f"   ✅ {expected_title} 저장 완료!")
        else:
            print(f"   ❌ {expected_title} 저장 실패!")
    
    # 배치 테스트
    print(f"\n3. 배치 크롤링 테스트...")
    app_ids = [game[0] for game in test_games]
    results = await crawler_db.crawl_and_save_multiple_games(app_ids, delay_between_requests=1.0)
    
    print(f"\n📊 배치 크롤링 결과:")
    print(f"   총 처리: {results['total']}개")
    print(f"   성공: {results['success']}개")
    print(f"   실패: {results['failed']}개")
    print(f"   성공률: {results['success']/results['total']*100:.1f}%")
    
    print(f"\n✅ 테스트 완료!")
    print(f"💡 이제 크롤링한 데이터가 바로 데이터베이스에 저장됩니다!")


if __name__ == "__main__":
    # 환경변수 로드
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(main()) 