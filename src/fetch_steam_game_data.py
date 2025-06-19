import requests
import aiohttp
import asyncio
from bs4 import BeautifulSoup, Tag
import re
from typing import Optional, Dict, Any
import logging

# 로거 유틸리티 import
from utils.logger import setup_logger

# 로거 설정
logger = logging.getLogger(__name__)

def html_to_text(html_content: str) -> str:
    """HTML을 읽기 쉬운 텍스트로 변환합니다 (구조 보존)."""
    if not html_content:
        return ""
    
    # BeautifulSoup으로 HTML 파싱
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 블록 레벨 요소들을 줄바꿈으로 교체
    block_elements = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'br', 'li']
    
    # HTML을 문자열로 변환하여 정규식으로 처리
    html_str = str(soup)
    
    # 블록 요소들 앞뒤에 줄바꿈 추가
    for element in block_elements:
        # 여는 태그 앞에 줄바꿈
        html_str = re.sub(f'<{element}[^>]*>', f'\n<{element}>', html_str)
        # 닫는 태그 뒤에 줄바꿈  
        html_str = re.sub(f'</{element}>', f'</{element}>\n', html_str)
    
    # br 태그는 단순 줄바꿈으로 교체
    html_str = re.sub(r'<br[^>]*>', '\n', html_str)
    
    # 다시 BeautifulSoup으로 파싱하여 텍스트 추출
    soup = BeautifulSoup(html_str, 'html.parser')
    text = soup.get_text()
    
    # 정리 작업
    # 1. 연속된 공백을 하나로 (단, 줄바꿈은 유지)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 2. 연속된 줄바꿈을 최대 2개로 제한
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 3. 각 줄의 앞뒤 공백 제거
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines]
    
    # 4. 빈 줄 정리 (연속된 빈 줄 제거)
    result_lines = []
    prev_empty = False
    for line in cleaned_lines:
        if line == '':
            if not prev_empty:  # 이전 줄이 빈 줄이 아닌 경우만 추가
                result_lines.append(line)
            prev_empty = True
        else:
            result_lines.append(line)
            prev_empty = False
    
    # 5. 시작과 끝의 빈 줄 제거
    while len(result_lines) > 0 and result_lines[0] == '':
        result_lines.pop(0)
    while len(result_lines) > 0 and result_lines[-1] == '':
        result_lines.pop()
    
    return '\n'.join(result_lines)

def clean_system_requirements(html_content: str) -> str:
    """시스템 요구사항 HTML을 읽기 쉬운 텍스트로 변환합니다."""
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    result = []
    
    # 현재 섹션 추적
    current_section = ""
    
    # 모든 요소를 순서대로 처리
    for element in soup.find_all(['strong', 'li']):
        # Tag 타입인지 확인하여 linter 오류 수정
        if isinstance(element, Tag) and element.name == 'strong':
            text = element.get_text().strip()
            # 메인 섹션 제목 (Minimum:, Recommended:)만 처리
            if text in ['Minimum:', 'Recommended:']:
                if result:  # 이전 섹션이 있으면 줄바꿈 추가
                    result.append('\n\n')
                result.append(f"{text}\n")
                current_section = text
        elif isinstance(element, Tag) and element.name == 'li' and current_section:
            # 리스트 항목 처리
            li_text = element.get_text().strip()
            if li_text:
                result.append(f"- {li_text}\n")
    
    # 위 방법이 작동하지 않으면 더 간단한 방법 사용
    if not result or len(result) <= 2:
        # HTML을 텍스트로 변환 후 구조화
        text = html_to_text(html_content)
        
        # 메인 섹션별로 분할
        if 'Minimum:' in text:
            parts = text.split('Minimum:')
            if len(parts) > 1:
                result.append('Minimum:\n')
                min_content = parts[1]
                
                # Recommended: 부분이 있으면 분리
                if 'Recommended:' in min_content:
                    min_parts = min_content.split('Recommended:')
                    min_content = min_parts[0].strip()
                    
                    # 최소 요구사항 처리
                    formatted_min = format_requirements_text(min_content)
                    result.append(formatted_min)
                    
                    # 권장 사양 처리
                    if len(min_parts) > 1:
                        result.append('\n\nRecommended:\n')
                        rec_content = min_parts[1].strip()
                        formatted_rec = format_requirements_text(rec_content)
                        result.append(formatted_rec)
                else:
                    # 최소 요구사항만 있는 경우
                    formatted_min = format_requirements_text(min_content)
                    result.append(formatted_min)
        elif 'Recommended:' in text:
            # 권장 사양만 있는 경우
            parts = text.split('Recommended:')
            if len(parts) > 1:
                result.append('Recommended:\n')
                rec_content = parts[1].strip()
                formatted_rec = format_requirements_text(rec_content)
                result.append(formatted_rec)
    
    final_result = ''.join(result).strip()
    return final_result

