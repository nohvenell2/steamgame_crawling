"""Game Data Inserter

크롤링한 게임 데이터를 데이터베이스에 직접 삽입하는 모듈
"""

import logging
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

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
    
    def parse_release_date(self, date_str: str) -> Optional[date]:
        """출시일 문자열을 date 객체로 변환"""
        if not date_str:
            return None
        
        try:
            # "9 Dec, 2020" 형식 파싱
            return datetime.strptime(date_str, "%d %b, %Y").date()
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
        
        logger.warning(f"날짜 파싱 실패: {date_str}")
        return None
    
    def insert_game(
        self,
        app_id: int,
        title: str = "",
        description: str = "",
        detailed_description: str = "",
        release_date: str = "",
        developer: str = "",
        publisher: str = "",
        tags: List[str] = None,
        genres: List[str] = None,
        current_price: str = "",
        original_price: str = "",
        discount_percent: Optional[int] = None,
        is_free: bool = False,
        recent_reviews: str = "",
        all_reviews: str = "",
        recent_review_count: str = "",
        total_review_count: str = "",
        recent_positive_percent: Optional[float] = None,
        total_positive_percent: Optional[float] = None,
        header_image_url: str = "",
        system_requirements_minimum: str = "",
        system_requirements_recommended: str = "",
        crawled_at: Optional[datetime] = None
    ) -> bool:
        """게임 데이터를 데이터베이스에 삽입"""
        try:
            if not app_id:
                logger.error("app_id가 없습니다.")
                return False
            
            # 기존 게임 확인
            existing_game = self._session.query(Game).filter_by(app_id=app_id).first()
            if existing_game:
                logger.info(f"게임 {app_id}는 이미 존재합니다. 업데이트를 진행합니다.")
                return self._update_existing_game(
                    existing_game, title, description, detailed_description, release_date,
                    developer, publisher, tags or [], genres or [], current_price, original_price,
                    discount_percent, is_free, recent_reviews, all_reviews, recent_review_count,
                    total_review_count, recent_positive_percent, total_positive_percent,
                    header_image_url, system_requirements_minimum, system_requirements_recommended,
                    crawled_at
                )
            
            # 새 게임 생성
            game = Game(
                app_id=app_id,
                title=title,
                description=description,
                detailed_description=detailed_description,
                release_date=self.parse_release_date(release_date),
                developer=developer,
                publisher=publisher,
                crawled_at=crawled_at or datetime.now(),
                header_image_url=header_image_url,
                system_requirements_minimum=system_requirements_minimum,
                system_requirements_recommended=system_requirements_recommended
            )
            
            self._session.add(game)
            self._session.flush()  # app_id 확보
            
            # 태그 삽입
            if tags:
                self._insert_game_tags(app_id, tags)
            
            # 장르 삽입
            if genres:
                self._insert_game_genres(app_id, genres)
            
            # 가격 정보 삽입
            if current_price or original_price or discount_percent is not None or is_free:
                self._insert_game_pricing(app_id, current_price, original_price, discount_percent, is_free)
            
            # 리뷰 정보 삽입
            if any([recent_reviews, all_reviews, recent_review_count, total_review_count, 
                   recent_positive_percent is not None, total_positive_percent is not None]):
                self._insert_game_reviews(
                    app_id, recent_reviews, all_reviews, recent_review_count, total_review_count,
                    recent_positive_percent, total_positive_percent
                )
            
            logger.info(f"게임 {app_id} ({title}) 삽입 완료")
            return True
            
        except Exception as e:
            logger.error(f"게임 삽입 중 오류 발생: {e}")
            return False
    
    def insert_game_from_dict(self, game_data: Dict[str, Any]) -> bool:
        """딕셔너리 형태의 게임 데이터를 데이터베이스에 삽입"""
        try:
            # 개발자/퍼블리셔 정보 추출
            dev_pub = game_data.get('developer_publisher', {})
            
            # 첫 번째 이미지 URL 추출
            header_images = game_data.get('header_images', [])
            header_image_url = header_images[0] if header_images else ""
            
            # 시스템 요구사항 추출
            sys_req = game_data.get('system_requirements', {})
            
            # 가격 정보 추출
            price_info = game_data.get('price_info', {})
            
            # 리뷰 정보 추출
            review_info = game_data.get('review_info', {})
            
            # crawled_at 파싱
            crawled_at = None
            if game_data.get('crawled_at'):
                try:
                    crawled_at = datetime.fromisoformat(game_data['crawled_at'])
                except ValueError:
                    crawled_at = datetime.now()
            else:
                crawled_at = datetime.now()
            
            return self.insert_game(
                app_id=game_data.get('app_id'),
                title=game_data.get('title', ''),
                description=game_data.get('description', ''),
                detailed_description=game_data.get('detailed_description', ''),
                release_date=game_data.get('release_date', ''),
                developer=dev_pub.get('developer', ''),
                publisher=dev_pub.get('publisher', ''),
                tags=game_data.get('tags', []),
                genres=game_data.get('genres', []),
                current_price=price_info.get('current_price', ''),
                original_price=price_info.get('original_price', ''),
                discount_percent=price_info.get('discount_percent'),
                is_free=price_info.get('is_free', False),
                recent_reviews=review_info.get('recent_reviews', ''),
                all_reviews=review_info.get('all_reviews', ''),
                recent_review_count=review_info.get('recent_review_count', ''),
                total_review_count=review_info.get('total_review_count', ''),
                recent_positive_percent=review_info.get('recent_positive_percent'),
                total_positive_percent=review_info.get('total_positive_percent'),
                header_image_url=header_image_url,
                system_requirements_minimum=sys_req.get('minimum', ''),
                system_requirements_recommended=sys_req.get('recommended', ''),
                crawled_at=crawled_at
            )
            
        except Exception as e:
            logger.error(f"딕셔너리에서 게임 삽입 중 오류 발생: {e}")
            return False
    
    def _insert_game_tags(self, app_id: int, tags: List[str]):
        """게임 태그 삽입"""
        for order, tag_name in enumerate(tags, 1):
            if tag_name and tag_name.strip():
                game_tag = GameTag(
                    app_id=app_id,
                    tag_name=tag_name.strip(),
                    tag_order=order
                )
                self._session.add(game_tag)
    
    def _insert_game_genres(self, app_id: int, genres: List[str]):
        """게임 장르 삽입"""
        for genre_name in genres:
            if genre_name and genre_name.strip():
                game_genre = GameGenre(
                    app_id=app_id,
                    genre_name=genre_name.strip()
                )
                self._session.add(game_genre)
    
    def _insert_game_pricing(
        self, 
        app_id: int, 
        current_price: str, 
        original_price: str, 
        discount_percent: Optional[int], 
        is_free: bool
    ):
        """게임 가격 정보 삽입"""
        game_pricing = GamePricing(
            app_id=app_id,
            current_price=current_price,
            original_price=original_price,
            discount_percent=discount_percent,
            is_free=is_free
        )
        self._session.add(game_pricing)
    
    def _insert_game_reviews(
        self,
        app_id: int,
        recent_reviews: str,
        all_reviews: str,
        recent_review_count: str,
        total_review_count: str,
        recent_positive_percent: Optional[float],
        total_positive_percent: Optional[float]
    ):
        """게임 리뷰 정보 삽입"""
        game_review = GameReview(
            app_id=app_id,
            recent_reviews=recent_reviews,
            all_reviews=all_reviews,
            recent_review_count=recent_review_count,
            total_review_count=total_review_count,
            recent_positive_percent=recent_positive_percent,
            total_positive_percent=total_positive_percent
        )
        self._session.add(game_review)
    
    def _update_existing_game(
        self,
        existing_game: Game,
        title: str,
        description: str,
        detailed_description: str,
        release_date: str,
        developer: str,
        publisher: str,
        tags: List[str],
        genres: List[str],
        current_price: str,
        original_price: str,
        discount_percent: Optional[int],
        is_free: bool,
        recent_reviews: str,
        all_reviews: str,
        recent_review_count: str,
        total_review_count: str,
        recent_positive_percent: Optional[float],
        total_positive_percent: Optional[float],
        header_image_url: str,
        system_requirements_minimum: str,
        system_requirements_recommended: str,
        crawled_at: Optional[datetime]
    ) -> bool:
        """기존 게임 정보 업데이트"""
        try:
            app_id = existing_game.app_id
            
            # 메인 정보 업데이트
            if title:
                existing_game.title = title
            if description:
                existing_game.description = description
            if detailed_description:
                existing_game.detailed_description = detailed_description
            
            # 날짜 파싱 및 업데이트
            if release_date:
                parsed_date = self.parse_release_date(release_date)
                if parsed_date is not None:
                    existing_game.release_date = parsed_date
            
            if developer:
                existing_game.developer = developer
            if publisher:
                existing_game.publisher = publisher
            if header_image_url:
                existing_game.header_image_url = header_image_url
            if system_requirements_minimum:
                existing_game.system_requirements_minimum = system_requirements_minimum
            if system_requirements_recommended:
                existing_game.system_requirements_recommended = system_requirements_recommended
            
            existing_game.crawled_at = crawled_at or datetime.now()
            
            # 태그 업데이트 (기존 태그 삭제 후 재삽입)
            if tags:
                self._session.query(GameTag).filter_by(app_id=app_id).delete()
                self._insert_game_tags(app_id, tags)
            
            # 장르 업데이트
            if genres:
                self._session.query(GameGenre).filter_by(app_id=app_id).delete()
                self._insert_game_genres(app_id, genres)
            
            # 가격 정보 업데이트
            if current_price or original_price or discount_percent is not None or is_free:
                existing_pricing = self._session.query(GamePricing).filter_by(app_id=app_id).first()
                if existing_pricing:
                    self._session.delete(existing_pricing)
                self._insert_game_pricing(app_id, current_price, original_price, discount_percent, is_free)
            
            # 리뷰 정보 업데이트
            if any([recent_reviews, all_reviews, recent_review_count, total_review_count,
                   recent_positive_percent is not None, total_positive_percent is not None]):
                existing_review = self._session.query(GameReview).filter_by(app_id=app_id).first()
                if existing_review:
                    self._session.delete(existing_review)
                self._insert_game_reviews(
                    app_id, recent_reviews, all_reviews, recent_review_count, total_review_count,
                    recent_positive_percent, total_positive_percent
                )
            
            logger.info(f"게임 {app_id} 업데이트 완료")
            return True
            
        except Exception as e:
            logger.error(f"게임 업데이트 중 오류 발생: {e}")
            return False


# 편의 함수들
def insert_single_game_dict(game_data: Dict[str, Any]) -> bool:
    """단일 게임 딕셔너리를 데이터베이스에 삽입 (편의 함수)"""
    with GameInserter() as inserter:
        return inserter.insert_game_from_dict(game_data)


def insert_multiple_games_dict(games_data: List[Dict[str, Any]]) -> tuple[int, int]:
    """여러 게임 딕셔너리를 배치로 데이터베이스에 삽입 (편의 함수)"""
    success_count = 0
    fail_count = 0
    
    with GameInserter() as inserter:
        for game_data in games_data:
            try:
                if inserter.insert_game_from_dict(game_data):
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"게임 처리 중 예외 발생: {e}")
                fail_count += 1
    
    logger.info(f"배치 처리 완료: 성공 {success_count}개, 실패 {fail_count}개")
    return success_count, fail_count 