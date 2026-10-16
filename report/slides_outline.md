# Dàn ý trình bày 10 phút

| Phút | Slide/phần | Ai nói | Nội dung |
| --- | --- | --- | --- |
| 0:00-1:00 | 1. Bài toán | P4 | Tài xế Xanh SM và trạm V-GREEN: căn và cắm sạc tốn thời gian; robot sạc cần biết cổng sạc ở đâu và chắc đến đâu. Câu chốt: "đầu sạc biết cổng sạc ở đâu, lệch bao nhiêu cm, và biết khi nào mình không chắc". |
| 1:00-5:00 | 2. Demo live | P3 cầm máy, P1 cầm thẻ | (1) Đưa thẻ lại gần thì chỉ dẫn đổi, ra xa thì elip bất định to ra. (2) Bấm F so raw và filtered. (3) Mời giám khảo cầm thẻ; thẻ id khác thì hệ thống bỏ qua. (4) Lóa hoặc nghiêng hơn 60 độ: DEGRADED, P1 giải thích. Hỏng thì chuyển video dự phòng và nói rõ là video. |
| 5:00-5:30 | 3. Kiến trúc và trụ cột | P2 | Sơ đồ webcam → Perceiver → Observation → Kalman → State → HUD. Hình học: hiệu chuẩn, PnP. Bất định: Kalman, R theo z², gating. Thời gian: frame mới nhất, latency. Bằng chứng: GT bằng thước. |
| 5:30-6:15 | 4. Số đo | P4 | Bảng MAE/p95 theo z (từ `metrics.md`), biểu đồ `error_vs_z.png`, độ rung raw và KF, tỉ lệ ±2 sigma, latency p50/p95. |
| 6:15-6:40 | 5. Ca lỗi và giới hạn | P4 | Ca yaw lớn hơn 60 độ hoặc lóa: hiện tượng, nguyên nhân, phản ứng. Giới hạn: marker, một camera, z 30-100 cm, sai số thước. |
| 6:40-7:00 | 6. Impact và lộ trình | P4 | Công thức, kịch bản cơ sở (giả định), lộ trình: thay marker bằng detector học được, rồi gắn vào robot sạc. |
| 7:00-10:00 | Hỏi đáp | Cả nhóm | Mỗi người trả lời câu về phần mình (`Q&A.md`). |

Bộ slide (10 slide, ô [__] chờ số đo thật): https://claude.ai/artifact/K2e6JWHpJS3EnrS1EoBcVD — chủ sở hữu cần chia sẻ từ menu Share thì người khác mới mở được.
