def format_time(t, short=True):
    seconds = t % 60
    minutes = (t // 60) % 60
    hours = (t // 3600)

    segments = []
    if hours or not short:
        segments.append("{} hour{}".format(hours, '' if hours == 1 else 's'))
    segments.append("{} minute{}".format(minutes, '' if minutes == 1 else 's'))
    segments.append("{} second{}".format(seconds, '' if seconds == 1 else 's'))

    return ", ".join(segments)
