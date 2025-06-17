# Steam Game Crawler

Steam 게임의 태그 정보를 크롤링하는 Python 프로그램입니다.

## 기능

- Steam 게임 페이지에서 태그 정보 추출
- 비동기 크롤링으로 빠른 데이터 수집
- JSON과 CSV 형식으로 결과 저장
- MySQL 데이터베이스 연결 지원

## 크롤러 모듈

### 1. crawler.py (구현 예정)
- Steam API에서 모든 게임 목록을 자동으로 수집
- 수집된 모든 게임의 상세 정보를 크롤링
- 대량 게임 데이터 처리에 최적화

### 2. single_game_crawler.py
- 개별 게임의 상세 정보를 크롤링
- 게임 기본 정보, 가격, 리뷰, 개발사/퍼블리셔 등 포함
- Steam API에서 제공하는 모든 게임 정보 수집

### 3. single_game_tag_crawler.py
- Steam API에서 제공하지 않는 태그 정보 전용 크롤링
- 게임 페이지에서 직접 태그 정보를 추출
- 태그 데이터만 필요한 경우 사용

## 설치 방법

### Poetry 사용 (권장)

```bash
# Poetry 설치 (아직 설치하지 않은 경우)
curl -sSL https://install.python-poetry.org | python3 -

# 의존성 설치
poetry install
```

### pip 사용

```bash
# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
.\venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

## 사용 방법

### 전체 게임 크롤링 (구현 예정)

```bash
# Poetry 사용 시
poetry shell
python src/crawler.py

# pip 사용 시
python src/crawler.py
```

### 개별 게임 정보 크롤링

```python
from src.single_game_crawler import get_steam_game_info_sync

# 개별 게임 정보 크롤링
game_info = get_steam_game_info_sync(1091500)  # Cyberpunk 2077
print(game_info)
```

### 개별 게임 태그 크롤링

```python
from src.single_game_tag_crawler import get_steam_game_tags_sync

# 게임 태그만 크롤링
tags = get_steam_game_tags_sync(1091500)  # Cyberpunk 2077
print(tags)
```

### 태그 분석

태그가 없는 게임 ID를 찾는 도구:

```bash
# Poetry 사용 시
poetry shell
python src/_tag/find_missing_tags.py

# pip 사용 시
python src/_tag/find_missing_tags.py
```

## 데이터베이스 설정

`.env` 파일을 생성하여 MySQL 연결 정보를 설정하세요:

```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_username
MYSQL_PW=your_password
MYSQL_DB_NAME=your_database_name
```

## 결과

- `data/steam_tags.json`: JSON 형식의 크롤링 결과
- `data/steam_tags.csv`: CSV 형식의 크롤링 결과
- `data/missing_tags_game_ids.csv`: 태그가 없는 게임 ID 목록
- `data/game_info/`: 개별 게임 정보 JSON 파일들

## 주의사항

- 안정적인 네트워크 연결이 필요합니다
- MySQL 데이터베이스 연결 설정이 필요합니다
- Steam API 호출 제한을 고려하여 적절한 대기 시간을 설정합니다