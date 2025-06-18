"""Database Queries

데이터베이스 조회를 위한 공통 쿼리 함수들
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from .models import Game, GameTag, GameGenre, GamePricing, GameReview
from .connection import get_db_session

logger = logging.getLogger(__name__)


class GameQueries:
    """게임 데이터 조회를 위한 쿼리 클래스"""
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_db_session()
        self._own_session = session is None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            self.session.close()
    
    def get_game_by_id(self, app_id: int) -> Optional[Game]:
        """게임 ID로 단일 게임 조회 (모든 관련 정보 포함)"""
        try:
            return (self.session.query(Game)
                   .options(
                       joinedload(Game.tags),
                       joinedload(Game.genres),
                       joinedload(Game.pricing),
                       joinedload(Game.reviews)
                   )
                   .filter(Game.app_id == app_id)
                   .first())
        except Exception as e:
            logger.error(f"게임 ID {app_id} 조회 중 오류: {e}")
            return None
    
    def get_games_by_title(self, title: str, exact_match: bool = False) -> List[Game]:
        """제목으로 게임 검색"""
        try:
            query = self.session.query(Game)
            
            if exact_match:
                query = query.filter(Game.title == title)
            else:
                query = query.filter(Game.title.contains(title))
            
            return query.options(
                joinedload(Game.tags),
                joinedload(Game.genres),
                joinedload(Game.pricing),
                joinedload(Game.reviews)
            ).all()
        except Exception as e:
            logger.error(f"제목 '{title}' 검색 중 오류: {e}")
            return []
    
    def get_games_by_developer(self, developer: str) -> List[Game]:
        """개발사로 게임 검색"""
        try:
            return (self.session.query(Game)
                   .options(
                       joinedload(Game.tags),
                       joinedload(Game.genres),
                       joinedload(Game.pricing),
                       joinedload(Game.reviews)
                   )
                   .filter(Game.developer.contains(developer))
                   .all())
        except Exception as e:
            logger.error(f"개발사 '{developer}' 검색 중 오류: {e}")
            return []
    
    def get_games_by_tag(self, tag_name: str, limit: int = 100) -> List[Game]:
        """태그로 게임 검색"""
        try:
            return (self.session.query(Game)
                   .join(GameTag)
                   .filter(GameTag.tag_name == tag_name)
                   .options(
                       joinedload(Game.tags),
                       joinedload(Game.genres),
                       joinedload(Game.pricing),
                       joinedload(Game.reviews)
                   )
                   .limit(limit)
                   .all())
        except Exception as e:
            logger.error(f"태그 '{tag_name}' 검색 중 오류: {e}")
            return []
    
    def get_games_by_genre(self, genre_name: str, limit: int = 100) -> List[Game]:
        """장르로 게임 검색"""
        try:
            return (self.session.query(Game)
                   .join(GameGenre)
                   .filter(GameGenre.genre_name == genre_name)
                   .options(
                       joinedload(Game.tags),
                       joinedload(Game.genres),
                       joinedload(Game.pricing),
                       joinedload(Game.reviews)
                   )
                   .limit(limit)
                   .all())
        except Exception as e:
            logger.error(f"장르 '{genre_name}' 검색 중 오류: {e}")
            return []
    
    def get_free_games(self, limit: int = 50) -> List[Game]:
        """무료 게임 목록 조회"""
        try:
            return (self.session.query(Game)
                   .join(GamePricing)
                   .filter(GamePricing.is_free == True)
                   .options(
                       joinedload(Game.tags),
                       joinedload(Game.genres),
                       joinedload(Game.pricing),
                       joinedload(Game.reviews)
                   )
                   .limit(limit)
                   .all())
        except Exception as e:
            logger.error(f"무료 게임 조회 중 오류: {e}")
            return []
    
    def get_discounted_games(self, min_discount: int = 50, limit: int = 50) -> List[Game]:
        """할인 게임 목록 조회"""
        try:
            return (self.session.query(Game)
                   .join(GamePricing)
                   .filter(
                       and_(
                           GamePricing.discount_percent >= min_discount,
                           GamePricing.discount_percent.isnot(None)
                       )
                   )
                   .options(
                       joinedload(Game.tags),
                       joinedload(Game.genres),
                       joinedload(Game.pricing),
                       joinedload(Game.reviews)
                   )
                   .order_by(desc(GamePricing.discount_percent))
                   .limit(limit)
                   .all())
        except Exception as e:
            logger.error(f"할인 게임 조회 중 오류: {e}")
            return []
    
    def get_highly_rated_games(self, min_rating: int = 90, limit: int = 50) -> List[Game]:
        """고평점 게임 목록 조회"""
        try:
            return (self.session.query(Game)
                   .join(GameReview)
                   .filter(GameReview.total_positive_percent >= min_rating)
                   .options(
                       joinedload(Game.tags),
                       joinedload(Game.genres),
                       joinedload(Game.pricing),
                       joinedload(Game.reviews)
                   )
                   .order_by(desc(GameReview.total_positive_percent))
                   .limit(limit)
                   .all())
        except Exception as e:
            logger.error(f"고평점 게임 조회 중 오류: {e}")
            return []
    
    def get_popular_games_by_review_count(self, limit: int = 50) -> List[Game]:
        """리뷰 수 기준 인기 게임 조회"""
        try:
            # 리뷰 수가 있는 게임들을 조회한 후 Python에서 정렬
            games_with_reviews = (self.session.query(Game)
                                .join(GameReview)
                                .filter(GameReview.total_review_count.isnot(None))
                                .options(
                                    joinedload(Game.tags),
                                    joinedload(Game.genres),
                                    joinedload(Game.pricing),
                                    joinedload(Game.reviews)
                                )
                                .all())
            
            # Python에서 리뷰 수로 정렬
            def extract_review_count(game):
                try:
                    if game.reviews and game.reviews[0].total_review_count:
                        # 콤마 제거하고 숫자만 추출
                        count_str = game.reviews[0].total_review_count.replace(',', '').replace(' ', '')
                        # 숫자가 아닌 문자 제거
                        import re
                        numbers = re.findall(r'\d+', count_str)
                        if numbers:
                            return int(numbers[0])
                    return 0
                except (ValueError, AttributeError, IndexError):
                    return 0
            
            # 리뷰 수로 내림차순 정렬하고 제한
            sorted_games = sorted(games_with_reviews, key=extract_review_count, reverse=True)
            return sorted_games[:limit]
            
        except Exception as e:
            logger.error(f"인기 게임 조회 중 오류: {e}")
            return []
    
    def search_games_multi_criteria(
        self,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        genres: Optional[List[str]] = None,
        developer: Optional[str] = None,
        is_free: Optional[bool] = None,
        min_rating: Optional[int] = None,
        max_price: Optional[str] = None,
        limit: int = 100
    ) -> List[Game]:
        """다중 조건 게임 검색"""
        try:
            query = self.session.query(Game).distinct()
            
            # 제목 필터
            if title:
                query = query.filter(Game.title.contains(title))
            
            # 개발사 필터
            if developer:
                query = query.filter(Game.developer.contains(developer))
            
            # 태그 필터
            if tags:
                for tag in tags:
                    query = query.join(GameTag).filter(GameTag.tag_name == tag)
            
            # 장르 필터
            if genres:
                for genre in genres:
                    query = query.join(GameGenre).filter(GameGenre.genre_name == genre)
            
            # 가격/무료 필터
            if is_free is not None or max_price is not None:
                query = query.join(GamePricing)
                if is_free is not None:
                    query = query.filter(GamePricing.is_free == is_free)
                if max_price is not None:
                    # 가격 문자열 처리 로직 필요 (₩ 66,000 형태)
                    pass
            
            # 평점 필터
            if min_rating is not None:
                query = query.join(GameReview).filter(GameReview.total_positive_percent >= min_rating)
            
            return query.options(
                joinedload(Game.tags),
                joinedload(Game.genres),
                joinedload(Game.pricing),
                joinedload(Game.reviews)
            ).limit(limit).all()
            
        except Exception as e:
            logger.error(f"다중 조건 검색 중 오류: {e}")
            return []
    
    def get_game_statistics(self) -> Dict[str, Any]:
        """게임 데이터베이스 통계 조회"""
        try:
            stats = {}
            
            # 전체 게임 수
            stats['total_games'] = self.session.query(Game).count()
            
            # 무료 게임 수
            stats['free_games'] = (self.session.query(Game)
                                 .join(GamePricing)
                                 .filter(GamePricing.is_free == True)
                                 .count())
            
            # 개발사 수
            stats['total_developers'] = (self.session.query(Game.developer)
                                       .filter(Game.developer.isnot(None))
                                       .distinct()
                                       .count())
            
            # 인기 태그 TOP 10
            popular_tags = (self.session.query(GameTag.tag_name, func.count(GameTag.id))
                          .group_by(GameTag.tag_name)
                          .order_by(desc(func.count(GameTag.id)))
                          .limit(10)
                          .all())
            stats['popular_tags'] = [{'tag': tag, 'count': count} for tag, count in popular_tags]
            
            # 인기 장르 TOP 10
            popular_genres = (self.session.query(GameGenre.genre_name, func.count(GameGenre.id))
                            .group_by(GameGenre.genre_name)
                            .order_by(desc(func.count(GameGenre.id)))
                            .limit(10)
                            .all())
            stats['popular_genres'] = [{'genre': genre, 'count': count} for genre, count in popular_genres]
            
            return stats
            
        except Exception as e:
            logger.error(f"통계 조회 중 오류: {e}")
            return {}
    
    def get_tag_list(self) -> List[str]:
        """모든 태그 목록 조회"""
        try:
            tags = (self.session.query(GameTag.tag_name)
                   .distinct()
                   .order_by(GameTag.tag_name)
                   .all())
            return [tag[0] for tag in tags]
        except Exception as e:
            logger.error(f"태그 목록 조회 중 오류: {e}")
            return []
    
    def get_genre_list(self) -> List[str]:
        """모든 장르 목록 조회"""
        try:
            genres = (self.session.query(GameGenre.genre_name)
                     .distinct()
                     .order_by(GameGenre.genre_name)
                     .all())
            return [genre[0] for genre in genres]
        except Exception as e:
            logger.error(f"장르 목록 조회 중 오류: {e}")
            return []
    
    def get_developer_list(self) -> List[str]:
        """모든 개발사 목록 조회"""
        try:
            developers = (self.session.query(Game.developer)
                         .filter(Game.developer.isnot(None))
                         .distinct()
                         .order_by(Game.developer)
                         .all())
            return [dev[0] for dev in developers]
        except Exception as e:
            logger.error(f"개발사 목록 조회 중 오류: {e}")
            return []


# 편의 함수들
def get_game_by_id(app_id: int) -> Optional[Game]:
    """게임 ID로 단일 게임 조회 (편의 함수)"""
    with GameQueries() as queries:
        return queries.get_game_by_id(app_id)


def search_games_by_tag(tag_name: str, limit: int = 100) -> List[Game]:
    """태그로 게임 검색 (편의 함수)"""
    with GameQueries() as queries:
        return queries.get_games_by_tag(tag_name, limit)


def get_game_statistics() -> Dict[str, Any]:
    """게임 통계 조회 (편의 함수)"""
    with GameQueries() as queries:
        return queries.get_game_statistics() 