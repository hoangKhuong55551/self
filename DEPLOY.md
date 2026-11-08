# Đưa Life OS lên mạng (miễn phí: Render + Neon)

- **Render** (gói Free) chạy web.
- **Neon** chứa database Postgres. Ảnh tải lên (hoá đơn, bìa sách...) cũng được lưu trong database này.
- **GitHub Actions** gọi vào app mỗi giờ để gửi nhắc việc và xử lý khoản định kỳ.

## 1. Tạo database trên Neon

1. Vào [console.neon.tech](https://console.neon.tech) và mở project bạn đang dùng.
   - Muốn tách hẳn khỏi web cũ thì tạo project mới.
2. Vào **Databases → New Database**. Đặt tên `lifeos`, owner giữ mặc định.
3. Bấm **Connect**, chọn database `lifeos` rồi copy chuỗi kết nối.
   - Chuỗi có dạng `postgresql://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/lifeos?sslmode=require`.
   - Bật hay tắt "Connection pooling" đều chạy được.

> Mọi database trong một project Neon miễn phí dùng chung dung lượng (khoảng 0,5 GB). Một người dùng thì còn dư nhiều.

## 2. Tạo web trên Render

1. Vào [dashboard.render.com](https://dashboard.render.com), chọn **New → Blueprint** rồi chọn repo `self` (nhánh `main`).
   - Render sẽ đọc file `render.yaml` và tạo web `lifeos` ở vùng Singapore, gói Free.
2. Render hỏi giá trị cho các biến sau:

   | Biến | Giá trị |
   |---|---|
   | `DATABASE_URL` | Chuỗi kết nối Neon ở bước 1 |
   | `DJANGO_VAPID_PUBLIC_KEY`, `DJANGO_VAPID_PRIVATE_KEY` | Copy từ file `.env` trên máy, hoặc tạo mới bằng `python manage.py generate_vapid_keys` |
   | `DJANGO_VAPID_SUBJECT` | `mailto:<email của bạn>` |
   | `DJANGO_ADMIN_URL` | Một chuỗi khó đoán, vd `quan-tri-7f3k9/` |

   `DJANGO_SECRET_KEY` và `DJANGO_CRON_SECRET` do Render tự sinh.
3. Bấm **Apply** rồi chờ build xong, khoảng 3–5 phút.
   - Lệnh build `./build.sh` tự cài thư viện, gom file tĩnh và tạo bảng trong database.
4. Mở link `https://lifeos-xxxx.onrender.com` rồi **Đăng ký** tài khoản của bạn.
5. Nếu app chỉ dành cho mình bạn: vào **Environment** trên Render, đổi `DJANGO_ALLOW_REGISTRATION` thành `False` rồi bấm Save. Render sẽ tự deploy lại.

### Vào trang admin

Gói Free của Render không có Shell, nên không chạy `createsuperuser` được. Thay vào đó:

1. Đăng ký tài khoản trên web như bình thường.
2. Trên Render, vào **Environment → Add Environment Variable**, thêm `DJANGO_SUPERUSER_USERNAME` = tên đăng nhập của bạn rồi bấm **Save**.
3. Render tự deploy lại. Lúc build, tài khoản đó được cấp quyền admin.
4. Vào `https://<web>.onrender.com/<DJANGO_ADMIN_URL>` để đăng nhập trang admin.

Để nguyên biến này cũng không sao, vì lần build sau sẽ không làm gì thêm.

## 3. Chuyển dữ liệu từ máy lên

1. Trên máy (`127.0.0.1:8000`): vào **Sao lưu → Tải file JSON**.
2. Trên web online: vào **Sao lưu → Khôi phục**, chọn file vừa tải, chọn **Thay thế toàn bộ** và gõ `KHOI PHUC`.

Ảnh (hoá đơn, bìa sách) không nằm trong file sao lưu, nên cần tải lại nếu cần.

## 4. Bật nhắc việc tự động

1. Trên Render, vào web `lifeos` → **Environment** và copy giá trị `DJANGO_CRON_SECRET`.
2. Trên GitHub, vào repo `self` → **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `LIFEOS_CRON_URL`
   - Secret: `https://lifeos-xxxx.onrender.com/cron/<DJANGO_CRON_SECRET>/`
3. Chạy thử: vào tab **Actions → Nhắc việc (cron) → Run workflow**. Bước "Gọi app" hiện `{"ok": true, ...}` là xong.

Sau đó workflow tự chạy **mỗi giờ từ 7h đến 23h**, và mỗi lần chạy sẽ:
- gửi thông báo cho task sắp đến hạn;
- gửi bản tóm tắt buổi sáng (lần chạy lúc 8h);
- ghi các khoản thu/chi định kỳ đến hạn.

## Dùng chung database giữa máy và Render

Thêm vào file `.env` trên máy:

```
DATABASE_URL=<chuỗi kết nối Neon, giống trên Render>
DJANGO_FILE_STORAGE=db
```

- `DJANGO_FILE_STORAGE=db` cũng phải đặt, để ảnh tải lên ở bên nào thì bên kia cũng thấy.
- Lệnh `python manage.py test` vẫn chạy trên SQLite, không đụng vào Neon.
- Trên máy, lúc này mọi thao tác đều sửa **dữ liệu thật**. Muốn thử nghiệm thì tạo một branch trên Neon (Branches → New branch) và dùng chuỗi kết nối của branch đó.
- Lệnh `migrate` chạy trên máy cũng sửa database thật. Chỉ chạy khi code mới đã sẵn sàng để đẩy lên Render.

## Giới hạn của gói miễn phí

- **Web ngủ sau 15 phút không dùng.** Lần mở đầu tiên sau đó mất khoảng 30–60 giây.
- **Nhắc việc có thể trễ tới khoảng 1 giờ**, vì app chỉ được gọi mỗi giờ. GitHub cũng đôi khi chạy lịch trễ vài phút.
  - Muốn nhắc chính xác từng phút thì lên gói Render trả phí và thêm một Background Worker chạy `python manage.py send_reminders --loop`.
- **Giờ chạy miễn phí dùng chung.** Render cho khoảng 750 giờ/tháng, chia cho mọi web Free trong tài khoản. Lịch nhắc việc ở trên dùng khoảng 130 giờ, phần còn lại đủ cho web cũ của bạn nếu nó không chạy suốt ngày.
- **Link lịch `.ics`** (trang Lịch → Đồng bộ) giờ dùng được với Google Calendar. Google tự cập nhật vài giờ một lần.

## Chạy thử bản production trên máy

```bash
export DATABASE_URL=postgres://postgres@127.0.0.1:5432/lifeos DJANGO_DB_SSL=False \
       DJANGO_DEBUG=False DJANGO_SECRET_KEY=thu-tren-may DJANGO_FILE_STORAGE=db \
       DJANGO_SECURE_COOKIES=False DJANGO_CRON_SECRET=khoa-thu-tren-may-0123456789
./build.sh && python manage.py runserver
```
