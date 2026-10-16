# Charge-Port Alignment Assist: tài liệu ngữ cảnh chung

Vin Perception Hackathon, AI20k Track 4. Tài liệu này là nguồn sự thật duy nhất cho cả team 4 người và 4 agent. Mọi agent phải đọc hết trước khi làm bất cứ việc gì.

## 1. Ngữ cảnh hackathon

Đề bài: xây một demo computer vision hoặc robotics chạy thật cho một bài toán của hệ sinh thái Vin, chỉ bằng kiến thức Track 4. Thời gian build 120 phút, theo team, mỗi team demo 10 phút gồm demo và hỏi đáp.

Bốn điều mỗi demo bắt buộc có:

1. **Chạy thật** trên webcam, cảm biến hoặc sim. Có video quay sẵn để dự phòng.
2. **Dùng kiến thức của khóa**: chỉ rõ ít nhất 2 trụ cột và vị trí của chúng trong hệ thống.
3. **Một số đo, một ca lỗi**: đo một điều kiểm chứng được, và cho xem một trường hợp hệ thống làm sai kèm lý do.
4. **Dữ liệu an toàn**: thành viên tự đóng vai, không dùng dữ liệu thật của bệnh nhân hay sinh viên.

Bảy trụ cột Track 4: Học, Hình học, Bất định, Biểu diễn, Thời gian, Dữ liệu, Bằng chứng.

### Thang điểm (agent phải tối ưu theo đây)

| Tiêu chí | Điểm | Điều giám khảo muốn thấy |
| --- | --- | --- |
| Vận dụng kiến thức đã học | 25 | Từ 2 trụ cột trở lên dùng đúng bản chất, giải thích vì sao chọn cách đó |
| Demo chạy được | 25 | Chạy trực tiếp, ổn định, xử lý được đầu vào do giám khảo đưa tại chỗ |
| Độ hữu ích | 15 | Người dùng và nỗi đau cụ thể, gắn với một đơn vị Vin |
| Impact | 15 | Ước lượng tác động bằng con số, nêu đường mở rộng và rủi ro |
| Bằng chứng | 10 | Số đo kiểm chứng được, ít nhất một ca lỗi có phân tích nguyên nhân, nêu giới hạn |
| Trình bày và hỏi đáp | 10 | Kể mạch lạc 10 phút, mọi thành viên trả lời được |

Hòa điểm thì xét Demo chạy được trước, rồi Bằng chứng. Suy ra: ưu tiên số 1 là một vòng end-to-end chạy sớm và ổn định, ưu tiên số 2 là giải thích được thiết kế.

### Lịch (đồng hồ hackathon)

| Giờ | Việc |
| --- | --- |
| 0:00-0:15 | Chốt đề, tạo repo, đóng băng `contract.py`, mỗi người mở agent riêng |
| 0:15-0:55 | Làm song song, dùng dữ liệu giả để không chờ nhau |
| 0:55-1:15 | Ghép end-to-end. **Mốc kiểm tra 1:15**: phải có thứ chạy từ đầu vào tới đầu ra |
| 1:15-1:50 | Đo đạc, xử lý lỗi, làm chắc demo, thử đầu vào lạ |
| 1:50-2:15 | Đóng băng tính năng, quay video dự phòng, chốt slide, tập nói |
| 2:15 | Dừng code. 2:30 bắt đầu demo |

## 2. Đề tài đã chọn

**Charge-Port Alignment Assist** cho V-GREEN (trạm sạc), VinFast và Xanh SM.

Webcam laptop đóng vai đầu sạc hoặc cánh tay robot. Một tấm thẻ ArUco gắn ở cổng sạc xe. Hệ thống tính độ lệch ngang (cm), khoảng cách (cm) và góc lệch (độ) của cổng sạc so với đầu sạc, rồi đưa chỉ dẫn như "SANG PHAI 3 cm | TIEN 12 cm" kèm độ tin cậy. Người dùng: kỹ thuật viên hoặc tài xế tại trạm sạc, và về sau là robot sạc tự động.

**Vì sao chọn:** demo ổn định (ArUco rất bền), kiến thức hình học thật sự (hiệu chuẩn, PnP, đổi hệ tọa độ), có ground truth bằng thước nên số đo kiểm chứng được, giám khảo có thể cầm thẻ di chuyển tại chỗ, ít bị trùng với team khác.

**Trụ cột dùng và vị trí trong hệ thống:**

