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
import signal
import sys

logger = logging.getLogger(__name__)

# 전역 변수로 실패한 게임 정보 저장 (시그널 핸들러에서 접근하기 위해)
global_failed_games: Dict[int, Dict[str, Any]] = {}
global_processed_count = 0

# 리뷰 갯수 변환 유틸함수
def parse_review_count_to_int(count_value):
    """리뷰 수를 정수로 변환합니다."""
    if not count_value:
        return 0
    try:
        # 이미 정수인 경우
        if isinstance(count_value, int):
            return count_value
        # 문자열인 경우 콤마 제거 후 정수 변환
        if isinstance(count_value, str):
            # 콤마와 공백 제거
            clean_count = count_value.replace(',', '').replace(' ', '')
            # 숫자만 추출 (예: "123k" -> "123" 처리 가능)
            import re
            numbers = re.findall(r'\d+', clean_count)
            if numbers:
                return int(numbers[0])
        return 0
    except (ValueError, AttributeError):
        return 0

def main_without_batch(app_ids: List[int], max_retries: int = 7, delay: float = 0.5, minimum_reviews: Optional[int] = 100):
    """
    단일 게임 처리 방식으로 Steam 게임 데이터를 수집하고 저장합니다.
    - 각 게임을 개별적으로 처리하고 즉시 DB에 저장
    - main_with_batch와 동일한 실패 수집 로직 사용
    
    Args:
        app_ids (List[int]): 처리할 게임 ID 목록
        max_retries (int): 최대 재시도 횟수
        delay (float): 각 게임 처리 후 지연 시간 (초)
        minimum_reviews (Optional[int]): 최소 리뷰 수 필터
    """
    global global_failed_games, global_processed_count
    
    # 통계 변수
    total_games = len(app_ids)
    processed_count = 0
    api_success_count = 0
    crawling_success_count = 0
    
    logger.info(f"[MAIN] 단일 게임 처리 시작: {total_games}개 게임")
    
    def save_failed_games_info():
        """실패한 게임 정보를 파일에 저장하는 함수"""
        save_failed_games_to_file(global_failed_games)
    
    try:
        for i, app_id in enumerate(app_ids):
            processed_count += 1
            global_processed_count = processed_count  # 전역 변수 업데이트
            
            # 1. 크롤링 데이터 수집 (먼저 실행)
            crawling_result = get_steam_game_info_crawler_minimal_sync(app_id, max_retries)
            
            if crawling_result.get('success') and crawling_result.get('data'):
                # 리뷰 수 추출 및 필터링
                raw_review_count = crawling_result['data'].get('review_info', {}).get('total_review_count', 0)
                review_count = 0 if raw_review_count == 0 else parse_review_count_to_int(raw_review_count)
                
                if minimum_reviews is None or review_count >= minimum_reviews:
                    logger.debug(f"[MAIN]({app_id}) 리뷰 수 충족: {review_count}개")
                    
                    # 2. 크롤링 데이터가 있을 때만 API 데이터 수집
                    api_result = get_steam_game_info_api_sync(app_id, max_retries)
                    
                    if api_result.get('success') and api_result.get('data'):
                        api_data = api_result['data']
                        
                        # id 불일치 체크
                        if api_data.get('steam_appid') != app_id:
                            logger.info(f"[MAIN]({app_id}) id 불일치: API - {api_data.get('app_id')}")
                            global_failed_games[app_id] = {
                                'type': 'api_failed',
                                'error': 'id_mismatch'
                            }
                            continue
                        
                        # 게임 타입 체크
                        if api_data.get('type') == 'game':
                            # 3. 모든 검증을 통과하면 즉시 DB에 저장
                            try:
                                insert_steam_crawling_game_single(crawling_result['data'])
                                crawling_success_count += 1
                                insert_steam_api_game_single(api_data)
                                api_success_count += 1
                                logger.info(f"[MAIN]({app_id}) 데이터 수집 및 저장 완료")
                            except Exception as e:
                                logger.error(f"[MAIN]({app_id}) DB 저장 실패: {e}")
                                global_failed_games[app_id] = {
                                    'type': 'db_failed',
                                    'error': 'db_insert_failed'
                                }
                        else:
                            # 게임 타입이 아님
                            logger.warning(f"[MAIN]({app_id}) 게임 타입 아님: 타입 - {api_data.get('type', 'Unknown')}")
                            global_failed_games[app_id] = {
                                'type': 'api_failed',
                                'error': 'invalid_game_type'
                            }
                            continue
                    # api 데이터 없음 처리
                    elif api_result.get('error') == 'no_data':
                        logger.warning(f"[MAIN]({app_id}) API 데이터 없음")
                        global_failed_games[app_id] = {
                            'type': 'api_failed',
                            'error': 'no_data_from_api'
                        }
                    # 기타 API 실패
                    else:
                        logger.warning(f"[MAIN]({app_id}) API 실패: {api_result.get('message', 'Unknown error')}")
                        global_failed_games[app_id] = {
                            'type': 'api_failed',
                            'error': 'unknown_api_error'
                        }
                else:
                    logger.debug(f"[MAIN]({app_id}) 리뷰 수 부족: {review_count}개")
                    global_failed_games[app_id] = {
                        'type': 'crawling_failed',
                        'error': 'review_count_too_low'
                    }
            else:       
                # 방문 불가능한 페이지의 경우
                if crawling_result.get('error') == 'invalid_game_page':
                    logger.warning(f"[MAIN]({app_id}) 크롤링 실패 : {crawling_result.get('message', 'Unknown error')}")
                    global_failed_games[app_id] = {
                        'type': 'crawling_failed',
                        'error': 'invalid_game_page'
                    }
                # 이외의 크롤링 오류
                else:
                    logger.warning(f"[MAIN]({app_id}) 크롤링 실패 : {crawling_result.get('message', 'Unknown error')}")
                    global_failed_games[app_id] = {
                        'type': 'crawling_failed',
                        'error': 'unknown_crawling_error'
                    }
            
            # 4. 진행률 표시 (1000개마다)
            if processed_count % 1000 == 0 or processed_count == total_games:
                progress_percent = (processed_count / total_games) * 100
                logger.info(f"[MAIN] 진행률: {processed_count}/{total_games} ({progress_percent:.1f}%)")
            
            # 5. 지연
            time.sleep(delay)
        
        # 6. 최종 결과 리포트
        logger.info(f"[MAIN] === 최종 결과 ===")
        logger.info(f"[MAIN] 전체 처리: {processed_count}개")
        logger.info(f"[MAIN] API 성공: {api_success_count}개")
        logger.info(f"[MAIN] 크롤링 성공: {crawling_success_count}개")
        logger.info(f"[MAIN] 실패한 게임: {len(global_failed_games)}개")
    
    except Exception as e:
        logger.error(f"[MAIN] 메인 처리 중 예외 발생: {e}")
        logger.error(f"[MAIN] 현재까지 처리된 게임: {processed_count}개")
        raise  # 예외를 다시 발생시켜서 finally에서 정리 작업 수행
    
    finally:
        # 프로그램 종료시 반드시 실행되는 부분
        logger.info(f"[MAIN] 프로그램 종료 - 정리 작업 수행 중...")
        
        # 실패한 게임 정보 저장 (반드시 실행)
        save_failed_games_info()
        
        logger.info(f"[MAIN] 정리 작업 완료")
    
    return {
        'total_processed': processed_count,
        'api_success_count': api_success_count,
        'crawling_success_count': crawling_success_count,
        'failed_games': global_failed_games
    }

