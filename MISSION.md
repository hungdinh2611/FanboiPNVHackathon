# Mission: giải thích kỹ thuật Charge-Port Alignment Assist

## Why
Hưng cần trình bày và trả lời câu hỏi kỹ thuật tại hackathon về chính hệ thống team đã xây.
Mục tiêu là giải thích được lựa chọn thiết kế, đọc đúng số đo và nói đúng giới hạn.

## Success looks like
- Kể đúng luồng ảnh -> ArUco -> PnP -> Kalman -> guidance trong 30 giây.
- Phân biệt calibration RMS, lỗi vị trí cm và sigma của filter.
- Giải thích được ít nhất hai trụ cột, một ca lỗi và nguồn gốc số liệu.

## Constraints
- Ôn nhanh bằng tiếng Việt, dùng ví dụ và câu trả lời mẫu từ code hiện tại.
- Hưng phụ trách P1; cần hiểu luồng P2/P3/P4 để trả lời câu liên quan.
- Bằng chứng hiện có gồm hiệu chuẩn thật và kiểm thử ảnh render; chưa có GT thước.

## Out of scope
- Hiện chưa đặt mục tiêu học một khóa đại số hoặc computer vision đầy đủ.
