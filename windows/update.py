import os
import re
from wsgiref import headers
import requests
import zipfile
import shutil
import stat

# DOWNLOAD_PAGE = "https://www.minecraft.net/ja-jp/download/server/bedrock"
version = None

def get_latest_version():
    url = "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()["result"]["links"]
            download_url = next((item["downloadUrl"] for item in data if item["downloadType"] == "serverBedrockWindows"), None)
            if download_url:
                match = re.search(r"bedrock-server-([\d.]+)\.zip$", download_url)
                if match:
                    print(f"latest version: {match.group(1)}")
                    return match.group(1)
                else:
                    raise Exception("Failed to extract version from download URL")
            else:
                raise Exception("No download URL found for serverBedrockWindows")
        else:
            raise Exception(f"Failed to fetch latest version: {response.status_code}")
    except Exception as e:
        print(f"error fetching latest version: {e}")
        return None


def download(version, path):
    # 最新バージョンのURLを生成
    url = f"https://www.minecraft.net/bedrockdedicatedserver/bin-win/bedrock-server-{version}.zip"
    #url = f"https://minecraft.azureedge.net/bin-win/bedrock-server-{version}.zip"
    print(f"downloading version {version} from {url}...")
    try:
        res = requests.get(url, stream=True, timeout=(5, 30), headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            with open(path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("download complete.")
            return True
        else:
            print(f"failed to download: {res.status_code}")
            return False
    except Exception as e:
        print(f"error during download: {e}")
        return False
    
def clear_readonly(path):
    for root, dirs, files in os.walk(path):
        for dir in dirs:
            os.chmod(os.path.join(root, dir), stat.S_IWRITE | stat.S_IREAD)
        for file in files:
            os.chmod(os.path.join(root, file), stat.S_IWRITE | stat.S_IREAD)

def update_server(server_path, temp_dir):
    print("updating server files...")
    temp_backup = os.path.join(server_path, "temp_backup")
    #os.makedirs(temp_backup, exist_ok=True)
    if os.path.exists(temp_backup):
        print("removing old temp backup...")
        clear_readonly(temp_backup)
        shutil.rmtree(temp_backup)
    print("creating temp backup...")
    shutil.copytree(server_path, temp_backup,ignore=shutil.ignore_patterns('temp_backup','temp'))
    #-----------------------------
    zip_path = os.path.join(temp_dir, "server.zip")
    extract_dir = os.path.join(temp_dir, "extracted")
    if not zipfile.is_zipfile(zip_path):
        raise Exception("zip file is corrupted")

    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)

    print("extracting downloaded server files...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

    # -----------------------------
    # ファイル置換
    # -----------------------------
    keep_files = [
        "worlds",
        "server.properties",
        "permissions.json",
        "allowlist.json"
    ]

    print("replacing server files...")
    for item in os.listdir(extract_dir):
        src = os.path.join(extract_dir, item)
        dst = os.path.join(server_path, item)

        # 保持対象はスキップ
        if item in keep_files and os.path.exists(dst):
            continue

        # 既存削除
        if os.path.exists(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)

        # 移動
        shutil.move(src, dst)
    print("server files replaced successfully.")
    # temp削除
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print("temp cleanup failed:", e)
        return False
    return True


def set_version(new_version):
    global version
    version = new_version

def get_version():
    return version