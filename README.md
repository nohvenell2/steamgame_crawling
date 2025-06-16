# Steam Game Tag Crawler

Steam 게임의 태그 정보를 크롤링하는 Python 프로그램입니다.

## 기능

- Steam 게임 페이지에서 태그 정보 추출
- 비동기 크롤링으로 빠른 데이터 수집
- JSON과 CSV 형식으로 결과 저장
- **🆕 인기 게임 필터링 기능** - 리뷰 수가 많은 의미있는 게임만 선별

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

### 1. 인기 게임 필터링 (추천)

의미없는 게임들을 제외하고 리뷰 수가 많은 인기 게임들만 선별합니다:

```bash
# Poetry 사용 시
poetry shell
python run_game_filter.py

# pip 사용 시
python run_game_filter.py
```

**필터링 기준:**
- Steam Spy 인기 게임 목록 (소유자 수, 플레이어 수 상위)
- 사용자 설정 최소 리뷰 수 (기본값: 100개)
- 인기 장르별 게임 포함

**생성되는 파일:**
- `data/steam_game_id_list.csv` - 필터링된 게임 ID 목록
- `data/steam_game_id_list_detailed.csv` - 게임 ID + 리뷰 수 정보

### 2. 게임 태그 크롤링

필터링된 게임 목록으로 태그 정보를 수집합니다:

```bash
# Poetry 사용 시
poetry shell
python src/crawler.py

# pip 사용 시
python src/crawler.py
```

## 필터링 기능 상세

### Steam Spy API 활용
- **top100owned**: 소유자 수 상위 100개 게임
- **top100in2weeks**: 최근 2주 플레이어 수 상위 100개 게임  
- **top100forever**: 평생 플레이어 수 상위 100개 게임
- **장르별 게임**: Action, Adventure, RPG, Strategy, Simulation, Indie

### Steam Reviews API 활용
- 각 게임의 총 리뷰 수 확인
- 사용자 설정 최소 리뷰 수로 필터링
- 리뷰 수 순으로 정렬

### 필터링 장점
- **의미있는 데이터**: 실제로 플레이되고 리뷰가 많은 게임만 선별
- **효율적인 크롤링**: 불필요한 게임 제외로 크롤링 시간 단축
- **데이터 품질 향상**: 태그 정보가 풍부한 게임들로 한정

## 결과

- `data/steam_tags.json`: JSON 형식의 크롤링 결과
- `data/steam_tags.csv`: CSV 형식의 크롤링 결과 
- `data/steam_game_id_list.csv`: 필터링된 게임 ID 목록
- `data/steam_game_id_list_detailed.csv`: 상세 게임 정보

## 주의사항

- 필터링 작업은 10-30분 정도 소요됩니다
- Steam API 호출 제한으로 각 요청마다 대기 시간이 있습니다
- 안정적인 네트워크 연결이 필요합니다 