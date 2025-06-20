"""Steam Game Data Database Inserter

Steam 게임 데이터를 데이터베이스에 효율적으로 삽입/업데이트하는 모듈

주요 기능:
    1. Steam API 데이터 처리 및 DB 저장
    2. Steam 크롤링 데이터 처리 및 DB 저장  
    3. 변경점만 업데이트하는 효율적인 로직
    4. HTML 콘텐츠를 읽기 쉬운 텍스트로 변환
    5. 배치 처리 지원
    6. 하이브리드 배치 처리 (새 게임: bulk insert, 기존 게임: 개별 업데이트)

데이터 소스별 처리:
    - Steam API: 상세한 게임 정보 (설명, 시스템 요구사항, 메타크리틱 점수 등)
    - Steam 크롤링: 사용자 태그, 리뷰 정보, 현지화된 가격 정보

성능 최적화:
    - 변경된 필드만 UPDATE (전체 삭제/재삽입 없음)
    - 관련 테이블(장르, 태그, 가격, 리뷰) 개별 변경점 체크
    - 배치 처리로 대량 데이터 효율적 처리
    - 하이브리드 배치: 새 게임 bulk insert + 기존 게임 선택적 업데이트

사용 예시:
    # 단일 게임 처리
    success = insert_steam_api_game_single(steam_api_data)
    success = insert_steam_crawling_game_single(crawling_data)

    # 배치 처리 (성능 최적화)
    success_count, fail_count = insert_steam_api_games_batch(api_data_list)
    success_count, fail_count = insert_steam_crawling_games_batch(crawling_data_list)
    
    # 컨텍스트 매니저 사용
    with GameInserter() as inserter:
        inserter.insert_steam_api_game(data1)
        inserter.insert_steam_crawling_game(data2)

처리 대상 테이블:
    - games: 게임 기본 정보
    - game_genres: 게임 장르
    - game_tags: 사용자 태그 (크롤링)
    - game_pricing: 가격 정보 (크롤링)
    - game_reviews: 리뷰 정보 (크롤링)
"""

import logging
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import Game, GameTag, GameGenre, GamePricing, GameReview
from .connection import get_db_session

logger = logging.getLogger(__name__)


