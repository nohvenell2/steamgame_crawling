import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional
from tqdm import tqdm
import json
from pathlib import Path
import time
import csv

class SteamTagCrawler:
    def __init__(self):
        self.base_url = "https://store.steampowered.com/app/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

    def load_game_ids_from_csv(self, csv_file: str = "data/steam_game_id_list.csv") -> List[int]:
        """CSV 파일에서 게임 ID 목록을 읽어옵니다."""
        game_ids = []
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                for row in csv_reader:
                    if row and row[0].strip().isdigit():
                        game_ids.append(int(row[0].strip()))
            print(f"CSV 파일에서 {len(game_ids)}개의 게임 ID를 로드했습니다.")
            return game_ids
        except FileNotFoundError:
            print(f"파일을 찾을 수 없습니다: {csv_file}")
            return []
        except Exception as e:
            print(f"CSV 파일 읽기 중 오류: {str(e)}")
            return []

    def load_progress(self) -> Dict:
        """이전 진행 상황을 로드합니다."""
        progress_file = self.data_dir / "crawling_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"completed_ids": [], "failed_ids": [], "last_batch": 0}
        return {"completed_ids": [], "failed_ids": [], "last_batch": 0}

    def save_progress(self, progress: Dict):
        """현재 진행 상황을 저장합니다."""
        progress_file = self.data_dir / "crawling_progress.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def get_age_verification_cookies(self):
        """나이 인증을 우회하기 위한 쿠키를 생성합니다."""
        # Steam의 나이 인증을 우회하는 쿠키 설정
        # birthtime=1은 1970년 1월 1일을 의미하며, 충분히 성인임을 나타냅니다
        return {
            'birthtime': '1',  # 1970년 1월 1일 (Unix timestamp)
            'mature_content': '1',  # 성인 콘텐츠 허용
            'lastagecheckage': '1-January-1970'  # 마지막 나이 확인 날짜
        }

    async def handle_age_check(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """나이 인증 페이지를 처리합니다."""
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # 나이 인증 페이지인지 확인
                    if 'agecheck' in html or 'agegate' in html:
                        print(f"나이 인증 페이지 감지: {url}")
                        
                        # 나이 인증 폼 데이터 준비
                        form_data = {
                            'snr': '1_agecheck_agecheck__age-gate',
                            'ageDay': '1',
                            'ageMonth': 'January', 
                            'ageYear': '1990'  # 충분히 성인인 연도
                        }
                        
                        # POST 요청으로 나이 인증 통과
                        async with session.post(url, data=form_data, headers=self.headers) as post_response:
                            if post_response.status == 200:
                                return await post_response.text()
                    
                    return html
        except Exception as e:
            print(f"나이 인증 처리 중 오류: {str(e)}")
            return None

    async def fetch_game_page(self, session: aiohttp.ClientSession, app_id: int) -> Optional[Dict]:
        """게임 페이지를 가져와서 태그 정보를 추출합니다."""
        url = f"{self.base_url}{app_id}"
        try:
            # 나이 인증 쿠키 설정
            cookies = self.get_age_verification_cookies()
            
            async with session.get(url, headers=self.headers, cookies=cookies) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # 나이 인증 페이지로 리다이렉트된 경우 처리
                    if 'agecheck' in response.url.path or 'agegate' in html.lower():
                        print(f"App ID {app_id}: 나이 인증 필요, 우회 시도 중...")
                        html = await self.handle_age_check(session, str(response.url))
                        if not html:
                            return None
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 게임 제목 추출 (여러 가능한 선택자 시도)
                    title = None
                    title_selectors = [
                        'div.apphub_AppName',
                        'h1.pageheader',
                        '.game_title h1',
                        '#appHubAppName'
                    ]
                    
                    for selector in title_selectors:
                        title_element = soup.select_one(selector)
                        if title_element:
                            title = title_element.get_text(strip=True)
                            break
                    
                    if not title:
                        title = "Unknown"
                    
                    # 태그 추출 (여러 가능한 선택자 시도)
                    tags = []
                    tag_selectors = [
                        'a.app_tag',
                        '.popular_tags a',
                        '.game_area_details_specs a'
                    ]
                    
                    for selector in tag_selectors:
                        tag_elements = soup.select(selector)
                        if tag_elements:
                            for tag in tag_elements:
                                tag_text = tag.get_text(strip=True)
                                if tag_text and tag_text not in tags:
                                    tags.append(tag_text)
                            break
                    
                    print(f"App ID {app_id}: {title} - {len(tags)}개 태그 발견")
                    
                    return {
                        "app_id": app_id,
                        "title": title,
                        "tags": tags
                    }
                else:
                    print(f"App ID {app_id}: HTTP {response.status} 오류")
                    return None
                    
        except Exception as e:
            print(f"App ID {app_id} 크롤링 중 오류: {str(e)}")
            return None

    async def crawl_batch(self, session: aiohttp.ClientSession, app_ids: List[int]) -> List[Dict]:
        """배치 단위로 게임들을 크롤링합니다."""
        tasks = []
        for app_id in app_ids:
            task = asyncio.create_task(self.fetch_game_page(session, app_id))
            tasks.append(task)
            await asyncio.sleep(0.1)  # 요청 간격 단축 (대량 처리용)
        
        results = []
        for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="배치 크롤링 중"):
            result = await future
            if result:
                results.append(result)
        
        return results

    async def crawl_all_games(self, batch_size: int = 100):
        """CSV 파일의 모든 게임을 배치 단위로 크롤링합니다."""
        # 게임 ID 로드
        all_game_ids = self.load_game_ids_from_csv()
        if not all_game_ids:
            print("크롤링할 게임 ID가 없습니다.")
            return
        
        # 진행 상황 로드
        progress = self.load_progress()
        completed_ids = set(progress.get("completed_ids", []))
        failed_ids = set(progress.get("failed_ids", []))
        last_batch = progress.get("last_batch", 0)
        
        # 아직 처리되지 않은 게임 ID 필터링
        remaining_ids = [gid for gid in all_game_ids if gid not in completed_ids and gid not in failed_ids]
        
        print(f"전체 게임: {len(all_game_ids)}개")
        print(f"완료된 게임: {len(completed_ids)}개")
        print(f"실패한 게임: {len(failed_ids)}개")
        print(f"남은 게임: {len(remaining_ids)}개")
        print(f"배치 크기: {batch_size}")
        
        if not remaining_ids:
            print("모든 게임이 이미 처리되었습니다.")
            return
        
        # 배치 단위로 처리
        jar = aiohttp.CookieJar(unsafe=True)
        all_results = []
        
        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            for i in range(0, len(remaining_ids), batch_size):
                batch_num = i // batch_size + 1
                batch_ids = remaining_ids[i:i + batch_size]
                
                print(f"\n=== 배치 {batch_num}/{(len(remaining_ids) + batch_size - 1) // batch_size} 처리 중 ===")
                print(f"게임 ID: {batch_ids[0]} ~ {batch_ids[-1]} ({len(batch_ids)}개)")
                
                try:
                    batch_results = await self.crawl_batch(session, batch_ids)
                    all_results.extend(batch_results)
                    
                    # 성공한 ID들을 완료 목록에 추가
                    successful_ids = [r["app_id"] for r in batch_results]
                    completed_ids.update(successful_ids)
                    
                    # 실패한 ID들을 실패 목록에 추가
                    failed_batch_ids = set(batch_ids) - set(successful_ids)
                    failed_ids.update(failed_batch_ids)
                    
                    print(f"배치 {batch_num} 완료: 성공 {len(successful_ids)}개, 실패 {len(failed_batch_ids)}개")
                    
                    # 진행 상황 저장
                    progress = {
                        "completed_ids": list(completed_ids),
                        "failed_ids": list(failed_ids),
                        "last_batch": batch_num
                    }
                    self.save_progress(progress)
                    
                    # 중간 결과 저장 (배치마다)
                    if all_results:
                        self.save_results(all_results, format="json")
                        self.save_results(all_results, format="csv")
                    
                    # 배치 간 휴식
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    print(f"배치 {batch_num} 처리 중 오류: {str(e)}")
                    failed_ids.update(batch_ids)
                    continue
        
        print(f"\n=== 크롤링 완료 ===")
        print(f"총 처리된 게임: {len(all_results)}개")
        print(f"성공: {len(completed_ids)}개")
        print(f"실패: {len(failed_ids)}개")

    def save_results(self, results: List[Dict], format: str = "json"):
        """크롤링 결과를 저장합니다."""
        if format == "json":
            output_file = self.data_dir / "steam_tags_all.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        elif format == "csv":
            output_file = self.data_dir / "steam_tags_all.csv"
            df = pd.DataFrame(results)
            df.to_csv(output_file, index=False, encoding='utf-8')

async def main():
    crawler = SteamTagCrawler()
    
    # 전체 게임 크롤링 (배치 크기: 50개씩)
    await crawler.crawl_all_games(batch_size=50)

if __name__ == "__main__":
    asyncio.run(main()) 