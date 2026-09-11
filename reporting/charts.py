from io import BytesIO

import matplotlib.pyplot as plt


def render_chart(data, *, chart_type, title):
    if data.empty:
        raise ValueError("No data available for this query.")

    figure, axis = plt.subplots()

    if chart_type == "line":
        axis.plot(
            data["_time"],
            data["_value"],
        )

    elif chart_type == "bar":
        axis.bar(
            data["_time"],
            data["_value"],
        )

    else:
        plt.close(figure)
        raise ValueError(
            f"Unsupported chart type: {chart_type}"
        )

    axis.set_title(title)
    axis.set_xlabel("Time")
    axis.set_ylabel("Value")

    figure.autofmt_xdate()
    figure.tight_layout()

    image = BytesIO()

    figure.savefig(
        image,
        format="png",
        dpi=150,
    )

    plt.close(figure)

    image.seek(0)

    return image
