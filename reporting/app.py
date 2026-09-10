from flask import Flask, jsonify

from influx import get_health


app = Flask(__name__)


@app.route("/")
def index():
    return """
    <!doctype html>
    <html>
        <head>
            <title>Home Reporting</title>
            <meta
                name="viewport"
                content="width=device-width, initial-scale=1"
            >
        </head>

        <body>
            <h1>Home Reporting</h1>

            <p>
                Reporting service is running.
            </p>

            <p>
                <a href="/health">Health check</a>
            </p>
        </body>
    </html>
    """


@app.route("/health")
def health():
    try:
        influx = get_health()

        return jsonify(
            {
                "status": "ok",
                "influxdb": influx,
            }
        )

    except Exception as error:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": str(error),
                }
            ),
            503,
        )
