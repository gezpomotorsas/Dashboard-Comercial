"""Pruebas del updater del launcher."""

import json
from unittest.mock import patch

from launcher.updater import check_for_update
from launcher.version_store import write_version


def test_check_update_when_release_available(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    write_version("aaa1111", path=runtime / "version.json")
    monkeypatch.setenv("GITHUB_REPO", "org/repo")

    release = {
        "tag_name": "build-bbb2222",
        "name": "Build bbb",
        "body": "commit: bbb222222222222222222222222222222222222",
        "assets": [
            {
                "name": "runtime.zip",
                "url": "https://api.github.com/repos/org/repo/releases/assets/1",
                "browser_download_url": "https://example.com/runtime.zip",
            }
        ],
    }

    with patch("launcher.updater.read_version", return_value={"commit": "aaa1111", "repo": "org/repo"}):
        with patch("launcher.updater.fetch_remote_main_commit", return_value="bbb222222222222222222222222222222222222"):
            with patch("launcher.updater.fetch_latest_release", return_value=release):
                status = check_for_update()

    assert status.update_available is True
    assert status.source == "release"
    assert status.release_tag == "build-bbb2222"


def test_check_update_up_to_date(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "org/repo")
    commit = "ccc333333333333333333333333333333333333"
    release = {
        "tag_name": f"build-{commit}",
        "name": "Build",
        "body": f"commit: {commit}",
        "assets": [
            {
                "name": "runtime.zip",
                "url": "https://api.github.com/repos/org/repo/releases/assets/1",
                "browser_download_url": "https://example.com/runtime.zip",
            }
        ],
    }

    with patch("launcher.updater.read_version", return_value={"commit": commit, "repo": "org/repo"}):
        with patch("launcher.updater.fetch_remote_main_commit", return_value=commit):
            with patch("launcher.updater.fetch_latest_release", return_value=release):
                status = check_for_update()

    assert status.update_available is False
