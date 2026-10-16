# Quy trình đo ground truth (P4)

Mục tiêu: so số đo của hệ thống (raw và Kalman) với số đo bằng thước, trên một lưới tư thế cố định,
để có bảng MAE/p95, độ rung đứng yên, độ tin của sigma và độ trễ.

## Dụng cụ

- Webcam laptop đúng máy demo, đúng chế độ 1280x720, đúng `calib.npz` của P1.
- Thẻ marker ArUco id 7, cạnh đen đo lại sau khi in (ghi vào `--marker-side-cm`).
- Thước dây (độ chia 1 mm), thước đo góc (độ chia 1 độ), băng dính, giấy A3 kẻ lưới.
- Giá đỡ thẻ đứng thẳng (hộp/sách + băng dính) để thẻ KHÔNG rung khi chụp.

## Hệ tọa độ (giống contract và P1)

- Gốc: tâm ống kính webcam. `z` dọc trục camera, `x` ngang, dương là bên phải camera (ảnh không lật gương).
- `yaw`: 0 là mặt thẻ đối diện thẳng camera; dương là pháp tuyến mặt thẻ quay về phía PHẢI camera.
- Điểm đo trên thẻ: tâm hình vuông đen.

## Bước 0: thống nhất dấu với P1 (bắt buộc, trước khi thu)

1. Chạy `python collect_gt.py --calib calib.npz`.
2. Đưa thẻ sang bên phải camera: `raw x` phải dương.
3. Xoay thẻ để pháp tuyến hướng sang phải camera khoảng 30 độ: `raw yaw` phải dương.
4. Nếu sai dấu: dừng, báo P1, ghi vào `STATUS.md`. Không thu dữ liệu khi dấu chưa thống nhất.

## Chuẩn bị bàn đo

1. Dán giấy lưới lên bàn. Kẻ trục z bằng thước từ điểm ngay dưới ống kính, vuông góc mặt màn hình.
2. Đánh dấu vạch z = 30, 60, 100 cm trên trục; tại z = 60 và z = 100 đánh dấu x = -15, +15 cm.
3. Tâm thẻ đặt cùng độ cao với ống kính (để `y` gần 0, tránh lẫn sai số dọc vào z).
4. Đo z theo trục camera (khoảng cách vuông góc), không phải đường chéo.

## Lưới 12 tư thế (đã cài sẵn trong `collect_gt.py`)

| pose | x (cm) | z (cm) | yaw (độ) |
| --- | --- | --- | --- |
| P01-P03 | 0 | 30 | 0 / 20 / 40 |
| P04-P06 | 0 | 60 | 0 / 20 / 40 |
| P07-P09 | 0 | 100 | 0 / 20 / 40 |
| P10 | -15 | 60 | 0 |
| P11 | +15 | 60 | 0 |
| P12 | +15 | 100 | 0 |

Nếu đặt thực tế lệch so với lưới (ví dụ z thực là 59.6), nhấn E trong `collect_gt.py` và nhập số đo thật.
Ground truth là số ĐO ĐƯỢC, không phải số dự định.

## Thu dữ liệu mỗi tư thế

1. Đặt thẻ, buông tay, chờ 2 s cho thẻ hết rung và Kalman hội tụ.
2. Nhấn SPACE: chương trình lấy 30 Observation liên tiếp (raw + Kalman + sigma + latency), ghi `data/gt_runs.csv`.
3. Nhấn N sang tư thế tiếp theo. Một người đặt thẻ, một người bấm máy và đọc to số.

## Ca lỗi có chủ đích (giai đoạn 2)

Nhấn K, gõ nhãn ca lỗi, đặt thẻ đúng tư thế ghi GT rồi nhấn SPACE như bình thường. Nhãn gợi ý:

- `fail_glare`: đèn flash điện thoại chiếu vào thẻ tạo vệt lóa.
- `fail_yaw70`: yaw khoảng 70 độ, quan sát lật nghiệm PnP / `ambiguous`.
- `fail_blur`: lắc thẻ nhanh khi chụp (mờ chuyển động).
- `fail_occlude`: ngón tay che một góc thẻ.

Mỗi ca ghi 3 dòng vào `report/failure_cases.md`: hiện tượng, nguyên nhân kỹ thuật, hệ thống phản ứng thế nào
(status, `ambiguous`, reproj error) — `evaluate.py` in sẵn số liệu cho từng nhãn.

## Sai số của chính ground truth (nêu ở phần giới hạn)

- Thước dây: khoảng ±2 mm khi đặt tâm thẻ, cộng sai số xác định vị trí tâm quang học ống kính (ước lượng
  thêm vài mm, chưa đo được). Thước đo góc: khoảng ±2 độ.
- Vì vậy lỗi đo nhỏ hơn khoảng 0.3 cm hoặc 2 độ là KHÔNG phân biệt được với sai số ground truth.
- Lưới chỉ phủ z 30-100 cm, yaw 0-40 độ, một điều kiện ánh sáng, một camera. Không suy rộng ra ngoài vùng này.
