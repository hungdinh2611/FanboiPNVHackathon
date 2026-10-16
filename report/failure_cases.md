# Ca lỗi

> **Toàn bộ số trong file này là MÔ PHỎNG**: video marker render bằng camera ảo (K và ground truth đã biết),
> ArUco/PnP/Kalman chạy thật trên từng frame. Nhóm không in thẻ nên **chưa có phép đo vật lý**; không suy các số này
> thành độ chính xác của webcam thật. Nguồn: `report/metrics_render.md` (`test_p4_e2e.py`) và
> `report/validation_render.md` (`verify_demo.py`).

## A. Phát hiện khi kiểm thử bằng video render

### A1. Lật nghiệm PnP ở xa, nghiêng vừa (z = 100 cm, yaw = 20 độ)
- **Hiện tượng:** yaw raw nhảy qua lại giữa +19 và −19 độ dù thẻ đứng yên; sai số yaw raw (trung vị) 38 độ. x và z vẫn đúng (lỗi z 0.5 cm).
- **Nguyên nhân:** marker chỉ còn khoảng 57 px, phép chiếu gần affine nên hai nghiệm IPPE (nghiêng trái/phải) có lỗi
  chiếu lại gần bằng nhau. Nhiễu pixel quyết định nghiệm nào thắng.
- **Hệ thống phản ứng:** 60% frame bị đánh `ambiguous`, status DEGRADED khoảng 77%, không xác nhận "đã căn chỉnh".
  Giới hạn: khoảng 40% frame lật mà KHÔNG bị đánh dấu, nên vẫn có frame GOOD với yaw sai. Cách giảm: tiến lại gần
  (dưới 60 cm, không thấy ca này trong lưới) hoặc marker to hơn.

### A2. Che một góc thẻ
- **Hiện tượng:** marker biến mất hoàn toàn (`found` 0%).
- **Nguyên nhân:** detector ArUco cần đủ 4 cạnh của khung đen để tìm tứ giác; mất một góc thì không còn ứng viên.
- **Hệ thống phản ứng:** DEGRADED rồi LOST sau 0.5 s, chỉ dẫn "MAT DAU MARKER - GIU NGUYEN", không đoán bừa.

### A3. Báo động giả khi nhìn thẳng (lỗi phần mềm, đã đề xuất sửa)
- **Hiện tượng:** thẻ đối diện thẳng camera (yaw = 0) bị đánh `ambiguous` ở 17–80% số frame, nên status DEGRADED
  và hệ thống không bao giờ báo "DA CAN CHINH" đúng ở tư thế quan trọng nhất.
- **Nguyên nhân:** khi nhìn thẳng, hai nghiệm IPPE gần như trùng nhau (lệch 2–5 độ yaw), nên lỗi chiếu lại của chúng
  chênh dưới 20%. Mơ hồ ở đây vô hại vì chọn nghiệm nào cũng đúng.
- **Đề xuất (P1):** chỉ báo `ambiguous` khi hai nghiệm còn lệch yaw hơn 12 độ
  (`report/proposals/p1_ambiguity_and_opencv5_test.patch`). Đo trên video render: ca nhìn thẳng còn 0% ambiguous,
  ca A1 vẫn được đánh dấu.

### A4. Kalman "đứng hình" 2 s khi thẻ đổi chỗ nhanh (lỗi phần mềm, đã đề xuất sửa)
- **Hiện tượng:** thẻ dịch đột ngột (yaw 0 → 20 độ, hoặc z 30 → 60 cm) thì filter giữ giá trị cũ, báo LOST dù vẫn
  thấy marker; 2 s sau mới reset. Trên lưới render, chỉ 4/12 tư thế đạt GOOD ≥ 90%.
- **Nguyên nhân:** gating Mahalanobis loại mọi phép đo xa dự đoán, kể cả khi chính dự đoán đã sai.
- **Đề xuất (P2):** nếu 5 frame liên tiếp bị loại nhưng nhất quán với nhau (lệch < 3 sigma đo) thì khởi tạo lại
  tại phép đo (`report/proposals/p2_reinit_after_consistent_gating.patch`). Outlier lẻ vẫn bị loại, nghiệm lật
  qua lại không kích hoạt. Đo trên video render: 11/12 tư thế GOOD 100%; test P2 vẫn PASS.

## B. Ca lỗi có chủ đích trong video demo không in (mô phỏng)

Kịch bản 28 giây của `run_demo.py --no-print`, 840 frame, kiểm bằng `verify_demo.py`: 12/12 mục PASS.

| Ca | Hiện tượng | Nguyên nhân kỹ thuật | Hệ thống phản ứng |
| --- | --- | --- | --- |
| Lóa (glare) | Vùng trắng phủ lên mã, 60/60 frame không nhận | Mất tương phản đen/trắng của các ô mã, detector không giải được ID | `found` 0%, chuyển LOST, không chỉ dẫn |
| Mờ chuyển động | 60/60 frame không nhận | Các ô mã bị trộn, cạnh khung đen không còn sắc | `found` 0%, LOST |
| Che một góc | 60/60 frame không nhận | Detector cần đủ tứ giác khung đen | `found` 0%, LOST |
| Thẻ ID 8 (sai ID) | Thấy marker nhưng bỏ qua | Chỉ nhận `marker_id=7` | `found` 0%, LOST, không bị đánh lừa |
| Đổi chỗ nhanh | Kalman bám lại sau 4 frame | Khởi tạo lại sau chuỗi phép đo tốt và nhất quán | GOOD 95.6% trong đoạn |
| Xa và nghiêng vừa (P08, z100 yaw20) | Yaw lật ±19 độ | Hai nghiệm IPPE gần bằng nhau khi marker nhỏ | ambiguous 60%, GOOD chỉ 23% (vẫn có frame sai mà GOOD: giới hạn) |

Nhận xét trung thực: trong mô phỏng, lóa và mờ làm mất marker hoàn toàn; ngoài đời có thể chỉ làm tăng reproj error
mà vẫn nhận (nguy hiểm hơn). Cần kiểm lại khi có thẻ thật.

## C. Cập nhật bản không cần in (Hưng ủy quyền sửa tích hợp)

Hai đề xuất A3/A4 đã được P1 áp dụng, có bổ sung kiểm soát: giữ ambiguous khi hai
nghiệm khác hướng chỉnh hoặc vượt các ngưỡng mặc định/hysteresis khác nhau; chỉ
khởi tạo lại KF từ chuỗi 5 quan sát liên tiếp chất lượng tốt, không ambiguous.
Quan sát mất, lỗi cao hoặc đứt thời gian ngắt chuỗi. Contract không đổi.

Chạy lại `test_p4_e2e.py` trên OpenCV 4.9: raw PASS các tư thế ổn định đã định nghĩa;
11/12 tư thế đạt GOOD >=90%. **P08 vẫn lỗi yaw** (median raw khoảng 38.18°, ambiguous
60%, GOOD 23%). Đây là lỗi mô phỏng còn giữ nguyên để giải thích giới hạn, không loại bỏ
khỏi báo cáo và không suy thành độ chính xác camera thật.

Bản chạy không in: `python run_demo.py --no-print`. Có thêm các đoạn che góc, mờ
và lóa được tạo có chủ đích trong ảnh; số kiểm tra lưu ở
`demo_assets/validation_render.md`, tất cả đều gắn nhãn mô phỏng. Phần B vẫn chưa
được đo trên thẻ in thật.
