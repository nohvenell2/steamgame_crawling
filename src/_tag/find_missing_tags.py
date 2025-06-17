#!/usr/bin/env python3
"""
태그가 없는 게임 ID를 찾는 프로그램

이 프로그램은 다음 작업을 수행합니다:
1. games_all 테이블에서 모든 game_id 추출 (고유함)
2. game_tags 테이블에서 고유한 game_id 추출 
3. games_all에는 있지만 game_tags에는 없는 game_id 찾기
"""

import sys
import os
from typing import List, Set, Tuple
from pathlib import Path

# 상위 디렉토리를 sys.path에 추가하여 모듈 import 가능하게 함
sys.path.append(str(Path(__file__).parent.parent.parent))

from src._tag.connect_db import MySQLConnector, test_connection

class GameTagAnalyzer:
    """게임 태그 분석 클래스"""
    
    def __init__(self):
        self.db = MySQLConnector()
        
    def get_all_game_ids_from_games_all(self) -> Set[int]:
        """games_all 테이블에서 모든 game_id를 추출합니다."""
        print("📋 games_all 테이블에서 game_id 추출 중...")
        
        query = "SELECT DISTINCT game_id FROM games_all ORDER BY game_id"
        result = self.db.execute_query(query)
        
        if result is None:
            print("❌ games_all 테이블 조회 실패")
            return set()
        
        game_ids = {row['game_id'] for row in result}
        print(f"✅ games_all에서 {len(game_ids)}개의 고유한 game_id를 찾았습니다.")
        return game_ids
    
    def get_all_game_ids_from_game_tags(self) -> Set[int]:
        """game_tags 테이블에서 고유한 game_id를 추출합니다."""
        print("🏷️  game_tags 테이블에서 고유한 game_id 추출 중...")
        
        query = "SELECT DISTINCT game_id FROM game_tags ORDER BY game_id"
        result = self.db.execute_query(query)
        
        if result is None:
            print("❌ game_tags 테이블 조회 실패")
            return set()
        
        game_ids = {row['game_id'] for row in result}
        print(f"✅ game_tags에서 {len(game_ids)}개의 고유한 game_id를 찾았습니다.")
        return game_ids
    
    def find_games_without_tags(self) -> Set[int]:
        """태그가 없는 게임 ID를 찾습니다."""
        print("\n🔍 태그가 없는 게임 ID 분석 중...")
        
        # 각 테이블에서 game_id 추출
        games_all_ids = self.get_all_game_ids_from_games_all()
        game_tags_ids = self.get_all_game_ids_from_game_tags()
        
        if not games_all_ids:
            print("❌ games_all 테이블에서 데이터를 가져올 수 없습니다.")
            return set()
        
        # games_all에는 있지만 game_tags에는 없는 ID 찾기
        missing_tags_ids = games_all_ids - game_tags_ids
        
        print(f"\n📊 분석 결과:")
        print(f"  - games_all 총 게임 수: {len(games_all_ids):,}개")
        print(f"  - game_tags에 있는 게임 수: {len(game_tags_ids):,}개")
        print(f"  - 태그가 없는 게임 수: {len(missing_tags_ids):,}개")
        
        return missing_tags_ids
    
    def get_game_details_without_tags(self, limit: int = 10) -> List[Tuple[int, str, str]]:
        """태그가 없는 게임의 상세 정보를 가져옵니다."""
        missing_ids = self.find_games_without_tags()
        
        if not missing_ids:
            return []
        
        # 처음 몇 개의 게임 정보만 가져오기
        limited_ids = list(missing_ids)[:limit]
        
        print(f"\n📖 태그가 없는 게임 상세 정보 (최대 {limit}개):")
        
        # IN 절을 위한 플레이스홀더 생성
        placeholders = ', '.join(['%s'] * len(limited_ids))
        query = f"""
        SELECT game_id, name, developer, release_date 
        FROM games_all 
        WHERE game_id IN ({placeholders})
        ORDER BY game_id
        """
        
        result = self.db.execute_query(query, tuple(limited_ids))
        
        if result is None:
            print("❌ 게임 상세 정보 조회 실패")
            return []
        
        game_details = []
        for i, row in enumerate(result, 1):
            game_id = row['game_id']
            name = row['name'] or 'Unknown'
            developer = row['developer'] or 'Unknown'
            release_date = row['release_date'] or 'Unknown'
            
            print(f"  {i:2d}. ID: {game_id:8d} | {name[:40]:<40} | {developer[:20]:<20} | {release_date}")
            game_details.append((game_id, name, developer))
        
        return game_details
    
    def save_missing_game_ids_to_file(self, filename: str = "missing_tags_game_ids.csv") -> Set[int]|None:
        """태그가 없는 게임 ID들을 CSV 파일로 저장합니다."""
        missing_ids = self.find_games_without_tags()
        
        if not missing_ids:
            print("저장할 게임 ID가 없습니다.")
            return None
        
        # data 디렉토리 생성
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        file_path = data_dir / filename
        
        # 정렬된 ID를 CSV 파일에 저장
        sorted_ids = sorted(missing_ids)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("game_id\n")  # CSV 헤더
            for game_id in sorted_ids:
                f.write(f"{game_id}\n")
        
        print(f"💾 태그가 없는 게임 ID {len(sorted_ids):,}개를 '{file_path}'에 저장했습니다.")
        return missing_ids
    
    def close(self):
        """데이터베이스 연결을 종료합니다."""
        self.db.disconnect()

def get_games_without_tags(save: bool = False) -> Set[int]|None:
    """메인 실행 함수"""
    print("🎮 태그가 없는 게임 ID 분석 도구")
    print("=" * 60)
    
    # 데이터베이스 연결 테스트
    print("🔗 데이터베이스 연결 테스트 중...")
    if not test_connection():
        print("❌ 데이터베이스 연결에 실패했습니다. .env 설정을 확인해주세요.")
        return
    
    try:
        # Python Set 연산 방식으로 분석
        analyzer = GameTagAnalyzer()
        if save:
            missing_ids = analyzer.save_missing_game_ids_to_file()
        else:
            missing_ids = analyzer.find_games_without_tags()
        analyzer.close()       
        # print(missing_ids)
        print("\n✅ 분석이 완료되었습니다.")
        return missing_ids
    except Exception as e:
        print(f"❌ 오류가 발생했습니다: {str(e)}")
        return

if __name__ == "__main__":
    get_games_without_tags(save=False)