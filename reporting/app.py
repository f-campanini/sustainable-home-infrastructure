import traceback

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
)

from audit import (
    QueryTimer,
    new_request_id,
    write_query_audit,
)
from charts import render_chart
from influx import get_health
from query_service import (
    ALLOWED_MEASUREMENTS,
    NoDataError,
    NonNumericDataError,
    QueryValidationError,
    list_entities,
    run_historical_query,
    validate_query,
)


app = Flask(__name__)


@app.route("/")
def index():
    return render_template(
        "index.html",
        measurements=ALLOWED_MEASUREMENTS,
    )


@app.route("/health")
def health():
    return jsonify(get_health())


@app.route("/api/entities")
def entities():
    measurement = request.args.get(
        "measurement",
        "W",
    )

    try:
        values = list_entities(measurement)

        return jsonify({
            "ok": True,
            "entities": values,
        })

    except Exception:
        return jsonify({
            "ok": False,
            "message": (
                "Unable to load the available sensors."
            ),
            "details": traceback.format_exc(),
        })


@app.route("/chart")
def chart():
    request_id = new_request_id()

    parameters = {
        "measurement": request.args.get(
            "measurement",
            "",
        ),
        "entity_id": request.args.get(
            "entity_id",
            "",
        ),
        "range_name": request.args.get(
            "range",
            "",
        ),
        "aggregation": request.args.get(
            "aggregation",
            "",
        ),
        "function": request.args.get(
            "function",
            "",
        ),
        "chart_type": request.args.get(
            "chart_type",
            "",
        ),
    }

    try:
        query = validate_query(**parameters)

        with QueryTimer() as timer:
            data = run_historical_query(query)

            image = render_chart(
                data,
                chart_type=query.chart_type,
                title=(
                    f"{query.entity_id} "
                    f"({query.range_name})"
                ),
            )

        write_query_audit(
            request_id=request_id,
            status="success",
            result_points=len(data),
            execution_ms=timer.execution_ms,
            **parameters,
        )

        response = send_file(
            image,
            mimetype="image/png",
        )

        response.headers[
            "X-Query-ID"
        ] = request_id

        return response

    except QueryValidationError as error:
        details = traceback.format_exc()

        write_query_audit(
            request_id=request_id,
            status="validation_error",
            error_message=str(error),
            **parameters,
        )

        return jsonify({
            "ok": False,
            "message": str(error),
            "details": details,
            "query_id": request_id,
        })

    except (NoDataError, NonNumericDataError) as error:
        details = traceback.format_exc()

        write_query_audit(
            request_id=request_id,
            status="no_data",
            error_message=str(error),
            **parameters,
        )

        return jsonify({
            "ok": False,
            "message": str(error),
            "details": details,
            "query_id": request_id,
        })

    except Exception as error:
        details = traceback.format_exc()

        write_query_audit(
            request_id=request_id,
            status="error",
            error_message=str(error),
            **parameters,
        )

        return jsonify({
            "ok": False,
            "message": (
                "Historical data could not be processed."
            ),
            "details": details,
            "query_id": request_id,
        })
