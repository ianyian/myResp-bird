"""The command lines used by the service, the installer and the docs."""

from birdguard.__main__ import DEFAULT_CONFIG, parse_args


def test_service_command_line():
    # exactly what birdguard.service.template runs
    a = parse_args(["run", "--config", "/home/admin/myresp-bird/config.yaml"])
    assert a.command == "run" and a.config == "/home/admin/myresp-bird/config.yaml"


def test_config_before_command():
    a = parse_args(["--config", "x.yaml", "check"])
    assert a.command == "check" and a.config == "x.yaml"


def test_defaults():
    a = parse_args([])
    assert a.command == "run" and a.config == str(DEFAULT_CONFIG) and a.verbose is False
    a = parse_args(["run", "--simulate", "--ignore-schedule", "-v"])
    assert a.simulate and a.ignore_schedule and a.verbose


def test_service_template_matches_cli():
    from pathlib import Path
    line = next(l for l in (Path(__file__).parent.parent / "birdguard.service.template").read_text().splitlines()
                if l.startswith("ExecStart="))
    argv = line.split("-m birdguard", 1)[1].replace("__DIR__", "/opt/bg").split()
    a = parse_args(argv)
    assert a.command == "run" and a.config == "/opt/bg/config.yaml"
