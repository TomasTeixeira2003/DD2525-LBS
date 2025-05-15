import re
from collections import defaultdict
from datetime import datetime
import csv

log_file = "logcat_output.txt"
output_file = "user_avg_timings.csv"

log_pattern = re.compile(
    r'User:(\d+)\s+;\s+Type:(\w+)\s+;\s+Message:.*?\s+;\s+MessageID:(\d+)\s+;\s+Time:(\d{2}:\d{2}:\d{2}\.\d{3})'
)

# user -> msg_id -> {type: time}
log_data = defaultdict(lambda: defaultdict(dict))

def parse_time(timestr):
    return datetime.strptime(timestr, "%H:%M:%S.%f")

# Parse logs
with open(log_file, "r") as f:
    for line in f:
        match = log_pattern.search(line)
        if match:
            user, log_type, msg_id, time_str = match.groups()
            timestamp = parse_time(time_str)
            log_data[user][msg_id][log_type] = timestamp

# Compute averages and write to CSV
with open(output_file, "w", newline="") as csvf:
    writer = csv.writer(csvf)
    writer.writerow(["user", "avg_time_to_server_ms", "avg_time_to_receiver_ms"])

    for user in sorted(log_data.keys()):
        total_tts = 0
        total_ttr = 0
        count = 0

        for events in log_data[user].values():
            if "new_msg" in events and "server_ack" in events and "receiver_ack" in events:
                tts = (events["server_ack"] - events["new_msg"]).total_seconds() * 1000
                ttr = (events["receiver_ack"] - events["new_msg"]).total_seconds() * 1000
                total_tts += tts
                total_ttr += ttr
                count += 1

        if count > 0:
            avg_tts = round(total_tts / count, 2)
            avg_ttr = round(total_ttr / count, 2)
            writer.writerow([user, avg_tts, avg_ttr])

print(f"Averages saved to {output_file}")

