# 9. スケジュール通知
from datetime import datetime, timedelta
def schedule_reminder(events):
    now = datetime.now()
    upcoming_events = []
    for event in events:
        event_time = datetime.strptime(event['time'], '%Y-%m-%d %H:%M')
        if now < event_time < now + timedelta(days=7):
            upcoming_events.append(event)
    return upcoming_events
