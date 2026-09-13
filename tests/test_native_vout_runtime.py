#!/usr/bin/env python3
"""REL-16: opt-in real VLC window, subtitle, seek and native-volume regression."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from playback_runtime import prepare_runtime, verify_plugin_maps


def execute(command):
    return subprocess.check_output(command, text=True)


def window_state(title):
    rows = [line.split(maxsplit=8) for line in execute(["wmctrl", "-lGp"]).splitlines()]
    ids = [row[0] for row in rows if len(row) == 9 and row[8] == title]
    return {wid: dict(geometry=execute(["xwininfo", "-id", wid]),
                      state=execute(["xprop", "-id", wid, "_NET_WM_STATE"])) for wid in ids}


def send(player, command, delay=.4):
    player.stdin.write(command + "\n")
    player.stdin.flush()
    time.sleep(delay)


def volume_probe(player):
    rows = []
    for value in (256, 64, 128):
        send(player, "volume " + str(value))
        streams = json.loads(execute(["pactl", "--format=json", "list", "sink-inputs"]))
        owned = [s for s in streams
                 if s.get("properties", {}).get("application.process.id") == str(player.pid)]
        percentages = [[channel["value_percent"] for channel in s["volume"].values()] for s in owned]
        rows.append(dict(requested=value, percentages=percentages))
    return rows


def controls(player, title, output):
    row = dict(before=window_state(title), volume=volume_probe(player))
    if not row["before"]:
        raise RuntimeError("VLC window not found")
    wid = next(iter(row["before"]))
    subprocess.run(["wmctrl", "-ir", wid, "-e", "0,-1,-1,1280,720"], check=True)
    time.sleep(.6)
    row["resized"] = window_state(title)
    shot = output / "subtitle.png"
    subprocess.run(["import", "-window", next(iter(row["before"])), str(shot)], check=True)
    row["subtitle"] = execute(["tesseract", str(shot), "stdout"])
    send(player, "fullscreen", 2)
    row["fullscreen"] = window_state(title)
    send(player, "fullscreen", 2)
    row["restored"] = window_state(title)
    send(player, "seek 10", .8)
    send(player, "get_time")
    send(player, "seek 1", .8)
    send(player, "get_time")
    send(player, "stats")
    return row


def window_sizes(states):
    sizes = []
    for state in states.values():
        fields = dict(re.findall(r"^\s*(Width|Height):\s*(\d+)", state["geometry"], re.M))
        sizes.append((int(fields["Width"]), int(fields["Height"])))
    return sorted(sizes)


def validate_windows(row):
    assert row["fullscreen"], "fullscreen window vanished"
    assert all("_NET_WM_STATE_FULLSCREEN" in w["state"] for w in row["fullscreen"].values())
    assert row["restored"], "window did not restore"
    assert all("_NET_WM_STATE_FULLSCREEN" not in w["state"] for w in row["restored"].values())
    assert window_sizes(row["resized"]) == [(1280, 720)], "resize did not take effect"
    assert window_sizes(row["restored"]) == window_sizes(row["resized"]), "restored size differs"
    assert not row["after_exit"], "owned window leaked"


def validate(row):
    assert row["returncode"] == 0, "VLC exit failed"
    assert row["native_geometry"], "native upscaling module did not engage"
    validate_windows(row)
    assert "AUTOUPSCALE" in row["subtitle"].upper(), "subtitle not visible"
    assert row["time_responses"][-2:] == ["10", "1"], "seek commands did not take effect"
    assert row["displayed"] and int(row["displayed"][-1]) > 0, "presentation not observed"
    for result, expected in zip(row["volume"], ("100%", "25%", "50%")):
        assert result["percentages"], "native audio stream absent"
        assert all(value == expected for channels in result["percentages"] for value in channels)


def playback(args, env, title):
    subtitle = args.output / "subtitle.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:01:00,000\nAUTOUPSCALE SUBTITLE TEST\n")
    command = ["vlc", "--ignore-config", "--no-one-instance", "--no-media-library",
               "--no-dbus", "-I", "rc", "--rc-fake-tty", "--stats", "--no-video-title-show",
               "--video-title=" + title, "--avcodec-hw=none", "--vout=autoupscale-vout",
               "--aout=pulse", "--audio-filter=", "--audio-visual=none", "--no-audio-time-stretch",
               "--audio-replay-gain-mode=none", "--gain=1", "--autoupscale-target=2",
               "--autoupscale-metrics=1", "--width=1280", "--height=720",
               "--freetype-background-opacity=255", "--freetype-background-color=0",
               "--sub-file=" + str(subtitle), "-vv", str(args.clip)]
    log = args.output / "vlc.log"
    with log.open("w") as stream:
        player = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=stream,
                                  stderr=stream, text=True)
        try:
            time.sleep(3)
            maps = Path(f"/proc/{player.pid}/maps").read_text()
            verify_plugin_maps(maps, args.build / "libautoupscale_plugin.so")
            row = controls(player, title, args.output)
            row["maps"] = maps
        finally:
            if player.poll() is None:
                send(player, "quit", 0)
            player.wait(timeout=10)
    row.update(command=command, returncode=player.returncode, after_exit=window_state(title))
    text = log.read_text()
    row["native_geometry"] = re.findall(r"AutoUpscale native vout:.*", text)
    row["time_responses"] = re.findall(r"^\s*(\d+)\s*$", text, re.M)
    row["displayed"] = re.findall(r"frames displayed\s*:\s*(\d+)", text)
    row["lost"] = re.findall(r"frames lost\s*:\s*(\d+)", text)
    return row


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    runtime = args.output / "runtime"
    prepare_runtime(runtime, args.build / "libautoupscale_plugin.so",
                    "/usr/lib/x86_64-linux-gnu/vlc/plugins", "/usr/lib/x86_64-linux-gnu/libvlccore.so.9",
                    args.build / "libautoupscale_vout_plugin.so")
    title = "AutoUpscaleNativeTest" + str(os.getpid())
    sink = "autoupscale_native_" + str(os.getpid())
    module = execute(["pactl", "load-module", "module-null-sink", "sink_name=" + sink]).strip()
    env = dict(os.environ, VLC_PLUGIN_PATH="", VLC_DATA_PATH="/usr/share/vlc", PULSE_SINK=sink,
               LD_LIBRARY_PATH=str(runtime.resolve()) + ":/usr/lib/x86_64-linux-gnu/vlc")
    try:
        row = playback(args, env, title)
        (args.output / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        validate(row)
    finally:
        subprocess.run(["pactl", "unload-module", module], check=True)
    print("REL-16 native playback controls PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("clip", type=Path)
    parser.add_argument("output", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
