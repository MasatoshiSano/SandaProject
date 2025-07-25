from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """乗算フィルタ"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """減算フィルタ"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """除算フィルタ"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def percentage(value, total):
    """パーセンテージ計算フィルタ"""
    try:
        if float(total) == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    return value - arg

@register.filter
def multiply(value, arg):
    return value * arg

@register.filter
def divide(value, arg):
    if arg != 0:
        return value / arg
    return 0

@register.filter
def index(sequence, position):
    try:
        return sequence[position]
    except (IndexError, TypeError):
        return None 