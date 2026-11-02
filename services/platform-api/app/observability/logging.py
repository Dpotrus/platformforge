import json
import logging
import sys
from datetime import datetime, timezone
from opentelemetry import trace


class JsonFormatter(logging.Formatter):

    def __init__(self, service_name: str = "platformforge-api"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service_name,
            "message": record.getMessage(),
        }

        span_context = trace.get_current_span().get_span_context()

        if span_context.is_valid:
            log_data["trace_id"] = format(
                span_context.trace_id,
                "032x",
            )
            log_data["span_id"] = format(
                span_context.span_id,
                "016x",
            )

        if record.exc_info:
            log_data["exception"] = self.formatException(
                record.exc_info,
            )

        return json.dumps(log_data)

def configure_logging(
        level: str = "INFO",
        log_format: str = "json",
        service_name: str = "platformforge-api",
) -> None:
    root_logger = logging.getLogger()

    root_logger.setLevel(level.upper())

    for existing_handler in root_logger.handlers[:]:
        if getattr(existing_handler, "_platformforge_handler", False):
            root_logger.removeHandler(existing_handler)
            existing_handler.close()

    handler = logging.StreamHandler(sys.stdout)
    handler._platformforge_handler = True

    if log_format.lower() == "json":
        handler.setFormatter(
            JsonFormatter(service_name=service_name)
        )
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
        )

    root_logger.addHandler(handler)