import os

from accounting.app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("ACCOUNTING_HOST", "0.0.0.0")
    port = int(os.environ.get("ACCOUNTING_PORT", "8090"))
    debug = os.environ.get("ACCOUNTING_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
