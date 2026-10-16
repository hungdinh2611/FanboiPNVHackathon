# P1 — Đinh Bảo Hưng

**Không kịp in:** chạy `python run_demo.py --no-print`. Xem [NO_PRINT_DEMO.md](NO_PRINT_DEMO.md)
để dùng video marker render qua ArUco/PnP thật, chạy lặp và có nhãn mô phỏng.

Phạm vi: `calibrate.py`, `perception.py`, `test_perception.py`, hai ảnh mẫu in.
Giao diện `contract.py` giữ nguyên. Không cần đợi filter hoặc main để thử P1.

## Chạy bản tích hợp P1/P2/P3/P4

```powershell
python run_demo.py
```

Lệnh này chạy `main.py` của P3 với perception P1 và Kalman P2. Nếu có `calib.npz`
thì dùng file đó. Nếu chưa có, tạo `calib_approx.npz` với HFOV **giả định 68°**,
ảnh 1280×720; HUD hiện cảnh báo `CALIB FOV UOC LUONG - CHUA KIEM CHUNG`.
Đây là chế độ dự phòng để demo chạy ngay, chưa xác nhận độ chính xác cm.
Không tự sửa module hoặc contract của người khác.

- R: ghi video + CSV, F: bật/tắt Kalman, SPACE: dừng/tiếp tục, Q: thoát.
- Demo không cần webcam: `python run_demo.py --synthetic` (hiện nhãn dữ liệu giả).
- Kiểm tra tự động: `python run_demo.py --check`.
- Kiểm webcam có giới hạn: `python run_demo.py --headless --max-frames 90`.
- Replay sau khi ghi: `python run_demo.py --source video.mp4 --replay log.csv`.
- Thu GT thật bằng công cụ P4: `python collect_gt.py --calib calib.npz`.
  Sau đó: `python evaluate.py --csv data/gt_runs.csv --out report`.

`test_integration.py` kiểm toàn luồng bằng ảnh ArUco render, marker sai ID/mất thẻ,
LOST, ghi/phát lại 48 frame cùng timestamp, camera lỗi chuyển video, và P4 sinh
360 dòng/12 tư thế rồi xuất báo cáo/biểu đồ có nhãn dữ liệu giả. Mọi file thử dùng
thư mục tạm; không ghi đè GT, báo cáo hay video của team.

P4 hiện đã bàn giao công cụ và báo cáo **tổng hợp**; còn cần hiệu chuẩn thật,
thu `data/gt_runs.csv`, ghi nhận ba ca lỗi, điền số thật trong Q&A và quay video live
dự phòng. Chưa có các mục này thì chưa đạt checklist nghiệm thu vật lý của hackathon.

## Chạy trên máy Hưng

Đã kiểm tra Python 3.10.4, OpenCV 4.9.0, NumPy 1.23.1.
Webcam 0 mở được, trả ảnh 1280×720. Driver **không hỗ trợ yêu cầu tắt autofocus**
qua OpenCV trên lần thử này; cần giữ khoảng lấy nét ổn định hoặc tắt trong phần mềm camera.
Chưa có đo thật bằng thước; kết quả self-test chỉ là dữ liệu tổng hợp.

```powershell
python test_perception.py --self-test
python calibrate.py --generate-patterns
python calibrate.py --source 0 --width 1280 --height 720
python test_perception.py --calib calib.npz --gt-z 50
```

Nếu máy khác thiếu thư viện: `python -m pip install opencv-contrib-python numpy`.

## In đúng kích thước

- `marker_7.png`: in toàn ảnh ở **80×80 mm**; cạnh đen bên trong là **60 mm**,
  phần trắng là vùng đệm, không tính vào `marker_side_cm`.
- `checkerboard_9x6.png`: 10×7 ô, tạo 9×6 góc trong. In toàn ảnh **300×225 mm**
  trên A3 để mỗi ô là 25 mm. Dùng A4 ngang thì cắt lề trắng, in riêng bàn cờ
  **250×175 mm**; đừng dùng “fit to page”.
- Đo lại bằng thước sau khi in, dán lên bìa phẳng, dùng giấy mờ.
  Nếu cạnh đen thực là 5.9 cm, chạy `--marker-side-cm 5.9`.
  Nếu ô bàn cờ khác 25 mm, truyền kích thước thực qua `--square-mm`.

## Hiệu chuẩn

Mở camera bằng lệnh trên; đưa toàn bộ bàn cờ vào ảnh. SPACE lưu một ảnh hợp lệ
vào `calibration_frames/<phiên>/`. Thay đổi vị trí, khoảng cách, nghiêng bàn cờ
và đưa bàn cờ ra các vùng rìa ảnh; ảnh gần trùng nhau bị bỏ qua. Đủ ít nhất 15 ảnh,
nhấn C để tính và lưu `calib.npz`; Q thoát.

File chứa `K`, `dist`, `rms`, `image_size=(width,height)` cùng RMS từng ảnh.
Mục tiêu RMS <0.6 px. RMS cao vẫn lưu nhưng in cảnh báo; cần chụp lại ảnh rõ,
đa dạng tư thế. Có thể hiệu chuẩn lại ảnh đã lưu:

