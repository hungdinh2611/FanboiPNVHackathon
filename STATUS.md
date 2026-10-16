# Trạng thái tích hợp

[2026-10-16 14:40 Asia/Saigon] P1 Đinh Bảo Hưng - Đã đọc toàn bộ ngữ cảnh, tạo và push contract.py (b2de447); Python 3.10.4, OpenCV 4.9.0, NumPy 1.23.1 - Tiếp: calibrate.py, perception.py, test_perception.py và mẫu in - Chưa đo với webcam/thước; không sửa file của P2/P3/P4.

[2026-10-16 14:48 Asia/Saigon] P1 Đinh Bảo Hưng - Có calibrate.py (>=15 ảnh, RMS từng ảnh, fallback FOV), perception.py (IPPE hai nghiệm, đúng ID và hệ tọa độ), công cụ test độc lập, ảnh marker/bàn cờ và P1_GUIDE.md. 16 test tổng hợp đã pass, đang bổ sung ca frontal/trùng ID và review - Webcam 0 trả ảnh thật 1280x720 nhưng driver không nhận lệnh tắt autofocus - Còn cần in thẻ/bàn cờ, hiệu chuẩn thật, đo z=50 cm (<1 cm) và thống nhất dấu yaw cùng P4. Chưa có số đo accuracy thật; HFOV 68 chỉ là giả định dự phòng.

Yêu cầu tích hợp P3: dùng Perceiver('calib.npz') hoặc chỉ rõ calib_approx.npz nếu fallback; K/dist có sẵn trên instance để vẽ trục. Giữ cùng camera mode/focus; nhận ảnh khác aspect ratio sẽ báo ValueError. P4: không dùng RMS/accuracy từ self-test làm bằng chứng thật; hẹn đo chung dấu yaw trước khi thu GT.
