"""
Lưu file (ảnh) ngay trong database — dùng khi chạy trên host không có ổ đĩa lâu dài
(Render gói miễn phí xoá sạch ổ đĩa mỗi lần deploy). Bật bằng DJANGO_FILE_STORAGE=db.

Ảnh trong app đều nhỏ (hoá đơn đã thu về ≤1600px, avatar, bìa sách...), nên để trong
Postgres là đủ cho một người dùng và không cần thêm dịch vụ lưu trữ nào.
"""
import mimetypes
import posixpath
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    """private=True: không có URL công khai (chỉ trả về qua view có kiểm tra quyền)."""

    def __init__(self, private=False):
        self.private = private

    @property
    def _model(self):
        from .models import StoredFile
        return StoredFile

    def _open(self, name, mode='rb'):
        row = self._model.objects.filter(name=name, is_private=self.private).only('content').first()
        if row is None:
            raise FileNotFoundError(name)
        return ContentFile(bytes(row.content), name=name)

    def _save(self, name, content):
        name = str(name).replace('\\', '/')  # Windows: os.path dùng dấu \ trong tên file
        if hasattr(content, 'seek'):
            content.seek(0)
        data = content.read()
        if isinstance(data, str):
            data = data.encode()
        content_type = getattr(content, 'content_type', None) or mimetypes.guess_type(name)[0] or 'application/octet-stream'
        self._model.objects.create(name=name, content=data, size=len(data),
                                   content_type=content_type, is_private=self.private)
        return name

    def get_available_name(self, name, max_length=None):
        name = str(name).replace('\\', '/')
        # Tên trùng thì thêm đoạn ngẫu nhiên (không dò từng số như FileSystemStorage)
        while self.exists(name):
            root, ext = posixpath.splitext(name)
            name = f'{root}_{uuid.uuid4().hex[:7]}{ext}'
        return name[:max_length] if max_length else name

    def delete(self, name):
        if name:
            self._model.objects.filter(name=name, is_private=self.private).delete()

    def exists(self, name):
        return self._model.objects.filter(name=name, is_private=self.private).exists()

    def size(self, name):
        row = self._model.objects.filter(name=name, is_private=self.private).only('size').first()
        if row is None:
            raise FileNotFoundError(name)
        return row.size

    def url(self, name):
        if self.private:
            raise ValueError('File riêng tư không có URL công khai.')
        return settings.MEDIA_URL + name

    def listdir(self, path):
        prefix = path.rstrip('/') + '/' if path else ''
        names = self._model.objects.filter(name__startswith=prefix, is_private=self.private).values_list('name', flat=True)
        dirs, files = set(), []
        for n in names:
            rest = n[len(prefix):]
            if '/' in rest:
                dirs.add(rest.split('/', 1)[0])
            else:
                files.append(rest)
        return sorted(dirs), files

    def get_modified_time(self, name):
        row = self._model.objects.filter(name=name, is_private=self.private).only('created_at').first()
        if row is None:
            raise FileNotFoundError(name)
        return row.created_at
