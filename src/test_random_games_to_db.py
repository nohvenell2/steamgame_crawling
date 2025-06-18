#!/usr/bin/env python3
"""Random Steam Games to Database Test

Steam API에서 모든 게임 ID를 가져온 후 랜덤한 10개를 선택하여
crawler_to_db를 이용해 데이터베이스에 저장하는 테스트 스크립트
"""

import asyncio
import random
import sys
from typing import List
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

from fetch_steam_game_ids import SteamGameList
from crawler_to_db import CrawlerToDatabase, setup_logging
from database.connection import test_connection


class RandomGamesTester:
    """랜덤 게임 크롤링 테스터"""
    
    def __init__(self, sample_size: int = 10, max_retries: int = 7):
        self.sample_size = sample_size
        self.max_retries = max_retries
        self.steam_game_list = SteamGameList()
        self.crawler_db = CrawlerToDatabase(max_retries)
    
    def get_random_game_ids(self) -> List[int]:
        """Steam API에서 모든 게임 ID를 가져와서 랜덤하게 선택"""
        print("🎲 Steam API에서 게임 목록 가져오는 중...")
        
        # 모든 게임 ID 가져오기 (limit=None)
        all_game_ids = self.steam_game_list.get_all_steam_games(limit=None)
        
        if not all_game_ids:
            print("❌ Steam API에서 게임 목록을 가져올 수 없습니다.")
            return []
        
        print(f"📋 총 {len(all_game_ids)}개의 게임 ID를 가져왔습니다.")
        
        # 랜덤하게 선택
        if len(all_game_ids) < self.sample_size:
            print(f"⚠️  요청한 샘플 수({self.sample_size})가 전체 게임 수({len(all_game_ids)})보다 큽니다.")
            sample_size = len(all_game_ids)
        else:
            sample_size = self.sample_size
        
        random_game_ids = random.sample(list(all_game_ids), sample_size)
        
        print(f"🎯 랜덤하게 선택된 {len(random_game_ids)}개 게임:")
        for i, game_id in enumerate(random_game_ids, 1):
            print(f"   {i}. {game_id}")
        
        return random_game_ids
    
    async def test_random_games_crawling(self) -> dict:
        """랜덤 게임들을 크롤링하여 DB에 저장하는 테스트"""
        print("\n" + "="*60)
        print("🧪 랜덤 게임 크롤링 & DB 저장 테스트 시작")
        print("="*60)
        
        # 1. 데이터베이스 연결 테스트
        print("\n1️⃣ 데이터베이스 연결 확인...")
        if not test_connection():
            print("❌ 데이터베이스 연결 실패!")
            print("환경변수(.env)를 확인하고 MySQL 서버가 실행 중인지 확인하세요.")
            return {'success': 0, 'failed': 0, 'total': 0}
        print("✅ 데이터베이스 연결 성공!")
        
        # 2. 랜덤 게임 ID 선택
        print("\n2️⃣ 랜덤 게임 ID 선택...")
        random_game_ids = self.get_random_game_ids()
        
        if not random_game_ids:
            print("❌ 랜덤 게임 ID를 가져올 수 없습니다.")
            return {'success': 0, 'failed': 0, 'total': 0}
        
        # 3. 크롤링 및 DB 저장
        print(f"\n3️⃣ {len(random_game_ids)}개 게임 크롤링 & DB 저장...")
        print("⏱️  예상 소요 시간: 약 {:.1f}분".format(len(random_game_ids) * 2.5 / 60))
        
        results = await self.crawler_db.crawl_and_save_multiple_games(
            random_game_ids, 
            delay_between_requests=2.0
        )
        
        return results
    
    async def test_with_specific_games(self, game_ids: List[int]) -> dict:
        """특정 게임 ID들로 테스트"""
        print(f"\n🎯 특정 게임 ID들로 테스트: {game_ids}")
        
        # 데이터베이스 연결 확인
        if not test_connection():
            print("❌ 데이터베이스 연결 실패!")
            return {'success': 0, 'failed': 0, 'total': 0}
        
        results = await self.crawler_db.crawl_and_save_multiple_games(
            game_ids,
            delay_between_requests=1.5
        )
        
        return results


def print_results(results: dict):
    """결과 출력"""
    print("\n" + "="*60)
    print("📊 최종 결과")
    print("="*60)
    
    total = results.get('total', 0)
    success = results.get('success', 0)
    failed = results.get('failed', 0)
    
    print(f"총 처리: {total}개")
    print(f"성공: {success}개 ✅")
    print(f"실패: {failed}개 ❌")
    
    if total > 0:
        success_rate = (success / total) * 100
        print(f"성공률: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 훌륭한 성공률입니다!")
        elif success_rate >= 60:
            print("👍 양호한 성공률입니다.")
        elif success_rate >= 40:
            print("⚠️ 성공률이 낮습니다. 네트워크나 API 상태를 확인해보세요.")
        else:
            print("🚨 성공률이 매우 낮습니다. 시스템 점검이 필요합니다.")
    
    print("\n💡 팁:")
    print("- 실패한 게임들은 주로 DLC나 접근 불가능한 게임일 수 있습니다.")
    print("- 네트워크 상태가 불안정하면 재시도 해보세요.")
    print("- 더 많은 게임을 테스트하려면 sample_size를 늘려보세요.")


async def main():
    """메인 함수"""
    # 로깅 설정
    setup_logging("INFO", "logs/random_games_test.log")
    
    print("🎮 Steam 랜덤 게임 크롤링 & DB 저장 테스트")
    print("=" * 60)
    
    # 명령줄 인수 확인
    sample_size = 10
    if len(sys.argv) > 1:
        try:
            sample_size = int(sys.argv[1])
            if sample_size <= 0:
                raise ValueError("샘플 크기는 양수여야 합니다.")
        except ValueError as e:
            print(f"❌ 잘못된 샘플 크기: {e}")
            print("사용법: python test_random_games_to_db.py [샘플_크기]")
            print("예시: python test_random_games_to_db.py 5")
            return
    
    print(f"🎯 랜덤 샘플 크기: {sample_size}개")
    
    # 테스터 생성
    tester = RandomGamesTester(sample_size=sample_size)
    
    try:
        # 메인 테스트 실행
        results = await tester.test_random_games_crawling()
        
        # 결과 출력
        print_results(results)
        
        # 추가 테스트 제안
        if results.get('success', 0) > 0:
            print(f"\n🔍 저장된 게임들을 확인하려면:")
            print(f"   python -c \"from database.queries import get_game_statistics; print(get_game_statistics())\"")
        
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


async def quick_test():
    """빠른 테스트 (인기 게임들로)"""
    print("⚡ 빠른 테스트 모드")
    print("인기 게임들로 테스트합니다...")
    
    # 인기 게임 ID들 (확실히 존재하는 게임들)
    popular_games = [
        1091500,  # Cyberpunk 2077
        570,      # Dota 2  
        730,      # Counter-Strike 2
        271590,   # Grand Theft Auto V
        292030,   # The Witcher 3
    ]
    
    tester = RandomGamesTester(sample_size=5)
    results = await tester.test_with_specific_games(popular_games)
    print_results(results)


if __name__ == "__main__":
    # 빠른 테스트 모드 확인
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['quick', 'fast', 'q']:
        asyncio.run(quick_test())
    else:
        asyncio.run(main()) 