"""Unit tests for the opt-in Scribus AppImage fetcher.

We mock ``urllib.request.urlopen`` so no real network traffic is
generated. The size floor is checked against the bytes the mock
serves, so each test crafts a body that's either above or below the
sanity floor.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from scribus_mcp import appimage


class _FakeResponse(io.BytesIO):
    """``urlopen`` context-manager stand-in returning ``data`` once."""

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def _payload(size_mb: float) -> bytes:
    return b"x" * int(size_mb * 1024 * 1024)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_install_target_matches_default_probe_glob(tmp_path: Path):
    target = appimage.install_target("1.7.3", install_dir=tmp_path)
    assert target == tmp_path / "Scribus-1.7.3-x86_64.AppImage"
    # ``config._default_scribus_bin`` globs ``Scribus*.AppImage`` in
    # ``~/Applications`` — make sure that pattern hits the file.
    matches = list(tmp_path.glob("Scribus*.AppImage"))
    target.touch()
    matches = list(tmp_path.glob("Scribus*.AppImage"))
    assert matches == [target]


def test_fetch_writes_target_and_chmods_executable(tmp_path: Path):
    body = _payload(60)
    with patch.object(appimage, "urlopen", return_value=_FakeResponse(body)):
        path = appimage.fetch_appimage(
            url="https://example.invalid/scribus.AppImage",
            version="1.7.3",
            install_dir=tmp_path,
            log_fn=lambda _m: None,
        )
    assert path.exists()
    assert path.stat().st_size == len(body)
    # 0o755 — owner rwx, group rx, other rx
    assert (path.stat().st_mode & 0o777) == 0o755


def test_fetch_is_idempotent_when_target_present(tmp_path: Path):
    target = appimage.install_target("1.7.3", install_dir=tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"already here")

    # urlopen must NOT be called the second time around
    with patch.object(appimage, "urlopen", side_effect=AssertionError("called!")):
        path = appimage.fetch_appimage(
            version="1.7.3",
            install_dir=tmp_path,
            log_fn=lambda _m: None,
        )
    assert path == target
    assert path.read_bytes() == b"already here"


def test_fetch_redownloads_when_existing_sha_mismatches(tmp_path: Path):
    target = appimage.install_target("1.7.3", install_dir=tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"old garbage")

    new_body = _payload(60)
    new_sha = _sha256(new_body)
    with patch.object(appimage, "urlopen", return_value=_FakeResponse(new_body)):
        path = appimage.fetch_appimage(
            version="1.7.3",
            install_dir=tmp_path,
            expected_sha256=new_sha,
            log_fn=lambda _m: None,
        )
    assert path.read_bytes() == new_body


def test_size_floor_rejects_truncated_payload(tmp_path: Path):
    body = _payload(0.5)  # 0.5 MB << 50 MB floor
    with (
        patch.object(appimage, "urlopen", return_value=_FakeResponse(body)),
        pytest.raises(appimage.AppImageError, match=r"too small|expected >="),
    ):
        appimage.fetch_appimage(
            url="https://example.invalid/scribus.AppImage",
            version="1.7.3",
            install_dir=tmp_path,
            log_fn=lambda _m: None,
        )
    # Partial file must be cleaned up
    assert not (tmp_path / "Scribus-1.7.3-x86_64.AppImage.part").exists()
    assert not appimage.install_target("1.7.3", install_dir=tmp_path).exists()


def test_sha256_pin_failure_aborts_install(tmp_path: Path):
    body = _payload(60)
    wrong_sha = "0" * 64
    with (
        patch.object(appimage, "urlopen", return_value=_FakeResponse(body)),
        pytest.raises(appimage.AppImageError, match="SHA256 mismatch"),
    ):
        appimage.fetch_appimage(
            version="1.7.3",
            install_dir=tmp_path,
            expected_sha256=wrong_sha,
            log_fn=lambda _m: None,
        )
    assert not appimage.install_target("1.7.3", install_dir=tmp_path).exists()


def test_sha256_pin_match_succeeds(tmp_path: Path):
    body = _payload(60)
    correct_sha = _sha256(body)
    with patch.object(appimage, "urlopen", return_value=_FakeResponse(body)):
        path = appimage.fetch_appimage(
            version="1.7.3",
            install_dir=tmp_path,
            expected_sha256=correct_sha,
            log_fn=lambda _m: None,
        )
    assert path.exists()


def test_network_error_cleans_up_partial(tmp_path: Path):
    from urllib.error import URLError

    with (
        patch.object(appimage, "urlopen", side_effect=URLError("DNS fail")),
        pytest.raises(appimage.AppImageError, match="Download failed"),
    ):
        appimage.fetch_appimage(
            version="1.7.3",
            install_dir=tmp_path,
            log_fn=lambda _m: None,
        )
    assert not (tmp_path / "Scribus-1.7.3-x86_64.AppImage.part").exists()


def test_fetch_from_env_reads_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    body = _payload(60)
    correct_sha = _sha256(body)
    monkeypatch.setenv("SCRIBUS_MCP_APPIMAGE_URL", "https://example.invalid/x.AppImage")
    monkeypatch.setenv("SCRIBUS_MCP_APPIMAGE_VERSION", "1.7.99")
    monkeypatch.setenv("SCRIBUS_MCP_APPIMAGE_SHA256", correct_sha)
    monkeypatch.setenv("SCRIBUS_MCP_APPIMAGE_INSTALL_DIR", str(tmp_path))

    with patch.object(appimage, "urlopen", return_value=_FakeResponse(body)) as op:
        path = appimage.fetch_appimage_from_env(log_fn=lambda _m: None)

    op.assert_called_once_with("https://example.invalid/x.AppImage")
    assert path == tmp_path / "Scribus-1.7.99-x86_64.AppImage"
    assert path.exists()