class GameInserter:
    """게임 데이터를 데이터베이스에 삽입하는 클래스"""
    
    def __init__(self):
        self.session: Optional[Session] = None
    
    def __enter__(self) -> 'GameInserter':
        self.session = get_db_session()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
            self.session.close()
    
    @property
    def _session(self) -> Session:
        """세션 객체를 안전하게 반환"""
        if self.session is None:
            raise RuntimeError("세션이 초기화되지 않았습니다. with 문을 사용하세요.")
        return self.session
    
    def parse_steam_release_date(self, date_str: str) -> Optional[date]:
        """Steam API 출시일 문자열을 date 객체로 변환"""
        if not date_str:
            return None
        
        try:
            # "Feb 24, 2022" 형식 파싱 (Steam API 형식)
            return datetime.strptime(date_str, "%b %d, %Y").date()
        except ValueError:
            try:
                # 다른 형식들 시도
                formats = [
                    '%d %b, %Y',  # 예: "25 Mar, 2015"
                    '%b %d, %Y',  # 예: "Mar 25, 2015"
                    '%d %B, %Y',  # 예: "25 March, 2015"
                    '%B %d, %Y',  # 예: "March 25, 2015"
                    '%d %b %Y',   # 예: "25 Mar 2015"
                    '%b %d %Y',   # 예: "Mar 25 2015"
                    '%Y-%m-%d',   # 예: "2015-03-25"
                    '%Y년 %m월 %d일',  # 예: "2015년 03월 25일"
                    '%Y.%m.%d',   # 예: "2015.03.25"
                    '%m/%d/%Y',   # 예: "03/25/2015"
                    '%d/%m/%Y'    # 예: "25/03/2015"
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
                
                # 정규식으로 날짜 추출 시도
                date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)(?:,|\s+)?\s+(\d{4})', date_str)
                if date_match:
                    day, month, year = date_match.groups()
                    months = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 
                            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
                    month_num = months.get(month.lower()[:3])
                    if month_num:
                        return datetime(int(year), month_num, int(day)).date()
                
            except Exception:
                logger.warning(f"날짜 파싱 실패: '{date_str}'")
                return None
        return None

    def convert_detailed_description(self, html_content: str) -> str:
        """HTML 상세 설명을 읽기 쉬운 텍스트로 변환합니다"""
        if not html_content:
            return ""
        
        from bs4 import BeautifulSoup, Tag
        
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

    def convert_system_requirements(self, html_content: str) -> str:
        """시스템 요구사항 HTML을 읽기 쉬운 텍스트로 변환합니다"""
        if not html_content:
            return ""
        
        from bs4 import BeautifulSoup, Tag
        
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
            text = self.convert_detailed_description(html_content)
            
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
                        formatted_min = self._format_requirements_text(min_content)
                        result.append(formatted_min)
                        
                        # 권장 사양 처리
                        if len(min_parts) > 1:
                            result.append('\n\nRecommended:\n')
                            rec_content = min_parts[1].strip()
                            formatted_rec = self._format_requirements_text(rec_content)
                            result.append(formatted_rec)
                    else:
                        # 최소 요구사항만 있는 경우
                        formatted_min = self._format_requirements_text(min_content)
                        result.append(formatted_min)
            elif 'Recommended:' in text:
                # 권장 사양만 있는 경우
                parts = text.split('Recommended:')
                if len(parts) > 1:
                    result.append('Recommended:\n')
                    rec_content = parts[1].strip()
                    formatted_rec = self._format_requirements_text(rec_content)
                    result.append(formatted_rec)
        
        final_result = ''.join(result).strip()
        return final_result

    def _format_requirements_text(self, content: str) -> str:
        """요구사항 텍스트를 리스트 형식으로 포맷팅합니다"""
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

    def insert_steam_api_game(self, steam_data: Dict[str, Any]) -> bool:
        """Steam API에서 가져온 게임 데이터를 데이터베이스에 삽입/업데이트 (변경점만)"""
        try:
            if not steam_data:
                logger.error("Steam 데이터가 비어있습니다.")
                return False
            
            app_id = steam_data.get('steam_appid') or steam_data.get('id')
            if not app_id:
                logger.error("app_id가 없습니다.")
                return False
            
            # 기존 데이터 확인
            existing_game = self._session.query(Game).filter_by(app_id=app_id).first()
            is_new_game = existing_game is None
            
            # 기본 정보 추출 및 변환
            title = steam_data.get('name', '')[:255]  # VARCHAR(255) 제한
            description = steam_data.get('short_description', '')
            
            # 상세 설명 HTML → 텍스트 변환
            raw_detailed_description = steam_data.get('detailed_description', '')
            detailed_description = self.convert_detailed_description(raw_detailed_description)
            
            # 출시일 정보
            release_info = steam_data.get('release_date', {})
            release_date = release_info.get('date', '') if release_info else ''
            parsed_release_date = self.parse_steam_release_date(release_date)
            
            # 개발사/퍼블리셔 정보
            developers = steam_data.get('developers', [])
            publishers = steam_data.get('publishers', [])
            developer = ', '.join(developers)[:255] if developers else None
            publisher = ', '.join(publishers)[:255] if publishers else None
            
            # 이미지 정보
            header_image_url = steam_data.get('header_image', '')[:500] if steam_data.get('header_image') else None
            
            # 시스템 요구사항 HTML → 텍스트 변환
            pc_requirements = steam_data.get('pc_requirements', {})
            raw_min_requirements = pc_requirements.get('minimum', '') if pc_requirements else ''
            raw_rec_requirements = pc_requirements.get('recommended', '') if pc_requirements else ''
            system_requirements_minimum = self.convert_system_requirements(raw_min_requirements) if raw_min_requirements else None
            system_requirements_recommended = self.convert_system_requirements(raw_rec_requirements) if raw_rec_requirements else None
            
            # 메타크리틱 점수
            metacritic = steam_data.get('metacritic', {})
            metacritic_score = metacritic.get('score') if metacritic else None
            
            if is_new_game:
                # 새 게임: 전체 삽입
                logger.debug(f"[API-DB] 새 게임 {app_id} ({title}) database 삽입")
                game = Game(
                    app_id=app_id,
                    title=title,
                    description=description,
                    detailed_description=detailed_description,
                    release_date=parsed_release_date,
                    developer=developer,
                    publisher=publisher,
                    header_image_url=header_image_url,
                    system_requirements_minimum=system_requirements_minimum,
                    system_requirements_recommended=system_requirements_recommended,
                    metacritic_score=metacritic_score
                )
                self._session.add(game)
            else:
                # 기존 게임: 변경점만 업데이트
                updated = False
                
                # 기본 정보 변경 체크
                if existing_game.title != title:
                    existing_game.title = title
                    updated = True
                if existing_game.description != description:
                    existing_game.description = description
                    updated = True
                if existing_game.detailed_description != detailed_description:
                    existing_game.detailed_description = detailed_description
                    updated = True
                if existing_game.release_date != parsed_release_date:
                    existing_game.release_date = parsed_release_date
                    updated = True
                if existing_game.developer != developer:
                    existing_game.developer = developer
                    updated = True
                if existing_game.publisher != publisher:
                    existing_game.publisher = publisher
                    updated = True
                if existing_game.header_image_url != header_image_url:
                    existing_game.header_image_url = header_image_url
                    updated = True
                if existing_game.system_requirements_minimum != system_requirements_minimum:
                    existing_game.system_requirements_minimum = system_requirements_minimum
                    updated = True
                if existing_game.system_requirements_recommended != system_requirements_recommended:
                    existing_game.system_requirements_recommended = system_requirements_recommended
                    updated = True
                if existing_game.metacritic_score != metacritic_score:
                    existing_game.metacritic_score = metacritic_score
                    updated = True
                
                if updated:
                    existing_game.updated_at = datetime.now()
                    logger.debug(f"[API-DB] 게임 {app_id} ({title}) 기본 정보 업데이트")
                else:
                    logger.debug(f"[API-DB] 게임 {app_id} ({title}) 기본 정보 변경 없음")
            
            self._session.flush()
            
            # 장르 정보 업데이트 (변경점만)
            self._update_genres(app_id, steam_data.get('genres', []))
            logger.debug(f"[API-DB] 데이터 삽입/업데이트 완료: {title} ({app_id})")
            return True
            
        except Exception as e:
            logger.error(f"Steam API 게임 데이터 삽입/업데이트 중 오류 발생: {e}")
            return False

    def _update_genres(self, app_id: int, genres_data: List[Dict[str, Any]]):
        """장르 정보 업데이트 (변경점만)"""
        # 현재 DB의 장르들
        existing_genres = {g.genre_name for g in self._session.query(GameGenre).filter_by(app_id=app_id).all()}
        
        # 새로운 장르들
        new_genres = {genre_data.get('description', '') for genre_data in genres_data if genre_data.get('description')}
        
        # 삭제할 장르들
        genres_to_delete = existing_genres - new_genres
        if genres_to_delete:
            self._session.query(GameGenre).filter(
                GameGenre.app_id == app_id,
                GameGenre.genre_name.in_(genres_to_delete)
            ).delete(synchronize_session=False)
            logger.debug(f"[API-DB] 게임 {app_id} 장르 삭제: {genres_to_delete}")
        
        # 추가할 장르들
        genres_to_add = new_genres - existing_genres
        for genre_name in genres_to_add:
            if genre_name:  # 빈 문자열 체크
                genre = GameGenre(
                    app_id=app_id,
                    genre_name=genre_name[:50]  # VARCHAR(50) 제한
                )
                self._session.add(genre)
        
        if genres_to_add:
            logger.debug(f"[API-DB] 게임 {app_id} 장르 추가: {len(genres_to_add)}개")

    def insert_steam_crawling_game(self, crawling_data: Dict[str, Any]) -> bool:
        """Steam 크롤링에서 가져온 게임 데이터를 데이터베이스에 삽입/업데이트"""
        try:
            if not crawling_data:
                logger.error("크롤링 데이터가 비어있습니다.")
                return False
            
            app_id = crawling_data.get('app_id')
            if not app_id:
                logger.error("app_id가 없습니다.")
                return False
            
            # 기존 게임 데이터 확인
            existing_game = self._session.query(Game).filter_by(app_id=app_id).first()
            
            # 크롤링 타임스탬프 파싱
            crawled_at_str = crawling_data.get('crawled_at', '')
            try:
                crawled_at = datetime.fromisoformat(crawled_at_str.replace('Z', '+00:00')) if crawled_at_str else datetime.now()
            except:
                crawled_at = datetime.now()
            
            if existing_game:
                # 기존 게임: 크롤링 특화 정보만 업데이트
                title = crawling_data.get('title', '')[:255]
                if existing_game.title != title and title:
                    existing_game.title = title
                    existing_game.updated_at = crawled_at
                    logger.debug(f"[CRW-DB] 게임 {app_id} 제목 업데이트: {title}")
            else:
                # 새 게임: 기본 정보만으로 레코드 생성
                title = crawling_data.get('title', '')[:255]
                game = Game(
                    app_id=app_id,
                    title=title,
                    description="크롤링으로 수집된 게임 (API 데이터 없음)",
                    updated_at=crawled_at
                )
                self._session.add(game)
                logger.debug(f"[CRW-DB] 게임 {app_id} 기본 정보 생성")
            
            self._session.flush()
            
            # 사용자 태그 정보 업데이트
            user_tags = crawling_data.get('user_tags', [])
            if user_tags:
                self._update_user_tags(app_id, user_tags)
            
            # 리뷰 정보 업데이트
            review_info = crawling_data.get('review_info', {})
            if review_info:
                self._update_review_info(app_id, review_info, crawled_at)
            
            # 현지화된 가격 정보 업데이트
            localized_price = crawling_data.get('localized_price', {})
            if localized_price:
                self._update_localized_pricing(app_id, localized_price, crawled_at)
            logger.debug(f"[CRW-DB] 데이터 삽입/업데이트 완료: {crawling_data.get('title', '')} ({app_id})")
            return True
            
        except Exception as e:
            logger.error(f"[CRW-DB] 데이터 삽입/업데이트 중 오류 발생: {e}")
            return False

    def _update_user_tags(self, app_id: int, user_tags: List[str]):
        """사용자 태그 정보 업데이트 (크롤링으로 수집된 태그)"""
        # 현재 DB의 태그들 (순서 포함)
        existing_tags = {(t.tag_name, t.tag_order) for t in self._session.query(GameTag).filter_by(app_id=app_id).all()}
        
        # 새로운 태그들 (순서 포함)
        new_tags = set()
        for i, tag_name in enumerate(user_tags):
            if tag_name and len(tag_name.strip()) > 0:
                clean_tag = tag_name.strip()[:100]  # VARCHAR(100) 제한
                new_tags.add((clean_tag, i + 1))
        
        # 변경이 있는지 체크
        if existing_tags != new_tags:
            # 모든 기존 태그 삭제 (순서가 중요하므로)
            self._session.query(GameTag).filter_by(app_id=app_id).delete()
            
            # 새 태그들 추가
            for tag_name, tag_order in new_tags:
                tag = GameTag(
                    app_id=app_id,
                    tag_name=tag_name,
                    tag_order=tag_order
                )
                self._session.add(tag)
            
            logger.debug(f"[CRW-DB] 게임 {app_id} 사용자 태그 업데이트: {len(new_tags)}개")
        else:
            logger.debug(f"[CRW-DB] 게임 {app_id} 사용자 태그 변경 없음")

    def _update_review_info(self, app_id: int, review_info: Dict[str, Any], crawled_at: datetime):
        """리뷰 정보 업데이트"""
        # 기존 리뷰 정보 찾기
        existing_review = self._session.query(GameReview).filter_by(app_id=app_id).first()
        
        # 리뷰 데이터 추출
        recent_reviews = review_info.get('recent_reviews', '')[:50] if review_info.get('recent_reviews') else None
        all_reviews = review_info.get('all_reviews', '')[:50] if review_info.get('all_reviews') else None
        
        # 리뷰 개수 (DB에 문자열로 저장되므로 문자열로 처리)
        def parse_review_count_to_string(count_str):
            if not count_str:
                return None
            try:
                # "6,337" -> "6337" (문자열로 반환)
                return str(int(str(count_str).replace(',', '')))
            except:
                return None
        
        recent_review_count = parse_review_count_to_string(review_info.get('recent_review_count'))
        total_review_count = parse_review_count_to_string(review_info.get('total_review_count'))
        recent_positive_percent = review_info.get('recent_positive_percent')
        total_positive_percent = review_info.get('total_positive_percent')
        
        if existing_review:
            # 기존 리뷰 정보 업데이트
            review_changed = (
                existing_review.recent_reviews != recent_reviews or
                existing_review.all_reviews != all_reviews or
                existing_review.recent_review_count != recent_review_count or
                existing_review.total_review_count != total_review_count or
                existing_review.recent_positive_percent != recent_positive_percent or
                existing_review.total_positive_percent != total_positive_percent
            )
            
            if review_changed:
                existing_review.recent_reviews = recent_reviews
                existing_review.all_reviews = all_reviews
                existing_review.recent_review_count = recent_review_count
                existing_review.total_review_count = total_review_count
                existing_review.recent_positive_percent = recent_positive_percent
                existing_review.total_positive_percent = total_positive_percent
                existing_review.updated_at = crawled_at
                logger.debug(f"[CRW-DB] 게임 {app_id} 리뷰 정보 업데이트")
            else:
                logger.debug(f"[CRW-DB] 게임 {app_id} 리뷰 정보 변경 없음")
        else:
            # 새 리뷰 정보 추가
            review = GameReview(
                app_id=app_id,
                recent_reviews=recent_reviews,
                all_reviews=all_reviews,
                recent_review_count=recent_review_count,
                total_review_count=total_review_count,
                recent_positive_percent=recent_positive_percent,
                total_positive_percent=total_positive_percent,
                updated_at=crawled_at
            )
            self._session.add(review)
            logger.debug(f"[CRW-DB] 게임 {app_id} 리뷰 정보 추가")

    def _update_localized_pricing(self, app_id: int, localized_price: Dict[str, Any], crawled_at: datetime):
        """현지화된 가격 정보 업데이트 (크롤링으로 수집된 가격)"""
        current_price = localized_price.get('current_price', '')[:50] if localized_price.get('current_price') else None
        original_price = localized_price.get('original_price', '')[:50] if localized_price.get('original_price') else None
        discount_percent = localized_price.get('discount_percent')
        is_free = localized_price.get('is_free', False)
        
        # 기존 가격 정보 찾기
        existing_pricing = self._session.query(GamePricing).filter_by(app_id=app_id).first()
        
        if existing_pricing:
            # 기존 가격 정보 업데이트 (현지화된 가격 우선)
            price_changed = (
                existing_pricing.current_price != current_price or
                existing_pricing.original_price != original_price or
                existing_pricing.discount_percent != discount_percent or
                existing_pricing.is_free != is_free
            )
            
            if price_changed:
                existing_pricing.current_price = current_price
                existing_pricing.original_price = original_price
                existing_pricing.discount_percent = discount_percent
                existing_pricing.is_free = is_free
                existing_pricing.updated_at = crawled_at
                logger.debug(f"[CRW-DB] 게임 {app_id} 현지화 가격 정보 업데이트")
            else:
                logger.debug(f"[CRW-DB] 게임 {app_id} 현지화 가격 정보 변경 없음")
        else:
            # 새 가격 정보 추가
            pricing = GamePricing(
                app_id=app_id,
                current_price=current_price,
                original_price=original_price,
                discount_percent=discount_percent,
                is_free=is_free,
                updated_at=crawled_at
            )
            self._session.add(pricing)
            logger.debug(f"[CRW-DB] 게임 {app_id} 현지화 가격 정보 추가")

    def insert_steam_api_games_hybrid_batch(self, games_data: List[Dict[str, Any]]) -> tuple[int, List[Dict[str, Any]]]:
        """
        하이브리드 배치 처리로 Steam API 게임 데이터를 삽입/업데이트
        - 새 게임: bulk insert (고성능)
        - 기존 게임: 개별 업데이트 (정확한 변경점 관리)
        """
        if not games_data:
            return 0, []
        
        try:
            # 1. 중복 제거된 games_data 생성
            seen_app_ids = set()
            deduplicated_games_data = []
            for game_data in games_data:
                app_id = game_data.get('steam_appid') or game_data.get('id')
                if app_id and app_id not in seen_app_ids:
                    seen_app_ids.add(app_id)
                    deduplicated_games_data.append(game_data)
            games_data = deduplicated_games_data
            
            # 모든 app_id 추출
            app_ids = [data.get('steam_appid') or data.get('id') for data in games_data]
            app_ids = [aid for aid in app_ids if aid]  # None 제거
            
            if not app_ids:
                logger.error("[API-DB] 유효한 app_id가 없습니다.")
                return 0, []
            
            # 2. 기존 게임 조회 (한 번의 쿼리로)
            self._session.flush()  # 이전 변경사항 반영
            existing_app_ids = set(
                row[0] for row in self._session.execute(
                    select(Game.app_id).where(Game.app_id.in_(app_ids))
                ).fetchall()
            )
            
            # 3. 새 게임 vs 기존 게임 분류
            new_games_data = []
            existing_games_data = []
            
            for game_data in games_data:
                app_id = game_data.get('steam_appid') or game_data.get('id')
                if app_id in existing_app_ids:
                    existing_games_data.append(game_data)
                else:
                    new_games_data.append(game_data)
            
            logger.debug(f"[API-DB] 새 게임: {len(new_games_data)}개, 기존 게임: {len(existing_games_data)}개")
            
            success_count = 0
            failed_games = []
            
            # 4. 새 게임들 bulk insert
            if new_games_data:
                new_success, new_fail = self._bulk_insert_new_api_games(new_games_data)
                success_count += new_success
                failed_games.extend([{'app_id': app_id, 'error': 'db_insert_failed', 'message': f'Steam API 게임 데이터 삽입/업데이트 실패'} for app_id in new_fail])
                logger.info(f"[API-DB] 새 게임 bulk insert: 성공 {new_success}개, 실패 {len(new_fail)}개")
            
            # 5. 기존 게임들 개별 업데이트
            if existing_games_data:
                existing_success, existing_fail = self._update_existing_api_games(existing_games_data)
                success_count += existing_success
                failed_games.extend([{'app_id': app_id, 'error': 'db_exception', 'message': f'예외 발생: {str(e)}'} for app_id in existing_fail])
                logger.info(f"[API-DB] 기존 게임 업데이트: 성공 {existing_success}개, 실패 {len(existing_fail)}개")
            
            return success_count, failed_games
            
        except Exception as e:
            logger.error(f"[API-DB] 하이브리드 배치 처리 중 오류: {e}")
            return 0, []
    
    def _bulk_insert_new_api_games(self, new_games_data: List[Dict[str, Any]]) -> tuple[int, List[int]]:
        """새 게임들을 bulk insert로 처리"""
        try:
            # 게임 기본 정보 bulk insert
            game_objects = []
            genre_objects = []
            
            for steam_data in new_games_data:
                try:
                    app_id = steam_data.get('steam_appid') or steam_data.get('id')
                    if not app_id:
                        continue
                    
                    # 기본 정보 변환
                    title = steam_data.get('name', '')[:255]
                    description = steam_data.get('short_description', '')
                    
                    # 상세 설명 변환
                    raw_detailed_description = steam_data.get('detailed_description', '')
                    detailed_description = self.convert_detailed_description(raw_detailed_description)
                    
                    # 출시일 변환
                    release_info = steam_data.get('release_date', {})
                    release_date = release_info.get('date', '') if release_info else ''
                    parsed_release_date = self.parse_steam_release_date(release_date)
                    
                    # 개발사/퍼블리셔
                    developers = steam_data.get('developers', [])
                    publishers = steam_data.get('publishers', [])
                    developer = ', '.join(developers)[:255] if developers else None
                    publisher = ', '.join(publishers)[:255] if publishers else None
                    
                    # 이미지 URL
                    header_image_url = steam_data.get('header_image', '')[:500] if steam_data.get('header_image') else None
                    
                    # 시스템 요구사항
                    pc_requirements = steam_data.get('pc_requirements', {})
                    raw_min_requirements = pc_requirements.get('minimum', '') if pc_requirements else ''
                    raw_rec_requirements = pc_requirements.get('recommended', '') if pc_requirements else ''
                    system_requirements_minimum = self.convert_system_requirements(raw_min_requirements) if raw_min_requirements else None
                    system_requirements_recommended = self.convert_system_requirements(raw_rec_requirements) if raw_rec_requirements else None
                    
                    # 메타크리틱 점수
                    metacritic = steam_data.get('metacritic', {})
                    metacritic_score = metacritic.get('score') if metacritic else None
                    
                    # 게임 객체 생성
                    game_obj = {
                        'app_id': app_id,
                        'title': title,
                        'description': description,
                        'detailed_description': detailed_description,
                        'release_date': parsed_release_date,
                        'developer': developer,
                        'publisher': publisher,
                        'header_image_url': header_image_url,
                        'system_requirements_minimum': system_requirements_minimum,
                        'system_requirements_recommended': system_requirements_recommended,
                        'metacritic_score': metacritic_score,
                        'updated_at': datetime.now()
                    }
                    game_objects.append(game_obj)
                    
                    # 장르 객체들 생성
                    for genre_data in steam_data.get('genres', []):
                        genre_name = genre_data.get('description', '')
                        if genre_name:
                            genre_objects.append({
                                'app_id': app_id,
                                'genre_name': genre_name[:50]
                            })
                
                except Exception as e:
                    logger.error(f"[API-DB] 게임 데이터 변환 실패 {app_id}: {e}")
                    continue
            
            # Bulk insert 실행
            if game_objects:
                self._session.bulk_insert_mappings(Game, game_objects)
                logger.debug(f"[API-DB] 게임 기본 정보 bulk insert: {len(game_objects)}개")
            
            if genre_objects:
                self._session.bulk_insert_mappings(GameGenre, genre_objects)
                logger.debug(f"[API-DB] 장르 정보 bulk insert: {len(genre_objects)}개")
            
            return len(game_objects), []
            
        except Exception as e:
            logger.error(f"[API-DB] Bulk insert 실패: {e}")
            return 0, []
    
    def _update_existing_api_games(self, existing_games_data: List[Dict[str, Any]]) -> tuple[int, List[int]]:
        """기존 게임들을 개별 업데이트로 처리"""
        success_count = 0
        failed_games = []
        
        for steam_data in existing_games_data:
            try:
                if self.insert_steam_api_game(steam_data):
                    success_count += 1
                else:
                    failed_games.append({'app_id': steam_data.get('steam_appid') or steam_data.get('id'), 'error': 'db_insert_failed', 'message': 'Steam API 게임 데이터 삽입/업데이트 실패'})
            except Exception as e:
                app_id = steam_data.get('steam_appid') or steam_data.get('id')
                logger.error(f"[API-DB] 기존 게임 업데이트 실패: {e}")
                failed_games.append({'app_id': app_id, 'error': 'db_exception', 'message': f'예외 발생: {str(e)}'})
        
        return success_count, failed_games

    def insert_steam_crawling_games_hybrid_batch(self, games_data: List[Dict[str, Any]]) -> tuple[int, List[Dict[str, Any]]]:
        """
        하이브리드 배치 처리로 Steam 크롤링 게임 데이터를 삽입/업데이트
        - 새 게임: bulk insert (고성능)
        - 기존 게임: 개별 업데이트 (정확한 변경점 관리)
        """
        if not games_data:
            return 0, []
        
        try:
            # 1. 중복 제거된 games_data 생성
            seen_app_ids = set()
            deduplicated_games_data = []
            for game_data in games_data:
                app_id = game_data.get('app_id')
                if app_id and app_id not in seen_app_ids:
                    seen_app_ids.add(app_id)
                    deduplicated_games_data.append(game_data)
            games_data = deduplicated_games_data
            
            # 모든 app_id 추출
            app_ids = [data.get('app_id') for data in games_data]
            app_ids = [aid for aid in app_ids if aid]  # None 제거
            
            if not app_ids:
                logger.error("[CRW-DB] 유효한 app_id가 없습니다.")
                return 0, []
            
            # 2. 기존 게임 조회
            existing_app_ids = set(
                row[0] for row in self._session.execute(
                    select(Game.app_id).where(Game.app_id.in_(app_ids))
                ).fetchall()
            )
            
            # 3. 새 게임 vs 기존 게임 분류
            new_games_data = []
            existing_games_data = []
            
            for game_data in games_data:
                app_id = game_data.get('app_id')
                if app_id in existing_app_ids:
                    existing_games_data.append(game_data)
                else:
                    new_games_data.append(game_data)
            
            logger.info(f"[CRW-DB] 새 게임: {len(new_games_data)}개, 기존 게임: {len(existing_games_data)}개")
            
            success_count = 0
            failed_games = []
            
            # 4. 새 게임들 bulk insert (기본 정보만)
            if new_games_data:
                new_success, new_fail = self._bulk_insert_new_crawling_games(new_games_data)
                success_count += new_success
                failed_games.extend([{'app_id': app_id, 'error': 'db_insert_failed', 'message': 'Steam 크롤링 게임 데이터 삽입/업데이트 실패'} for app_id in new_fail])
                logger.debug(f"[CRW-DB] 새 게임 bulk insert: 성공 {new_success}개, 실패 {len(new_fail)}개")
            
            # 5. 기존 게임들 개별 업데이트
            if existing_games_data:
                existing_success, existing_fail = self._update_existing_crawling_games(existing_games_data)
                success_count += existing_success
                failed_games.extend([{'app_id': app_id, 'error': 'db_exception', 'message': f'예외 발생: {str(e)}'} for app_id in existing_fail])
                logger.info(f"[CRW-DB] 기존 게임 업데이트: 성공 {existing_success}개, 실패 {len(existing_fail)}개")
            
            return success_count, failed_games
            
        except Exception as e:
            logger.error(f"[CRW-DB] 크롤링 하이브리드 배치 처리 중 오류: {e}")
            return 0, []
    
    def _bulk_insert_new_crawling_games(self, new_games_data: List[Dict[str, Any]]) -> tuple[int, List[int]]:
        """새 크롤링 게임들을 bulk insert로 처리"""
        try:
            # 게임 기본 정보, 태그, 리뷰, 가격 데이터 준비
            game_objects = []
            tag_objects = []
            review_objects = []
            pricing_objects = []
            
            for crawling_data in new_games_data:
                try:
                    app_id = crawling_data.get('app_id')
                    if not app_id:
                        continue
                    
                    # 크롤링 타임스탬프
                    crawled_at_str = crawling_data.get('crawled_at', '')
                    try:
                        crawled_at = datetime.fromisoformat(crawled_at_str.replace('Z', '+00:00')) if crawled_at_str else datetime.now()
                    except:
                        crawled_at = datetime.now()
                    
                    # 게임 기본 정보
                    title = crawling_data.get('title', '')[:255]
                    game_objects.append({
                        'app_id': app_id,
                        'title': title,
                        'description': "크롤링으로 수집된 게임 (API 데이터 없음)",
                        'updated_at': crawled_at
                    })
                    
                    # 사용자 태그
                    for i, tag_name in enumerate(crawling_data.get('user_tags', [])):
                        if tag_name and len(tag_name.strip()) > 0:
                            tag_objects.append({
                                'app_id': app_id,
                                'tag_name': tag_name.strip()[:100],
                                'tag_order': i + 1
                            })
                    
                    # 리뷰 정보
                    review_info = crawling_data.get('review_info', {})
                    if review_info:
                        recent_reviews = review_info.get('recent_reviews', '')[:50] if review_info.get('recent_reviews') else None
                        all_reviews = review_info.get('all_reviews', '')[:50] if review_info.get('all_reviews') else None
                        
                        def parse_review_count_to_string(count_str):
                            if not count_str:
                                return None
                            try:
                                return str(int(str(count_str).replace(',', '')))
                            except:
                                return None
                        
                        recent_review_count = parse_review_count_to_string(review_info.get('recent_review_count'))
                        total_review_count = parse_review_count_to_string(review_info.get('total_review_count'))
                        
                        review_objects.append({
                            'app_id': app_id,
                            'recent_reviews': recent_reviews,
                            'all_reviews': all_reviews,
                            'recent_review_count': recent_review_count,
                            'total_review_count': total_review_count,
                            'recent_positive_percent': review_info.get('recent_positive_percent'),
                            'total_positive_percent': review_info.get('total_positive_percent'),
                            'updated_at': crawled_at
                        })
                    
                    # 가격 정보
                    localized_price = crawling_data.get('localized_price', {})
                    if localized_price:
                        current_price = localized_price.get('current_price', '')[:50] if localized_price.get('current_price') else None
                        original_price = localized_price.get('original_price', '')[:50] if localized_price.get('original_price') else None
                        
                        pricing_objects.append({
                            'app_id': app_id,
                            'current_price': current_price,
                            'original_price': original_price,
                            'discount_percent': localized_price.get('discount_percent'),
                            'is_free': localized_price.get('is_free', False),
                            'updated_at': crawled_at
                        })
                
                except Exception as e:
                    logger.error(f"[CRW-DB] 크롤링 데이터 변환 실패 {app_id}: {e}")
                    continue
            
            # Bulk insert 실행
            if game_objects:
                self._session.bulk_insert_mappings(Game, game_objects)
                logger.debug(f"[CRW-DB] 게임 기본 정보 bulk insert: {len(game_objects)}개")
            
            if tag_objects:
                self._session.bulk_insert_mappings(GameTag, tag_objects)
                logger.debug(f"[CRW-DB] 태그 정보 bulk insert: {len(tag_objects)}개")
            
            if review_objects:
                self._session.bulk_insert_mappings(GameReview, review_objects)
                logger.debug(f"[CRW-DB] 리뷰 정보 bulk insert: {len(review_objects)}개")
            
            if pricing_objects:
                self._session.bulk_insert_mappings(GamePricing, pricing_objects)
                logger.debug(f"[CRW-DB] 가격 정보 bulk insert: {len(pricing_objects)}개")
            
            return len(game_objects), []
            
        except Exception as e:
            logger.error(f"[CRW-DB] 크롤링 Bulk insert 실패: {e}")
            return 0, []
    
    def _update_existing_crawling_games(self, existing_games_data: List[Dict[str, Any]]) -> tuple[int, List[int]]:
        """기존 크롤링 게임들을 개별 업데이트로 처리"""
        success_count = 0
        failed_games = []
        
        for crawling_data in existing_games_data:
            try:
                if self.insert_steam_crawling_game(crawling_data):
                    success_count += 1
                else:
                    failed_games.append({'app_id': crawling_data.get('app_id'), 'error': 'db_insert_failed', 'message': 'Steam 크롤링 게임 데이터 삽입/업데이트 실패'})
            except Exception as e:
                app_id = crawling_data.get('app_id')
                logger.error(f"[CRW-DB] 기존 크롤링 게임 업데이트 실패: {e}")
                failed_games.append({'app_id': app_id, 'error': 'db_exception', 'message': f'예외 발생: {str(e)}'})
        
        return success_count, failed_games


