# SPDX-License-Identifier: GPL-3.0-or-later
# launch_studio_mcp.py - finds the newest StudioMCP.exe and launches it.
# NovaScript: added Linux support (Vinegar / Wine).
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

ENV_OVERRIDE = "VS_STUDIO_MCP_PATH"
ENV_WINE = "VS_WINE_PATH"
IS_LINUX = sys.platform.startswith("linux")
WINDOWS_STUDIO_EXECUTABLES = ("RobloxStudioBeta.exe", "RobloxStudio.exe")
MAC_STUDIO_EXECUTABLES = ("RobloxStudio", "RobloxStudioBeta", "Roblox")


def _vinegar_dirs() -> list[Path]:
    """Vinegar data folders (native install and Flatpak)."""
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return [
        Path(xdg) / "vinegar",
        Path.home() / ".var" / "app" / "org.vinegarhq.Vinegar" / "data" / "vinegar",
    ]


def _candidate_roots() -> list[Path]:
    """Directories that may contain Roblox Studio version folders."""
    roots: list[Path] = []
    if IS_LINUX:
        roots.extend(d / "versions" for d in _vinegar_dirs())
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        roots.append(Path(local_appdata) / "Roblox" / "Versions")
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(env)
        if value:
            roots.append(Path(value) / "Roblox" / "Versions")
    return roots


def _resolve_override_path(path_value: str) -> Optional[Path]:
    path = Path(path_value).expanduser()
    if path.is_file():
        return path
    if path.is_dir():
        if sys.platform == "darwin":
            candidate = path / "Contents" / "MacOS" / "StudioMCP"
        else:
            candidate = path / "StudioMCP.exe"
        if candidate.is_file():
            return candidate
    return None


def _newest_path(paths: Iterable[Path]) -> Optional[Path]:
    try:
        return max(paths, key=lambda p: p.stat().st_mtime)
    except (ValueError, OSError):
        return None


def _find_studio_mcp_windows() -> Optional[Path]:
    """Newest StudioMCP.exe that sits next to a real Studio executable.
    (Also used on Linux, where the roots point at Vinegar's versions folder.)"""
    paired: list[Path] = []
    orphans: list[Path] = []
    for root in _candidate_roots():
        if not root.is_dir():
            continue
        try:
            for version_dir in root.iterdir():
                if not version_dir.is_dir():
                    continue
                studio_mcp = version_dir / "StudioMCP.exe"
                if not studio_mcp.is_file():
                    continue
                if any((version_dir / n).is_file() for n in WINDOWS_STUDIO_EXECUTABLES):
                    paired.append(studio_mcp)
                else:
                    orphans.append(studio_mcp)
        except OSError:
            continue
    return _newest_path(paired) or _newest_path(orphans)


def _mac_app_candidates() -> list[Path]:
    home = Path.home()
    return [
        Path("/Applications/RobloxStudio.app"),
        home / "Applications" / "RobloxStudio.app",
        Path("/Applications/Roblox.app"),
        home / "Applications" / "Roblox.app",
        Path("/Applications/RobloxStudioBeta.app"),
        home / "Applications" / "RobloxStudioBeta.app",
    ]


def _find_studio_mcp_mac() -> Optional[Path]:
    for app in _mac_app_candidates():
        macos_dir = app / "Contents" / "MacOS"
        studio_mcp = macos_dir / "StudioMCP"
        if not studio_mcp.is_file():
            continue
        if any((macos_dir / n).is_file() for n in MAC_STUDIO_EXECUTABLES):
            return studio_mcp
    return None


def find_studio_mcp() -> Optional[Path]:
    override_value = os.environ.get(ENV_OVERRIDE)
    if override_value:
        override_path = _resolve_override_path(override_value)
        if override_path:
            return override_path
        sys.stderr.write(
            f"launch_studio_mcp: {ENV_OVERRIDE} is set but does not point to a valid StudioMCP binary: {override_value}\n"
        )
    if sys.platform == "darwin":
        return _find_studio_mcp_mac()
    return _find_studio_mcp_windows()


def _find_wine(vinegar_dir: Path) -> Optional[Path]:
    """Vinegar ships its own Wine/Proton build (folder 'kombucha*'). Prefer that."""
    override = os.environ.get(ENV_WINE)
    if override and Path(override).expanduser().is_file():
        return Path(override).expanduser()
    for sub in sorted(vinegar_dir.glob("kombucha*"), reverse=True):
        for rel in ("bin/wine64", "bin/wine", "files/bin/wine64", "files/bin/wine"):
            cand = sub / rel
            if cand.is_file():
                return cand
    found = shutil.which("wine64") or shutil.which("wine")
    return Path(found) if found else None


def _build_command(exe: Path) -> tuple[list[str], dict]:
    """Return (command, env). On Linux the .exe must run through Vinegar's Wine
    inside Vinegar's Studio prefix so it can see the running Studio."""
    args = sys.argv[1:]
    env = dict(os.environ)
    if IS_LINUX and exe.suffix.lower() == ".exe":
        vinegar_dir = exe.parents[2]          # <vinegar>/versions/<version>/StudioMCP.exe
        wine = _find_wine(vinegar_dir)
        if not wine:
            raise RuntimeError(
                "no Wine found. Looked for Vinegar's build in "
                f"{vinegar_dir}/kombucha*. Set {ENV_WINE} to your wine binary."
            )
        env["WINEPREFIX"] = os.environ.get("WINEPREFIX") or str(vinegar_dir / "prefixes" / "studio")
        env.setdefault("WINEDEBUG", "-all")
        sys.stderr.write(f"launch_studio_mcp: wine={wine} prefix={env['WINEPREFIX']}\n")
        return [str(wine), str(exe)] + args, env
    return [str(exe)] + args, env


def main() -> int:
    exe = find_studio_mcp()
    binary_name = "StudioMCP" if sys.platform == "darwin" else "StudioMCP.exe"
    if not exe:
        sys.stderr.write(
            f"launch_studio_mcp: no {binary_name} found. Open Roblox Studio and "
            "enable 'Studio as MCP server' (Assistant Settings > MCP Servers).\n"
        )
        return 1
    sys.stderr.write(f"launch_studio_mcp: using {exe}\n")
    sys.stderr.flush()
    try:
        cmd, env = _build_command(exe)
    except RuntimeError as err:
        sys.stderr.write(f"launch_studio_mcp: {err}\n")
        return 1
    proc = subprocess.Popen(cmd, env=env)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
