from django import template

register = template.Library()

@register.filter(name='currency_vn')
def currency_vn(value):
    """
    Format số tiền theo định dạng Việt Nam với dấu chấm phân cách hàng nghìn.
    Ví dụ: 14850000 -> 14.850.000
    -265000 -> -265.000
    """
    if value is None or value == '':
        return '0'
    try:
        val = int(round(float(value)))
        is_neg = val < 0
        abs_str = f"{abs(val):,}".replace(',', '.')
        return f"-{abs_str}" if is_neg else abs_str
    except (ValueError, TypeError):
        return str(value)

@register.filter(name='currency_signed_vn')
def currency_signed_vn(value):
    """
    Hiển thị số tiền kèm dấu + hoặc - chuẩn xác, không bị lỗi +-
    Ví dụ: 265000 -> +265.000
    -265000 -> -265.000
    0 -> 0
    """
    if value is None or value == '':
        return '0'
    try:
        val = int(round(float(value)))
        if val > 0:
            return f"+{val:,}".replace(',', '.')
        elif val < 0:
            return f"-{abs(val):,}".replace(',', '.')
        else:
            return '0'
    except (ValueError, TypeError):
        return str(value)

@register.filter(name='float_vn')
def float_vn(value, decimal_places=2):
    """
    Format số thực theo chuẩn Việt Nam (dấu phẩy thập phân): 3.73 -> 3,73
    """
    if value is None or value == '':
        return '0'
    try:
        val = float(value)
        formatted = f"{val:.{decimal_places}f}".replace('.', ',')
        # Bỏ ,00 nếu là số nguyên
        if formatted.endswith(',00'):
            formatted = formatted[:-3]
        return formatted
    except (ValueError, TypeError):
        return str(value)


@register.filter(name='minutes_hm')
def minutes_hm(value):
    """125 -> '2h 05m', 40 -> '40m'."""
    try:
        total = int(value or 0)
    except (TypeError, ValueError):
        return value
    hours, minutes = divmod(total, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
