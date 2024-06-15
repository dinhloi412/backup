import requests
import os
from datetime import datetime


def convert_time(from_year: str, to_year: str):
    try:
        from_year = int(from_year)
        to_year = int(to_year)
        from_start_date = datetime(from_year, 1, 1).strftime('%Y-%m-%d')
        from_end_date = datetime(to_year, 12, 31).strftime('%Y-%m-%d')
        return from_start_date, from_end_date
    except Exception as e:
        return e


def get_year(timestamp: str):
    res = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
    return res.year


def convert_bytes_to_gb(bytes: int):
    gb = bytes / (1024 ** 3)
    return gb


def delete_file(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except FileNotFoundError:
        print(f"File '{file_path}' not found.")


def get_host_name(url: str):
    url_without_protocol = url.split("//")[-1]
    hostname_with_port = url_without_protocol.split("/")[0]
    hostname = hostname_with_port.split(":")[0]
    return hostname


def convert_time_measure(t: datetime):
    hours, remainder = divmod(t.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    time_elapsed_formatted = '{:02d}:{:02d}:{:02d}'.format(int(hours), int(minutes), int(seconds))
    return time_elapsed_formatted
