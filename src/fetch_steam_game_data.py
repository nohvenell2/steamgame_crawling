"""
Steam API를 이용한 게임 데이터 수집 모듈

이 모듈은 Steam Store API를 활용하여 게임의 원시 데이터를 수집합니다.
순수하게 데이터 수집만 담당하며, 데이터 변환은 database.inserter.py에서 처리합니다.

주요 기능:
- Steam Store API를 통한 게임 정보 수집
- 비동기/동기 처리 모두 지원
- 여러 게임 동시 처리
- 자동 재시도 및 에러 처리

반환 구조:
- 성공시: {'success': True, 'data': {api_response}, 'app_id': app_id}
- 실패시: {'success': False, 'error': 'error_type', 'message': 'error_message', 'app_id': app_id}

가능한 에러 타입:
- 'rate_limit_exceeded': API 요청 제한 초과
- 'http_error': HTTP 에러 (404, 500 등)
- 'exception': 예외 발생 (네트워크 오류 등)
- 'unknown': 알 수 없는 오류

사용 예시:
```python
import asyncio
from fetch_steam_game_data import get_steam_game_info_api, setup_logger

# 로거 설정 (선택사항)
setup_logger("INFO")

# 비동기 사용
async def main():
    result = await get_steam_game_info_api(1091500)
    if result['success']:
        print(f"게임명: {result['data']['name']}")
    else:
        print(f"오류: {result['message']}")

# 동기 사용 (편의 함수)
result = get_steam_game_info_api_sync(1091500)
print(result)
```

데이터 변환 및 DB 저장은 다음 모듈들 참고:
- database.inserter.py: 데이터 변환 및 DB 저장
- save_steam_api_to_db.py: Steam API → DB 저장 통합 예제
"""

import requests
import aiohttp
import asyncio
from typing import Optional, Dict, Any
import logging

# 로거 유틸리티 import
from utils.logger import setup_logger

# 로거 설정
logger = logging.getLogger(__name__)

# 형식 변환 함수들은 database.inserter.py로 이동됨

# 비동기 버전 (기본 버전)
async def get_steam_game_info_api(app_id: int, max_retries: int = 7) -> Dict[str, Any]:
    """게임 상세 정보를 가져옵니다 (기본 비동기 버전)."""
    base_url = f"https://store.steampowered.com/api/appdetails"
    params = {
        'appids': app_id,
        'cc': 'us',
        'l': 'english'
    }
    logger.debug(f"[API] 게임 API 정보 요청 중: {app_id}")
    for attempt in range(max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    # 성공적인 응답
                    if response.status == 200:
                        raw_data = await response.json()
                        data = raw_data.get(str(app_id),{}).get('data',{})
                        logger.info(f"[API] 정보 요청 완료: {data.get('name', '')} ({app_id})")
                        return {
                            'success': True,
                            'data': data,
                            'app_id': app_id
                        }
                    
                    # 요청 제한 관련 상태 코드 (Steam은 403도 사용)
                    elif response.status in [403, 429, 503, 502, 504]:
                        if attempt < max_retries:
                            # 지수적으로 증가하는 딜레이 (2초, 4초, 8초, 16초, 32초, 64초, 128초)
                            delay = 2 * (2 ** attempt)
                            logger.warning(f"게임 ID {app_id}: HTTP {response.status} - {attempt + 1}회 실패, {delay}초 후 재시도...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"게임 ID {app_id}: HTTP {response.status} - 최대 재시도 횟수 초과")
                            return {
                                'success': False,
                                'error': 'rate_limit_exceeded',
                                'message': f'HTTP {response.status} - 최대 재시도 횟수 ({max_retries}) 초과',
                                'app_id': app_id,
                                'http_status': response.status
                            }
                    
                    # 기타 HTTP 에러
                    else:
                        logger.error(f"게임 ID {app_id}: HTTP {response.status} 오류")
                        return {
                            'success': False,
                            'error': 'http_error',
                            'message': f'HTTP {response.status} 오류',
                            'app_id': app_id,
                            'http_status': response.status
                        }
                        
        except Exception as e:
            if attempt < max_retries and "HTTP" in str(e) and any(code in str(e) for code in ["403", "429", "503", "502", "504"]):
                # 재시도 가능한 네트워크 오류
                delay = 2 * (2 ** attempt)
                logger.warning(f"게임 ID {app_id}: 네트워크 오류 - {attempt + 1}회 실패, {delay}초 후 재시도... ({str(e)})")
                await asyncio.sleep(delay)
                continue
            elif attempt == max_retries:
                logger.error(f"게임 ID {app_id}: 최대 재시도 횟수 초과 - {str(e)}")
                return {
                    'success': False,
                    'error': 'exception',
                    'message': f'최대 재시도 횟수 ({max_retries}) 초과 - {str(e)}',
                    'app_id': app_id,
                    'exception_type': type(e).__name__
                }
            else:
                logger.error(f"게임 ID {app_id}: API 호출 중 오류 - {str(e)}")
                return {
                    'success': False,
                    'error': 'exception',
                    'message': f'API 호출 중 오류 - {str(e)}',
                    'app_id': app_id,
                    'exception_type': type(e).__name__
                }
    
    # 이론적으로 도달하지 않는 코드이지만 안전을 위해
    logger.error(f"게임 ID {app_id}: API 호출 중 오류. 알 수 없는 오류")
    return {
        'success': False,
        'error': 'unknown',
        'message': '알 수 없는 오류',
        'app_id': app_id
    }

# 동기 버전 (편의 함수)
def get_steam_game_info_api_sync(app_id: int, max_retries: int = 7) -> Dict[str, Any]:
    """게임 상세 정보를 가져옵니다 (동기 버전 - 편의 함수)."""
    return asyncio.run(get_steam_game_info_api(app_id, max_retries))

# 여러 게임 동시 처리
async def get_multiple_games_api(app_ids: list[int], max_retries: int = 7) -> Dict[int, Dict[str, Any]]:
    """여러 게임의 상세 정보를 동시에 가져옵니다 (기본 비동기 버전)."""
    tasks = [get_steam_game_info_api(app_id, max_retries) for app_id in app_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 결과를 딕셔너리로 매핑
    game_data = {}
    for app_id, result in zip(app_ids, results):
        if isinstance(result, Exception):
            game_data[app_id] = {
                'success': False,
                'error': 'exception',
                'message': str(result),
                'app_id': app_id,
                'exception_type': type(result).__name__
            }
        else:
            game_data[app_id] = result
    
    return game_data

# 편의 함수
def get_multiple_games_api_sync(app_ids: list[int], max_retries: int = 7) -> Dict[int, Dict[str, Any]]:
    """여러 게임의 상세 정보를 가져옵니다 (동기 버전 - 편의 함수)."""
    return asyncio.run(get_multiple_games_api(app_ids, max_retries))

if __name__ == "__main__":
    setup_logger("INFO")
    # 새로운 return 형식 테스트
    result = get_steam_game_info_api_sync(1245620)
    print(result['data'])
    