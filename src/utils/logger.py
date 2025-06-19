"""
간단한 로거 설정 유틸리티
"""

import logging
from typing import Optional


def setup_logger(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """
    로거를 설정합니다.
    
    Args:
        level (str): 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string (str, optional): 로그 포맷 문자열
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[
            logging.StreamHandler(),  # 콘솔 출력
        ]
    ) 