#!/usr/bin/env python3
"""Build an isolated, unmodified Linux VLC runtime for playback measurements."""
from pathlib import Path
import shutil


def prepare_runtime(destination, plugin, system_plugins, core, extra_plugin=None):
    """Use one requested AutoUpscale binary and stock modules without duplicates."""
    destination = Path(destination)
    destination.mkdir()
    modules = destination / "vlc/plugins"
    modules.mkdir(parents=True)
    shutil.copy2(core, destination / "libvlccore.so.9")
    lua = Path(system_plugins).parent / "lua"
    if lua.is_dir():
        (destination / "vlc/lua").symlink_to(lua.resolve())
    for source in Path(system_plugins).rglob("*_plugin.so"):
        if source.name.startswith("libautoupscale"):
            continue
        target = modules / source.relative_to(system_plugins)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source.resolve())
    (modules / Path(plugin).name).symlink_to(Path(plugin).resolve())
    if extra_plugin is not None:
        (modules / Path(extra_plugin).name).symlink_to(Path(extra_plugin).resolve())


def verify_plugin_maps(maps, expected):
    """Reject absent, deleted or ambiguous plugin mappings before accepting data."""
    paths = set()
    for line in maps.splitlines():
        if "libautoupscale_plugin.so" not in line:
            continue
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or fields[5].endswith(" (deleted)"):
            raise ValueError("unidentifiable AutoUpscale mapping")
        paths.add(Path(fields[5]).resolve())
    expected = Path(expected).resolve()
    if paths != {expected}:
        raise ValueError(f"ambiguous AutoUpscale selection: {sorted(map(str, paths))}")
    return expected
