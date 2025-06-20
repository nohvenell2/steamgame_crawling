# Steam Game Data Collector

Steam 게임 데이터를 효율적으로 수집하는 Python 프로그램입니다. Steam API와 웹 크롤링을 조합하여 다양한 게임 정보를 수집할 수 있습니다.

## 주요 기능

- **Steam API 기반 데이터 수집**: 공식 API를 통한 안정적인 게임 정보 수집
- **웹 크롤링**: API에서 제공하지 않는 추가 정보 (사용자 태그, 리뷰 통계 등)
- **비동기 처리**: 빠른 대량 데이터 수집
- **다양한 수집 옵션**: 전체 정보부터 특정 정보만 선택적 수집
- **안정적인 에러 처리**: 재시도 로직과 상세한 에러 리포팅

## 프로젝트 구조

```
src/
├── fetch_steam_game_ids.py      # Steam API로 게임 ID 목록 수집
├── fetch_steam_game_data.py     # Steam API로 게임 상세 정보 수집
├── single_game_crawler.py       # 웹 크롤링으로 포괄적 게임 정보 수집
├── single_game_crawler_minimal.py # 웹 크롤링으로 핵심 정보만 수집
├── single_game_tag_crawler.py   # 웹 크롤링으로 태그 정보만 수집
├── run_save_all_games.py        # 대량 데이터 수집 및 DB 저장 메인 스크립트
├── database/                    # 데이터베이스 관련 모듈
│   ├── connection.py           # DB 연결 관리
│   ├── inserter.py            # 데이터 삽입 로직
│   ├── models.py              # 데이터 모델 정의
│   ├── queries.py             # SQL 쿼리 관리
│   └── schema.sql             # 데이터베이스 스키마
└── utils/
    ├── __init__.py
    └── logger.py               # 로깅 설정 유틸리티
```

## 모듈별 상세 기능

### 1. fetch_steam_game_ids.py
Steam API에서 모든 게임 ID 목록을 수집합니다.
- Steam GetAppList API 사용
- 중복 제거된 게임 ID Set 반환
- 테스트용 제한 옵션 제공

### 2. fetch_steam_game_data.py  
Steam Store API를 통한 게임 상세 정보 수집
- 공식 API 사용으로 안정적인 데이터 수집
- HTML 콘텐츠를 읽기 쉬운 텍스트로 변환
- 시스템 요구사항 포맷팅
- 비동기/동기 처리 모두 지원
- 여러 게임 동시 처리 가능

### 3. single_game_crawler.py
웹 크롤링을 통한 포괄적 게임 정보 수집
- 게임 기본 정보 (제목, 설명, 상세 설명)
- 태그 및 장르 정보
- 가격 정보 (할인 포함)
- 개발사/퍼블리셔 정보
- 출시일 및 리뷰 통계
- 헤더 이미지 URL
- 시스템 요구사항
- 나이 인증 자동 처리

### 4. single_game_crawler_minimal.py
API에서 제공하지 않는 핵심 정보만 크롤링
- **사용자가 붙인 태그**: Steam API에서 제공하지 않는 실제 사용자 태그
- **리뷰 통계**: 긍정 비율, 리뷰 개수 등 상세 통계
- **현지화된 가격 정보**: 할인 정보 포함한 실시간 가격
- 최소한의 요청으로 효율적인 데이터 수집

### 5. single_game_tag_crawler.py
게임 태그 정보만 전용으로 크롤링
- 사용자가 붙인 태그만 추출
- 가장 가벼운 크롤링 옵션
- 태그 데이터만 필요한 경우 최적화

### 6. run_save_all_games.py
대량 데이터 수집 및 DB 저장 메인 스크립트
- **전체 Steam 게임 자동 수집**: 모든 Steam 게임을 자동으로 순회하며 데이터 수집
- **API + 크롤링 하이브리드**: Steam API와 웹 크롤링을 조합한 포괄적 정보 수집
- **배치 처리 최적화**: 고성능 bulk insert로 DB 저장 성능 최적화
- **지능형 필터링**: 게임 타입 및 리뷰 수 기반 필터링으로 품질 관리
- **실패 추적 및 복구**: 실패한 게임들의 상세 분류 및 재시도 가능
- **실시간 모니터링**: 진행률, 성공률 등 실시간 처리 상황 확인
- **백그라운드 실행**: nohup을 통한 장시간 무인 실행 지원
- **로그 관리**: 상세한 처리 로그 및 실패 게임 JSON 저장

**주요 처리 흐름**:
1. Steam 게임 ID 목록 수집
2. 각 게임별 API 데이터 수집 및 검증
3. 웹 크롤링으로 추가 정보 수집
4. 배치 단위로 DB 저장
5. 실패 게임 추적 및 리포팅

**사용 예시**:
```bash
# 백그라운드에서 전체 수집 실행
nohup poetry run python -u src/run_save_all_games.py > logs/run_save_all_games_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 진행 상황 실시간 모니터링
tail -f logs/run_save_all_games_*.log

# 프로세스 종료
pkill -f "run_save_all_games.py"
```

### 7. database/
데이터베이스 관련 모듈
- connection.py: DB 연결 관리
- inserter.py: 데이터 삽입 로직
- models.py: 데이터 모델 정의
- queries.py: SQL 쿼리 관리
- schema.sql: 데이터베이스 스키마

