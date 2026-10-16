# Q&A: câu hỏi khó nhất cho từng vai

Mỗi người đọc kỹ phần của mình và đọc lướt phần của người khác. Chỗ ghi `[điền số thật]` thì thay bằng số
trong `report/metrics.md` sau khi thu dữ liệu thật. Không đọc số từ `metrics_synthetic.md`.

## P1 — Hưng (Hình học)

**1. Hiệu chuẩn camera để làm gì? RMS bao nhiêu là đủ?**
Hiệu chuẩn tìm tiêu cự theo pixel, tâm ảnh và hệ số méo ống kính bằng một bàn cờ có kích thước biết trước.
Không có các số này thì không đổi được pixel sang cm. RMS là độ lệch trung bình (pixel) giữa góc bàn cờ đo được
và góc chiếu lại từ mô hình. Mục tiêu là dưới 0.6 px. RMS nhỏ mới là điều kiện cần: vẫn phải kiểm bằng thước,
vì bản in sai kích thước thì RMS vẫn nhỏ nhưng cm sai. Kết quả của mình: `[RMS thật]`.

**2. Vì sao một camera mà đo được khoảng cách?**
Vì biết trước cạnh marker là 6 cm. Ảnh marker càng nhỏ thì càng xa (u ≈ f·s/z). PnP giải tư thế 3D
khớp 4 góc marker với 4 điểm 3D đã biết. Hệ quả là sai số z tăng theo z²: ở xa, lệch 1 pixel tương ứng
nhiều cm hơn. Bảng lỗi theo z cho thấy điều đó: `[điền số thật]`.

**3. Khi nào hệ thống báo ambiguous? Nghiêng lớn thì sao?**
Marker phẳng ở xa hoặc ảnh nhỏ thì phép chiếu gần như affine: hai tư thế nghiêng ngược nhau cho ảnh gần giống nhau.
IPPE trả về cả hai nghiệm. Nếu lỗi chiếu lại chênh dưới 20% và hai nghiệm khác đáng kể về tư thế/chỉ dẫn
thì bật `ambiguous=True` và chuyển DEGRADED. Bản sửa P1 không báo khi hai nghiệm gần trùng và cùng hướng chỉnh;
vẫn báo nếu yaw lệch hơn 12 độ, khác hướng chỉnh hoặc x/z lệch hơn 1 cm. 12 độ là heuristic demo.
Nghiêng lớn (hơn 60 độ) KHÔNG bảo đảm lúc nào cũng ambiguous. Nó làm marker co ngắn, góc khó tìm, có thể mất
nhận diện hoặc reproj error tăng. Chỉ nói phản ứng đã thấy trên ca lỗi thật: `[điền từ bảng ca lỗi metrics.md]`.
Trên video render, mơ hồ thật xuất hiện ở z = 100 cm, yaw = 20 độ (yaw nhảy giữa +19 và −19). Còn nhìn thẳng thì hai nghiệm
chỉ lệch vài độ, mơ hồ vô hại (xem `report/failure_cases.md`, đây là dữ liệu render, không phải bằng chứng).

## P2 — Việt (Bất định, Thời gian)

**1. Q và R nghĩa là gì? Vì sao R tăng theo khoảng cách?**
R là độ nhiễu của phép đo, Q là mức "xe có thể đổi chuyển động bất ngờ". R lớn thì filter tin dự đoán hơn,
Q lớn thì filter bám đo hơn. R tăng theo (z/50)² vì sai số độ sâu của PnP tăng theo z² (xem P1 câu 2),
và tăng thêm khi reproj error lớn hoặc có `ambiguous`.

**2. Sigma trên màn hình có đáng tin không? Kiểm chứng thế nào?**
Kiểm bằng tỉ lệ lỗi thực (so với thước) nằm trong ±2 sigma. Nếu sigma đúng thì tỉ lệ này phải khoảng 95%.
Số thật: `[điền từ mục (d) metrics.md]`. Phải nói thẳng: trên dữ liệu giả tỉ lệ đẹp là hiển nhiên,
vì dữ liệu giả được sinh bằng gần đúng công thức nhiễu của R. Chỉ số trên dữ liệu thật mới có giá trị.
Sigma cũng không bắt được sai số hệ thống (hiệu chuẩn lệch, in sai kích thước marker).

**3. Vì sao cần deadband và hysteresis cho chỉ dẫn?**
Gần ngưỡng, nhiễu làm giá trị dao động qua lại, chữ sẽ nhấp nháy "SANG PHAI / SANG TRAI".
Vào trạng thái căn chỉnh khi |x| < 1 cm, nhưng chỉ thoát khi vượt 1.5 lần ngưỡng.
Khoảng đệm đó giữ chữ đứng yên.

## P3 — Đô (Hệ thống)

**1. Vì sao chỉ giữ frame mới nhất?**
Nếu xử lý chậm hơn tốc độ camera mà vẫn xếp hàng mọi frame thì độ trễ tăng dần không giới hạn,
màn hình chiếu chuyện đã xảy ra vài giây trước. Bỏ frame cũ thì độ trễ luôn chỉ khoảng một frame
cộng thời gian xử lý. Với cánh tay robot, dữ liệu cũ nguy hiểm hơn thiếu dữ liệu.

**2. Độ trễ đến từ đâu? Bao nhiêu?**
Gồm chờ camera, phát hiện marker cộng PnP, filter, rồi vẽ. Mỗi tầng được gắn timestamp bằng `perf_counter`.
Số thật (p50/p95): `[điền số thật]`. Phần lớn nằm ở camera và detect. Filter chỉ chiếm dưới 1 ms.

**3. Vì sao hiển thị độ bất định thay vì một con số?**
"z = 32 cm" ở 30 cm và ở 1 m có độ tin rất khác nhau. Elip bất định và "±" cho người dùng hoặc robot biết
lúc nào nên dừng chờ, không cắm. Khi sigma vượt ngưỡng thì status là LOST và hệ thống không đưa chỉ dẫn.

## P4 — Linh/Đạo (Đo đạc, Bằng chứng)

**1. Số đo của nhóm lấy thế nào? Ground truth sai bao nhiêu?**
Đặt thẻ trên lưới 12 tư thế kẻ sẵn: z 30/60/100 cm, yaw 0/20/40 độ, và vài điểm lệch ngang.
Đo bằng thước dây và thước đo góc, mỗi tư thế lấy 30 frame (`protocol.md`). Thước có sai số khoảng ±2 mm,
thước góc khoảng ±2 độ. Thêm vài mm do không biết chính xác tâm quang học ống kính nằm đâu.
Lỗi nhỏ hơn mức đó thì nhóm không khẳng định được.

**2. Kết quả chính là gì? Đã chứng minh tới đâu?**
MAE z ở 60 cm là `[số]` cm, p95 là `[số]` cm. Kalman giảm rung đứng yên `[số]`%.
Giới hạn: một camera, một phòng, một điều kiện ánh sáng, z 30-100 cm, yaw tối đa 40 độ.
Ngoài vùng đó nhóm không khẳng định. Lưới chỉ có 12 tư thế, chưa phải phép đo thống kê lớn.

**3. Con số impact có đáng tin không?**
Không phải số liệu Vin, mọi tham số đều là giả định ghi rõ trong `impact.md`. Giữa kịch bản thấp và cao
chênh khoảng 300 lần. Ý chính là công thức và tham số nhạy nhất (phút tiết kiệm mỗi lần sạc),
và tham số đó cần đo ở trạm thật. Demo dùng marker. Bước tiếp theo bắt buộc là detector học được
cho cổng sạc thật.