# 편의 함수
def insert_steam_api_game_single(steam_data: Dict[str, Any]) -> bool:
    """단일 Steam API 게임 데이터를 데이터베이스에 삽입 (편의 함수)"""
    with GameInserter() as inserter:
        return inserter.insert_steam_api_game(steam_data)


def insert_steam_api_games_batch(games_data: List[Dict[str, Any]]) -> tuple[int, List[Dict[str, Any]]]:
    """여러 Steam API 게임 데이터를 하이브리드 배치로 데이터베이스에 삽입 (편의 함수)"""
    with GameInserter() as inserter:
        success_count, failed_games = inserter.insert_steam_api_games_hybrid_batch(games_data)
        return success_count, failed_games


def insert_steam_crawling_game_single(crawling_data: Dict[str, Any]) -> bool:
    """단일 Steam 크롤링 게임 데이터를 데이터베이스에 삽입 (편의 함수)"""
    with GameInserter() as inserter:
        return inserter.insert_steam_crawling_game(crawling_data)


def insert_steam_crawling_games_batch(games_data: List[Dict[str, Any]]) -> tuple[int, List[Dict[str, Any]]]:
    """여러 Steam 크롤링 게임 데이터를 하이브리드 배치로 데이터베이스에 삽입 (편의 함수)"""
    with GameInserter() as inserter:
        success_count, failed_games = inserter.insert_steam_crawling_games_hybrid_batch(games_data)
        return success_count, failed_games