| Trụ cột | Nằm ở đâu |
| --- | --- |
| Hình học | Hiệu chuẩn camera, solvePnP, đổi hệ tọa độ (P1) |
| Bất định | Kalman filter, noise phụ thuộc khoảng cách, loại quan sát xấu, elip bất định trên UI (P2, P3) |
| Thời gian | Timestamp từng frame, độ trễ từng tầng, luôn xử lý frame mới nhất (P2, P3) |
| Dữ liệu | Log, replay, video dự phòng (P3, P4) |
| Bằng chứng | Thí nghiệm ground truth, ca lỗi có chủ đích, nêu giới hạn (P4) |

**Hạn chế phải nói thẳng khi trình bày:** demo dùng marker, còn thực tế cổng sạc không có marker nên về sau phải thay bằng detector học được. Đây là bước 1 của lộ trình mở rộng. Ground truth bằng thước dây và thước đo góc có sai số riêng (khoảng ±2 mm, ±2 độ).

## 3. Kiến trúc và quy ước

Luồng dữ liệu: `webcam -> capture thread (frame mới nhất) -> Perceiver (P1) -> Observation -> AlignmentKF (P2) -> State -> HUD (P3)`; log ghi cả raw lẫn filtered để P4 đánh giá.

**Hệ tọa độ** (đơn vị cm và độ): camera là đầu sạc, marker là cổng sạc.

- `x`: lệch ngang, dương nghĩa là cổng sạc nằm bên phải trục camera.
- `z`: khoảng cách dọc trục camera tới cổng sạc.
- `yaw`: góc xoay mặt marker quanh trục đứng, 0 là đối diện thẳng, dương là mặt marker quay về phía phải camera. Công thức đề xuất: `n = R[:,2]; if n[2] > 0: n = -n; yaw = degrees(atan2(n[0], -n[2]))`.
- P1 và P4 phải test cùng một tư thế để thống nhất dấu trước khi thu dữ liệu.

**Cấu trúc repo:**

```
contract.py        # đóng băng sau 0:15
calibrate.py       # P1
perception.py      # P1
filter.py          # P2
guidance.py        # P2
timing.py          # P2
synthetic.py       # P2 (dữ liệu giả)
main.py            # P3
collect_gt.py      # P4
evaluate.py        # P4
data/  report/     # P4
marker_7.png  checkerboard_9x6.png
TEAM.md  STATUS.md  ROLE.local (gitignore)
```

**Quy ước chung:**

- Chuỗi hiển thị trong OpenCV phải là tiếng Việt KHÔNG DẤU (cv2.putText không vẽ được dấu).
- Dùng `time.perf_counter()` cho mọi timestamp.
- Marker: `cv2.aruco.DICT_5X5_50`, id 7, cạnh 6.0 cm (đo lại cạnh thực tế sau khi in rồi ghi vào config).
- Bàn cờ hiệu chuẩn: 9x6 góc trong, ô 25 mm.
- OpenCV >= 4.7 (`cv2.aruco.ArucoDetector`). Cài: `pip install opencv-contrib-python numpy matplotlib pandas`.

## 4. contract.py (đóng băng sau 0:15)

Nếu repo chưa có `contract.py`, agent đầu tiên chạy phải tạo đúng nội dung dưới đây rồi commit trước khi làm việc khác.

```python
# contract.py
from dataclasses import dataclass, field
import numpy as np

@dataclass
class Observation:            # P1 -> P2
    t_capture: float          # perf_counter() lúc grab frame
    t_detect_done: float
    found: bool
    x_cm: float = 0.0
    z_cm: float = 0.0
    yaw_deg: float = 0.0
    reproj_err_px: float = 0.0
    ambiguous: bool = False   # hai nghiệm IPPE có reproj error gần nhau
    corners: "np.ndarray | None" = None   # (4,2) để vẽ
    rvec: "np.ndarray | None" = None
    tvec: "np.ndarray | None" = None

@dataclass
class State:                  # P2 -> P3
    t_capture: float
    x_cm: float; z_cm: float; yaw_deg: float
    sigma_x: float; sigma_z: float; sigma_yaw: float
    status: str               # "GOOD" | "DEGRADED" | "LOST"
    guidance: str             # ASCII không dấu, vd "SANG PHAI 3 cm | TIEN 12 cm"
    aligned: bool
    latency_ms: dict = field(default_factory=dict)  # capture/detect/filter/total

# Giao diện bắt buộc:
# perception.py: class Perceiver(calib_path, marker_id=7, marker_side_cm=6.0); process(frame, t_capture) -> Observation
# filter.py:     class AlignmentKF: update(obs) -> State; thuộc tính filter_enabled: bool
# main.py:       python main.py --source 0|file.mp4 [--replay log.csv]
```

