import os
import re
import json
import time
import requests
import hashlib
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# =====================================================================
# CONFIGURATION - CẤU HÌNH HỆ THỐNG v10.7 (AUTHENTICATION DIRECT FIX)
# =====================================================================
WATCH_DIRECTORY = r"D:\Thanhtheblackcat-Art\QUẢN LÝ TÁC PHẨM"
PROJECT_WEB_DIR = r"D:\Thanhtheblackcat-Art\QUẢN LÝ TÁC PHẨM"
WEB_DATA_JSON_PATH = os.path.join(PROJECT_WEB_DIR, "artworks_data.json")

GITHUB_USERNAME = "vinhvanvo2015-hub"
GITHUB_REPO_NAME = "thanhtheblackcat-artstudio"

# Điền trực tiếp Token hoặc lấy từ biến môi trường
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
NETLIFY_BUILD_HOOK_URL = os.getenv("NETLIFY_BUILD_HOOK_URL", "").strip()

PINATA_API_KEY = "387743902cb5c45a9c48"
PINATA_SECRET_KEY = "c4c700e54cd1bf975858dc550fc8607f095336f353f7605df15410ddc3f40988"
PINATA_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiIyYWUyNDY4MC1kYzljLTRkNTQtOTY0Zi1kYzI1ODExYTIxYmIiLCJlbWFpbCI6InZpbmh2YW52bzIwMTVAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsInBpbl9wb2xpY3kiOnsicmVnaW9ucyI6W3siZGVzaXJlZFJlcGxpY2F0aW9uQ291bnQiOjEsImlkIjoiRlJBMSJ9LHsiZGVzaXJlZFJlcGxpY2F0aW9uQ291bnQiOjEsImlkIjoiTllDMSJ9XSwidmVyc2lvbiI6MX0sIm1mYV9lbmFibGVkIjpmYWxzZSwic3RhdHVzIjoiQUNUSVZFIn0sImF1dGhlbnRpY2F0aW9uVHlwZSI6InNjb3BlZEtleSIsInNjb3BlZEtleUtleSI6IjM4Nzc0MzkwMmNiNWM0NWE5YzQ4Iiwic2NvcGVkS2V5U2VjcmV0IjoiYzRjNzAwZTU0Y2QxYmY5NzU4NThkYzU1MGZjODYwN2YwOTUzMzZmMzUzZjc20Vk1NDEwZGRjM2Y0MDk4OCIsImV4cCI6MTgxOTAzNDg3N30.MI8LQJBXYDPr3xNnFLU8HupkwGFidTPHHPUih4qAMM4"

def find_git_executable():
    possible_paths = [
        "git",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe")
    ]
    for path in possible_paths:
        try:
            res = subprocess.run(f'"{path}" --version', shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                return path
        except Exception:
            continue
    return "git"

GIT_CMD = find_git_executable()

def ensure_correct_git_remote():
    if GITHUB_TOKEN:
        correct_url = f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO_NAME}.git"
    else:
        correct_url = f"https://github.com/{GITHUB_USERNAME}/{GITHUB_REPO_NAME}.git"
    
    try:
        subprocess.run(f'"{GIT_CMD}" remote set-url origin {correct_url}', cwd=PROJECT_WEB_DIR, shell=True, check=True, capture_output=True)
        print(f"[✓] Kết nối Git Remote OK!")
    except Exception as e:
        print(f"[-] Lỗi kết nối Git Remote: {str(e)}")

class ArtworkPipelineHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.processed_folders = set()

    def on_created(self, event):
        self.handle_system_event(event)

    def on_modified(self, event):
        self.handle_system_event(event)

    def handle_system_event(self, event):
        src_path = event.src_path
        folder_path = src_path if event.is_directory else os.path.dirname(src_path)

        if folder_path == WATCH_DIRECTORY or not folder_path.startswith(WATCH_DIRECTORY):
            return

        time.sleep(1)

        if os.path.exists(folder_path) and folder_path not in self.processed_folders:
            text_file = os.path.join(folder_path, "thong_tin.txt")
            if os.path.exists(text_file):
                self.processed_folders.add(folder_path)
                self.process_artwork_folder(folder_path)

    def process_artwork_folder(self, folder_path):
        text_file = os.path.join(folder_path, "thong_tin.txt")
        image_file = None

        for file in os.listdir(folder_path):
            if file.lower().endswith(('.png', '.jpg', '.jpeg')) and not file.startswith('web_secured_display'):
                image_file = os.path.join(folder_path, file)
                break

        if not os.path.exists(text_file) or not image_file:
            self.processed_folders.discard(folder_path)
            return

        metadata = self.parse_text_file(text_file)
        if not metadata:
            self.processed_folders.discard(folder_path)
            return

        print(f"\n[+] Đang xử lý tác phẩm: {metadata.get('title_vi', 'Chưa rõ tên')}")
        processed_image_path = self.activate_arttech_shield(image_file, folder_path)

        ipfs_link, ipfs_cid = self.upload_to_pinata_ipfs(processed_image_path, metadata.get('id', 'TBC-ART'))

        if ipfs_link and ipfs_cid:
            print(f"[✓] Đã lấy được IPFS Link: {ipfs_link}")
            self.save_ipfs_to_local_text(text_file, ipfs_link, ipfs_cid)
            json_success = self.sync_to_netlify_json(metadata, ipfs_link, ipfs_cid)

            if json_success:
                self.deploy_to_netlify(metadata.get('title_vi', 'Artwork mới'))
        else:
            self.processed_folders.discard(folder_path)

    def parse_text_file(self, file_path):
        data = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "====================================" in content:
                content = content.split("====================================")[0]

            fields = ["ID", "Title_VI", "Title_EN", "Medium_VI", "Medium_EN", "Dimensions", "Year", "Price", "Description_VI", "Description_EN", "Category"]
            for field in fields:
                match = re.search(rf"{field}:\s*(.*)", content, re.IGNORECASE)
                if match:
                    clean_val = match.group(1).strip().replace('\r', '').replace('\n', ' ')
                    data[field.lower()] = clean_val
            return data
        except Exception as e:
            return None

    def activate_arttech_shield(self, original_image, folder_path):
        shielded_image_path = os.path.join(folder_path, "web_secured_display.png")
        if not os.path.exists(shielded_image_path):
            with open(original_image, 'rb') as src, open(shielded_image_path, 'wb') as dst:
                dst.write(src.read())
        return shielded_image_path

    def upload_to_pinata_ipfs(self, image_path, artwork_id):
        url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(artwork_id))
        upload_name = f"{safe_id}_secured_artwork.png"

        if PINATA_JWT_TOKEN:
            token = "".join(PINATA_JWT_TOKEN.split())
            headers = {"Authorization": f"Bearer {token}"}
            try:
                with open(image_path, 'rb') as f:
                    files = [('file', (upload_name, f, 'image/png'))]
                    res = requests.post(url, files=files, headers=headers, timeout=30)
                    if res.status_code == 200:
                        cid = res.json()["IpfsHash"]
                        return f"https://gateway.pinata.cloud/ipfs/{cid}", cid
            except Exception:
                pass

        folder_name = os.path.basename(os.path.dirname(image_path))
        web_relative_path = f"./{folder_name}/web_secured_display.png"
        with open(image_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        return web_relative_path, f"LOCAL_{file_hash}"

    def sync_to_netlify_json(self, metadata, ipfs_link, ipfs_cid):
        try:
            artworks = []
            if os.path.exists(WEB_DATA_JSON_PATH):
                with open(WEB_DATA_JSON_PATH, 'r', encoding='utf-8') as jf:
                    try:
                        artworks = json.load(jf)
                    except json.JSONDecodeError:
                        artworks = []

            new_entry = {
                "id": metadata.get("id"),
                "title_vi": metadata.get("title_vi"),
                "title_en": metadata.get("title_en"),
                "medium_vi": metadata.get("medium_vi"),
                "medium_en": metadata.get("medium_en"),
                "dimensions": metadata.get("dimensions"),
                "year": metadata.get("year"),
                "price": metadata.get("price"),
                "description_vi": metadata.get("description_vi"),
                "description_en": metadata.get("description_en"),
                "category": metadata.get("category", "TẤT CẢ"),
                "ipfs_url": ipfs_link,
                "ipfs_cid": ipfs_cid
            }

            artworks = [item for item in artworks if item.get("id") != metadata.get("id")]
            artworks.append(new_entry)

            with open(WEB_DATA_JSON_PATH, 'w', encoding='utf-8') as jf:
                json.dump(artworks, jf, ensure_ascii=False, indent=4)

            print(f"[✓] Đã ghi nhận tác phẩm vào artworks_data.json!")
            return True
        except Exception as e:
            print(f"[-] Lỗi cập nhật file JSON: {str(e)}")
            return False

    def deploy_to_netlify(self, title):
        try:
            cwd = PROJECT_WEB_DIR
            subprocess.run(f'"{GIT_CMD}" add .', cwd=cwd, shell=True, check=True)
            subprocess.run(f'"{GIT_CMD}" commit -m "Auto-add artwork: {title}"', cwd=cwd, shell=True, capture_output=True)
            
            # Đẩy dữ liệu với thông số không tương tác để tránh bị treo
            push_res = subprocess.run(f'"{GIT_CMD}" -c core.askPass= push origin master', cwd=cwd, shell=True, capture_output=True, text=True)
            if push_res.returncode == 0:
                print(f"[✓] THÀNH CÔNG: Đã đẩy dữ liệu mới lên Web Netlify!")
            else:
                print(f"[-] Cảnh báo Push: {push_res.stderr.strip()}")
        except Exception as e:
            print(f"[-] Lỗi Sync Git: {str(e)}")

    def save_ipfs_to_local_text(self, file_path, ipfs_link, ipfs_cid):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "IPFS_CID:" not in content:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n====================================")
                    f.write(f"\nIPFS_CID: {ipfs_cid}")
                    f.write(f"\nIPFS_URL: {ipfs_link}")
        except Exception:
            pass

def scan_and_process_existing_folders(handler):
    print("[*] Đang quét toàn bộ thư mục tranh...")
    for item in os.listdir(WATCH_DIRECTORY):
        item_path = os.path.join(WATCH_DIRECTORY, item)
        if os.path.isdir(item_path) and not item.startswith("."):
            text_file = os.path.join(item_path, "thong_tin.txt")
            if os.path.exists(text_file):
                with open(text_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if "IPFS_CID:" not in content:
                    print(f"[+] Tìm thấy thư mục tranh mới: {item}")
                    handler.processed_folders.add(item_path)
                    handler.process_artwork_folder(item_path)

if __name__ == "__main__":
    if not os.path.exists(WATCH_DIRECTORY):
        os.makedirs(WATCH_DIRECTORY)

    ensure_correct_git_remote()
    event_handler = ArtworkPipelineHandler()
    
    scan_and_process_existing_folders(event_handler)

    observer = Observer()
    observer.schedule(event_handler, path=WATCH_DIRECTORY, recursive=True)
    observer.start()

    print(f"====================================================================")
    print(f"  THANHTHEBLACKCAT ARTTECH PIPELINE v10.7 (AUTHENTICATION FIX)      ")
    print(f"====================================================================")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()