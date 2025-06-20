#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Steam 게임 데이터 대량 수집 및 DB 저장 스크립트

이 스크립트는 Steam의 모든 게임 데이터를 자동으로 수집하고 데이터베이스에 저장합니다.
API 호출과 웹 크롤링을 병행하여 포괄적인 게임 정보를 수집합니다.

주요 기능:
==========
1. 데이터 수집
   - Steam Store API: 기본 게임 정보 (가격, 개발사, 출시일 등)
   - Steam Store 웹 크롤링: 상세 정보 (태그, 리뷰 수, 평점 등)

2. 데이터 필터링
   - 게임 타입 필터링: 'game' 타입만 수집 (DLC, Software 등 제외)
   - 리뷰 수 필터링: 지정된 최소 리뷰 수 이상인 게임만 저장

3. 배치 처리
   - 고성능 bulk insert로 DB 저장 최적화
   - 메모리 효율성을 위한 배치 단위 처리

4. 에러 처리 및 모니터링
   - 재시도 로직: 네트워크 오류 등에 대한 자동 재시도
   - 실패 추적: 실패한 게임들의 상세 로그 및 분류
   - 진행률 모니터링: 실시간 처리 상황 및 성공률 확인

5. 로그 관리
   - 상세한 처리 로그 기록
   - 실패한 게임들의 JSON 파일 저장

사용법:
=======
# 백그라운드 실행 (권장)
nohup poetry run python -u src/run_save_all_games.py > logs/run_save_all_games_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 진행 상황 모니터링
tail -f logs/run_save_all_games_*.log

# 프로세스 종료
pkill -f "run_save_all_games.py"

설정 가능한 매개변수:
==================
- max_retries: 최대 재시도 횟수 (기본: 10)
- delay: 각 게임 처리 후 지연 시간 (기본: 0.5초)
- batch_size: 배치 크기 (기본: 100)
- limit: 처리할 게임 수 제한 (테스트용, 기본: 무제한)
- minimum_reviews: 최소 리뷰 수 필터 (기본: 100)

주의사항:
=========
- 전체 Steam 게임 수집 시 수십만 개의 게임을 처리하므로 장시간 실행
- Steam API Rate Limit 준수를 위해 지연 시간 설정 필수
- 충분한 디스크 공간과 DB 저장 공간 확보 필요
- 네트워크 연결 상태 및 Steam 서버 상태에 따라 성공률 변동

