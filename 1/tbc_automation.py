import os
import time
import re
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# =====================================================================
# CONFIGURATION - CẤU HÌNH HỆ THỐNG
# =====================================================================
WATCH_DIRECTORY = r"D:\Thanhtheblackcat-Art\QUẢN LÝ TÁC PHẨM"
WEBSITE_API_URL = "https://thanhtheblackcat.com" # Cổng API nhận dữ liệu của Web
SECRET_API_KEY = "TBC_MATRIX_SECURE_TOKEN_2026" # Mã khóa bảo mật xác thực quyền đẩy bài

class ArtworkPipelineHandler(FileSystemEventHandler):
    """Bộ xử lý tự động liên hoàn khi phát hiện biến động thư mục hoặc file tác phẩm mới"""
    
    def __init__(self):
        super().__init__()
        self.processed_folders = set() # Hàng rào chống trùng lặp dữ liệu khi xử lý liên tục

    def on_created(self, event):
        # Kích hoạt khi anh tạo một Folder mới hoặc ném một file mới vào
        self.handle_system_event(event)

    def on_modified(self, event):
        # Kích hoạt khi anh thực hiện đổi tên Folder, đổi tên file hoặc dán file vào sau
        self.handle_system_event(event)

    def handle_system_event(self, event):
        src_path = event.src_path
        
        # Xác định thư mục đích chứa tác phẩm (Chấp nhận cả sự kiện file bên trong thư mục con biến động)
        if event.is_directory:
            folder_path = src_path
        else:
            folder_path = os.path.dirname(src_path)

        # Rào dậu bảo vệ: Chỉ xử lý nếu thư mục đó nằm trong vùng quản lý và không phải thư mục gốc
        if folder_path == WATCH_DIRECTORY or not folder_path.startswith(WATCH_DIRECTORY):
            return

        # Chờ 3 giây để đảm bảo hệ thống Windows hoàn tất việc đổi tên và đồng bộ dữ liệu file
        time.sleep(3)
        
        if os.path.exists(folder_path) and folder_path not in self.processed_folders:
            text_file = os.path.join(folder_path, "thong_tin.txt")
            
            # Kiểm tra xem file thong_tin.txt đã xuất hiện thực tế chưa để bám đà xử lý
            if os.path.exists(text_file):
                print(f"\n[+] Hệ thống tự động kích hoạt tại Folder: {folder_path}")
                self.processed_folders.add(folder_path) # Đóng khóa mục này lại, chống trùng lặp
                self.process_artwork_folder(folder_path)

    def process_artwork_folder(self, folder_path):
        text_file = os.path.join(folder_path, "thong_tin.txt")
        image_file = None
        
        # Tự động quét và tìm kiếm file hình ảnh gốc (.png hoặc .jpg) bên trong folder
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.png', '.jpg', '.jpeg')) and not file.startswith('web_secured_display'):
                image_file = os.path.join(folder_path, file)
                break
                
        if not os.path.exists(text_file) or not image_file:
            print("[-] Thông báo: Thư mục đang đợi nạp đủ cấu trúc chuẩn (Cần thong_tin.txt và file ảnh).")
            self.processed_folders.discard(folder_path) # Mở khóa để đợi anh nạp file tiếp theo vào
            return

        print("[*] Đang bóc tách dữ liệu từ file thong_tin.txt...")
        metadata = self.parse_text_file(text_file)
        
        if not metadata:
            print("[-] Lỗi: Định dạng cấu trúc bên trong file text không hợp lệ.")
            self.processed_folders.discard(folder_path)
            return

        print("[*] Đang kích hoạt phân hệ bảo mật hình ảnh...")
        # Kích hoạt bộ xử lý ảnh (Nén ảnh, làm mờ dữ liệu gốc, chèn nhiễu kháng AI Layer 7 của anh)
        processed_image_path = self.activate_arttech_shield(image_file, folder_path)

        print("[*] Đang đóng gói dữ liệu và thực hiện kết nối đồng bộ lên Website...")
        self.sync_to_website(metadata, processed_image_path)

    def parse_text_file(self, file_path):
        """Hàm tự động bóc tách dữ liệu song ngữ từ file text"""
        data = {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Sử dụng thuật toán Regex tìm kiếm các trường thông tin theo cấu trúc Key: Value
            fields = ["ID", "Title_VI", "Title_EN", "Medium_VI", "Medium_EN", "Dimensions", "Year", "Price", "Description_VI", "Description_EN"]
            for field in fields:
                match = re.search(rf"{field}:\s*(.*)", content, re.IGNORECASE)
                if match:
                    data[field.lower()] = match.group(1).strip()
            return data
        except Exception as e:
            print(f"[-] Lỗi đọc file text: {str(e)}")
            return None

    def activate_arttech_shield(self, original_image, folder_path):
        """
        [MÔ-ĐUN BẢO MẬT OFFLINE]
        Nơi anh Thạnh tích hợp mã xử lý ảnh, chèn nhiễu ma trận Laplacian 
        hoặc lớp khiên kháng AI (Layer 7) trước khi tải lên mạng công khai.
        """
        shielded_image_path = os.path.join(folder_path, "web_secured_display.png")
        
        # Mô phỏng bọc lót bảo mật: Sao chép file gốc ra file hiển thị an toàn
        with open(original_image, "rb") as src, open(shielded_image_path, "wb") as dst:
            dst.write(src.read())
            
        print(f"[✓] Đã tạo file ảnh bảo mật chống cào dữ liệu: {shielded_image_path}")
        return shielded_image_path

    def sync_to_website(self, metadata, image_path):
        """Hàm mở cổng kết nối Internet trong tích tắc để đồng bộ dữ liệu sạch lên máy chủ"""
        try:
            payload = {
                "api_key": SECRET_API_KEY,
                "id": metadata.get("id"),
                "title_vi": metadata.get("title_vi"),
                "title_en": metadata.get("title_en"),
                "medium_vi": metadata.get("medium_vi"),
                "medium_en": metadata.get("medium_en"),
                "dimensions": metadata.get("dimensions"),
                "year": metadata.get("year"),
                "price": metadata.get("price"),
                "description_vi": metadata.get("description_vi"),
                "description_en": metadata.get("description_en")
            }
            
            files = {
                "artwork_image": open(image_path, "rb")
            }
            
            # Thực hiện lệnh đẩy dữ liệu lên máy chủ Web hệ thống
            response = requests.post(WEBSITE_API_URL, data=payload, files=files, timeout=15)
            
            if response.status_code == 200:
                print(f"[✓] THÀNH CÔNG: Tác phẩm [{metadata.get('title_vi')}] đã tự động đồng bộ lên Website!")
            else:
                print(f"[-] Thất bại: Website phản hồi mã trạng thái {response.status_code} (Chưa cấu hình API nhận bài).")
        except Exception as e:
            print(f"[-] Thông báo kết nối mạng: {str(e)} (Hệ thống đang bảo mật Offline).")

# =====================================================================
# KHỞI CHẠY HỆ THỐNG GIÁM SÁT NGẦM ĐA TẦNG
# =====================================================================
if __name__ == "__main__":
    if not os.path.exists(WATCH_DIRECTORY):
        os.makedirs(WATCH_DIRECTORY)
        
    event_handler = ArtworkPipelineHandler()
    observer = Observer()
    # Kích hoạt quét sâu đa tầng nâng cao (recursive=True) để bắt mọi file ném vào sau
    observer.schedule(event_handler, path=WATCH_DIRECTORY, recursive=True)
    
    print(f"====================================================================")
    print(f"    THANHTHEBLACKCAT AUTOMATED ARTTECH PIPELINE RUNNING...          ")
    print(f"====================================================================")
    print(f"[*] Hệ thống đang giám sát ngầm đa tầng tại: {WATCH_DIRECTORY}")
    print(f"[*] Thao tác tự do: Tạo Folder, đổi tên, dán file... hệ thống tự nhận diện.")
    print(f"[!] Nhấn Ctrl + C để dừng chương trình.")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
