import subprocess
import threading
import time
import os
import schedule
import shutil
from datetime import datetime
import log_watcher
import discord_sender
import update

SERVER_PATH = r"C:\Users\user\server"
BACKUP_PATH = r"C:\Users\user\server\backup"
LOG_PATH = r"C:\Users\user\server\logs\server.log"
ERROR_LOG_PATH = r"C:\Users\user\server\logs\error.log"
WORLD_NAME = "Bedrock level"
BACKUP_TIMES = ["00:00","06:00","12:00","18:00"]
RESTART_TIME = "03:00"
MAX_BACKUPS = 12

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

def restart_server(verify=False, notify=True):
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
    threading.Thread(target=logging, args=(process,), kwargs={'notify_init_msg': False}, daemon=True).start()
    print("server restarted")

def update_server(version=None):
    global process,players
    if version:
        if version == update.get_version():
            print("already up to date.")
            return
        print(f"current version is {update.get_version()}. updating to {version}...")
        os.makedirs(os.path.join(SERVER_PATH,"temp"), exist_ok=True)
        res = update.download(version, os.path.join(SERVER_PATH,"temp","server.zip"))
        if not res:
            print("download failed.")
            return
        send_cmd("stop")
        discord_sender.send(f"[INFO] server is updating to version {version}...")
        process.wait()
        time.sleep(5)
        backup_world(status="stop")
        # 解凍して必要なファイルを置き換える
        res = False
        try:
            res = update.update_server(SERVER_PATH, os.path.join(SERVER_PATH,"temp"))
            if not res:
                raise Exception("update failed during file replacement.")
        except Exception as e:
            print(f"update failed: {e}")
            discord_sender.send(f"[ERROR] server update failed")
            return
        #処理終了
        process = start_server()
        players = 0
        threading.Thread(target=catch_error,args=(process,), daemon=True).start()
        threading.Thread(target=logging,args=(process,), daemon=True).start()
        time.sleep(5)
        if update.get_version() == version:
            discord_sender.send(f"[INFO] server updated successfully to version {version}.")
            print(f"update complete. current version is {version}.")
    else:
        print("version info is not provided.")

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
        elif cmd == "version":
            print(f"current version: {update.get_version()}")
        elif cmd.startswith("update "):
            threading.Thread(target=update_server,args=(cmd[7:],), daemon=True).start()
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

def logging(proc, notify_init_msg=True):
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

        if "Version: " in line:
            version = log_watcher.get_version(line)
            if version:
                update.set_version(version)
                if notify_init_msg:
                    discord_sender.send(f"[INFO] server started. version: {version}")

        if "Player connected:" in line:
            players += 1
            print(f"[INFO] players online: {players}")


        elif "Player disconnected:" in line:
            players = max(0, players - 1)
            print(f"[INFO] players online: {players}")

        info = log_watcher.check_log(line)
        if info:
            discord_sender.send(info)
            
def manage_schedule():
    schedule.every().day.at(RESTART_TIME).do(restart_server,verify=True,notify=False)
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