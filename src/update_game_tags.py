from single_game_tag_crawler import get_steam_game_tags_sync
import time
from _tag.connect_db import MySQLConnector
from typing import Optional, List, Set, Union
from _tag.find_missing_tags import get_games_without_tags
from pathlib import Path
from datetime import datetime

def get_or_create_tag_id(tag_name: str, db: MySQLConnector) -> Optional[int]:
    # 태그가 존재하는지 확인
    query = "SELECT tag_id FROM tags WHERE name = %s"
    result = db.execute_query(query, (tag_name,))
    
    if result and len(result) > 0:
        return result[0]['tag_id']
    
    # 태그가 없으면 새로 생성
    query = "INSERT INTO tags (name) VALUES (%s)"
    new_tag_id = db.execute_insert(query, (tag_name,))
    if new_tag_id:
        print(f"  🆕 새로운 태그 생성: '{tag_name}' (ID: {new_tag_id})")
    return new_tag_id

def save_failed_games_to_file(failed_games: list) -> str:
    """실패한 게임 ID들을 파일로 저장합니다."""
    if not failed_games:
        return ""
    
    # data 디렉토리 생성
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # 현재 시간을 포함한 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"failed_game_tags_{timestamp}.csv"
    file_path = data_dir / filename
    
    # CSV 파일로 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("game_id,reason\n")  # CSV 헤더
        for game_id in failed_games:
            f.write(f"{game_id},tag_not_found_or_error\n")
    
    return str(file_path)

def update_game_tags():
    db = MySQLConnector()
    
    try:
        if not db.connect():
            print("데이터베이스 연결 실패")
            return
        
        # 태그가 없는 게임 ID 목록 가져오기
        games_without_tags_result = get_games_without_tags(save=False)
        if games_without_tags_result is None or not games_without_tags_result:
            print("태그가 없는 게임이 없습니다.")
            return
        
        # 타입 확정
        games_without_tags: Union[List[int], Set[int]] = games_without_tags_result
        print(f"태그가 없는 게임 수: {len(games_without_tags)}")
        
        failed_games = []
        processed_count = 0
        success_count = 0
        
        for game_id in games_without_tags:
            try:
                processed_count += 1
                print(f"[{processed_count}/{len(games_without_tags)}] 게임 ID {game_id} 처리 중...")
                
                # 게임의 태그 정보 크롤링
                tags = get_steam_game_tags_sync(game_id)
                
                if not tags:
                    print(f"게임 ID {game_id}의 태그를 찾을 수 없습니다.")
                    failed_games.append(game_id)
                    continue
                
                # 각 태그에 대해 처리
                tag_count = 0
                for tag_name in tags:
                    # 태그 ID 가져오기 또는 생성
                    tag_id = get_or_create_tag_id(tag_name, db)
                    
                    if tag_id:
                        # game_tags 테이블에 추가
                        query = "INSERT INTO game_tags (game_id, tag_id) VALUES (%s, %s)"
                        try:
                            db.execute_insert(query, (game_id, tag_id))
                            tag_count += 1
                        except Exception as e:
                            if "Duplicate entry" in str(e):
                                tag_count += 1  # 이미 존재하는 태그도 성공으로 간주
                                continue
                            raise
                
                success_count += 1
                print(f"게임 ID {game_id}의 태그 업데이트 완료 ({tag_count}개 태그)")
                
                # API 호출 제한을 위한 딜레이
                time.sleep(1)
                
            except Exception as e:
                print(f"게임 ID {game_id} 처리 중 오류 발생: {str(e)}")
                failed_games.append(game_id)
                continue
    
    finally:
        db.disconnect()
        
        # 결과 요약 출력
        print(f"\n📊 처리 결과:")
        print(f"  - 총 처리 대상: {len(games_without_tags)}개")
        print(f"  - 성공: {success_count}개")
        print(f"  - 실패: {len(failed_games)}개")
        
        # 실패한 게임 ID를 파일로 저장
        if failed_games:
            saved_file = save_failed_games_to_file(failed_games)
            print(f"  - 실패한 게임 ID들이 '{saved_file}'에 저장되었습니다.")
        else:
            print("  - 실패한 게임이 없습니다! 🎉")

if __name__ == "__main__":
    update_game_tags()