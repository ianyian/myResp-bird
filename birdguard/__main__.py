"""Command line entry point.

  python -m birdguard run                 # normal operation
  python -m birdguard run --simulate      # no camera/AI needed (e.g. on a Mac)
  python -m birdguard sound-test          # play one random 10 s sound
  python -m birdguard check               # diagnose camera / AI HAT / speaker / ntfy
"""

from __future__ import annotations

import argparse
import logging
import platform
import signal
import sys
import threading
from pathlib import Path

from .config import load_config

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
log = logging.getLogger("birdguard")


def cmd_run(args) -> int:
    overrides: dict = {}
    if args.simulate:
        overrides.setdefault("detector", {})["backend"] = "simulated"
    if args.backend:
        overrides.setdefault("detector", {})["backend"] = args.backend
    cfg = load_config(args.config, overrides)

    from .app import BirdGuard
    from .deterrents import build_deterrents
    from .detectors import build_detector
    from .notify import NtfyNotifier

    detector = build_detector(cfg)
    deterrents = build_deterrents(cfg)
    notifier = NtfyNotifier(cfg.get("notify", {}).get("ntfy", {}))
    guard = BirdGuard(cfg, detector, deterrents, notifier)
    guard.ignore_schedule = args.ignore_schedule

    web = cfg.get("web", {})
    if web.get("enabled", True) and not args.no_web:
        from .web import create_app
        app = create_app(guard)
        port = int(args.port or web.get("port", 8080))
        threading.Thread(
            target=lambda: app.run(host=web.get("host", "0.0.0.0"), port=port, threaded=True),
            daemon=True,
        ).start()
        log.info("dashboard: http://%s:%d", "localhost" if platform.system() == "Darwin" else platform.node(), port)

    signal.signal(signal.SIGTERM, lambda *_: guard.stop())
    try:
        guard.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        log.info("shutting down")
        for d in deterrents:
            d.close()
        detector.close()
    return 0


def cmd_sound_test(args) -> int:
    cfg = load_config(args.config)
    from .sounds import SoundComposer, write_wav

    s = cfg["deterrents"]["sound"]
    lib = s.get("library_dir")
    composer = SoundComposer(
        duration=float(s.get("duration_seconds", 10)), sample_rate=int(s.get("sample_rate", 44100)),
        volume=float(s.get("volume", 0.9)), use_generated=bool(s.get("use_generated", True)),
        library_dir=cfg.path(lib) if lib else None,
    )
    for i in range(args.count):
        samples, kinds = composer.compose()
        print(f"sound {i + 1}: {', '.join(kinds)}")
        if args.save:
            out = Path(args.save)
            if args.count > 1:
                out = out.with_name(f"{out.stem}-{i + 1}{out.suffix}")
            write_wav(out, samples, composer.sr)
            print(f"  saved {out}")
        else:
            import tempfile
            import time
            from .audio import AudioPlayer
            player = AudioPlayer(s.get("alsa_device", "auto"))
            print(f"  playing via: {player.describe()}")
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                write_wav(Path(tmp.name), samples, composer.sr)
                player.play(Path(tmp.name))
                while player.is_playing():
                    time.sleep(0.2)
                player.stop()
    return 0


def cmd_check(args) -> int:
    cfg = load_config(args.config)
    ok = True

    def report(name: str, good: bool, detail: str) -> None:
        nonlocal ok
        ok &= good
        print(f"[{'OK ' if good else 'FAIL'}] {name}: {detail}")

    report("python", sys.version_info >= (3, 9), sys.version.split()[0])

    from .audio import AudioPlayer, list_alsa_devices
    devices = list_alsa_devices()
    for d in devices:
        print(f"       sound device: card {d['card']} '{d['name']}' ({d['id']})")
    player = AudioPlayer(cfg["deterrents"]["sound"].get("alsa_device", "auto"))
    good = bool(player.command) and (platform.system() == "Darwin" or player.device is not None)
    report("speaker", good, player.describe() + ("" if good else "  <- plug in a USB speaker"))

    if cfg["detector"]["backend"] == "hailo":
        try:
            from .detectors.hailo import find_model
            report("AI model", True, find_model(cfg["detector"].get("model", "auto")))
        except Exception as exc:
            report("AI model", False, str(exc))
        try:
            from picamera2 import Picamera2
            cams = Picamera2.global_camera_info()
            report("camera", bool(cams), ", ".join(c.get("Model", "?") for c in cams) or
                   "no camera found - check the ribbon cable")
        except Exception as exc:
            report("camera", False, f"picamera2 not available: {exc}")
        hailo_dev = Path("/dev/hailo0").exists()
        report("AI HAT", hailo_dev, "/dev/hailo0 present" if hailo_dev else
               "/dev/hailo0 missing - is the AI HAT fitted and hailo-all installed? (then reboot)")

    from .notify import NtfyNotifier
    n = NtfyNotifier(cfg.get("notify", {}).get("ntfy", {}))
    if n.enabled:
        n._send("BirdGuard test", "If you can read this, phone alerts work.", None)
        report("ntfy", True, f"test message sent to topic '{n.topic}' - check your phone")
    else:
        print("[ -- ] ntfy: disabled")

    print("\nAll good!" if ok else "\nSome checks failed - see above.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="birdguard", description="Detect birds and scare them away.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="path to config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="start BirdGuard (default)")
    run.add_argument("--simulate", action="store_true", help="fake camera, no hardware needed")
    run.add_argument("--backend", choices=["hailo", "simulated", "yolo-cpu"])
    run.add_argument("--ignore-schedule", action="store_true", help="ignore quiet hours (for testing)")
    run.add_argument("--no-web", action="store_true", help="don't start the dashboard")
    run.add_argument("--port", type=int)

    st = sub.add_parser("sound-test", help="play (or save) a random deterrent sound")
    st.add_argument("--save", help="write to this .wav file instead of playing")
    st.add_argument("--count", type=int, default=1)

    sub.add_parser("check", help="check camera, AI HAT, speaker and ntfy")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S",
    )
    if args.command is None:
        args = parser.parse_args((sys.argv[1:] if argv is None else argv) + ["run"])
    return {"run": cmd_run, "sound-test": cmd_sound_test, "check": cmd_check}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
