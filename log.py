import re
from datetime import datetime

def parse_clf_log(log_entry):
    clf_pattern = r'(?P<host>[\d\.]+) - - \[(?P<timestamp>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes_sent>\d+)'

    match = re.match(clf_pattern, log_entry)
    if match:
        data = match.groupdict()
        data['timestamp'] = datetime.strptime(data['timestamp'], '%d/%b/%Y:%H:%M:%S %z')
        return data
    else:
        return None

# テスト用のログエントリ
log_entry = '127.0.0.1 - - [11/Dec/2023:12:34:56 +0000] "GET /example/path HTTP/1.1" 200 1234'

parsed_data = parse_clf_log(log_entry)
if parsed_data:
    print(parsed_data)
else:
    print('Failed to parse log entry')



##事例２

import re
from datetime import datetime

def parse_clf_log(log_entry):
    clf_pattern = r'(?P<host>[\d\.]+) - - \[(?P<timestamp>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes_sent>\d+)'

    match = re.match(clf_pattern, log_entry)
    if match:
        data = match.groupdict()
        data['timestamp'] = datetime.strptime(data['timestamp'], '%d/%b/%Y:%H:%M:%S %z')
        return data
    else:
        return None

# テスト用のログエントリ
log_entry = '127.0.0.1 - - [11/Dec/2023:12:34:56 +0000] "GET /example/path HTTP/1.1" 200 1234'

parsed_data = parse_clf_log(log_entry)
if parsed_data:
    print(parsed_data)
else:
    print('Failed to parse log entry')
