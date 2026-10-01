"""Chromium build that runs inside a Vercel function.

Playwright's own browser is not installed on Vercel, and the function image has
no Chrome or Edge. The Sparticuz pack is a headless Chromium built for that
environment. The first audit on an instance downloads it into /tmp; later
audits on the same instance reuse it.
"""

import io
import logging
import os
import platform
import shutil
import tarfile
from pathlib import Path

import brotli
import httpx

logger = logging.getLogger(__name__)

CHROMIUM_VERSION = "153.0.0"
_MIN_EXECUTABLE_BYTES = 20_000_000
_MIN_PACK_BYTES = 50_000_000
_PACK_FILES = (
    "al2023.tar.br",
    "chromium.br",
    "fonts.tar.br",
    "swiftshader.tar.br",
)

# Flags from @sparticuz/chromium for Lambda and Vercel. The headless shell
# build needs these; a normal Playwright Chromium launch does not.
SERVERLESS_ARGS = (
    "--ash-no-nudges",
    "--disable-domain-reliability",
    "--disable-print-preview",
    "--disk-cache-size=33554432",
    "--no-default-browser-check",
    "--no-pings",
    "--single-process",
    "--font-render-hinting=none",
    "--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process",
    "--enable-features=SharedArrayBuffer",
    "--ignore-gpu-blocklist",
    "--in-process-gpu",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--allow-running-insecure-content",
    "--disable-setuid-sandbox",
    "--disable-site-isolation-trials",
    "--disable-web-security",
    "--headless='shell'",
    "--no-sandbox",
    "--no-zygote",
)


class ServerlessBrowserError(Exception):
    pass


def serverless_runtime() -> bool:
    return os.environ.get("VERCEL") == "1"


def chromium_pack_url(machine: str | None = None) -> str:
    machine = platform.machine().lower() if machine is None else machine.lower()
    arch = "arm64" if machine in {"aarch64", "arm64"} else "x64"
    version = CHROMIUM_VERSION
    return (
        "https://github.com/Sparticuz/chromium/releases/download/"
        f"v{version}/chromium-v{version}-pack.{arch}.tar"
    )


def browser_environment(root: Path | None = None) -> dict[str, str]:
    """Environment Chromium needs to find its libraries, fonts, and a writable home."""
    root = root or Path("/tmp")
    env = {key: value for key, value in os.environ.items() if isinstance(value, str)}
    env["HOME"] = str(root)
    env["FONTCONFIG_PATH"] = str(root / "fonts")
    library = str(root / "al2023" / "lib")
    current = [part for part in env.get("LD_LIBRARY_PATH", "").split(":") if part]
    if library not in current:
        env["LD_LIBRARY_PATH"] = ":".join([library, *current])
    return env


def ensure_serverless_chromium(
    root: Path | None = None,
    *,
    minimum_bytes: int = _MIN_EXECUTABLE_BYTES,
) -> str:
    root = root or Path("/tmp")
    executable = root / "chromium"
    libraries = root / "al2023" / "lib"
    if (
        executable.is_file()
        and executable.stat().st_size >= minimum_bytes
        and libraries.is_dir()
    ):
        _apply_environment(root)
        return str(executable)

    archive = root / "chromium-pack.tar"
    pack_dir = root / "chromium-pack"
    try:
        _download(chromium_pack_url(), archive)
        _extract_pack(archive, pack_dir)
        _inflate_pack(pack_dir, root)
    except ServerlessBrowserError:
        raise
    except Exception as exc:
        logger.exception("serverless_chromium_setup_failed")
        raise ServerlessBrowserError("serverless chromium could not be installed") from exc
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(pack_dir, ignore_errors=True)

    ready = (
        executable.is_file()
        and executable.stat().st_size >= minimum_bytes
        and libraries.is_dir()
    )
    if not ready:
        executable.unlink(missing_ok=True)
        logger.error("serverless_chromium_incomplete")
        raise ServerlessBrowserError("serverless chromium could not be installed")
    _apply_environment(root)
    return str(executable)


def _apply_environment(root: Path) -> None:
    env = browser_environment(root)
    os.environ["HOME"] = env["HOME"]
    os.environ["FONTCONFIG_PATH"] = env["FONTCONFIG_PATH"]
    os.environ["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH"]


def _download(url: str, dest: Path) -> None:
    if dest.is_file() and dest.stat().st_size >= _MIN_PACK_BYTES:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for _attempt in range(2):
        partial = dest.with_suffix(".part")
        try:
            logger.info("serverless_chromium_download")
            timeout = httpx.Timeout(180.0, connect=30.0)
            with httpx.Client(follow_redirects=True, timeout=timeout) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with partial.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if chunk:
                                handle.write(chunk)
            partial.replace(dest)
            return
        except Exception as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            dest.unlink(missing_ok=True)
            logger.warning("serverless_chromium_download_failed")
    raise ServerlessBrowserError("serverless chromium could not be downloaded") from last_error


def _extract_pack(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    found: set[str] = set()
    with tarfile.open(archive, mode="r:") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = Path(member.name).name
            if name not in _PACK_FILES:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            target = dest / name
            with target.open("wb") as handle:
                while chunk := extracted.read(1024 * 1024):
                    handle.write(chunk)
            found.add(name)
    missing = [name for name in _PACK_FILES if name not in found]
    if missing:
        raise ServerlessBrowserError("serverless chromium pack is incomplete")


def _inflate_pack(pack_dir: Path, root: Path) -> None:
    _decompress_file(pack_dir / "chromium.br", root / "chromium", executable=True)
    (pack_dir / "chromium.br").unlink(missing_ok=True)
    _extract_tar_brotli(pack_dir / "fonts.tar.br", root / "fonts")
    _extract_tar_brotli(pack_dir / "al2023.tar.br", root / "al2023")
    # SwiftShader ships beside the binary. The loader looks for libGLESv2.so in /tmp.
    _extract_tar_brotli(pack_dir / "swiftshader.tar.br", root)


def _decompress_file(source: Path, target: Path, *, executable: bool) -> None:
    temporary = target.with_name(f"{target.name}.partial")
    temporary.write_bytes(brotli.decompress(source.read_bytes()))
    if executable:
        temporary.chmod(0o755)
    temporary.replace(target)


def _extract_tar_brotli(source: Path, dest: Path) -> None:
    payload = brotli.decompress(source.read_bytes())
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as tar:
        tar.extractall(dest, filter="data")
