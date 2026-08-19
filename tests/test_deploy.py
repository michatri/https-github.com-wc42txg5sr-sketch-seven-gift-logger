from datetime import timedelta
from pathlib import Path

from chatriacc.app import create_app
from chatriacc.dates import BANGKOK, today


def test_install_scripts_target_chatriacc_and_65():
    root = Path(__file__).resolve().parents[1]
    install = (root / "scripts" / "install_on_server.sh").read_text()
    unit = (root / "chatriacc" / "deploy" / "chatriacc.service").read_text()
    runner = (root / "scripts" / "chatriacc-run.sh").read_text()
    ports = (root / "scripts" / "open_lan_ports.sh").read_text()
    assert "192.168.10.56" in install
    assert "hostname -I" in install
    assert "chatriacc" in install
    assert "chatriacc-run.sh" in unit
    assert "/home/aaa/chatriacc" in install
    assert "/root/chatriacc" in install
    assert "Permission denied" in install
    assert "ย้ายไป" in install
    assert "chatriacc.wsgi:app" in runner
    assert "chatriacc.importer" in runner
    assert "8100" in unit
    assert "CHATRIACC_PORT=8100" in unit
    assert "CHATRIACC_PORT:-8100" in runner
    assert "CHATRIACC_BIND_80=0" in install
    assert "chatriacc.importer" in install
    assert "AC25-209.xlsb" in install
    assert "8090" in runner
    assert "8100" in ports
    assert "192.168.10.0/24" in ports
    assert "firewall-cmd" in ports


def test_app_name_constant():
    app = create_app("/tmp/chatriacc-name-test.db")
    assert app.name == "chatriacc"


def test_bangkok_is_fixed_utc_plus_7():
    assert BANGKOK.utcoffset(None) == timedelta(hours=7)
    assert today() is not None