def main(max_retries: int = 7, delay: float = 0.5, limit: Optional[int] = None, minimum_reviews: Optional[int] = 100):
    app_ids = list(get_all_steam_games(limit))
    return main_without_batch(app_ids, max_retries, delay, minimum_reviews)

def main_with_batch(app_ids: List[int], max_retries: int = 7, delay: float = 0.5, batch_size: int = 100, minimum_reviews: Optional[int] = 100):
    """
    배치 처리 방식으로 Steam 게임 데이터를 수집하고 저장합니다.
    - 새 게임: bulk insert (고성능)
    - 기존 게임: 개별 업데이트 (정확한 변경점 관리)
    
    Args:
        app_ids (List[int]): 처리할 게임 ID 목록
        max_retries (int): 최대 재시도 횟수
        delay (float): 각 게임 처리 후 지연 시간 (초)
        batch_size (int): 배치 크기 (DB에 한 번에 저장할 게임 수)
        minimum_reviews (Optional[int]): 최소 리뷰 수 필터
    """
    global global_failed_games, global_processed_count
    
    # 배치 데이터 저장소
    api_batch = []
    crawling_batch = []
    
    # 통계 변수
    total_games = len(app_ids)
    processed_count = 0
    api_success_count = 0
    crawling_success_count = 0
    
    logger.info(f"[MAIN] 배치 처리 시작: {total_games}개 게임, 배치 크기: {batch_size}")
    
    def save_failed_games_info():
        """실패한 게임 정보를 파일에 저장하는 함수"""
        save_failed_games_to_file(global_failed_games)
    
    try:
        for i, app_id in enumerate(app_ids):
            processed_count += 1
            global_processed_count = processed_count  # 전역 변수 업데이트
            
            # 1. 크롤링 데이터 수집 (먼저 실행)
            crawling_result = get_steam_game_info_crawler_minimal_sync(app_id, max_retries)
            
            if crawling_result.get('success') and crawling_result.get('data'):
                # 리뷰 수 추출 및 필터링
                raw_review_count = crawling_result['data'].get('review_info', {}).get('total_review_count', 0)
                review_count = 0 if raw_review_count == 0 else parse_review_count_to_int(raw_review_count)
                
                if minimum_reviews is None or review_count >= minimum_reviews:
                    logger.debug(f"[MAIN]({app_id}) 리뷰 수 충족: {review_count}개")
                    
                    # 2. 크롤링 데이터가 있을 때만 API 데이터 수집
                    api_result = get_steam_game_info_api_sync(app_id, max_retries)
                    
                    if api_result.get('success') and api_result.get('data'):
                        api_data = api_result['data']
                        
                        # id 불일치 체크
                        # API 에 요청한 id 와 API 에서 제공한 id 가 불일치 하는 경우가 발생
                        # 동일 게임이 여러 id 를 사용할 경우 발생하는걸로 추측됨
                        # id 가 일치하는 하나의 데이터만 사용하면 되기 때문에 id 가 불일치하는 데이터를 사용하지 않음
                        if api_data.get('steam_appid') != app_id:
                            logger.info(f"[MAIN]({app_id}) id 불일치: API - {api_data.get('app_id')}")
                            global_failed_games[app_id] = {
                                'type': 'api_failed',
                                'error': 'id_mismatch'
                            }
                            continue
                        
                        # 게임 타입 체크
                        if api_data.get('type') == 'game':
                            # 모든 검증을 통과하면 배치에 추가
                            api_batch.append(api_data)
                            api_success_count += 1
                            crawling_batch.append(crawling_result['data'])
                            crawling_success_count += 1
                            logger.info(f"[MAIN]({app_id}) 데이터 수집 완료")
                        else:
                            # 게임 타입이 아님
                            logger.warning(f"[MAIN]({app_id}) 게임 타입 아님: 타입 - {api_data.get('type', 'Unknown')}")
                            global_failed_games[app_id] = {
                                'type': 'api_failed',
                                'error': 'invalid_game_type'
                            }
                            continue
                    # api 데이터 없음 처리 - 실패 수집 안함
                    elif api_result.get('error') == 'no_data':
                        logger.warning(f"[MAIN]({app_id}) API 데이터 없음")
                        global_failed_games[app_id] = {
                            'type': 'api_failed',
                            'error': 'no_data_from_api'
                        }
                    # 기타 - 실패 수집 함
                    else:
                        logger.warning(f"[MAIN]({app_id}) API 실패: {api_result.get('message', 'Unknown error')}")
                        global_failed_games[app_id] = {
                            'type': 'api_failed',
                            'error': 'unknown_api_error'
                        }
                else:
                    logger.debug(f"[MAIN]({app_id}) 리뷰 수 부족: {review_count}개")
                    global_failed_games[app_id] = {
                        'type': 'crawling_failed',
                        'error': 'review_count_too_low'
                    }
            else:       
                # 방문 불가능한 페이지의 경우 - 실패 수집 안함
                if crawling_result.get('error') == 'invalid_game_page':
                    logger.warning(f"[MAIN]({app_id}) 크롤링 실패 : {crawling_result.get('message', 'Unknown error')}")
                    global_failed_games[app_id] = {
                        'type': 'crawling_failed',
                        'error': 'invalid_game_page'
                    }
                # 이외의 크롤링 오류 - 실패 수집 함
                else:
                    logger.warning(f"[MAIN]({app_id}) 크롤링 실패 : {crawling_result.get('message', 'Unknown error')}")
                    # 크롤링 실패 기록
                    global_failed_games[app_id] = {
                        'type': 'crawling_failed',
                        'error': 'unknown_crawling_error'
                    }
          
            # 3. 배치가 찼거나 마지막 게임인 경우 하이브리드 배치 저장
            if len(api_batch) >= batch_size or i == len(app_ids) - 1:
                if api_batch:
                    logger.debug(f"[MAIN] API 데이터 배치 저장 중: {len(api_batch)}개")
                    api_success_batch, api_failed_batch = insert_steam_api_games_batch(api_batch)
                    logger.info(f"[MAIN] API 데이터 저장 완료: 성공 {api_success_batch}개, 실패 {len(api_failed_batch)}개")
                    
                    # DB 저장 실패한 게임들 추가
                    for failed_game in api_failed_batch:
                        global_failed_games[failed_game['app_id']] = {
                            'type': 'api_db_failed',
                            'error': 'db_insert_failed_api'
                        }
                
                if crawling_batch:
                    logger.debug(f"[MAIN] 크롤링 데이터 배치 저장 중: {len(crawling_batch)}개")
                    crawling_success_batch, crawling_failed_batch = insert_steam_crawling_games_batch(crawling_batch)
                    logger.info(f"[MAIN] 크롤링 데이터 저장 완료: 성공 {crawling_success_batch}개, 실패 {len(crawling_failed_batch)}개")
                    
                    # DB 저장 실패한 게임들 추가
                    for failed_game in crawling_failed_batch:
                        global_failed_games[failed_game['app_id']] = {
                            'type': 'crawling_db_failed',
                            'error': 'db_insert_failed_crawling'
                        }
                
                # 배치 초기화
                api_batch.clear()
                crawling_batch.clear()
                
                # 진행률
                progress_percent = (processed_count / total_games) * 100
                logger.info(f"[MAIN] 진행률: {processed_count}/{total_games} ({progress_percent:.1f}%)")
            
            # 4. 지연
            time.sleep(delay)
        
        # 5. 최종 결과 리포트
        logger.info(f"[MAIN] === 최종 결과 ===")
        logger.info(f"[MAIN] 전체 처리: {processed_count}개")
        logger.info(f"[MAIN] API 성공: {api_success_count}개")
        logger.info(f"[MAIN] 크롤링 성공: {crawling_success_count}개")
        logger.info(f"[MAIN] 실패한 게임: {len(global_failed_games)}개")
    
    except Exception as e:
        logger.error(f"[MAIN] 메인 처리 중 예외 발생: {e}")
        logger.error(f"[MAIN] 현재까지 처리된 게임: {processed_count}개")
        raise  # 예외를 다시 발생시켜서 finally에서 정리 작업 수행
    
    finally:
        # 프로그램 종료시 반드시 실행되는 부분
        logger.info(f"[MAIN] 프로그램 종료 - 정리 작업 수행 중...")
        
        # 7. 실패한 게임 정보 저장 (반드시 실행)
        save_failed_games_info()
        
        logger.info(f"[MAIN] 정리 작업 완료")
    
    return {
        'total_processed': processed_count,
        'api_success_count': api_success_count,
        'crawling_success_count': crawling_success_count,
        'failed_games': global_failed_games
    }

