# Ca lỗi

> Phần A lấy từ video marker **RENDER** (`python test_p4_e2e.py`, K ước lượng HFOV 68 độ, nhiễu Gaussian và blur nhẹ).
> Phần này KHÔNG phải bằng chứng thật: nó cho biết nên tìm gì khi đo bằng thẻ in. Phần B điền sau khi thu bằng
> `collect_gt.py` (nhấn K), số lấy từ bảng "Phan bo status va ca loi" trong `report/metrics.md`.

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

## B. Ca lỗi trên thẻ in thật (điền sau khi thu)

| Nhãn | Hiện tượng | Nguyên nhân kỹ thuật | Phản ứng (found / ambiguous / reproj / status) |
| --- | --- | --- | --- |
| fail_glare | `[điền]` | `[điền]` | `[điền]` |
| fail_yaw70 | `[điền]` | `[điền]` | `[điền]` |
| fail_occlude hoặc fail_blur | `[điền]` | `[điền]` | `[điền]` |