## 5. Đội hình và giao thức khởi động cho agent

### Đội hình

Tên người cầm máy được điền khi có đội hình thật. Nếu để trống, agent sẽ hỏi.

| Vai | Tên người cầm máy | Trách nhiệm | File sở hữu |
| --- | --- | --- | --- |
| **P1** Hình học và Perception | Đinh Bảo Hưng - 2A202602524 | Hiệu chuẩphát hiện marker, ước lượng tư thế | `calibrate.py`, `perception.py` |
| **P2** Bất định, Thời gian, Guidance |Ngô Thế Việt - 2A202602594 | Kalman filter, đo độ trễ, sinh chỉ dẫn | `filter.py`, `guidance.py`, `timing.py`, `synthetic.py` |
| **P3** Demo app và UI (người ghép hệ thống) | Nguyễn Khánh Đô - 2A202602687 | Vòng lặp chính, HUD, record/replay, video dự phòng | `main.py` |
| **P4** Dữ liệu, Bằng chứng, Câu chuyện |Nguyễn Quang Đạo - 2A202602394 | Thí nghiệm, đánh giá, ca lỗi, impact, slide, Q&A | `collect_gt.py`, `evaluate.py`, `data/`, `report/`, `impact.md`, `Q&A.md` |

### Giao thức khi agent bắt đầu một phiên (làm theo đúng thứ tự)

1. **Đọc toàn bộ tài liệu này.**
2. **Kiểm tra `ROLE.local`** ở gốc repo. Nếu có, đọc tên và vai, chào một câu rồi nhảy tới bước 6.
3. **Hỏi đúng một câu:** "Bạn tên gì, người đang cầm máy này?" Không hỏi gì khác ở bước này.
4. **Xác định vai:** tra tên trong bảng Đội hình và trong `TEAM.md` (không phân biệt hoa thường, chấp nhận tên gọi tắt). Nếu khớp thì lấy vai đó. Nếu bảng chưa điền hoặc không khớp, liệt kê 4 vai mỗi vai một dòng và hỏi "Bạn đảm nhận vai nào?". Nếu vai đó đã có người trong `TEAM.md`, báo cho người dùng để cả nhóm giải quyết, không tự quyết.
5. **Ghi nhớ:** tạo `ROLE.local` (`name=...`, `role=P?`), thêm vào `.gitignore`, và thêm một dòng `tên -> vai` vào `TEAM.md`.
6. **Xác nhận một dòng rồi làm luôn:** "Chào \<tên>, bạn là \<vai>. Mình bắt đầu từ \<việc đầu tiên>." Không xin phép thêm. Chỉ hỏi lại khi bị chặn thật sự (thiếu webcam, lỗi cài đặt, quyết định ảnh hưởng người khác) và tối đa một câu mỗi lần.
7. **Chuẩn bị môi trường:** kiểm tra Python và `cv2.__version__` (phải >= 4.7). Kiểm tra `contract.py` có chưa, nếu chưa thì tạo từ mục 4 và commit.
8. **Làm đúng nhiệm vụ của vai mình ở mục 6.** Mọi việc đều có hạn thời gian và phương án dự phòng.

### Quy tắc cho mọi agent

- Chỉ sửa file thuộc vai của mình. Cần đổi file của người khác thì ghi yêu cầu vào `STATUS.md`, không tự sửa. P3 được viết adapter phía `main.py` để khớp giao diện.
- Không đổi `contract.py` sau 0:15 trừ khi cả nhóm đồng ý (ghi vào `STATUS.md`).
- Commit mỗi 15 phút. Trước khi ghép (0:55) và trước khi demo, `git pull` và đọc `STATUS.md`.
- Sau mỗi mốc, thêm một dòng vào `STATUS.md`: `[giờ] P? tên - việc xong - việc tiếp - vướng gì`.
- **Dạy kèm:** sau mỗi file chính, giải thích 3 đến 5 dòng bằng tiếng Việt đơn giản vì sao thiết kế như vậy và các tham số nghĩa là gì. Người dùng sẽ bị giám khảo hỏi trực tiếp, nên họ phải hiểu code của chính mình.
- Code ngắn, ít phụ thuộc, không thư viện nặng, không refactor ngoài phạm vi. Ưu tiên chạy được hơn đẹp.
- Không bịa số liệu thực tế của Vin. Con số nào chưa có nguồn phải ghi rõ là giả định.
- Không dùng dữ liệu thật của người khác. Chỉ thành viên team đóng vai.

