import requests
from bs4 import BeautifulSoup, Tag
import re

def html_to_text(html_content: str) -> str:
    """HTML을 일반 텍스트로 변환합니다."""
    if not html_content:
        return ""
    
    # BeautifulSoup으로 HTML 파싱
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 텍스트만 추출
    text = soup.get_text()
    
    # 불필요한 공백과 줄바꿈 정리
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

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
        if element.name == 'strong':
            text = element.get_text().strip()
            # 메인 섹션 제목 (Minimum:, Recommended:)만 처리
            if text in ['Minimum:', 'Recommended:']:
                if result:  # 이전 섹션이 있으면 줄바꿈 추가
                    result.append('\n\n')
                result.append(f"{text}\n")
                current_section = text
        elif element.name == 'li' and current_section:
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

def get_game_details(app_id: int):
    """게임 상세 정보를 가져옵니다."""
    base_url = f"https://store.steampowered.com/api/appdetails"
    params = {
        'appids': app_id,
        'cc': 'us',
        'l': 'english'
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching game details for app ID {app_id}: {e}")
        return None
    
if __name__ == "__main__":
    # 한 게임만 테스트
    game_id = 238960    # Cyberpunk 2077
    
    print(f"테스트 게임: Cyberpunk 2077 (ID: {game_id})")
    print("="*60)
    
    game_details = get_game_details(game_id)
    
    