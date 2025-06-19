"""SQLAlchemy Database Models

Steam 게임 데이터베이스 테이블들의 SQLAlchemy 모델 정의
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Game(Base):
    """게임 메인 테이블"""
    __tablename__ = 'games'
    
    app_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    detailed_description = Column(Text)
    release_date = Column(Date)
    developer = Column(String(255))
    publisher = Column(String(255))
    crawled_at = Column(DateTime, default=datetime.utcnow)
    
    # 단순화된 필드들
    header_image_url = Column(String(500))
    system_requirements_minimum = Column(Text)
    system_requirements_recommended = Column(Text)
    
    # 관계 설정
    tags = relationship("GameTag", back_populates="game", cascade="all, delete-orphan")
    genres = relationship("GameGenre", back_populates="game", cascade="all, delete-orphan")
    pricing = relationship("GamePricing", back_populates="game", uselist=False, cascade="all, delete-orphan")
    reviews = relationship("GameReview", back_populates="game", uselist=False, cascade="all, delete-orphan")
    
    # 인덱스
    __table_args__ = (
        Index('idx_title', 'title'),
        Index('idx_developer', 'developer'),
        Index('idx_release_date', 'release_date'),
        Index('idx_crawled_at', 'crawled_at'),
    )
    
    def __repr__(self):
        return f"<Game(app_id={self.app_id}, title='{self.title}')>"


class GameTag(Base):
    """게임 태그 테이블"""
    __tablename__ = 'game_tags'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(Integer, ForeignKey('games.app_id', ondelete='CASCADE'), nullable=False)
    tag_name = Column(String(100), nullable=False)
    tag_order = Column(Integer, default=1)
    
    # 관계 설정
    game = relationship("Game", back_populates="tags")
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_app_id', 'app_id'),
        Index('idx_tag_name', 'tag_name'),
        Index('idx_tag_order', 'tag_order'),
        Index('idx_tag_name_app_id', 'tag_name', 'app_id'),
        Index('unique_app_tag', 'app_id', 'tag_name', unique=True),
    )
    
    def __repr__(self):
        return f"<GameTag(app_id={self.app_id}, tag_name='{self.tag_name}')>"


class GameGenre(Base):
    """게임 장르 테이블"""
    __tablename__ = 'game_genres'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(Integer, ForeignKey('games.app_id', ondelete='CASCADE'), nullable=False)
    genre_name = Column(String(50), nullable=False)
    
    # 관계 설정
    game = relationship("Game", back_populates="genres")
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_app_id', 'app_id'), 
        Index('idx_genre_name', 'genre_name'),
        Index('idx_genre_name_app_id', 'genre_name', 'app_id'),
        Index('unique_app_genre', 'app_id', 'genre_name', unique=True),
    )
    
    def __repr__(self):
        return f"<GameGenre(app_id={self.app_id}, genre_name='{self.genre_name}')>"


class GamePricing(Base):
    """게임 가격 정보 테이블"""
    __tablename__ = 'game_pricing'
    
    app_id = Column(Integer, ForeignKey('games.app_id', ondelete='CASCADE'), primary_key=True)
    current_price = Column(String(50))
    original_price = Column(String(50))
    discount_percent = Column(Integer)
    is_free = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    game = relationship("Game", back_populates="pricing")
    
    # 인덱스
    __table_args__ = (
        Index('idx_is_free', 'is_free'),
        Index('idx_discount_percent', 'discount_percent'),
        Index('idx_updated_at', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<GamePricing(app_id={self.app_id}, current_price='{self.current_price}')>"


class GameReview(Base):
    """게임 리뷰 정보 테이블"""
    __tablename__ = 'game_reviews'
    
    app_id = Column(Integer, ForeignKey('games.app_id', ondelete='CASCADE'), primary_key=True)
    recent_reviews = Column(String(50))
    all_reviews = Column(String(50))
    recent_review_count = Column(String(20))
    total_review_count = Column(String(20))
    recent_positive_percent = Column(Integer)
    total_positive_percent = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    game = relationship("Game", back_populates="reviews")
    
    # 인덱스
    __table_args__ = (
        Index('idx_recent_reviews', 'recent_reviews'),
        Index('idx_all_reviews', 'all_reviews'),
        Index('idx_total_positive_percent', 'total_positive_percent'),
        Index('idx_updated_at', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<GameReview(app_id={self.app_id}, all_reviews='{self.all_reviews}')>"


def create_all_tables(engine):
    """모든 테이블을 생성합니다."""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """모든 테이블을 삭제합니다."""
    Base.metadata.drop_all(engine) 

if __name__ == "__main__":
    from connection import get_db_engine
    engine = get_db_engine()
    create_all_tables(engine)