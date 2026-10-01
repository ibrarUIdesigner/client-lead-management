import asyncio
import io
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import brotli
import pytest

from app.core.config import Settings
from app.services.audit_browser import AuditRunError, _capture_website, _launch_browser
from app.services.serverless_chromium import (
    ServerlessBrowserError,
    browser_environment,
    chromium_pack_url,
    ensure_serverless_chromium,
)


def _brotli_tar(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:") as tar:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return brotli.compress(buffer.getvalue())


def _pack_bytes() -> bytes:
    members = {
        "chromium.br": brotli.compress(b"fake-chromium-binary"),
        "fonts.tar.br": _brotli_tar({"fonts.conf": b"<fontconfig/>"}),
        "al2023.tar.br": _brotli_tar({"lib/libnss3.so": b"lib"}),
        "swiftshader.tar.br": _brotli_tar({"libGLESv2.so": b"gl"}),
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def test_pack_url_follows_the_function_cpu() -> None:
    assert chromium_pack_url("x86_64").endswith("/chromium-v153.0.0-pack.x64.tar")
    assert chromium_pack_url("aarch64").endswith("/chromium-v153.0.0-pack.arm64.tar")


def test_browser_environment_points_at_the_serverless_libraries(tmp_path: Path) -> None:
    env = browser_environment(tmp_path)

    assert env["HOME"] == str(tmp_path)
    assert env["FONTCONFIG_PATH"] == str(tmp_path / "fonts")
    assert env["LD_LIBRARY_PATH"].startswith(str(tmp_path / "al2023" / "lib"))


def test_serverless_chromium_is_unpacked_for_vercel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _pack_bytes()

    def fake_download(_url: str, dest: Path) -> None:
        dest.write_bytes(pack)

    monkeypatch.setattr("app.services.serverless_chromium._download", fake_download)
    launched = Path(ensure_serverless_chromium(tmp_path, minimum_bytes=1))

    assert (tmp_path / "chromium").read_bytes() == b"fake-chromium-binary"
    assert (tmp_path / "al2023" / "lib" / "libnss3.so").is_file()
    assert (tmp_path / "fonts" / "fonts.conf").is_file()
    assert (tmp_path / "libGLESv2.so").is_file()
    assert 'exec "' in launched.read_text(encoding="utf-8")
    assert not (tmp_path / "chromium-pack.tar").exists()


def test_installed_serverless_chromium_is_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "chromium"
    binary.write_bytes(b"x")
    (tmp_path / "al2023" / "lib").mkdir(parents=True)

    def fail_download(_url: str, _dest: Path) -> None:
        raise AssertionError("chromium should be reused")

    monkeypatch.setattr("app.services.serverless_chromium._download", fail_download)

    assert Path(ensure_serverless_chromium(tmp_path, minimum_bytes=1)).name == "chromium-launcher"


def test_vercel_capture_installs_chromium_before_playwright(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VERCEL", "1")
    order: list[str] = []

    def ensure() -> str:
        order.append("ensure")
        return "/tmp/chromium"

    class Chromium:
        async def launch(self, **_kwargs: object) -> object:
            order.append("launch")
            raise AuditRunError("stop")

    class Playwright:
        def __init__(self) -> None:
            order.append("driver")
            self.chromium = Chromium()

        async def __aenter__(self) -> "Playwright":
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

    module = ModuleType("playwright.async_api")
    module.async_playwright = lambda: Playwright()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", module)
    monkeypatch.setattr("app.services.audit_browser.ensure_serverless_chromium", ensure)

    with pytest.raises(AuditRunError, match="stop"):
        asyncio.run(_capture_website("https://example.com/"))

    assert order.index("ensure") < order.index("driver")
    assert order[-1] == "launch"


def test_vercel_launch_uses_the_serverless_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    seen: dict[str, object] = {}

    class Chromium:
        async def launch(self, **kwargs: object) -> str:
            seen.update(kwargs)
            return "browser"

    class Playwright:
        chromium = Chromium()

    monkeypatch.setattr(
        "app.services.audit_browser.ensure_serverless_chromium",
        lambda: "/tmp/chromium",
    )

    assert asyncio.run(_launch_browser(Playwright())) == "browser"
    assert seen["executable_path"] == "/tmp/chromium"
    assert seen["headless"] is False
    assert "--headless=shell" in seen["args"]
    assert "--no-sandbox" in seen["args"]


def test_vercel_browser_failure_does_not_ask_for_a_local_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VERCEL", "1")

    def explode() -> str:
        raise ServerlessBrowserError("download failed")

    class Chromium:
        async def launch(self, **_kwargs: object) -> None:
            raise AssertionError("browser should not launch")

    class Playwright:
        chromium = Chromium()

    monkeypatch.setattr("app.services.audit_browser.ensure_serverless_chromium", explode)

    with pytest.raises(AuditRunError, match="could not be started") as error:
        asyncio.run(_launch_browser(Playwright()))

    assert "playwright install" not in error.value.message


def test_local_missing_browser_keeps_install_instructions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)

    class Chromium:
        async def launch(self, **_kwargs: object) -> None:
            raise RuntimeError("Executable doesn't exist at /ms-playwright/chromium")

    class Playwright:
        chromium = Chromium()

    with pytest.raises(AuditRunError, match="playwright install chromium"):
        asyncio.run(_launch_browser(Playwright()))


def test_vercel_screenshot_storage_is_writable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("STORAGE_DIR", raising=False)

    settings = Settings(_env_file=None)

    assert settings.storage_dir == Path("/tmp/storage")
    kept = Settings(_env_file=None, storage_dir=tmp_path)
    assert kept.storage_dir == tmp_path