def format_requirements_text(content: str) -> str:
    """요구사항 텍스트를 리스트 형식으로 포맷팅합니다."""
    # OS:, Processor:, Memory: 등의 패턴을 찾아서 각각을 리스트 항목으로 만듦
    formatted_items = []
    
    # 주요 요구사항 항목들을 찾기 위한 패턴
    patterns = [
        r'((?:OS|Operating System)[^:]*:\s*[^A-Z]+?)(?=\s+(?:Processor|CPU|Memory|RAM|Graphics|Video|DirectX|Storage|Network|Additional|Sound))',
        r'((?:Processor|CPU)[^:]*:\s*[^A-Z]+?)(?=\s+(?:Memory|RAM|Graphics|Video|DirectX|Storage|Network|Additional|Sound|OS))',
        r'((?:Memory|RAM)[^:]*:\s*[^A-Z]+?)(?=\s+(?:Graphics|Video|DirectX|Storage|Network|Additional|Sound|OS|Processor))',
        r'((?:Graphics|Video)[^:]*:\s*[^A-Z]+?)(?=\s+(?:DirectX|Storage|Network|Additional|Sound|OS|Processor|Memory))',
        r'(DirectX[^:]*:\s*[^A-Z]+?)(?=\s+(?:Storage|Network|Additional|Sound|OS|Processor|Memory|Graphics))',
        r'((?:Storage|Network)[^:]*:\s*[^A-Z]+?)(?=\s+(?:Additional|Sound|OS|Processor|Memory|Graphics|DirectX))',
        r'((?:Additional|Sound)[^:]*:\s*.+?)(?=\s+(?:OS|Processor|Memory|Graphics|DirectX|Storage|Network)|\s*$)'
    ]
    
    content = content.strip()
    used_positions = set()
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            start, end = match.span()
            # 이미 사용된 위치와 겹치지 않는지 확인
            if not any(start < pos < end or pos < start < pos_end for pos, pos_end in used_positions):
                item = match.group(1).strip()
                if item and len(item) > 5:  # 너무 짧은 항목 제외
                    # 줄바꿈과 여분의 공백 정리
                    item = re.sub(r'\s+', ' ', item)
                    formatted_items.append(f"- {item}")
                    used_positions.add((start, end))
    
    # 패턴으로 찾지 못한 경우 전체 텍스트를 하나의 항목으로
    if not formatted_items and content:
        content = re.sub(r'\s+', ' ', content)
        formatted_items.append(f"- {content}")
    
    return '\n'.join(formatted_items) + '\n' if formatted_items else ""

# 비동기 버전 (기본 버전)
async def get_steam_game_info_api(app_id: int, max_retries: int = 7) -> Dict[str, Any]:
    """게임 상세 정보를 가져옵니다 (기본 비동기 버전)."""
    base_url = f"https://store.steampowered.com/api/appdetails"
    params = {
        'appids': app_id,
        'cc': 'us',
        'l': 'english'
    }
    logger.info(f"게임 API 정보 요청 중: {app_id}")
    for attempt in range(max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    # 성공적인 응답
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'data': data.get(str(app_id),{}).get('data',{}),
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

# 테스트 함수들
# 동기 vs 비동기 비교
def test_sync_vs_async(save: bool = False):
    """동기와 비동기 성능 비교 테스트"""
    import time
    
    # 테스트 게임들
    test_game_ids = [238960, 1091500, 730]  # Cyberpunk 2077, 사이버펑크 2077, CS2
    
    print("=== 동기 버전 테스트 ===")
    start_time = time.time()
    
    sync_results = []
    for game_id in test_game_ids:
        result = get_steam_game_info_api_sync(game_id)
        if result['success']:
            print(f"게임 ID {game_id}: 성공")
            sync_results.append(f"게임 ID {game_id}: 성공")
        else:
            print(f"게임 ID {game_id}: 실패 - {result.get('error', 'unknown')}")
            sync_results.append(f"게임 ID {game_id}: 실패 - {result.get('error', 'unknown')}")
    
    sync_time = time.time() - start_time
    print(f"동기 처리 시간: {sync_time:.2f}초")
    
    print("\n=== 비동기 버전 테스트 ===")
    start_time = time.time()
    
    async def test_async():
        results = await get_multiple_games_api(test_game_ids)
        async_results = []
        for game_id, result in results.items():
            if result['success']:
                print(f"게임 ID {game_id}: 성공")
                async_results.append(f"게임 ID {game_id}: 성공")
            else:
                print(f"게임 ID {game_id}: 실패 - {result.get('error', 'unknown')}")
                async_results.append(f"게임 ID {game_id}: 실패 - {result.get('error', 'unknown')}")
        return async_results
    
    async_results = asyncio.run(test_async())
    async_time = time.time() - start_time
    print(f"비동기 처리 시간: {async_time:.2f}초")
    print(f"성능 향상: {sync_time/async_time:.1f}배")
    
    # 결과 저장
    if save:
        import json
        import os
        from datetime import datetime
        
        os.makedirs("data/temp", exist_ok=True)
        
        test_result = {
            "test_type": "sync_vs_async",
            "timestamp": datetime.now().isoformat(),
            "test_game_ids": test_game_ids,
            "sync_time": sync_time,
            "async_time": async_time,
            "performance_improvement": sync_time/async_time,
            "sync_results": sync_results,
            "async_results": async_results
        }
        
        filename = f"data/temp/sync_vs_async_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 테스트 결과가 저장되었습니다: {filename}")

