# Impact: Charge-Port Alignment Assist

> Mọi con số dưới đây là **GIẢ ĐỊNH** của nhóm để minh họa cách tính, KHÔNG phải số liệu của V-GREEN,
> VinFast hay Xanh SM. Khi có số thật chỉ cần thay vào công thức.

## Người dùng và nỗi đau

- **Tài xế xe dịch vụ (Xanh SM) và kỹ thuật viên trạm (V-GREEN):** mất thời gian căn và cắm đầu sạc,
  nhất là khi đỗ lệch, trời tối, cổng sạc khuất. Xe dịch vụ thì mỗi phút đứng chờ là mất doanh thu.
- **Robot sạc tự động (hướng tương lai):** muốn robot tự cắm sạc thì trước hết phải biết cổng sạc nằm đâu
  (x, z, yaw) và biết mình chắc đến đâu (sigma). Demo này là đúng khâu đó.

## Công thức

```
Impact (VND/ngày) = N xe dùng hệ thống × số lần sạc/xe/ngày × phút tiết kiệm/lần × giá trị 1 phút
```

| Kịch bản | N xe | Lần sạc/ngày | Phút tiết kiệm/lần | Giá trị 1 phút (VND) | Phút/ngày | VND/ngày | Tỷ VND/năm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Thấp | 2,000 | 1.0 | 0.25 | 1,000 | 500 | 500,000 | 0.18 |
| Cơ sở | 10,000 | 1.5 | 0.5 | 1,500 | 7,500 | 11,250,000 | 4.11 |
| Cao | 30,000 | 2.0 | 1.0 | 2,500 | 60,000 | 150,000,000 | 54.75 |

Giải thích các giả định:

- **N xe:** số xe dịch vụ được trang bị hoặc được phục vụ bởi trạm có hệ thống. Chưa có số thật, đây là tham số.
- **Lần sạc/ngày:** xe chạy dịch vụ cả ngày thường phải sạc nhiều hơn xe cá nhân. Đây là giả định, chưa đo.
- **Phút tiết kiệm/lần:** thời gian bớt được nhờ không phải căn lại hoặc cắm lại. Chưa có thí nghiệm nào đo con số này.
- **Giá trị 1 phút:** chi phí cơ hội của một phút xe dịch vụ đứng chờ. Đây là giả định.

Kết quả thay đổi khoảng **300 lần** giữa kịch bản thấp và cao, nên con số chỉ dùng để thấy độ lớn,
không dùng làm cam kết. Tham số quyết định nhiều nhất là số phút tiết kiệm mỗi lần sạc, và chưa ai đo nó.

## Giá trị không quy ra tiền

- **An toàn:** cắm lệch có thể làm mòn chân sạc hoặc gây hồ quang. Hệ thống biết khi nào **không chắc**
  (DEGRADED/LOST) và lúc đó không đưa chỉ dẫn, thay vì đoán bừa.
- **Nền móng cho robot sạc:** pose cộng sigma, đã kiểm chứng bằng thước, là đầu vào tối thiểu
  cho bộ điều khiển cánh tay.

## Lộ trình mở rộng

1. **Hiện tại (demo):** marker ArUco, một webcam, có kiểm chứng bằng thước ở z 30-100 cm.
2. **Thay marker bằng detector học được:** nhận diện nắp hoặc khe cổng sạc thật, lấy keypoint rồi giải PnP với
   mô hình 3D của cổng. Cần thu và gán nhãn dữ liệu cổng sạc thật của các dòng xe VinFast.
3. **Thêm cảm biến độ sâu hoặc stereo** để z không phụ thuộc kích thước vật đã biết.
4. **Gắn vào cánh tay robot ở trạm V-GREEN:** vòng điều khiển dùng pose và sigma, có ngưỡng dừng an toàn.

## Rủi ro

| Rủi ro | Ảnh hưởng | Giảm thiểu |
| --- | --- | --- |
| Che khuất (tay, nắp sạc, bùn) | Mất marker hoặc pose sai | Trạng thái LOST, không đưa chỉ dẫn; gating Mahalanobis loại outlier |
| Thời tiết, lóa, đêm | Detector hỏng, reproj error tăng | Theo dõi reproj error; về sau thêm đèn IR, camera HDR |
| Nghiêng lớn, marker nhỏ hoặc xa | Co ngắn, mất góc, hoặc hai nghiệm PnP gần nhau | Reproj error, cờ `ambiguous` chuyển DEGRADED; hướng dẫn tiếp cận gần trực diện |
| Hiệu chuẩn lệch (autofocus, đổi camera) | Sai số hệ thống mà filter không thấy | Khóa focus, kiểm tra lại bằng thước định kỳ |
| An toàn điện khi robot cắm | Hư hỏng, nguy hiểm | Con người xác nhận cuối; robot chỉ cắm khi status GOOD và sigma nhỏ |
| Marker không có trên xe thật | Demo không chuyển thẳng ra thực tế được | Đã nêu: bước 2 của lộ trình |