### 8. utils/logger.py
로깅 설정 유틸리티
- 통일된 로그 포맷
- 레벨별 로그 설정
- 콘솔 출력 지원

## 설치 방법

### 필수 요구사항
- Python 3.12+
- 안정적인 인터넷 연결

### 의존성 설치

```bash
# Poetry 사용 (권장)
poetry install

# 또는 pip 사용
pip install -r requirements.txt
```

## 사용 방법

### 1. 게임 ID 목록 수집

```python
from src.fetch_steam_game_ids import get_all_steam_games

# 전체 게임 ID 가져오기
all_game_ids = get_all_steam_games()
print(f"총 {len(all_game_ids)}개의 게임 ID")

# 제한된 개수만 가져오기 (테스트용)
limited_ids = get_all_steam_games(limit=100)
```

### 2. Steam API로 게임 정보 수집

```python
from src.fetch_steam_game_data import get_steam_game_info_api_sync

# 단일 게임 정보 수집
result = get_steam_game_info_api_sync(1091500)  # Cyberpunk 2077
if result['success']:
    print(f"게임명: {result['data']['name']}")
else:
    print(f"오류: {result['message']}")
```

### 3. 포괄적 게임 정보 크롤링

```python
from src.single_game_crawler import get_steam_game_info_crawler_sync, print_game_info

# 게임의 모든 정보 크롤링
result = get_steam_game_info_crawler_sync(1091500)
print_game_info(result)
```

### 4. 핵심 정보만 크롤링 (권장)

```python
from src.single_game_crawler_minimal import get_steam_game_info_crawler_minimal_sync, print_minimal_info

# API에서 제공하지 않는 핵심 정보만 수집
result = get_steam_game_info_crawler_minimal_sync(1091500)
print_minimal_info(result)
```

### 5. 태그 정보만 크롤링

```python
from src.single_game_tag_crawler import get_steam_game_tags_sync

# 게임 태그만 수집
tags = get_steam_game_tags_sync(1091500)
print(f"태그: {tags}")
```

### 6. 대량 데이터 수집 및 DB 저장

모든 Steam 게임 데이터를 자동으로 수집하고 데이터베이스에 저장:

```bash
# 백그라운드에서 전체 수집 실행 (권장)
nohup poetry run python -u src/run_save_all_games.py > logs/run_save_all_games_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 진행 상황 실시간 모니터링
tail -f logs/run_save_all_games_*.log

# 프로세스 상태 확인
ps aux | grep "run_save_all_games" | grep -v grep

# 프로세스 종료
pkill -f "run_save_all_games.py"
```

**설정 가능한 매개변수** (파일 내부 수정):
```python
# 기본 설정 (파일 마지막 부분)
result = main_with_batch(
    max_retries=10,      # 최대 재시도 횟수
    delay=0.5,           # 각 게임 처리 후 지연 시간 (초)
    batch_size=100,      # 배치 크기
    limit=None,          # 처리할 게임 수 제한 (None=무제한)
    minimum_reviews=100  # 최소 리뷰 수 필터
)
```

**로그 파일 위치**:
- 실행 로그: `logs/run_save_all_games_YYYYMMDD_HHMMSS.log`
- 실패 게임 정보: `logs/failed_games_YYYYMMDD_HHMMSS.json`

## 에러 처리

모든 모듈은 통일된 에러 처리 구조를 사용합니다:

```python
{
    'success': False,
    'error': 'error_type',
    'message': 'error_message',
    'app_id': app_id
}
```

**에러 타입:**
- `rate_limit_exceeded`: API/요청 제한 초과
- `http_error`: HTTP 에러 (404, 500 등)
- `age_verification_failed`: 나이 인증 처리 실패
- `invalid_game_page`: 유효하지 않은 게임 페이지
- `exception`: 네트워크 오류 등 예외 발생
- `unknown`: 알 수 없는 오류

## 데이터 출력 형식

### 성공 응답
```python
{
    'success': True,
    'data': {
        # 수집된 게임 정보
    },
    'app_id': 1091500
}
```

### 실패 응답
```python
{
    'success': False,
    'error': 'http_error',
    'message': 'HTTP 404 오류',
    'app_id': 1091500,
    'http_status': 404
}
```

## 권장 사용 패턴

1. **게임 ID 수집**: `fetch_steam_game_ids.py`
2. **기본 정보**: `fetch_steam_game_data.py` (Steam API)
3. **추가 정보**: `single_game_crawler_minimal.py` (웹 크롤링)

이 조합으로 Steam API의 안정성과 웹 크롤링의 추가 정보를 모두 활용할 수 있습니다.

## 주의사항

- **요청 제한**: Steam에서 요청 제한을 적용할 수 있으므로 적절한 대기 시간을 두고 사용하세요
- **나이 제한 게임**: 자동으로 나이 인증을 처리하지만 일부 게임은 추가 인증이 필요할 수 있습니다  
- **네트워크 안정성**: 안정적인 인터넷 연결이 필요합니다
- **로그 모니터링**: utils.logger를 사용하여 진행 상황을 모니터링하세요
- **크롤링 문제점**: 게임 정보 확인에 로그인이 필요한 게임, 지역락이 걸린 게임은 크롤링으로 데이터를 가져올 수 없습니다

## 개발 환경

- Python 3.12+
- aiohttp: 비동기 HTTP 요청
- requests: 동기 HTTP 요청  
- beautifulsoup4: HTML 파싱
- pyproject.toml: 프로젝트 설정