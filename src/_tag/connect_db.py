import os
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List, Union
import logging

# 환경변수 로드
load_dotenv()

class MySQLConnector:
    """MySQL 데이터베이스 연결 관리 클래스"""
    
    def __init__(self):
        """환경변수에서 데이터베이스 설정을 로드합니다."""
        self.host = os.getenv('MYSQL_HOST', 'localhost')
        self.port = int(os.getenv('MYSQL_PORT', '3306'))
        self.user = os.getenv('MYSQL_USER', '')
        self.password = os.getenv('MYSQL_PW', '')
        self.database = os.getenv('MYSQL_DB_NAME', '')
        self.connection: Optional[pymysql.Connection] = None
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 필수 환경변수 확인
        self._validate_config()
    
    def _validate_config(self):
        """필수 환경변수가 설정되어 있는지 확인합니다."""
        required_vars = ['MYSQL_USER', 'MYSQL_PW', 'MYSQL_DB_NAME']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    
    def connect(self) -> bool:
        """데이터베이스에 연결합니다."""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True
            )
            self.logger.info(f"MySQL 데이터베이스에 성공적으로 연결되었습니다: {self.host}:{self.port}/{self.database}")
            return True
        except Exception as e:
            self.logger.error(f"데이터베이스 연결 실패: {str(e)}")
            return False
    
    def disconnect(self):
        """데이터베이스 연결을 종료합니다."""
        if self.connection:
            self.connection.close()
            self.logger.info("데이터베이스 연결이 종료되었습니다.")
    
    def is_connected(self) -> bool:
        """데이터베이스 연결 상태를 확인합니다."""
        try:
            if self.connection:
                self.connection.ping(reconnect=True)
                return True
        except:
            pass
        return False
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """SELECT 쿼리를 실행하고 결과를 반환합니다."""
        if not self.is_connected():
            if not self.connect():
                return None
        
        if not self.connection:
            return None
            
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                # self.logger.info(f"쿼리 실행 성공: {len(result)}개 행 반환")
                return result
        except Exception as e:
            self.logger.error(f"쿼리 실행 실패: {str(e)}")
            return None
    
    def execute_insert(self, query: str, params: Optional[tuple] = None) -> Optional[int]:
        """INSERT 쿼리를 실행하고 생성된 ID를 반환합니다."""
        if not self.is_connected():
            if not self.connect():
                return None
        
        if not self.connection:
            return None
            
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                last_insert_id = cursor.lastrowid
                #self.logger.info(f"INSERT 실행 성공: ID {last_insert_id}")
                return last_insert_id
        except Exception as e:
            self.logger.error(f"INSERT 실행 실패: {str(e)}")
            return None
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> Optional[int]:
        """UPDATE 쿼리를 실행하고 영향받은 행 수를 반환합니다."""
        if not self.is_connected():
            if not self.connect():
                return None
        
        if not self.connection:
            return None
            
        try:
            with self.connection.cursor() as cursor:
                affected_rows = cursor.execute(query, params)
                self.logger.info(f"UPDATE 실행 성공: {affected_rows}개 행 영향")
                return affected_rows
        except Exception as e:
            self.logger.error(f"UPDATE 실행 실패: {str(e)}")
            return None
    
    def execute_delete(self, query: str, params: Optional[tuple] = None) -> Optional[int]:
        """DELETE 쿼리를 실행하고 삭제된 행 수를 반환합니다."""
        if not self.is_connected():
            if not self.connect():
                return None
        
        if not self.connection:
            return None
            
        try:
            with self.connection.cursor() as cursor:
                affected_rows = cursor.execute(query, params)
                self.logger.info(f"DELETE 실행 성공: {affected_rows}개 행 삭제")
                return affected_rows
        except Exception as e:
            self.logger.error(f"DELETE 실행 실패: {str(e)}")
            return None
    
    def batch_insert(self, query: str, data_list: List[tuple]) -> bool:
        """여러 데이터를 한 번에 INSERT합니다."""
        if not self.is_connected():
            if not self.connect():
                return False
        
        if not self.connection:
            return False
            
        try:
            with self.connection.cursor() as cursor:
                cursor.executemany(query, data_list)
                self.logger.info(f"배치 INSERT 실행 성공: {len(data_list)}개 행 삽입")
                return True
        except Exception as e:
            self.logger.error(f"배치 INSERT 실행 실패: {str(e)}")
            return False
    
    def __enter__(self):
        """with 문 지원: 연결 시작"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """with 문 지원: 연결 종료"""
        self.disconnect()


# 편의 함수들
def get_db_connection() -> MySQLConnector:
    """데이터베이스 연결 객체를 반환합니다."""
    return MySQLConnector()

def test_connection() -> bool:
    """데이터베이스 연결을 테스트합니다."""
    try:
        with MySQLConnector() as db:
            if db.is_connected():
                print("✅ 데이터베이스 연결 테스트 성공!")
                return True
            else:
                print("❌ 데이터베이스 연결 실패!")
                return False
    except Exception as e:
        print(f"❌ 데이터베이스 연결 테스트 중 오류: {str(e)}")
        return False

def main():
    """테스트 실행"""
    print("🔗 MySQL 데이터베이스 연결 테스트")
    print("=" * 40)
    
    # 환경변수 확인
    required_vars = ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PW', 'MYSQL_DB_NAME']
    print("📋 환경변수 확인:")
    for var in required_vars:
        value = os.getenv(var)
        if var == 'MYSQL_PW':
            display_value = "*" * len(value) if value else None
        else:
            display_value = value
        print(f"  {var}: {display_value}")
    
    print("\n🔍 연결 테스트 중...")
    test_connection()

if __name__ == "__main__":
    main()
