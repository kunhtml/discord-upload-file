import discord
from discord.ext import commands
import tkinter as tk
from tkinter import filedialog
import threading
import asyncio
import requests
import os
import re

# Đọc token và channel ID từ file cấu hình
def read_config():
    with open('config.txt', 'r') as f:
        lines = f.readlines()
        token = lines[0].strip()  # Dòng đầu tiên là token
        channel_id = int(lines[1].strip())  # Dòng thứ hai là channel ID
    return token, channel_id

# Khởi tạo intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Kích hoạt intents để đọc nội dung tin nhắn

# Khởi tạo bot với prefix "!" và intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Tạo một hàng đợi cho thông điệp (sử dụng asyncio.Queue)
message_queue = asyncio.Queue()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

async def queue_message(message):
    await message_queue.put(message)

# Khởi tạo GUI
class DiscordBotGUI:
    def __init__(self, master, channel_id):
        self.master = master
        self.master.title("Discord Bot File Uploader")

        self.label = tk.Label(master, text="Chọn file để tải lên:")
        self.label.pack(pady=10)

        self.upload_button = tk.Button(master, text="Chọn File", command=self.upload_file)
        self.upload_button.pack(pady=5)

        self.send_button = tk.Button(master, text="Tải lên File", command=lambda: self.run_send_file(channel_id))
        self.send_button.pack(pady=5)

        self.url_label = tk.Label(master, text="Nhập URL để tải xuống:")
        self.url_label.pack(pady=10)

        self.url_entry = tk.Entry(master, width=50)
        self.url_entry.pack(pady=5)

        self.download_button = tk.Button(master, text="Tải xuống từ URL", command=self.download_from_url)
        self.download_button.pack(pady=5)

        self.link_label = tk.Label(master, text="Liên kết tải xuống:")
        self.link_label.pack(pady=10)

        self.link_entry = tk.Entry(master, width=50)
        self.link_entry.pack(pady=5)

        self.copy_button = tk.Button(master, text="Sao chép liên kết", command=self.copy_link)
        self.copy_button.pack(pady=5)

        # Thêm một Text widget để thông báo
        self.output_box = tk.Text(master, height=5, width=60, state='disabled')
        self.output_box.pack(pady=10)

        self.file_path = None  # Đường dẫn file đã chọn
        self.channel_id = channel_id  # Lưu channel_id để sử dụng

        # Bắt đầu thread để xử lý hàng đợi
        self.update_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.update_thread.start()

    def process_queue(self):
        """Xử lý thông điệp trong hàng đợi."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.run())

    async def run(self):
        while True:
            message = await message_queue.get()  # Chờ nhận thông điệp mới từ hàng đợi
            self.log_message(message)  # Gọi hàm để log thông điệp

    def log_message(self, message):
        """Cập nhật Text widget với thông điệp mới."""
        self.output_box.config(state='normal')
        self.output_box.insert(tk.END, f"{message}\n")  # Thêm thông điệp vào ô
        self.output_box.config(state='disabled')  # Chuyển lại chế độ chỉ đọc

    def upload_file(self):
        self.file_path = filedialog.askopenfilename()
        if self.file_path:
            asyncio.run_coroutine_threadsafe(queue_message(f"File đã chọn: {self.file_path}"), bot.loop)

    def run_send_file(self, channel_id):
        if self.file_path:
            asyncio.run_coroutine_threadsafe(self.send_file(self.channel_id), bot.loop)

    async def send_file(self, channel_id):
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                message = await channel.send(file=discord.File(self.file_path))
                # Lưu liên kết vào trường nhập liệu
                link = message.attachments[0].url
                await queue_message("File đã được tải lên thành công!")
                await queue_message(f"Liên kết tải xuống: {link}")

                # Cập nhật liên kết vào ô input
                self.update_link_entry(link)
                return True  # Trả về True nếu upload thành công
            except Exception as e:
                await queue_message(f"Đã có lỗi xảy ra: {e}")
                return False
        else:
            await queue_message("Không tìm thấy kênh!")
            return False

    def update_link_entry(self, link):
        """Cập nhật ô nhập liệu liên kết một cách an toàn."""
        self.clear_link_entry()  # Xóa nội dung cũ
        self.link_entry.insert(0, link)  # Chèn URL vào ô nhập liệu

    def clear_link_entry(self):
        self.link_entry.delete(0, tk.END)  # Xóa nội dung cũ

    def copy_link(self):
        link = self.link_entry.get()
        if link:
            self.master.clipboard_clear()  # Xóa clipboard
            self.master.clipboard_append(link)  # Thêm liên kết vào clipboard
            asyncio.run_coroutine_threadsafe(queue_message("Liên kết đã được sao chép!"), bot.loop)
        else:
            asyncio.run_coroutine_threadsafe(queue_message("Không có liên kết nào để sao chép."), bot.loop)

    def sanitize_filename(self, filename):
        # Sử dụng biểu thức chính quy để thay thế các ký tự không hợp lệ
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return sanitized

    def download_from_url(self):
        url = self.url_entry.get()
        if url:
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    # Lấy tên tệp từ URL và loại bỏ tham số
                    file_name = url.split('/')[-1].split('?')[0]
                    # Làm sạch tên tệp
                    sanitized_file_name = self.sanitize_filename(file_name)
                    # Lưu file vào bộ nhớ tạm
                    with open(sanitized_file_name, 'wb') as f:
                        f.write(response.content)

                    self.file_path = sanitized_file_name  # Cập nhật đường dẫn file
                    asyncio.run_coroutine_threadsafe(queue_message(f"Tải xuống thành công: {sanitized_file_name}"), bot.loop)
                    
                    # Chạy send_file trong một coroutine mới
                    asyncio.run_coroutine_threadsafe(self.send_file(self.channel_id), bot.loop)
                else:
                    asyncio.run_coroutine_threadsafe(queue_message(f"Lỗi tải xuống, mã trạng thái: {response.status_code}"), bot.loop)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue_message(f"Đã có lỗi xảy ra khi tải xuống: {e}"), bot.loop)
        else:
            asyncio.run_coroutine_threadsafe(queue_message("Bạn cần nhập một URL hợp lệ."), bot.loop)

# Khởi động GUI
def start_gui(channel_id):
    root = tk.Tk()
    app = DiscordBotGUI(root, channel_id)
    root.mainloop()

# Chạy bot và GUI
if __name__ == "__main__":
    # Đọc cấu hình
    token, channel_id = read_config()
    
    # Chạy bot Discord trong một thread riêng biệt
    discord_thread = threading.Thread(target=lambda: bot.run(token), daemon=True)
    discord_thread.start()
    
    # Khởi động GUI
    start_gui(channel_id)