# detailed_description 테스트
def test_detailed_description(app_id: int, save: bool = False):
    """detailed_description HTML 변환 테스트"""
    result = get_steam_game_info_api_sync(app_id)
    
    if result['success'] and str(app_id) in result['data'] and 'data' in result['data'][str(app_id)]:
        game_name = result['data'][str(app_id)]['data']['name']
        des = result['data'][str(app_id)]['data']['detailed_description']
        _des = html_to_text(des)
        print("=== Raw detailed_description ===")
        print(des)
        print("\n=== After html_to_text conversion ===")
        print(_des)

        if save:
            import os, json
            folder_path = "data/detailed_description_test"
            test_result = {
                "test_type": "detailed_description",
                "app_id": app_id,
                "game_name": game_name,
                "raw_detailed_description": des,
                "cleaned_detailed_description": _des
            }
            os.makedirs(folder_path, exist_ok=True)
            filename = f"{folder_path}/detailed_description_test_{game_name}_{app_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(test_result, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 테스트 결과가 저장되었습니다: {filename}")
    else:
        print(f"❌ API 호출 실패: {result.get('error', 'unknown')} - {result.get('message', '알 수 없는 오류')}")

# 시스템 요구사항 테스트
def test_system_requirements(app_id: int, save: bool = False):
    """시스템 요구사항 HTML 변환 테스트"""
    print("=== 시스템 요구사항 테스트 ===")
    result = get_steam_game_info_api_sync(app_id)
    
    if result['success'] and str(app_id) in result['data'] and 'data' in result['data'][str(app_id)]:
        game_name = result['data'][str(app_id)]['data']['name']

        print(f"\n{'='*60}")
        print(f"게임: {game_name} (ID: {app_id})")
        print(f"{'='*60}")

        game_data = result['data'][str(app_id)]['data']
        
        # PC 요구사항 확인
        pc_requirements = game_data.get('pc_requirements', {})
        
        if pc_requirements:
            print("--- Raw PC Requirements ---")
            min_raw = pc_requirements.get('minimum', 'N/A')
            rec_raw = pc_requirements.get('recommended', 'N/A')
            print(f"Minimum: {min_raw}")
            print(f"Recommended: {rec_raw}")
            
            print("\n--- Cleaned Requirements ---")
            
            min_cleaned = ""
            rec_cleaned = ""
            
            # Minimum 요구사항 정리
            if pc_requirements.get('minimum'):
                min_cleaned = clean_system_requirements(pc_requirements['minimum'])
                print("MINIMUM:")
                print(min_cleaned)
            
            # Recommended 요구사항 정리
            if pc_requirements.get('recommended'):
                rec_cleaned = clean_system_requirements(pc_requirements['recommended'])
                print("\nRECOMMENDED:")
                print(rec_cleaned)
            
            # 결과 저장
            if save:
                import json
                import os
                from datetime import datetime
                
                folder_path = "data/requirements_test"
                os.makedirs(folder_path, exist_ok=True)
                
                test_result = {
                    "test_type": "system_requirements",
                    "timestamp": datetime.now().isoformat(),
                    "app_id": app_id,
                    "game_name": game_name,
                    "raw_minimum": min_raw,
                    "raw_recommended": rec_raw,
                    "cleaned_minimum": min_cleaned,
                    "cleaned_recommended": rec_cleaned
                }
                
                filename = f"{folder_path}/system_requirements_test_{game_name}_{app_id}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(test_result, f, ensure_ascii=False, indent=2)
                
                print(f"\n💾 테스트 결과가 저장되었습니다: {filename}")
                
        else:
            print("❌ PC 시스템 요구사항 없음")
            if save:
                import json
                import os
                from datetime import datetime
                
                folder_path = "data/requirements_test"
                os.makedirs(folder_path, exist_ok=True)
                
                test_result = {
                    "test_type": "system_requirements",
                    "timestamp": datetime.now().isoformat(),
                    "app_id": app_id,
                    "game_name": game_name,
                    "error": "PC 시스템 요구사항 없음"
                }
                
                filename = f"{folder_path}/system_requirements_test_{game_name}_{app_id}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(test_result, f, ensure_ascii=False, indent=2)
                
                print(f"\n💾 테스트 결과가 저장되었습니다: {filename}")
    else:
        print(f"❌ API 호출 실패: {result.get('error', 'unknown')} - {result.get('message', '알 수 없는 오류')}")

    print("\n" + "-"*60)

if __name__ == "__main__":
    setup_logger("INFO")
    # 새로운 return 형식 테스트
    result = get_steam_game_info_api_sync(1245620)
    print(result['data'])
    