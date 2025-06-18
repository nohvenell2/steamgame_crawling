"""Database Connection Management

MySQL 데이터베이스 연결을 관리합니다.
"""

import os
from typing import Optional
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)

# 전역 엔진 및 세션 팩토리
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_db_config() -> dict:
    """환경 변수에서 데이터베이스 설정을 가져옵니다."""
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'steam_games'),
        'charset': 'utf8mb4'
    }


def create_database_url() -> str:
    """데이터베이스 URL을 생성합니다."""
    config = get_db_config()
    return (
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
        f"?charset={config['charset']}"
    )


def get_db_engine() -> Engine:
    """데이터베이스 엔진을 반환합니다."""
    global _engine
    
    if _engine is None:
        database_url = create_database_url()
        _engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        logger.info("데이터베이스 엔진이 생성되었습니다.")
    
    return _engine


def get_session_factory() -> sessionmaker:
    """세션 팩토리를 반환합니다."""
    global _session_factory
    
    if _session_factory is None:
        engine = get_db_engine()
        _session_factory = sessionmaker(bind=engine)
        logger.info("세션 팩토리가 생성되었습니다.")
    
    return _session_factory


def get_db_session() -> Session:
    """새로운 데이터베이스 세션을 반환합니다."""
    session_factory = get_session_factory()
    return session_factory()


def get_db_connection():
    """원시 데이터베이스 연결을 반환합니다."""
    engine = get_db_engine()
    return engine.connect()


def test_connection() -> bool:
    """데이터베이스 연결을 테스트합니다."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("데이터베이스 연결 테스트 성공")
        return True
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {e}")
        return False


def close_all_connections():
    """모든 데이터베이스 연결을 닫습니다."""
    global _engine, _session_factory
    
    if _engine:
        _engine.dispose()
        _engine = None
        logger.info("데이터베이스 엔진이 정리되었습니다.")
    
    _session_factory = None
    logger.info("세션 팩토리가 정리되었습니다.") 
if __name__ == "__main__":
    # 로깅 설정 - INFO 레벨 이상 출력
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 연결 테스트
    print("=== 데이터베이스 연결 테스트 ===")
    try:
        if test_connection():
            print("✅ 연결 성공!")
        else:
            print("❌ 연결 실패!")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
    finally:
        close_all_connections()