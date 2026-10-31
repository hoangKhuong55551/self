"""
Trang sửa/xoá dùng chung cho mọi phân hệ (template: templates/form_page.html).
"""
from django.http import HttpResponse
from django.shortcuts import render


def edit_page(request, instance, form_class, *, title, back_url, delete_url=None, delete_warning='',
              nav=None, **form_kwargs):
    """
    GET hiện form; POST hợp lệ thì lưu và trả về instance đã lưu,
    ngược lại trả về HttpResponse (form kèm lỗi) để view trả thẳng cho client.
    `nav`: template điều hướng con của phân hệ (tuỳ chọn).
    """
    form = form_class(request.POST or None, request.FILES or None, instance=instance, **form_kwargs)
    if request.method == 'POST' and form.is_valid():
        return form.save()
    return render(request, 'form_page.html', {
        'form': form, 'title': title, 'back_url': back_url, 'nav': nav,
        'delete_url': delete_url, 'delete_warning': delete_warning,
    })


def is_response(result):
    return isinstance(result, HttpResponse)
