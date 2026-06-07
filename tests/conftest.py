"""pytest 全局配置"""

import pytest


@pytest.fixture
def project_root():
    """返回项目根目录路径"""
    from pathlib import Path
    return Path(__file__).parent.parent
