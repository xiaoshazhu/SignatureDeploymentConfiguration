"""
二维码生成工具模块
用于生成签字入口链接的二维码图片,支持中心Logo嵌入
"""
import qrcode
from io import BytesIO
import logging
import os
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def generate_qrcode(url: str) -> bytes:
    """
    生成带Logo的二维码图片
    
    Args:
        url: 要生成二维码的URL链接
        
    Returns:
        bytes: PNG格式的二维码图片字节数据
        
    Raises:
        ValueError: 如果URL为空
        Exception: 如果生成二维码失败
    """
    if not url:
        raise ValueError("URL不能为空")
    
    try:
        # 从环境变量读取配置
        qr_size = int(os.getenv('QRCODE_SIZE', '300'))  # 二维码大小,默认300px
        logo_size = int(os.getenv('QRCODE_LOGO_SIZE', '60'))  # Logo大小,默认60px
        logo_path = os.getenv('QRCODE_LOGO_PATH', 'static/image/ahlogo.png')  # Logo路径
        
        # 创建二维码实例
        # 使用高容错率(ERROR_CORRECT_H)以支持Logo遮挡
        qr = qrcode.QRCode(
            version=1,  # 控制二维码大小,1-40,1最小
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # 高容错率(30%),支持Logo遮挡
            box_size=10,  # 每个格子的像素大小
            border=4,  # 边框格子宽度
        )
        
        # 添加数据
        qr.add_data(url)
        qr.make(fit=True)
        
        # 生成图片
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        
        # 调整二维码大小到指定尺寸
        img = img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        
        # 尝试添加Logo (仅当logo_size > 0时)
        if logo_size > 0:
            try:
                # 检查Logo文件是否存在
                if os.path.exists(logo_path):
                    # 打开Logo图片
                    logo = Image.open(logo_path)
                    
                    # 将Logo转换为RGBA模式以支持透明度
                    if logo.mode != 'RGBA':
                        logo = logo.convert('RGBA')
                    
                    # 调整Logo大小
                    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    
                    # 创建白色背景(圆角矩形)
                    # Logo区域应该略大于Logo本身,留出白边
                    logo_bg_size = int(logo_size * 1.15)
                    logo_bg = Image.new('RGB', (logo_bg_size, logo_bg_size), 'white')
                    
                    # 创建圆角矩形遮罩
                    mask = Image.new('L', (logo_bg_size, logo_bg_size), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.rounded_rectangle(
                        [(0, 0), (logo_bg_size, logo_bg_size)],
                        radius=int(logo_bg_size * 0.1),  # 圆角半径为10%
                        fill=255
                    )
                    
                    # 将Logo粘贴到白色背景中心
                    logo_offset = (logo_bg_size - logo_size) // 2
                    logo_bg.paste(logo, (logo_offset, logo_offset), logo if logo.mode == 'RGBA' else None)
                    
                    # 计算Logo在二维码中的位置(居中)
                    logo_pos = ((qr_size - logo_bg_size) // 2, (qr_size - logo_bg_size) // 2)
                    
                    # 将Logo背景粘贴到二维码中心
                    img.paste(logo_bg, logo_pos, mask)
                    
                    logger.info(f"成功添加Logo到二维码,Logo大小: {logo_size}px, 二维码大小: {qr_size}px")
                else:
                    logger.warning(f"Logo文件不存在: {logo_path},生成普通二维码")
            except Exception as e:
                logger.warning(f"添加Logo失败,生成普通二维码: {e}")
        else:
            logger.info(f"Logo大小设置为0,生成普通二维码,二维码大小: {qr_size}px")
        
        # 转换为字节数据
        buffer = BytesIO()
        img.save(buffer, format='PNG', quality=95)
        qr_bytes = buffer.getvalue()
        
        logger.info(f"成功生成二维码,大小: {len(qr_bytes)} 字节")
        return qr_bytes
        
    except Exception as e:
        logger.error(f"生成二维码失败: {e}")
        raise Exception(f"生成二维码失败: {str(e)}")
