import os
from psa_web import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.getenv("PSA_DEBUG", "").lower() in ("1", "true", "yes", "on")
    app.run(debug=debug, host='0.0.0.0', port=5000)
