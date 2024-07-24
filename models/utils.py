import os
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

def get_year(timestamp: str):
    res = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
    return res.year


def convert_bytes_to_gb(bytes: float):
    gb = bytes / (1024**3)
    return gb


def delete_file(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except FileNotFoundError:
        _logger.error(f"cannot delete file '{file_path}")


def read_file(file_path: str):
    try:
        file_content = None
        if os.path.exists(file_path):
            with open(file_path, "rb") as file:
                file_content = file.read()
        return file_content
    except Exception as e:
        _logger.error(f"cannot read file '{file_path}: ", {e})


def get_host_name(url: str):
    url_without_protocol = url.split("//")[-1]
    hostname_with_port = url_without_protocol.split("/")[0]
    hostname = hostname_with_port.split(":")[0]
    return hostname


def convert_time_measure(t: datetime):
    hours, remainder = divmod(t.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    time_elapsed_formatted = "{:02d}:{:02d}:{:02d}".format(
        int(hours), int(minutes), int(seconds)
    )
    return time_elapsed_formatted


def convert_query_db(data: list):
    res = ", ".join(["'%s'" % name for name in data])
    return res