작성자: nohvenell2
버전: 1.0
최종 수정일: 2024-06-20
"""

from utils.logger import setup_logger
from fetch_steam_game_data import get_steam_game_info_api_sync
from single_game_crawler_minimal import get_steam_game_info_crawler_minimal_sync
from database.inserter import insert_steam_api_game_single, insert_steam_crawling_game_single, insert_steam_api_games_batch, insert_steam_crawling_games_batch
from fetch_steam_game_ids import get_all_steam_games
from typing import List, Optional, Dict, Any
import time
import logging
import json

logger = logging.getLogger(__name__)

def data_to_db_by_app_id(app_id: int, max_retries: int = 7) -> bool:
    # api 데이터 수집
    data_api = get_steam_game_info_api_sync(app_id, max_retries).get('data')
    if not data_api:
        logger.info(f"[main] api 데이터가 없습니다. {app_id}")
        return False
    elif data_api.get('type') != 'game':
        logger.info(f"[main] api 데이터 타입이 게임이 아닙니다: {data_api.get('name', '')}({app_id})")
        return False
    # api 데이터 삽입
    else: 
        insert_steam_api_game_single(data_api)
    # 크롤링 데이터 수집
    data_crawling = get_steam_game_info_crawler_minimal_sync(app_id, max_retries).get('data')
    # 크롤링 데이터 삽입
    if not data_crawling:
        logger.info(f"[main] 크롤링 데이터가 없습니다. {app_id}")
        return False
    else:
        insert_steam_crawling_game_single(data_crawling)
    return True

def main(max_retries: int = 7, delay: float = 0.5, limit: Optional[int] = None):
    app_ids = get_all_steam_games(limit)
    for app_id in app_ids:
        data_to_db_by_app_id(app_id, max_retries)
        time.sleep(delay)

def main_with_batch(max_retries: int = 7, delay: float = 0.5, batch_size: int = 100, limit: Optional[int] = None, minimum_reviews: Optional[int] = 100):
    """
    배치 처리 방식으로 Steam 게임 데이터를 수집하고 저장합니다.
    - 새 게임: bulk insert (고성능)
    - 기존 게임: 개별 업데이트 (정확한 변경점 관리)
    
    Args:
        max_retries (int): 최대 재시도 횟수
        delay (float): 각 게임 처리 후 지연 시간 (초)
        batch_size (int): 배치 크기 (DB에 한 번에 저장할 게임 수)
        limit (Optional[int]): 처리할 게임 수 제한 (테스트용)
    """
    app_ids = get_all_steam_games(limit)
    
    # 배치 데이터 저장소
    api_batch = []
    crawling_batch = []
    
    # 실패한 게임들 추적
    failed_games: Dict[int, Dict[str, Any]] = {}
    
    # 통계 변수
    total_games = len(app_ids)
    processed_count = 0
    api_success_count = 0
    crawling_success_count = 0
    
    logger.info(f"[MAIN] 배치 처리 시작: {total_games}개 게임, 배치 크기: {batch_size}")
    
    for i, app_id in enumerate(app_ids):
        processed_count += 1
        
        # 1. API 데이터 수집
        api_result = get_steam_game_info_api_sync(app_id, max_retries)
        
        if api_result.get('success') and api_result.get('data'):
            api_data = api_result['data']

            # 게임 타입 체크
            if api_data.get('type') == 'game':
                
                # 2. 크롤링 데이터 수집 (API가 성공한 게임만)
                crawling_result = get_steam_game_info_crawler_minimal_sync(app_id, max_retries)
                
                if crawling_result.get('success') and crawling_result.get('data'):
                    review_count = crawling_result['data'].get('total_review_count', 0)
                    if review_count > minimum_reviews or minimum_reviews is None:
                        api_batch.append(api_data)
                        api_success_count += 1
                        crawling_batch.append(crawling_result['data'])
                        crawling_success_count += 1
                    else:
                        logger.debug(f"[MAIN] 크롤링 리뷰 수 부족: {app_id} - {review_count}개")
                else:       
                    # 방문 불가능한 페이지의 경우 - 실패 수집 안함
                    if crawling_result.get('error') == 'invalid_game_page':
                        logger.debug(f"[MAIN] 크롤링 실패: {app_id} - {crawling_result.get('message', 'Unknown error')}")
                    # 이외의 크롤링 오류 - 실패 수집 함
                    else:
                        logger.warning(f"[MAIN] 크롤링 실패: {app_id} - {crawling_result.get('message', 'Unknown error')}")
                        # 크롤링 실패 기록
                        failed_games[app_id] = {
                            'type': 'crawling_failed',
                            'api_success': True,
                            'crawling_error': crawling_result
                        }
            else:
                # 게임 타입이 아님
                logger.debug(f"[MAIN] 게임 타입 아님: {api_data.get('name', '')}({app_id}) - 타입: {api_data.get('type', 'Unknown')}")
                continue
        # api 데이터 없음 처리 - 실패 수집 안함
        elif api_result.get('error') == 'no_data':
            logger.debug(f"[MAIN] API 데이터 없음: {app_id}")
        # 기타 - 실패 수집 함
        else:
            logger.warning(f"[MAIN] API 실패: {app_id} - {api_result.get('message', 'Unknown error')}")
            failed_games[app_id] = {
                'type': 'api_failed',
                'api_error': api_result
            }

        # 3. 배치가 찼거나 마지막 게임인 경우 하이브리드 배치 저장
        if len(api_batch) >= batch_size or i == len(app_ids) - 1:
            if api_batch:
                logger.info(f"[MAIN] API 데이터 배치 저장 중: {len(api_batch)}개")
                api_success_batch, api_failed_batch = insert_steam_api_games_batch(api_batch)
                logger.info(f"[MAIN] API 데이터 저장 완료: 성공 {api_success_batch}개, 실패 {len(api_failed_batch)}개")
                
                # DB 저장 실패한 게임들 추가
                for failed_game in api_failed_batch:
                    failed_games[failed_game['app_id']] = {
                        'type': 'api_db_failed',
                        'api_success': True,
                        'db_error': failed_game
                    }
            
            if crawling_batch:
                logger.info(f"[MAIN] 크롤링 데이터 배치 저장 중: {len(crawling_batch)}개")
                crawling_success_batch, crawling_failed_batch = insert_steam_crawling_games_batch(crawling_batch)
                logger.info(f"[MAIN] 크롤링 데이터 저장 완료: 성공 {crawling_success_batch}개, 실패 {len(crawling_failed_batch)}개")
                
                # DB 저장 실패한 게임들 추가
                for failed_game in crawling_failed_batch:
                    failed_games[failed_game['app_id']] = {
                        'type': 'crawling_db_failed',
                        'crawling_success': True,
                        'db_error': failed_game
                    }
            
            # 배치 초기화
            api_batch.clear()
            crawling_batch.clear()
            
            # 진행상황 로그
            progress_percent = (processed_count / total_games) * 100
            logger.info(f"[MAIN] 진행률: {processed_count}/{total_games} ({progress_percent:.1f}%)")
        
        # 4. 지연
        time.sleep(delay)
    
    # 5. 최종 결과 리포트
    logger.info(f"[MAIN] === 최종 결과 ===")
    logger.info(f"[MAIN] 전체 처리: {processed_count}개")
    logger.info(f"[MAIN] API 성공: {api_success_count}개")
    logger.info(f"[MAIN] 크롤링 성공: {crawling_success_count}개")
    logger.info(f"[MAIN] 실패한 게임: {len(failed_games)}개")
    
    # 6. 실패한 게임들 상세 정보
    if failed_games:
        logger.info(f"[MAIN] === 실패한 게임 목록 ===")
        api_failures = {k: v for k, v in failed_games.items() if v['type'] == 'api_failed'}
        crawling_failures = {k: v for k, v in failed_games.items() if v['type'] == 'crawling_failed'}
        api_db_failures = {k: v for k, v in failed_games.items() if v['type'] == 'api_db_failed'}
        crawling_db_failures = {k: v for k, v in failed_games.items() if v['type'] == 'crawling_db_failed'}
        
        logger.info(f"[MAIN] API 실패: {len(api_failures)}개")
        for app_id, failure_info in list(api_failures.items())[:10]:  # 처음 10개만 로그
            error_type = failure_info['api_error'].get('error', 'unknown')
            logger.info(f"[MAIN]   - {app_id}: {error_type}")
        
        logger.info(f"[MAIN] 크롤링 실패: {len(crawling_failures)}개")
        for app_id, failure_info in list(crawling_failures.items())[:10]:  # 처음 10개만 로그
            error_type = failure_info['crawling_error'].get('error', 'unknown')
            logger.info(f"[MAIN]   - {app_id}: {error_type}")
        
        logger.info(f"[MAIN] API DB 저장 실패: {len(api_db_failures)}개")
        for app_id, failure_info in list(api_db_failures.items())[:10]:  # 처음 10개만 로그
            error_type = failure_info['db_error'].get('error', 'unknown')
            logger.info(f"[MAIN]   - {app_id}: {error_type}")
        
        logger.info(f"[MAIN] 크롤링 DB 저장 실패: {len(crawling_db_failures)}개")
        for app_id, failure_info in list(crawling_db_failures.items())[:10]:  # 처음 10개만 로그
            error_type = failure_info['db_error'].get('error', 'unknown')
            logger.info(f"[MAIN]   - {app_id}: {error_type}")
        
        if len(failed_games) > 40:
            logger.info(f"[MAIN] (실패 목록이 길어 일부만 표시함)")
    # 7. 실패한 게임 정보 저장
    try:
        import os
        os.makedirs('logs', exist_ok=True)
        
        # 타임스탬프 추가하여 덮어쓰기 방지
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'logs/failed_games_{timestamp}.json'
        
        # 한글 포함 가능성 고려하여 인코딩 지정
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(failed_games, f, indent=4, ensure_ascii=False)
        
        logger.info(f"[MAIN] 실패한 게임 정보 저장 완료: {filename}")
        logger.info(f"[MAIN] 실패한 게임 총 {len(failed_games)}개")
        
    except Exception as e:
        logger.error(f"[MAIN] 실패한 게임 정보 저장 중 오류: {e}")
    return {
        'total_processed': processed_count,
        'api_success_count': api_success_count,
        'crawling_success_count': crawling_success_count,
        'failed_games': failed_games
    }

if __name__ == "__main__":
    setup_logger("INFO")
    
    # 기존 방식 (개별 처리)
    # main(max_retries=7, delay=0.3, limit=100)
    
    # 기존 배치 방식
    # result = main_with_batch(max_retries=7, delay=0.3, batch_size=50, limit=100)
    
    # 배치 방식 (하이브리드: 새 게임 bulk insert + 기존 게임 개별 업데이트)
    result = main_with_batch(max_retries=10, delay=0.5, batch_size=100)
