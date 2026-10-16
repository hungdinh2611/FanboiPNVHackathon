# Charge-Port Alignment Assist — nguồn học

## Knowledge

- [OpenCV: Camera Calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html)
  K, distortion, góc bàn cờ và hiệu chuẩn. Dùng khi giải thích checkerboard/RMS.
- [OpenCV: Detection of ArUco Markers](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html)
  Dictionary, ID, bốn góc marker. Dùng khi giải thích phát hiện mốc.
- [OpenCV: Perspective-n-Point](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html)
  Đổi điểm 3D sang camera, IPPE_SQUARE và hai nghiệm. Dùng cho hình học tư thế.
- [OpenCV: KalmanFilter](https://docs.opencv.org/4.x/dd/d6a/classcv_1_1KalmanFilter.html)
  Predict/correct, Q/R/P. Repo triển khai bằng NumPy, không gọi lớp này.
- [Kết quả đã bàn giao](report/RESULTS_STATUS.md)
  Nguồn của số liệu riêng team; phải đọc trước khi nói về độ chính xác.
- Code: `calibrate.py`, `perception.py`, `filter.py`, `guidance.py`, `main.py`, `evaluate.py`.
  Nguồn quyết định cho hành vi và tham số thực tế; tài liệu OpenCV không định nghĩa các heuristic của team.

## Wisdom

- Tập hỏi đáp cùng P2/P3/P4: mỗi người kiểm tra một câu về phần mình, đối chiếu code hoặc log.

## Gaps

- Chưa có data/gt_runs.csv đo bằng thước để xác nhận accuracy và hiệu chỉnh sigma trên dữ liệu thật.
- Chưa đánh giá hệ thống trên cổng sạc thật không marker.
