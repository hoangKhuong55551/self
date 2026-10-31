"""
Danh mục mặc định tạo cho mỗi tài khoản mới (tên, loại, icon Bootstrap, màu).
"""

DEFAULT_CATEGORIES = [
    ('Ăn uống', 'expense', 'cup-hot', '#f97316'),
    ('Di chuyển', 'expense', 'bus-front', '#0ea5e9'),
    ('Nhà ở & Hoá đơn', 'expense', 'house', '#8b5cf6'),
    ('Mua sắm', 'expense', 'bag', '#ec4899'),
    ('Học tập', 'expense', 'book', '#3b82f6'),
    ('Giải trí', 'expense', 'controller', '#eab308'),
    ('Sức khoẻ', 'expense', 'heart-pulse', '#ef4444'),
    ('Khác', 'expense', 'three-dots', '#64748b'),
    ('Lương', 'income', 'briefcase', '#10b981'),
    ('Freelance', 'income', 'laptop', '#14b8a6'),
    ('Thu nhập khác', 'income', 'gift', '#22c55e'),
]


def create_default_categories(category_model, user_id):
    """Dùng được cả trong migration (model lịch sử) lẫn code thường."""
    category_model.objects.bulk_create([
        category_model(user_id=user_id, name=name, type=type_, icon=icon, color=color)
        for name, type_, icon, color in DEFAULT_CATEGORIES
    ])
