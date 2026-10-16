# Q&A: câu hỏi khó nhất cho từng vai

Mỗi người đọc kỹ phần của mình và đọc lướt phần của người khác. Nhóm KHÔNG in thẻ nên chưa có phép đo
vật lý. Số dưới đây lấy từ video marker render bằng camera ảo (`report/metrics_render.md`,
`report/validation_render.md`); khi nói phải kèm chữ "mô phỏng". Riêng độ trễ là đo trên webcam thật.

## P1 — Hưng (Hình học)

**1. Hiệu chuẩn camera để làm gì? RMS bao nhiêu là đủ?**
Hiệu chuẩn tìm tiêu cự theo pixel, tâm ảnh và hệ số méo ống kính bằng một bàn cờ có kích thước biết trước.
Không có các số này thì không đổi được pixel sang cm. RMS là độ lệch trung bình (pixel) giữa góc bàn cờ đo được
và góc chiếu lại từ mô hình. Mục tiêu là dưới 0.6 px. RMS nhỏ mới là điều kiện cần: vẫn phải kiểm bằng thước,
vì bản in sai kích thước thì RMS vẫn nhỏ nhưng cm sai. Nói thẳng: nhóm **chưa hiệu chuẩn webcam thật**.
Demo mô phỏng dùng K của camera ảo (biết chính xác); chạy webcam thì dùng K ước lượng từ HFOV 68 độ, nên cm chưa kiểm chứng.

**2. Vì sao một camera mà đo được khoảng cách?**
Vì biết trước cạnh marker là 6 cm. Ảnh marker càng nhỏ thì càng xa (u ≈ f·s/z). PnP giải tư thế 3D
khớp 4 góc marker với 4 điểm 3D đã biết. Hệ quả là sai số z tăng theo z²: ở xa, lệch 1 pixel tương ứng
nhiều cm hơn. Mô phỏng cho thấy đúng xu hướng: lỗi z trung bình 0.04 cm ở 30 cm, 0.15 cm ở 60 cm, 0.41 cm ở 100 cm.
Đó là giới hạn của thuật toán khi ảnh gần lý tưởng; webcam thật chắc chắn kém hơn.

**3. Khi nào hệ thống báo ambiguous? Nghiêng lớn thì sao?**
Marker phẳng ở xa hoặc ảnh nhỏ thì phép chiếu gần như affine: hai tư thế nghiêng ngược nhau cho ảnh gần giống nhau.
IPPE trả về cả hai nghiệm. Nếu lỗi chiếu lại chênh dưới 20% và hai nghiệm khác đáng kể về tư thế/chỉ dẫn
thì bật `ambiguous=True` và chuyển DEGRADED. Bản sửa P1 không báo khi hai nghiệm gần trùng và cùng hướng chỉnh;
vẫn báo nếu yaw lệch hơn 12 độ, khác hướng chỉnh hoặc x/z lệch hơn 1 cm. 12 độ là heuristic demo.
Nghiêng lớn (hơn 60 độ) KHÔNG bảo đảm lúc nào cũng ambiguous. Nó làm marker co ngắn, góc khó tìm, có thể mất
nhận diện hoặc reproj error tăng. Trong mô phỏng, yaw 75 độ ở 60 cm vẫn nhận tốt (lỗi yaw 1.4 độ, không ambiguous),
nên không nói "nghiêng lớn là hỏng".
Trên video render, mơ hồ thật xuất hiện ở z = 100 cm, yaw = 20 độ (yaw nhảy giữa +19 và −19). Còn nhìn thẳng thì hai nghiệm
chỉ lệch vài độ, mơ hồ vô hại (xem `report/failure_cases.md`, đây là dữ liệu render, không phải bằng chứng).

## P2 — Việt (Bất định, Thời gian)

**1. Q và R nghĩa là gì? Vì sao R tăng theo khoảng cách?**
R là độ nhiễu của phép đo, Q là mức "xe có thể đổi chuyển động bất ngờ". R lớn thì filter tin dự đoán hơn,
Q lớn thì filter bám đo hơn. R tăng theo (z/50)² vì sai số độ sâu của PnP tăng theo z² (xem P1 câu 2),
và tăng thêm khi reproj error lớn hoặc có `ambiguous`.

**2. Sigma trên màn hình có đáng tin không? Kiểm chứng thế nào?**
Kiểm bằng tỉ lệ lỗi thực (so với thước) nằm trong ±2 sigma. Nếu sigma đúng thì tỉ lệ này phải khoảng 95%.
Mô phỏng render: 100% (x, z) và 91.7% (yaw), phần thiếu nằm ở ca lật nghiệm P08. Phải nói thẳng: ảnh render ít
nhiễu nên sigma dễ "đủ rộng"; chỉ dữ liệu thật mới kiểm được sigma có đáng tin không.
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
Đo trên webcam thật của máy demo, 300 frame: p50 12.2 ms, p95 15.5 ms từ lúc grab frame tới vẽ xong HUD
(chỉ tính phần mềm, chưa gồm độ trễ cảm biến và màn hình). Filter chỉ chiếm dưới 0.1 ms.

**3. Vì sao hiển thị độ bất định thay vì một con số?**
"z = 32 cm" ở 30 cm và ở 1 m có độ tin rất khác nhau. Elip bất định và "±" cho người dùng hoặc robot biết
lúc nào nên dừng chờ, không cắm. Khi sigma vượt ngưỡng thì status là LOST và hệ thống không đưa chỉ dẫn.

## P4 — Linh/Đạo (Đo đạc, Bằng chứng)

**1. Số đo của nhóm lấy thế nào? Ground truth sai bao nhiêu?**
Không kịp in thẻ, nên nhóm dùng camera ảo: render marker ở đúng lưới 12 tư thế (z 30/60/100 cm, yaw 0/20/40 độ,
và vài điểm lệch ngang), thêm nhiễu và blur, rồi cho chạy qua đúng code ArUco/PnP/Kalman, mỗi tư thế 30 frame.
Ground truth là tư thế đặt trong mô hình nên biết chính xác. Đã chuẩn bị sẵn quy trình đo bằng thước
(`protocol.md`, `collect_gt.py`) cho bước tiếp theo.

**2. Kết quả chính là gì? Đã chứng minh tới đâu?**
Mô phỏng: MAE z ở 60 cm là 0.15 cm (p95 0.46 cm); Kalman giảm rung đứng yên khoảng 85%; 11/12 tư thế GOOD ≥ 90%;
ca lóa, mờ, che góc, sai ID đều về LOST, không đoán bừa. Tư thế P08 (100 cm, 20 độ) lật yaw: ca lỗi giữ lại.
Đã chứng minh: pipeline đúng hình học và phản ứng đúng với ca lỗi. CHƯA chứng minh: độ chính xác cm trên webcam thật.

**3. Con số impact có đáng tin không?**
Không phải số liệu Vin, mọi tham số đều là giả định ghi rõ trong `impact.md`. Giữa kịch bản thấp và cao
chênh khoảng 300 lần. Ý chính là công thức và tham số nhạy nhất (phút tiết kiệm mỗi lần sạc),
và tham số đó cần đo ở trạm thật. Demo dùng marker. Bước tiếp theo bắt buộc là detector học được
cho cổng sạc thật.