## 6. Nhiệm vụ của từng vai

### P1: Hình học và Perception

Bạn là kỹ sư computer vision. Việc đầu tiên là `calibrate.py`.

1. **`calibrate.py`**: mở webcam, nhấn SPACE để lưu ảnh bàn cờ, khi đủ >= 15 ảnh nhấn C để chạy `cv2.calibrateCamera`. Lưu `calib.npz` (K, dist, rms, image\_size). In RMS reprojection error tổng và theo từng ảnh. Mục tiêu RMS < 0.6 px. Thêm chế độ `--approx-fov 68` tạo K ước lượng nếu hiệu chuẩn không ổn (fx ≈ width / (2·tan(HFOV/2))). Khóa focus webcam nếu driver cho phép và hiệu chuẩn bằng chính camera sẽ dùng demo.
2. **`perception.py`**: `Perceiver(calib_path, marker_id=7, marker_side_cm=6.0).process(frame, t_capture) -> Observation`.
   - Chỉ nhận đúng `marker_id`, bỏ qua id khác (giám khảo có thể đưa thẻ lạ).
   - `solvePnP` với `SOLVEPNP_IPPE_SQUARE`. Dùng `solvePnPGeneric` để lấy cả hai nghiệm; nếu reproj error hai nghiệm chênh dưới 20% thì `ambiguous=True`.
   - Tính `reproj_err_px` (trung bình 4 góc), đổi sang `x_cm`, `z_cm`, `yaw_deg` theo mục 3 và ghi công thức trong docstring.
   - Gán `t_detect_done = time.perf_counter()` ngay khi xong.
3. **Kiểm tra bằng thước:** đặt marker cách 50 cm, sai lệch z phải dưới 1 cm. Test một tư thế nghiêng cùng P4 để thống nhất dấu yaw.

**Xong khi:** `python test_perception.py` in x, z, yaw ở 10 Hz, đúng với thước. **Dự phòng:** quá 0:45 mà RMS vẫn lớn thì dùng `--approx-fov` và ghi vào `STATUS.md` để P4 nêu trong giới hạn.

**Giải thích được:** hiệu chuẩn là gì và RMS nói lên điều gì, vì sao PnP phẳng bị mơ hồ khi nghiêng nhiều, vì sao đo khoảng cách bằng kích thước marker đã biết.

### P2: Bất định, Thời gian, Guidance

Bạn là kỹ sư state estimation, numpy thuần, không dùng filterpy. Bắt đầu bằng `synthetic.py` để P3 và P4 có dữ liệu giả sớm.

1. **`synthetic.py`**: sinh chuỗi `Observation` giả (marker trượt từ z=80 về 15 cm, nhiễu Gaussian tăng theo z, vài frame `found=False`, vài outlier). Để mọi người test không cần webcam.
2. **`filter.py`**: `AlignmentKF.update(obs) -> State`.
   - State `[x, z, yaw, vx, vz, vyaw]`, vận tốc không đổi, `dt` lấy từ `t_capture`.
   - Noise đo R phụ thuộc quan sát: `sigma_x`, `sigma_z` tăng theo `z^2` (lỗi pixel thành lỗi độ sâu), tăng thêm khi `reproj_err_px` lớn. Ghi công thức trong comment.
   - Gating Mahalanobis (chi2, 3 bậc tự do, 99%): loại quan sát ngoài ngưỡng.
   - `ambiguous` hoặc bị loại thì `DEGRADED`. Mất marker quá 0.5 s hoặc sigma vượt ngưỡng thì `LOST`; `LOST` quá 2 s thì reset filter.
   - Cờ `filter_enabled`: tắt thì trả thẳng giá trị raw (để demo so raw và filtered).
3. **`guidance.py`**: từ State sinh chỉ dẫn ASCII không dấu và `aligned`. Dùng deadband và hysteresis để chữ không nhấp nháy: aligned khi `|x| < 1 cm`, `|yaw| < 5 độ`, `z <= stop_z`; thoát aligned khi vượt 1.5 lần ngưỡng. Không đưa chỉ dẫn khi `LOST`.
4. **`timing.py`**: ghi độ trễ theo tầng (capture-detect, detect-filter, filter-display), hàm `latency_report()` trả p50 và p95 ms, điền `State.latency_ms`.
5. **`test_filter.py`**: in độ lệch chuẩn raw và filtered ở tư thế đứng yên.

