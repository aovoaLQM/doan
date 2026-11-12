# Hướng dẫn làm việc với dự án

## Tổng quan

Dự án Python sử dụng Streamlit để sinh và duyệt kịch bản đào tạo nhận thức về kỹ thuật tấn công phi kỹ thuật (social engineering).

## Các thành phần chính

- `app.py`: giao diện Streamlit.
- `schema_builder.py`: định nghĩa cấu trúc, nhóm và các ràng buộc của kịch bản.
- `pipeline.py`: xử lý quy trình sinh kịch bản.
- `review`: chức năng lưu trữ và duyệt kịch bản.
- `requirements.txt`: các thư viện Python cần thiết.

## Cài đặt và chạy

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

## Nguyên tắc chỉnh sửa

- Đọc mã liên quan trước khi sửa; giới hạn thay đổi trong phạm vi yêu cầu.
- Giữ nội dung tiếng Việt và lưu tệp bằng UTF-8.
- Tuân theo cách tổ chức mã và quy ước đặt tên hiện có.
- Giữ các lựa chọn trên giao diện đồng bộ với schema và ràng buộc nghiệp vụ.
- Không ghi API key hoặc thông tin nhạy cảm vào mã nguồn; sử dụng biến môi trường hoặc `.env`.
- Không tự ý ghi đè dữ liệu kịch bản hoặc kết quả duyệt.

## Kiểm tra thay đổi

- Chạy các kiểm thử liên quan bằng `python -m pytest` nếu dự án có kiểm thử.
- Với thay đổi giao diện, chạy Streamlit và kiểm tra luồng bị ảnh hưởng.
- Khi bàn giao, nêu ngắn gọn phần đã sửa, cách kiểm tra và hạn chế còn lại.
