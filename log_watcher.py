import re

def check_log(log):
    if "Player connected: " in log:
        player = get_player_name(log, "connected")
        return f"[INFO] player online: {player}"
    elif "Player disconnected: " in log:
        player = get_player_name(log, "disconnected")
        return f"[INFO] player offline: {player}"
    else :
        return None

def get_player_name(log,type):
    if type == "connected":
        match = re.search(r"Player connected:\s*(.*?),", log)
        if match:
            return match.group(1)
        return None
    elif type == "disconnected":
        match = re.search(r"Player disconnected:\s*(.*?),", log)
        if match:
            return match.group(1)
        return None
    else:
        return None

def get_version(log):
    match = re.search(r"Version:\s*(.*)", log)
    if match:
        return match.group(1)
    return None