**Xong khi:** filter nhận dữ liệu giả và trả State hợp lý, std filtered thấp hơn raw rõ rệt, guidance không nhấp nháy. **Dự phòng:** nếu Mahalanobis gây rắc rối thì dùng ngưỡng cứng theo reproj error trước, cải thiện sau.

**Giải thích được:** Q và R nghĩa là gì, vì sao R tăng theo khoảng cách, sigma của filter có đáng tin không và kiểm chứng ra sao, vì sao cần deadband.

### P3: Demo app và UI (người ghép hệ thống)

Bạn là kỹ sư demo. Ban đầu chưa có `perception.py` và `filter.py` thật nên tạo stub tạm rồi thay bằng module thật khi P1 và P2 xong. Dùng cửa sổ OpenCV, KHÔNG dùng Streamlit.

1. **Vòng lặp chính** `main.py --source 0|file.mp4`: capture chạy thread riêng và chỉ giữ frame MỚI NHẤT (bỏ frame cũ để không tích lũy trễ). Gán `t_capture` lúc grab.
2. **HUD:** vẽ khung marker và trục 3D (`cv2.drawFrameAxes`), mũi tên hướng chỉnh, chỉ dẫn chữ lớn, viền xanh/vàng/đỏ theo GOOD/DEGRADED/LOST, FPS, latency p50, sigma (ví dụ `z = 32.1 +- 0.4 cm`).
3. **Minimap** nhìn từ trên xuống ở góc: vị trí cổng sạc so với đầu sạc kèm elip bất định theo `sigma_x`, `sigma_z`.
4. **Phím:** R bật/tắt ghi (`video.mp4` và `log.csv` gồm `t_capture`, raw x z yaw, filtered x z yaw, sigma, status, latency), F bật/tắt Kalman, SPACE đóng băng, Q thoát. Chế độ `--replay log.csv --source video.mp4` phát lại.
5. **Độ bền:** nguồn là file video thì hiện banner đỏ "VIDEO DA GHI - KHONG PHAI LIVE". Webcam mất thì tự chuyển sang video dự phòng, không crash. Không crash khi không thấy marker.
6. **Ghép hệ thống lúc 0:55:** `git pull`, thay stub bằng module thật, sửa khác biệt giao diện bằng adapter trong `main.py`, ghi vấn đề cần người khác sửa vào `STATUS.md`. Chạy thử trên đúng máy và phòng sẽ demo. Quay video dự phòng ở 2:00.

**Xong khi:** một lệnh chạy duy nhất, cửa sổ 1280x720 đọc được từ xa, chạy ổn định 10 phút liên tục.

**Giải thích được:** vì sao chỉ giữ frame mới nhất, độ trễ đến từ đâu, vì sao hiển thị bất định thay vì chỉ hiển thị một con số.

### P4: Dữ liệu, Bằng chứng, Câu chuyện

Bạn là kỹ sư đánh giá và làm tài liệu. Giai đoạn 1 chưa cần hệ thống thật.

**Giai đoạn 1 (0:15-0:55)**

1. **`protocol.md`**: quy trình đo ground truth bằng thước dây và thước đo góc. Lưới 12 tư thế: z in {30, 60, 100 cm} x yaw in {0, 20, 40 độ}, cộng vài điểm lệch ngang x in {-15, 0, +15 cm}. Ghi sai số của chính ground truth (±2 mm, ±2 độ) để nêu trong phần giới hạn. Chuẩn bị giấy đánh dấu lưới sẵn trên bàn.
2. **`collect_gt.py`**: nhập ground truth cho tư thế hiện tại, nhấn phím để chụp 30 Observation liên tiếp từ Perceiver và AlignmentKF, ghi `data/gt_runs.csv` (`pose_id, gt_x, gt_z, gt_yaw, est_raw_*, est_kf_*, sigma_*, reproj_err, status, t`).
3. **`evaluate.py`**: đọc CSV và xuất (a) bảng MAE và p95 theo khoảng cách và theo yaw, (b) biểu đồ lỗi theo z và theo yaw, (c) std đứng yên raw và filtered, (d) tỷ lệ lỗi thực nằm trong ±2 sigma, (e) latency p50 và p95. Lưu PNG vào `report/`. Test trước bằng dữ liệu giả của P2.

