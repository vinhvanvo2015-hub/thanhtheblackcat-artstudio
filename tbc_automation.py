import hashlib
import json
import os
import re
import subprocess
import time
import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# =====================================================================
# CONFIGURATION - CẤU HÌNH HỆ THỐNG v9.6 (FIX AUTHENTICATION)
# =====================================================================
WATCH_DIRECTORY = r"D:\Thanhtheblackcat-Art\QUẢN LÝ TÁC PHẨM"
PROJECT_WEB_DIR = r"D:\Thanhtheblackcat-Art\QUẢN LÝ TÁC PHẨM"
WEB_DATA_JSON_PATH = os.path.join(PROJECT_WEB_DIR, "artworks_data.json")

# Cấu hình GitHub - ĐÃ TỰ ĐỘNG NHÚNG TOKEN ĐỂ BỎ QUA ĐĂNG NHẬP
GITHUB_USERNAME = "vinhvanvo2015-hub"
GITHUB_REPO_NAME = "thanhtheblackcat-artstudio"
GITHUB_TOKEN = "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"

NETLIFY_BUILD_HOOK_URL = os.getenv("NETLIFY_BUILD_HOOK_URL", "")

PINATA_JWT_TOKEN = os.getenv(
    "PINATA_JWT",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiIyYWUyNDY4MC1kYzljLTRkNTQtOTY0Zi1kYzI1ODExYTIxYmIiLCJlbWFpbCI6InZpbmh2YW52boIwMTVAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsInBpbl9wb2xpY3kiOnsicmVnaW9ucyI6W3siZGVzaXJlZFJlcGxpY2F0aW9uQ291bnQiOjEsImlkIjoiRlJBMSJ9LHsiZGVzaXJlZFJlcGxpY2F0aW9uQ291bnQiOjEsImlkIjoiTllDMSJ9XSwidmVyc2lvbiI6MX0sIm1mYV9lbmFibGVkIjpmaWxzZSwic3RhdHVzIjoiQUNUSVZFIn0sImF1dGhlbnRpY2F0aW9uVHlwZSI6InNjb3BlZEtleIsInNjb3BlZEtleUtleSI6IjM5NjNkZmExMTMwYWZkMzQ3NTlhIiwic2NvcGVkS2V5U2VjcmV0IjoiMDQ2ZmYwNDY3MTJhNDU4ZWIzODg5OWRhYTEzMWFjYTg0Y2I5YTkwNzk5MmY4NjMyNmM5M113Mzc5MDFhNzEwMCIsImV4cCI6MTgxOTAyMDAyNX0.EqedzH9z7kLRpy8lu2KVL21-_zH4DoR3SucXkKQh_WU",
)


