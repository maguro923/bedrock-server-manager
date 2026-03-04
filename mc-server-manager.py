import subprocess
import threading
import time
import os
import schedule
import shutil
from datetime import datetime

SERVER_PATH = r"C:\Users\user\server"
BACKUP_PATH = r"C:\Users\user\server\backup"
LOG_PATH = r"C:\Users\user\server\logs\server.log"
ERROR_LOG_PATH = r"C:\Users\user\server\logs\error.log"
WORLD_NAME = "Bedrock level"
BACKUP_TIMES = ["00:00","06:00","12:00","18:00"]
RESTART_TIME = "03:00"
MAX_BACKUPS = 5

players = 0

def start_server():
    exe_path = os.path.join(SERVER_PATH,"bedrock_server.exe")
    return subprocess.Popen(
        [exe_path],
        cwd=SERVER_PATH,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

def send_cmd(cmd):
    global process
    if process and process.poll() is None:
        try:
            process.stdin.write(cmd + "\n")
            process.stdin.flush()
        except:
            print("Error!: failed to send command")

def broadcast(message):
    send_cmd(f"say {message}")

def backup_world(status="running"):
    print("start to create backup")
    if status == "running":
        send_cmd("save hold")
        time.sleep(5)

    world_path = os.path.join(SERVER_PATH,"worlds",WORLD_NAME)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_PATH, f"world_{timestamp}")

    shutil.copytree(world_path,dest)
    rotate_backups()
    
    if status == "running":
        send_cmd("save resume")
    print("backup complete")

def rotate_backups():
    backups = sorted(os.listdir(BACKUP_PATH))
    while len(backups) > MAX_BACKUPS:
        shutil.rmtree(os.path.join(BACKUP_PATH, backups[0]))
        backups.pop(0)

def restart_server(verify=False):
    global players,process
    if verify==True and players != 0:
        print("players remein at server. restart was passed")
        backup_world()
        return
    send_cmd("stop")
    process.wait()
    time.sleep(5)
    backup_world(status="stop")
    process = start_server()
    players = 0
    threading.Thread(target=catch_error,args=(process,), daemon=True).start()
    threading.Thread(target=logging,args=(process,), daemon=True).start()
    print("server restarted")

def console():
    while True:
        cmd = input()

        if cmd=="exit":
            send_cmd("stop")
            break
        elif cmd == "restart":
            restart_server()
        elif cmd == "backup":
            backup_world()
        elif cmd.startswith("say "):
            broadcast(cmd[4:])
        else:
            send_cmd(cmd)

def catch_error(proc):
    while True:
        line = proc.stderr.readline()
        if not line:
            break
        print("\033[31m"+"Erorr! "+line.rstrip()+"\033[0m")
        with open(ERROR_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line + "\n")

def logging(proc):
    global players
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.rstrip()
        if not ("Running AutoCompaction..." in line):
            print(line)
            with open(LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(line + "\n")

        if "Player connected:" in line:
            players += 1
            print(f"[INFO] players online: {players}")


        elif "Player disconnected:" in line:
            players = max(0, players - 1)
            print(f"[INFO] players online: {players}")

def manage_schedule():
    schedule.every().day.at(RESTART_TIME).do(restart_server,verify=True)
    for i in BACKUP_TIMES:
        schedule.every().day.at(i).do(backup_world)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print("Scheduler error:",e)
        time.sleep(1)

def init_logs():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        f.write(f"logging started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    with open(ERROR_LOG_PATH, 'w', encoding='utf-8') as f:
        f.write(f"error logging started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

"""def test():
    print("thread start successfully")
    time.sleep(50)
    print("thread work successfully")"""

if __name__ == "__main__":
    init_logs()
    os.makedirs(BACKUP_PATH, exist_ok=True)
    process = start_server()
    threading.Thread(target=manage_schedule,daemon=True).start()
    threading.Thread(target=catch_error,args=(process,), daemon=True).start()
    threading.Thread(target=logging,args=(process,), daemon=True).start()
    #threading.Thread(target=test, daemon=True).start()
    console()