**Giai đoạn 2 (1:15-1:50):** thu số đo thật và 3 ca lỗi CÓ CHỦ ĐÍCH: lóa phản chiếu, yaw lớn hơn 60 độ làm lật nghiệm PnP, mờ do chuyển động hoặc che một góc. Mỗi ca viết 3 dòng: hiện tượng, nguyên nhân kỹ thuật, hệ thống phản ứng thế nào (status, `ambiguous`, reproj error).

**Giai đoạn 3 (1:50-2:15):**

- `impact.md`: công thức `Impact = số xe x số lần sạc/ngày x phút tiết kiệm mỗi lần x chi phí mỗi phút`. Mọi con số phải ghi rõ giả định hoặc nguồn. Nêu thêm đường mở rộng (robot sạc, thay marker bằng detector học được) và rủi ro (che khuất, thời tiết, an toàn khi cắm sạc).
- Slide outline 10 phút: 1 phút bài toán và người dùng, 4 phút demo, 2 phút số đo cùng ca lỗi cùng trụ cột cùng impact, 3 phút hỏi đáp.
- `Q&A.md`: 3 câu hỏi khó nhất cho mỗi vai (P1 hình học, P2 filter, P3 hệ thống, P4 đo đạc) kèm câu trả lời mẫu. Cho từng thành viên đọc phần của mình.

**Xong khi:** có bảng số đo, biểu đồ, 3 ca lỗi được giải thích, impact có giả định rõ, slide và Q&A.

**Giải thích được:** số đo lấy thế nào và ground truth có sai số gì, vì sao sigma đáng tin hay không, giới hạn của những gì đã chứng minh.

## 7. Kịch bản demo (4 phút trong 10 phút)

1. Chạy live: đưa thẻ lại gần thì chỉ dẫn đổi theo, ra xa thì độ bất định tăng.
2. Bấm F để chuyển raw và filtered, cho thấy filter giảm rung.
3. Mời giám khảo cầm thẻ di chuyển. Nếu họ đưa thẻ id khác, hệ thống bỏ qua.
4. Cố tình làm lóa hoặc nghiêng quá 60 độ: hệ thống chuyển DEGRADED và nhóm giải thích lý do. Đây là ca lỗi ăn điểm Bằng chứng.
5. Nếu hỏng thì chuyển sang video dự phòng và nói rõ đó là video.

## 8. Rủi ro và cách xử lý

| Rủi ro | Cách xử lý |
| --- | --- |
| Webcam tự lấy nét làm lệch hiệu chuẩn | Khóa focus nếu được, hiệu chuẩn bằng đúng camera dùng demo |
| Phòng demo khác ánh sáng | Thử sớm, in marker trên giấy mờ, tránh giấy bóng |
| API aruco khác phiên bản OpenCV | Mọi agent kiểm tra `cv2.__version__ >= 4.7` ở bước khởi động |
| Tích hợp muộn | Mọi module làm việc với dữ liệu giả của P2; P3 ghép lúc 0:55; mốc 1:15 là bắt buộc |
| Agent sinh code không ai hiểu | Mọi agent phải dạy kèm; 1:50 mỗi người đọc to phần của mình cho cả nhóm |
| Demo hỏng khi lên sân khấu | Video dự phòng quay lúc 2:00, `main.py` tự chuyển video khi mất webcam |

## 9. Chuẩn bị trước giờ G và checklist cuối

**Chuẩn bị:** in marker ArUco id 7 (cạnh khoảng 6 cm) và bàn cờ 9x6 dán lên bìa cứng phẳng, giấy mờ; mang thước dây, thước đo góc, băng dính; dán thẻ marker lên miếng bìa có tay cầm; cả 4 máy cài sẵn thư viện và chạy được `cv2.__version__`.

**Checklist trước khi lên demo:**

- Demo chạy trên đúng máy sẽ dùng, đã thử webcam ở phòng demo.
- Có video quay sẵn dự phòng.
- Có một con số đo, cả team nói được đo thế nào.
- Có ít nhất một ca lỗi kèm lý do.
- Chỉ ra được ít nhất 2 trụ cột và vị trí của chúng trong hệ thống.
- Không dùng dữ liệu thật của bệnh nhân hoặc sinh viên.
- Mỗi thành viên trả lời được vì sao team chọn cách làm này.
- Nói được người dùng là ai và họ được gì.
- Có một ước lượng tác động nếu triển khai ở Vin, dù chỉ là phép tính đơn giản.