def save_failed_games_to_file(failed_games: Dict[int, Dict[str, Any]]):
    """실패한 게임 정보를 파일에 저장하는 함수"""
    if not failed_games:
        logger.info(f"[CLEANUP] 실패한 게임이 없어 저장하지 않습니다.")
        return
        
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
        
        logger.info(f"[CLEANUP] 실패한 게임 정보 저장 완료: {filename}")
        logger.info(f"[CLEANUP] 실패한 게임 총 {len(failed_games)}개")
        
    except Exception as e:
        logger.error(f"[CLEANUP] 실패한 게임 정보 저장 중 오류: {e}")

def signal_handler(signum, frame):
    """시그널 핸들러: Ctrl+C나 kill 명령 시 실행"""
    logger.warning(f"[SIGNAL] 프로그램 종료 신호 수신 (시그널: {signum})")
    logger.info(f"[SIGNAL] 현재까지 처리된 게임: {global_processed_count}개")
    logger.info(f"[SIGNAL] 정리 작업 수행 중...")
    
    # 실패한 게임 정보 저장
    save_failed_games_to_file(global_failed_games)
    
    logger.info(f"[SIGNAL] 정리 작업 완료. 프로그램을 종료합니다.")
    sys.exit(0)

def run_all_games(max_retries: int = 10, delay: float = 0.5, batch_size: int = 100, minimum_reviews: int = 100, use_batch: bool = True):
    """
    전체 Steam 게임 ID로 크롤링 실행
    
    Args:
        max_retries (int): 최대 재시도 횟수
        delay (float): 각 게임 처리 후 지연 시간 (초)
        batch_size (int): 배치 크기 (use_batch=True일 때만 사용)
        minimum_reviews (int): 최소 리뷰 수 필터
        use_batch (bool): 배치 처리 사용 여부
        
    Returns:
        dict: 처리 결과
    """
    if use_batch:
        logger.info("[SETUP] 전체 Steam 게임 ID로 배치 크롤링 실행")
    else:
        logger.info("[SETUP] 전체 Steam 게임 ID로 단일 크롤링 실행")
    
    # Steam API에서 전체 게임 ID 가져오기
    all_game_ids = list(get_all_steam_games())
    logger.info(f"[SETUP] 전체 게임 ID 수집 완료: {len(all_game_ids):,}개")
    
    if use_batch:
        # 배치 처리 실행
        result = main_with_batch(
            app_ids=all_game_ids,
            max_retries=max_retries, 
            delay=delay, 
            batch_size=batch_size, 
            minimum_reviews=minimum_reviews
        )
    else:
        # 단일 게임 처리 실행
        result = main_without_batch(
            app_ids=all_game_ids,
            max_retries=max_retries, 
            delay=delay, 
            minimum_reviews=minimum_reviews
        )
    
    return result

# 시그널 핸들러 등록
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # kill 명령

if __name__ == "__main__":
    setup_logger("INFO")
    
    result = run_all_games(minimum_reviews=100)
    