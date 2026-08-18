from pathlib import Path

from chatriacc.app import create_app


def test_install_scripts_target_chatriacc_and_65():
    root = Path(__file__).resolve().parents[1]
    install = (root / "scripts" / "install_on_server.sh").read_text()
    unit = (root / "chatriacc" / "deploy" / "chatriacc.service").read_text()
    assert "192.168.10.65" in install
    assert "chatriacc" in install
    assert "chatriacc.wsgi:app" in unit
    assert "8090" in unit


def test_app_name_constant():
    app = create_app("/tmp/chatriacc-name-test.db")
    assert app.name == "chatriacc"
