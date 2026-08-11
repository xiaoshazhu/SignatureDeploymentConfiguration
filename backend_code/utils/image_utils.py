import base64
import re

def decode_base64_image(base64_string):
    """
    将带有 data:image/png;base64, 前缀的字符串解码为 bytes
    """
    # 移除前缀
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    try:
        image_data = base64.b64decode(base64_string)
        return image_data
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}")