```powershell
python calibrate.py --images (Get-ChildItem calibration_frames/<phien>/*.png).FullName
```

Nếu không kịp hiệu chuẩn, có phương án dự phòng (68° là **giả định**, chưa đo HFOV camera):

```powershell
python calibrate.py --approx-fov 68 --width 1280 --height 720 --output calib_approx.npz
python test_perception.py --calib calib_approx.npz --marker-side-cm 6
```

K ước lượng giả sử pixel vuông, tâm ảnh ở giữa và không méo; RMS được lưu là NaN,
không phải 0. Giao diện hiện cảnh báo. Nếu dùng dự phòng, ghi vào `STATUS.md` cho P4.
Hiệu chuẩn phải dùng đúng camera, chế độ ảnh và focus của buổi demo.

## Kiểm chứng bằng thước và dấu yaw với P4

Đặt mặt marker song song mặt camera, tâm gần trục camera, cách theo trục z **50 cm**;
đo từ vị trí ống kính camera và ghi nhận sai số đặt thước. Giữ thẻ đứng yên,
chạy `--gt-z 50`, chờ ít nhất 30 lần nhận diện rồi Q. Terminal in median z,
sai số tuyệt đối của median và std; chỉ PASS nếu sai số median <1 cm.
PASS này chỉ xác nhận tư thế đang đo, không chứng minh mọi khoảng cách đều chính xác.

Ảnh không lật gương: đưa marker sang bên phải camera phải làm x dương.
Với P4, xoay mặt marker để pháp tuyến hướng sang bên phải camera: yaw phải dương;
xoay ngược lại phải âm. Chụp và ghi nhận cùng tư thế trước khi P4 thu dữ liệu.

## Để Hưng giải thích khi hỏi đáp

`calibrate.py`:
1. Hiệu chuẩn tìm tiêu cự pixel, tâm ảnh và méo ống kính từ bàn cờ có hình học biết trước.
2. `K` là ma trận chiếu; `dist` sửa méo; `image_size` ràng buộc chế độ ảnh đã hiệu chuẩn.
3. RMS là căn trung bình bình phương khoảng cách pixel giữa góc đo và góc chiếu lại.
4. RMS nhỏ chưa đủ bảo đảm cm đúng: phải kiểm kích thước bản in và đo thật bằng thước.

`perception.py`:
1. Marker có cạnh biết trước giúp PnP suy ra khoảng cách và vị trí theo cm.
2. IPPE trả hai nghiệm; chọn nghiệm có lỗi chiếu lại trung bình nhỏ hơn, báo ambiguous
   nếu lỗi hai nghiệm chênh dưới 20%; chỉ đưa nghiệm hữu hạn có cả bốn góc trước camera.
3. Mơ hồ thường tăng khi ảnh marker nhỏ hoặc phép chiếu gần affine, ví dụ ở xa;
   góc nghiêng lớn còn gây co ngắn, che góc và mất chính xác khi tìm góc.
4. Trên OpenCV 4.9, các ca tổng hợp nằm ngang hoàn hảo làm IPPE gặp suy biến số.
   Chỉ đầu vào solver được cộng 0.001 px vào tọa độ y góc đầu để phá đối xứng;
   góc xuất ra và reprojection error vẫn tính trên quan sát gốc. Có regression test.

`test_perception.py`:
1. Đây là công cụ kiểm P1 độc lập, in x/z/yaw tối đa 10 Hz, vẽ cạnh và trục 3D.
2. `--self-test` thử hình học có ground truth tổng hợp, detector thật trên ảnh render,
   marker sai ID, mất marker, suy biến, méo ảnh, và hiệu chuẩn bàn cờ tổng hợp.
3. `--gt-z` dùng số đo do người cầm thước nhập; thẻ phải cố định trong lượt đo.
4. `--headless --max-frames 30` dùng kiểm nguồn ảnh có giới hạn mà không mở cửa sổ.

## Tích hợp cho P2/P3/P4

```python
from perception import Perceiver

perceiver = Perceiver('calib.npz', marker_id=7, marker_side_cm=6.0)
obs = perceiver.process(frame, t_capture)  # t_capture từ time.perf_counter()
```

`corners` là (4,2), `rvec/tvec` dùng được với `cv2.drawFrameAxes`.
P3 dùng `perceiver.K`, `perceiver.dist` để vẽ trục, cùng đơn vị cm.
K tự scale khi ảnh resize cùng tỉ lệ; khác tỉ lệ thì báo lỗi rõ để tránh sai cm.
Resize cùng tỉ lệ chỉ hợp lệ nếu ảnh không bị crop hoặc đổi FOV trong driver.
Không có marker đúng ID hoặc PnP không hợp lệ: `found=False`, timestamp vẫn đầy đủ.
Có hai bản in trùng ID trong khung: chọn bản lớn hơn và báo `ambiguous=True`.

Tài liệu gốc: [OpenCV PnP](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html),
[OpenCV calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html),
[tác giả IPPE giải thích hai nghiệm](https://github.com/tobycollins/IPPE).
