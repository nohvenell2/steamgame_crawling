#!/usr/bin/env python3
"""
Steam 게임 필터링 실행 스크립트

이 스크립트는 Steam Spy API를 사용하여 인기 게임들을 수집하고,
Steam Reviews API로 리뷰 수를 확인하여 조건에 맞는 게임만 필터링합니다.

사용법:
    python run_game_filter.py
    
설정 가능한 옵션:
    - 최소 리뷰 수
    - 최소 소유자 수 (Steam Spy 기준)
    - 출력 파일 경로
"""

import sys
import os
from filter_popular_games import SteamGameFilter

def main():
    print("🎮 Steam 인기 게임 필터링 도구")
    print("=" * 60)
    print("이 도구는 다음 조건으로 게임을 필터링합니다:")
    print("1. Steam Spy 인기 게임 목록에서 수집")
    print("2. 사용자가 설정한 최소 리뷰 수 이상")
    print("3. 리뷰 수 순으로 정렬하여 CSV 저장")
    print("=" * 60)
    
    # 사용자 설정 입력
    try:
        min_reviews = input("최소 리뷰 수를 입력하세요 (기본값: 100): ").strip()
        min_reviews = int(min_reviews) if min_reviews else 100
        
        print(f"\n📋 설정된 조건:")
        print(f"- 최소 리뷰 수: {min_reviews}개")
        print(f"- 출력 파일: data/steam_game_id_list.csv")
        print(f"- 상세 정보 파일: data/steam_game_id_list_detailed.csv")
        
        # 진행 확인
        print("\n⚠️  주의사항:")
        print("- 이 작업은 10-30분 정도 소요될 수 있습니다")
        print("- Steam API 호출 제한으로 인해 각 게임마다 0.5초씩 대기합니다")
        print("- 네트워크 연결이 안정적이어야 합니다")
        
        confirm = input("\n계속 진행하시겠습니까? (y/N): ").strip().lower()
        
        if confirm not in ['y', 'yes']:
            print("작업이 취소되었습니다.")
            return
        
        # 필터링 실행
        filter_manager = SteamGameFilter()
        filter_manager.run_filtering(
            min_reviews=min_reviews,
            output_file="data/steam_game_id_list.csv"
        )
        
        print("\n🎉 작업이 완료되었습니다!")
        print("📁 다음 파일들이 생성되었습니다:")
        print("  - data/steam_game_id_list.csv (기본 게임 ID 목록)")
        print("  - data/steam_game_id_list_detailed.csv (게임 ID + 리뷰 수)")
        
    except KeyboardInterrupt:
        print("\n\n작업이 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except ValueError:
        print("❌ 올바른 숫자를 입력해주세요.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 예상치 못한 오류가 발생했습니다: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 