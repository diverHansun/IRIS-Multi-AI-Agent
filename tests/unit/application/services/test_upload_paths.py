"""Paths passed by a macOS/Linux terminal must reach the uploader unchanged."""

import os
from types import SimpleNamespace
from pathlib import Path

import pytest
from rich.console import Console

from src.application.services.dify.upload import _resolve_file_paths

pytestmark = pytest.mark.skipif(os.name == 'nt', reason='POSIX terminal syntax')


@pytest.mark.parametrize('query', ['"会议 记录.txt"', '会议\\ 记录.txt', "'会议 记录.txt'"])
def test_quoted_and_escaped_posix_upload_path(query, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    uploader = SimpleNamespace(console=Console())
    assert _resolve_file_paths(query, uploader) == [str(tmp_path / '会议 记录.txt')]


def test_upload_expands_home_and_handles_multiple_files():
    user_home = Path.home()
    uploader = SimpleNamespace(console=Console())
    assert _resolve_file_paths('~/a.txt "~/b c.txt"', uploader) == [
        str(user_home / 'a.txt'), str(user_home / 'b c.txt')
    ]