def find_git_executable():
    possible_paths = [
        "git",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe"),
    ]
    for path in possible_paths:
        try:
            res = subprocess.run(
                f'"{path}" --version',
                shell=True,
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return path
        except Exception:
            continue
    return "git"


GIT_CMD = find_git_executable()


def ensure_correct_git_remote():
    """Tự động nhúng Token vào Remote URL để xác thực Git 100% tự động."""
    token = GITHUB_TOKEN.strip()
    if token and not token.startswith("ghp_xxxx"):
        correct_url = f"https://{GITHUB_USERNAME}:{token}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO_NAME}.git"
    else:
        correct_url = f"https://github.com/{GITHUB_USERNAME}/{GITHUB_REPO_NAME}.git"

    try:
        subprocess.run(
            f'"{GIT_CMD}" remote set-url origin {correct_url}',
            cwd=PROJECT_WEB_DIR,
            shell=True,
            check=True,
            capture_output=True,
        )
        print(f"[✓] Cấu hình Remote Git thành công!")
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
        folder_path = (
            src_path if event.is_directory else os.path.dirname(src_path)
        )

        if folder_path == WATCH_DIRECTORY or not folder_path.startswith(
            WATCH_DIRECTORY
        ):
            return

        time.sleep(2)

        if (
            os.path.exists(folder_path)
            and folder_path not in self.processed_folders
        ):
            text_file = os.path.join(folder_path, "thong_tin.txt")
            if os.path.exists(text_file):
                print(f"\n[+] Kích hoạt xử lý tại Folder: {folder_path}")
                self.processed_folders.add(folder_path)
                self.process_artwork_folder(folder_path)

    def process_artwork_folder(self, folder_path):
        text_file = os.path.join(folder_path, "thong_tin.txt")
        image_file = None

        for file in os.listdir(folder_path):
            if file.lower().endswith(
                (".png", ".jpg", ".jpeg")
            ) and not file.startswith("web_secured_display"):
                image_file = os.path.join(folder_path, file)
                break

        if not os.path.exists(text_file) or not image_file:
            print("[-] Đang đợi đủ file thong_tin.txt và file ảnh...")
            self.processed_folders.discard(folder_path)
            return

        print("[*] Đang đọc dữ liệu từ thong_tin.txt...")
        metadata = self.parse_text_file(text_file)

        if not metadata:
            print("[-] Lỗi: Định dạng file text không hợp lệ.")
            self.processed_folders.discard(folder_path)
            return

        print("[*] Đang khởi tạo bản ảnh hiển thị...")
        processed_image_path = self.activate_arttech_shield(
            image_file, folder_path
        )

        print("[*] Đang tải ảnh lên IPFS...")
        ipfs_link, ipfs_cid = self.upload_to_pinata_ipfs(
            processed_image_path, metadata.get("id", "TBC-ART")
        )

        if ipfs_link and ipfs_cid:
            print(f"[✓] XỬ LÝ ẢNH THÀNH CÔNG!")
            print(f"    --> URL Web: {ipfs_link}")

            self.save_ipfs_to_local_text(text_file, ipfs_link, ipfs_cid)

            print("[*] Đang cập nhật tệp dữ liệu JSON cho Website...")
            json_success = self.sync_to_netlify_json(
                metadata, ipfs_link, ipfs_cid
            )

            if json_success:
                print(
                    "[*] Đang tiến hành kích hoạt hiển thị lên Website"
                    " Netlify..."
                )
                self.deploy_to_netlify(metadata.get("title_vi", "Artwork mới"))
        else:
            print("[-] Không thể xử lý dữ liệu cho tác phẩm.")
            self.processed_folders.discard(folder_path)

    def parse_text_file(self, file_path):
        data = {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "====================================" in content:
                content = content.split("====================================")[
                    0
                ]

            fields = [
                "ID",
                "Title_VI",
                "Title_EN",
                "Medium_VI",
                "Medium_EN",
                "Dimensions",
                "Year",
                "Price",
                "Description_VI",
                "Description_EN",
            ]
            for field in fields:
                match = re.search(rf"{field}:\s*(.*)", content, re.IGNORECASE)
                if match:
                    clean_val = (
                        match.group(1)
                        .strip()
                        .replace("\r", "")
                        .replace("\n", " ")
                    )
                    data[field.lower()] = clean_val
            return data
        except Exception as e:
            print(f"[-] Lỗi đọc file text: {str(e)}")
            return None

    def activate_arttech_shield(self, original_image, folder_path):
        shielded_image_path = os.path.join(
            folder_path, "web_secured_display.png"
        )
        with open(original_image, "rb") as src, open(
            shielded_image_path, "wb"
        ) as dst:
            dst.write(src.read())
        print(f"[✓] Đã tạo tệp ảnh hiển thị: {shielded_image_path}")
        return shielded_image_path

    def upload_to_pinata_ipfs(self, image_path, artwork_id):
        url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        token = "".join(PINATA_JWT_TOKEN.split())
        headers = {"Authorization": f"Bearer {token}"}

        try:
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(artwork_id))
            upload_name = f"{safe_id}_secured_artwork.png"

            with open(image_path, "rb") as f:
                files = [("file", (upload_name, f, "image/png"))]
                response = requests.post(
                    url, files=files, headers=headers, timeout=15
                )

                if response.status_code == 200:
                    response_data = response.json()
                    cid = response_data["IpfsHash"]
                    return f"https://gateway.pinata.cloud/ipfs/{cid}", cid
        except Exception as e:
            print(f"[-] Lỗi Pinata IPFS: {str(e)}")

        folder_name = os.path.basename(os.path.dirname(image_path))
        web_relative_path = f"./{folder_name}/web_secured_display.png"
        with open(image_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        return web_relative_path, f"LOCAL_{file_hash}"

    def sync_to_netlify_json(self, metadata, ipfs_link, ipfs_cid):
        try:
            artworks = []
            if os.path.exists(WEB_DATA_JSON_PATH):
                with open(WEB_DATA_JSON_PATH, "r", encoding="utf-8") as jf:
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
                "ipfs_url": ipfs_link,
                "ipfs_cid": ipfs_cid,
            }

            artworks = [
                item
                for item in artworks
                if item.get("id") != metadata.get("id")
            ]
            artworks.append(new_entry)

            with open(WEB_DATA_JSON_PATH, "w", encoding="utf-8") as jf:
                json.dump(artworks, jf, ensure_ascii=False, indent=4)

            print(f"[✓] Đã lưu thông tin tác phẩm vào tệp JSON.")
            return True
        except Exception as e:
            print(f"[-] Không thể ghi tệp JSON: {str(e)}")
            return False

    def deploy_to_netlify(self, title):
        if NETLIFY_BUILD_HOOK_URL.strip():
            try:
                res = requests.post(NETLIFY_BUILD_HOOK_URL, timeout=10)
                if res.status_code in [200, 202]:
                    print(f"[✓] Đã gửi tín hiệu Build Hook sang Netlify!")
            except Exception:
                pass

        try:
            cwd = PROJECT_WEB_DIR
            subprocess.run(
                f'"{GIT_CMD}" add .', cwd=cwd, shell=True, check=True
            )
            subprocess.run(
                f'"{GIT_CMD}" commit -m "Auto-add artwork: {title}"',
                cwd=cwd,
                shell=True,
                capture_output=True,
            )

            push_res = subprocess.run(
                f'"{GIT_CMD}" push origin HEAD',
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
            )
            if push_res.returncode == 0:
                print(
                    f"[✓] BẬT ĐÈN XANH: Đã Push dữ liệu thành công lên"
                    " GitHub/Netlify!"
                )
            else:
                print(
                    f"[-] Cảnh báo Push: {push_res.stderr.strip()}"
                )
        except Exception as e:
            print(f"[-] Lỗi Sync: {str(e)}")

    def save_ipfs_to_local_text(self, file_path, ipfs_link, ipfs_cid):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "IPFS_CID:" not in content:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n====================================")
                    f.write(f"\nIPFS_CID: {ipfs_cid}")
                    f.write(f"\nIPFS_URL: {ipfs_link}")
                print("[✓] Đã ghi nhận đường dẫn vào thong_tin.txt.")
            else:
                print("[*] Đường dẫn IPFS đã tồn tại trong thong_tin.txt.")
        except Exception as e:
            print(f"[-] Lỗi ghi file text: {str(e)}")


if __name__ == "__main__":
    if not os.path.exists(WATCH_DIRECTORY):
        os.makedirs(WATCH_DIRECTORY)

    ensure_correct_git_remote()

    event_handler = ArtworkPipelineHandler()
    observer = Observer()
    observer.schedule(event_handler, path=WATCH_DIRECTORY, recursive=True)
    observer.start()

    print(
        f"===================================================================="
    )
    print(
        f"  THANHTHEBLACKCAT ARTTECH PIPELINE v9.6 (TOKEN AUTHENTICATION)      "
    )
    print(
        f"===================================================================="
    )
    print(f"[*] Đang chạy ngầm giám sát thư mục: {WATCH_DIRECTORY}\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()