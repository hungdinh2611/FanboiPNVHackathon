# Demo không cần in — dùng ngay

```powershell
python run_demo.py --no-print
```

Video mô phỏng chạy lặp đến khi nhấn **Q**. **F** so raw/Kalman, **SPACE** dừng/tiếp tục,
**R** ghi video và CSV. Không cần webcam, giấy in hay bàn cờ. Lần đầu tự tạo dữ liệu
trong `demo_assets/`; các máy khác chỉ cần pull code và chạy cùng lệnh.

Đây là **xử lý ảnh thật trên đầu vào render**: video → ArUco → hai nghiệm IPPE →
Kalman → HUD. Không gán sẵn Observation. K và ground truth thuộc camera ảo;
không tuyên bố đây là hiệu chuẩn camera thật hay sai số đo bằng thước.

## Kịch bản 28 giây, tự lặp

| Giây | Việc trên màn hình | Giải thích khi nói |
| --- | --- | --- |
| 0–6 | Thẻ tiến từ 80 cm về 14 cm, giảm lệch x/yaw | Kích thước marker biết trước giúp PnP đổi pixel thành vị trí. |
| 6–9 | Đứng yên, DA CAN CHINH | F để so raw và Kalman; SPACE để giải thích sigma. |
| 9–12 | Thẻ đổi chỗ nhanh | Filter bám lại sau 5 quan sát chất lượng tốt và nhất quán, không chờ 2 giây. |
| 12–14 | Thẻ ID 8 | Bỏ qua ID sai; hết 0.5 s thì LOST. |
| 14–16 | Che góc | Không nhận đủ khung ArUco; không đoán vị trí mới. |
| 16–18 | Mờ chuyển động | Các ô mã bị trộn, detector không giải được ID. |
| 18–20 | Lóa | Vùng trắng làm mất thông tin mã. |
| 20–23 | Xa, nghiêng | Giải thích giới hạn PnP phẳng. Không mặc định mọi frame đều ambiguous. |
| 23–28 | Căn chỉnh lại | Kết thúc tại vị trí chuẩn; video tự lặp. |

Mở đầu demo: **“Vì chưa kịp in marker, nhóm dùng camera ảo với marker render.
Thuật toán ArUco, PnP và Kalman vẫn chạy trực tiếp trên từng frame; các số GT đến
từ mô hình mô phỏng, chưa phải phép đo vật lý.”**

## Kiểm tra và tạo video dự phòng

```powershell
python run_demo.py --check
python run_demo.py --no-print --once --headless --record --video-out demo_assets/final_recording_render.mp4 --log-out demo_assets/final_log_render.csv --snapshot demo_assets/final_preview_render.png
python verify_demo.py --export-video
```

Recorder không ghi đè: nếu video hoặc log đã tồn tại, app tự thêm ngày giờ vào
cả hai tên file. Nếu trùng cả ngày giờ, thêm số thứ tự. Xem tên thực trong terminal
hoặc dòng DANG GHI / DA LUU rồi truyền đúng cặp qua `verify_demo.py --log ... --video ...`.

- `demo_assets/validation_render.md`: báo cáo kiểm tra đúng ID, LOST, bám lại và căn chỉnh.
- `demo_assets/demo_hud_render.mp4`: video đã ghép HUD, mở bằng trình phát bình thường khi app lỗi.
- `demo_assets/final_preview_render.png`: ảnh trạng thái cuối.
- Các file trong `demo_assets/` là mô phỏng, không trộn vào `data/gt_runs.csv` thật.

Muốn chạy webcam: `python run_demo.py`. Có thể mở `marker_7.png` trên màn hình điện thoại
và đưa trước webcam; đo cạnh đen thực trên màn hình rồi truyền `--marker-side-cm`.
Camera dùng FOV ước lượng khi chưa có `calib.npz`, nên cm chưa được kiểm chứng.

## Phần sửa đã hoàn tất

- P1 bỏ báo mơ hồ với hai nghiệm tương đương về chỉ dẫn; vẫn báo khi yaw chênh >12°,
  khác hướng chỉnh hoặc x/z khác >1 cm. 12° là heuristic demo, không phải khoảng tin cậy.
- P2 khởi tạo lại khi 5 quan sát liên tiếp bị gate nhưng chất lượng tốt và nhất quán.
  Mất marker, ambiguous, lỗi chiếu lại cao hoặc đứt thời gian sẽ ngắt chuỗi này.
- Test marker ID tương thích kết quả dạng `(1,)` hoặc `(1,1)` của OpenCV.
- Không đổi `contract.py`. Theo ủy quyền của Hưng, đã sửa phần tích hợp P2/P3 liên quan.

## Hưng cần giải thích được

`prepare_demo.py`: tạo từng ảnh marker bằng phép chiếu camera, thêm nhiễu/che/mờ/lóa.
K là tham số camera ảo đã biết; khoảng cách GT được đặt trong mô hình, không đo ngoài đời.
Nhãn mô phỏng nằm trong ảnh gốc nên cả video ghi lại cũng giữ nhãn.

`filter.py`: một outlier vẫn bị loại; chỉ chuỗi 5 phép đo mới nhất quán mới cho phép bám lại.
Quan sát ambiguous hoặc mờ/lỗi cao không được dùng để kích hoạt khởi tạo lại.

`verify_demo.py`: ghép log với GT bằng frame_index, kiểm cả ca âm tính và căn chỉnh cuối.
Video HUD xuất lại giữ nguyên kết quả đã ghi; không tính lại filter hoặc gọi đó là webcam live.
