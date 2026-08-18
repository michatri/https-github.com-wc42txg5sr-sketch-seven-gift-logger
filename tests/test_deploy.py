from pathlib import Path


def test_server_unit_listens_on_8090():
    unit = Path("accounting/deploy/accounting.service").read_text(encoding="utf-8")
    assert "0.0.0.0:8090" in unit
    assert "accounting.wsgi:app" in unit
    assert "8080" not in unit
    assert "8888" not in unit


def test_install_script_targets_cameraserver():
    script = Path("scripts/install_on_server.sh").read_text(encoding="utf-8")
    assert "192.168.10.56" in script
    assert "8090" in script
    assert "ufw allow" in script
