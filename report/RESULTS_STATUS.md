# Kết quả đã bàn giao — 2026-10-16

## Hiệu chuẩn camera thật của Hưng

- File: [calibration_hung.npz](../data/calibration_hung.npz), bản sao `calib.npz` trên máy Hưng.
- Phương pháp: chessboard, 15 ảnh, độ phân giải 1280×720.
- RMS tổng: **0.226114 px**, đạt mục tiêu <0.6 px.
- Đây là độ khớp góc bàn cờ; chưa phải bằng chứng sai số vị trí theo cm.
- Chỉ dùng cho đúng camera/chế độ ảnh/focus đã hiệu chuẩn trên máy Hưng.
  Máy khác cần hiệu chuẩn riêng; không tự dùng file này làm camera mặc định.

## Lượt chạy webcam thật

- File: [live_check_hung.csv](../data/live_check_hung.csv), bản sao `log.csv` tại thời điểm bàn giao.
- 298 frame, nguồn LIVE, **0 frame nhận được marker**, toàn bộ trạng thái LOST.
- Giữ làm log chẩn đoán không nhận diện được; không dùng để báo accuracy hoặc đã căn chỉnh.
- Chưa có `data/gt_runs.csv` đo bằng thước và không có `video.mp4` live trên máy ở thời điểm kiểm tra.
- Bước kiểm trực tiếp tiếp theo: đưa đúng marker ID 7 vào đầy đủ khung hình, giữ ảnh sắc nét,
  tránh lóa; phải thấy khung marker và raw x/z/yaw rồi mới thu số đo.

## Demo không cần in — tất cả là mô phỏng

- [Video dự phòng có HUD](demo_hud_render.mp4): 28 giây, 840 frame, 30 FPS;
  chữ mô phỏng và nguồn SYNTHETIC_RENDER được giữ rõ trong video.
- [Báo cáo kiểm tra mô phỏng](no_print_validation.md): 12/12 điều kiện đạt trên clip này;
  bám lại sau 4 frame khi đổi chỗ nhanh; các đoạn ID sai/che/mờ/lóa không nhận marker và về LOST.
- [Ảnh trạng thái cuối](no_print_preview.png).
- K và GT thuộc camera ảo. Không thay thế số đo thước hoặc độ chính xác camera thật.
- Ca P08 (z100/yaw20) trong bài test P4 vẫn còn lỗi lật yaw; xem [ca lỗi](failure_cases.md).

Chạy lại demo: `python run_demo.py --no-print`.

Các file làm việc ở gốc như `calib.npz`, `log.csv`, và thư mục `demo_assets/` vẫn được gitignore
để tránh trộn phiên hoặc vô tình ghi đè; các bản bàn giao chọn lọc ở trên được commit riêng.
