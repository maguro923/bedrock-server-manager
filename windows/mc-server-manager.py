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
from setting import load_settings

settings = load_settings()

players = 0

def start_server():
    exe_path = os.path.join(settings.server_path,"bedrock_server.exe")
    return subprocess.Popen(
        [exe_path],
        cwd=settings.server_path,
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

    world_path = os.path.join(settings.server_path,"worlds",settings.world_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(settings.backup_path, f"world_{timestamp}")

    shutil.copytree(world_path,dest)
    rotate_backups()
    
    if status == "running":
        send_cmd("save resume")
    print("backup complete")

def rotate_backups():
    # 世代管理の対象は、backup_world が作る world_<日時> フォルダだけにする。
    backups = sorted(
        entry.name
        for entry in os.scandir(settings.backup_path)
        if entry.is_dir() and entry.name.startswith("world_")
    )
    while len(backups) > settings.max_backups:
        shutil.rmtree(os.path.join(settings.backup_path, backups[0]))
        backups.pop(0)

def wait_for_stop(timeout=60):
    # stop送信後の終了待ち。時間内に終わらなければ強制終了する
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"server did not stop within {timeout} seconds. killing process...")
        process.kill()
        process.wait()

def restart_server(verify=False, notify=True):
    global players,process
    if verify==True and players != 0:
        print("players remain at server. restart was passed")
        backup_world()
        return
    send_cmd("stop")
    wait_for_stop()
    time.sleep(5)
    backup_world(status="stop")
    process = start_server()
    players = 0
    threading.Thread(target=catch_error,args=(process,), daemon=True).start()
    threading.Thread(target=logging, args=(process,), kwargs={'notify_init_msg': False}, daemon=True).start()
    print("server restarted")

def update_server(version=None):
    global process,players
    if version == "latest":
        version = update.get_latest_version()
        if version is None:
            return
    if version and not update.is_valid_version(version):
        print(f"invalid version format: {version}")
        return
    if version:
        if version == update.get_version():
            print("already up to date.")
            return
        print(f"current version is {update.get_version()}. updating to {version}...")
        os.makedirs(os.path.join(settings.server_path,"temp"), exist_ok=True)
        res = update.download(version, os.path.join(settings.server_path,"temp","server.zip"))
        if not res:
            print("download failed.")
            return
        send_cmd("stop")
        discord_sender.send(f"[INFO] server is updating to version {version}...")
        wait_for_stop()
        time.sleep(5)
        backup_world(status="stop")
        # 解凍して必要なファイルを置き換える
        res = False
        try:
            res = update.update_server(settings.server_path, os.path.join(settings.server_path,"temp"))
            if not res:
                raise Exception("update failed during file replacement.")
        except Exception as e:
            print(f"update failed: {e}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copytree(os.path.join(settings.server_path,"temp_backup"), os.path.join(settings.emergency_backup_path,"backup_"+timestamp), dirs_exist_ok=True)  
            discord_sender.send(f"[ERROR] server update failed: {e}")
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
        elif cmd == "update":
            threading.Thread(target=update_server, args=("latest",), daemon=True).start()
        elif cmd.startswith("update "):
            threading.Thread(target=update_server,args=(cmd[7:],), daemon=True).start()
        else:
            send_cmd(cmd)

def catch_error(proc):
    while True:
        line = proc.stderr.readline()
        if not line:
            break
        print("\033[31m"+"Error! "+line.rstrip()+"\033[0m")
        with open(settings.error_log_path, 'a', encoding='utf-8') as f:
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
            with open(settings.log_path, 'a', encoding='utf-8') as f:
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
    schedule.every().day.at(settings.restart_time).do(restart_server,verify=True,notify=False)
    schedule.every().day.at(settings.update_check_time).do(update_server, version="latest")
    for i in settings.backup_times:
        schedule.every().day.at(i).do(backup_world)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print("Scheduler error:",e)
        time.sleep(1)

def init_logs():
    os.makedirs(os.path.dirname(settings.log_path), exist_ok=True)
    with open(settings.log_path, 'w', encoding='utf-8') as f:
        f.write(f"logging started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    with open(settings.error_log_path, 'w', encoding='utf-8') as f:
        f.write(f"error logging started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    init_logs()
    os.makedirs(settings.backup_path, exist_ok=True)
    process = start_server()
    threading.Thread(target=manage_schedule,daemon=True).start()
    threading.Thread(target=catch_error,args=(process,), daemon=True).start()
    threading.Thread(target=logging,args=(process,), daemon=True).start()
    console()