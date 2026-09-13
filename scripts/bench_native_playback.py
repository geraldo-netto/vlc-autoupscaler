#!/usr/bin/env python3
"""Compare native upscaling with the existing encode/decode display bridge."""
import argparse
import json
import os
from pathlib import Path
import random
import re
import subprocess
import time

from bench_playback_policies import digest
from playback_runtime import prepare_runtime, verify_plugin_maps


def cpu_seconds(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().split(") ")[1].split()
    return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")


def send(player, command):
    player.stdin.write(command + "\n")
    player.stdin.flush()


def stop(player):
    if player.poll() is None:
        send(player, "quit")
    try:
        return player.wait(timeout=10)
    except subprocess.TimeoutExpired:
        player.kill()
        player.wait()
        raise


def resize(title):
    output = subprocess.check_output(["wmctrl", "-lGp"], text=True)
    windows = [line.split(maxsplit=8) for line in output.splitlines()]
    ids = [row[0] for row in windows if len(row) == 9 and row[8] == title]
    if len(ids) != 1:
        raise RuntimeError("expected exactly one owned playback window")
    subprocess.run(["wmctrl", "-ir", ids[0], "-e", "0,-1,-1,1280,720"], check=True)
    return ids[0]


def measure(player, title, plugin):
    started = time.monotonic()
    time.sleep(2)
    window = resize(title)
    maps = Path(f"/proc/{player.pid}/maps").read_text()
    verify_plugin_maps(maps, plugin)
    samples = []
    for second in range(3, 16):
        time.sleep(max(0, started + second - time.monotonic()))
        samples.append(dict(time=time.monotonic(), cpu=cpu_seconds(player.pid)))
        send(player, "stats")
    delta = samples[-1]["time"] - samples[0]["time"]
    return dict(samples=samples, window=window,
                cpu_percent=100 * (samples[-1]["cpu"] - samples[0]["cpu"]) / delta)


def command(args, clip, mode, title):
    cmd = ["vlc", "--ignore-config", "--no-one-instance", "--no-media-library", "--no-dbus",
           "-I", "rc", "--rc-fake-tty", "--no-video-title-show", "--stats", "--avcodec-hw=none",
           "--audio-filter=", "--audio-visual=none", "--no-audio-time-stretch",
           "--audio-replay-gain-mode=none", "--autoupscale-target=3", "--autoupscale-algo=3",
           "--autoupscale-usm=20", "--autoupscale-metrics=1", "--autoupscale-pin-threads=1",
           "--video-title=" + title, "-vv"]
    if mode == "native":
        cmd += ["--vout=autoupscale-vout"]
    else:
        cmd += ["--vout=gl", "--sout=#transcode{vcodec=h264,vb=10000,"
                "venc=x264{preset=ultrafast,tune=zerolatency},vfilter=autoupscale}:display"]
    return cmd + [str(args.clips / (clip + ".mkv"))]


def capture(args, env, clip, mode, repeat, index):
    title = "AutoUpscalePlayback" + str(os.getpid())
    cmd = command(args, clip, mode, title)
    log = args.output / (str(index) + ".log")
    load = os.getloadavg()
    with log.open("w") as stream:
        player = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=stream,
                                  stderr=stream, text=True)
        try:
            row = measure(player, title, args.build / "libautoupscale_plugin.so")
        finally:
            rc = stop(player)
    text = log.read_text()
    row.update(clip=clip, mode=mode, repeat=repeat, command=cmd, returncode=rc,
               load_before=load, load_after=os.getloadavg(),
               engaged=re.findall(r"AutoUpscale engaged:.*", text),
               native_geometry=re.findall(r"AutoUpscale native vout:.*", text),
               metrics=[line for line in text.splitlines() if "AutoUpscale metrics" in line],
               displayed=re.findall(r"frames displayed\s*:\s*(\d+)", text),
               lost=re.findall(r"frames lost\s*:\s*(\d+)", text))
    if rc or not row["engaged"]:
        raise RuntimeError("upscaler failed to engage")
    if mode == "native" and not row["native_geometry"]:
        raise RuntimeError("native video output failed to engage")
    return row


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    runtime = args.output / "runtime"
    prepare_runtime(runtime, args.build / "libautoupscale_plugin.so",
                    "/usr/lib/x86_64-linux-gnu/vlc/plugins", "/usr/lib/x86_64-linux-gnu/libvlccore.so.9",
                    args.build / "libautoupscale_vout_plugin.so")
    env = dict(os.environ, VLC_PLUGIN_PATH="", VLC_DATA_PATH="/usr/share/vlc",
               LD_LIBRARY_PATH=str(runtime.resolve()) + ":/usr/lib/x86_64-linux-gnu/vlc")
    paths = [args.build / "libautoupscale_plugin.so", args.build / "libautoupscale_vout_plugin.so",
             Path(__file__), Path("tests/experiment_vout.c")]
    paths += [args.clips / (clip + ".mkv") for clip in ("animation", "live-action-540")]
    hashes = {str(path): digest(path) for path in paths}
    (args.output / "manifest.json").write_text(json.dumps(hashes, indent=2) + "\n")
    rows = []
    randomizer = random.Random(20260914)
    for repeat in range(3):
        jobs = [(clip, mode) for clip in ("animation", "live-action-540") for mode in ("sout", "native")]
        randomizer.shuffle(jobs)
        for clip, mode in jobs:
            row = capture(args, env, clip, mode, repeat, len(rows))
            rows.append(row)
            (args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
            print(len(rows), clip, mode, row["cpu_percent"], flush=True)
    if hashes != {str(path): digest(path) for path in paths}:
        raise RuntimeError("inputs changed during playback measurements")
    (args.output / "verified.json").write_text('{"hashes_unchanged": true}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("clips", type=Path)
    parser.add_argument("output", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
