#!/usr/bin/env python3
"""Steam Game Crawler to Database Runner

크롤링 데이터를 바로 데이터베이스에 저장하는 간단한 실행 스크립트
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

from crawler_to_db import (
    crawl_single_game_to_db,
    crawl_multiple_games_to_db,
    CrawlerToDatabase,
    setup_logging
)
from database.connection import test_connection


def print_usage():
    """사용법 출력"""
    print("🎯 Steam 게임 크롤러 → 데이터베이스 저장")
    print("=" * 50)
    print("사용법:")
    print("  python run_crawler_to_db.py <명령> [인수...]")
    print()
    print("명령:")
    print("  single <app_id>     : 단일 게임 크롤링 및 저장")
    print("  list <app_id1,app_id2,...> : 여러 게임 크롤링 및 저장")
    print("  file <파일경로>      : 파일에서 게임 ID 목록 읽어서 처리")
    print("  test               : 테스트 게임들 크롤링")
    print()
    print("예시:")
    print("  python run_crawler_to_db.py single 1091500")
    print("  python run_crawler_to_db.py list 1091500,570,730")
    print("  python run_crawler_to_db.py file game_ids.txt")
    print("  python run_crawler_to_db.py test")


async def run_single(app_id: int):
    """단일 게임 크롤링"""
    print(f"📥 게임 {app_id} 크롤링 시작...")
    success = await crawl_single_game_to_db(app_id)
    
    if success:
        print(f"✅ 게임 {app_id} 저장 완료!")
    else:
        print(f"❌ 게임 {app_id} 저장 실패!")
    
    return success


async def run_multiple(app_ids: list[int]):
    """여러 게임 크롤링"""
    print(f"📥 {len(app_ids)}개 게임 크롤링 시작...")
    print(f"게임 ID: {', '.join(map(str, app_ids))}")
    
    results = await crawl_multiple_games_to_db(app_ids, delay=2.0)
    
    print(f"\n📊 크롤링 결과:")
    print(f"   총 처리: {results['total']}개")
    print(f"   성공: {results['success']}개")
    print(f"   실패: {results['failed']}개")
    print(f"   성공률: {results['success']/results['total']*100:.1f}%")
    
    return results['success'] > 0


async def run_from_file(file_path: str):
    """파일에서 게임 ID 목록 읽어서 크롤링"""
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {file_path_obj}")
        return False
    
    print(f"📄 파일에서 게임 ID 읽는 중: {file_path_obj}")
    
    crawler_db = CrawlerToDatabase()
    results = await crawler_db.crawl_and_save_from_file(file_path)
    
    print(f"\n📊 크롤링 결과:")
    print(f"   총 처리: {results['total']}개")
    print(f"   성공: {results['success']}개")
    print(f"   실패: {results['failed']}개")
    
    if results['total'] > 0:
        print(f"   성공률: {results['success']/results['total']*100:.1f}%")
    
    return results['success'] > 0


async def run_test():
    """테스트 게임들 크롤링"""
    test_games = [
        (1091500, "Cyberpunk 2077"),
        (570, "Dota 2"),
        (730, "Counter-Strike 2")
    ]
    
    print("🧪 테스트 게임들 크롤링 시작...")
    
    app_ids = [game[0] for game in test_games]
    success = await run_multiple(app_ids)
    
    if success:
        print("✅ 테스트 완료!")
    else:
        print("❌ 테스트 실패!")
    
    return success


async def main():
    """메인 함수"""
    # 로깅 설정
    setup_logging("INFO")
    
    # 인수 확인
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    # 데이터베이스 연결 테스트
    print("🔌 데이터베이스 연결 확인 중...")
    if not test_connection():
        print("❌ 데이터베이스 연결 실패!")
        print("환경변수(.env)를 확인하고 MySQL 서버가 실행 중인지 확인하세요.")
        return
    print("✅ 데이터베이스 연결 성공!\n")
    
    try:
        if command == "single":
            if len(sys.argv) < 3:
                print("❌ 게임 ID를 입력하세요.")
                print("예시: python run_crawler_to_db.py single 1091500")
                return
            
            app_id = int(sys.argv[2])
            await run_single(app_id)
        
        elif command == "list":
            if len(sys.argv) < 3:
                print("❌ 게임 ID 목록을 입력하세요.")
                print("예시: python run_crawler_to_db.py list 1091500,570,730")
                return
            
            app_ids_str = sys.argv[2]
            app_ids = [int(x.strip()) for x in app_ids_str.split(',')]
            await run_multiple(app_ids)
        
        elif command == "file":
            if len(sys.argv) < 3:
                print("❌ 파일 경로를 입력하세요.")
                print("예시: python run_crawler_to_db.py file game_ids.txt")
                return
            
            file_path = sys.argv[2]
            await run_from_file(file_path)
        
        elif command == "test":
            await run_test()
        
        else:
            print(f"❌ 알 수 없는 명령: {command}")
            print_usage()
    
    except ValueError as e:
        print(f"❌ 잘못된 입력: {e}")
        print_usage()
    except KeyboardInterrupt:
        print("\n⏹️  사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 