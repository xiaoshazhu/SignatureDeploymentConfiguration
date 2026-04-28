import os
import logging
from dotenv import load_dotenv
from wechatpayv3 import WeChatPay, WeChatPayType

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_config():
    load_dotenv()
    
    mchid = os.getenv('WECHAT_MCH_ID')
    v3_key = os.getenv('WECHAT_API_V3_KEY')
    cert_serial_no = os.getenv('WECHAT_CERT_SERIAL_NO')
    key_path = os.getenv('WECHAT_KEY_PATH')
    appid = os.getenv('WECHAT_APP_ID')
    pub_key_id = os.getenv('WECHAT_PUB_KEY_ID')
    pub_key_path = os.getenv('WECHAT_PUB_KEY_PATH')
    
    logger.info(f"Checking config for MCHID: {mchid}, AppID: {appid}")
    logger.info(f"Using Serial No: {cert_serial_no}")
    
    if pub_key_id:
        logger.info(f"Public Key Mode detected. ID: {pub_key_id}")

    if not os.path.exists(key_path):
        logger.error(f"Private key file not found at: {key_path}")
        return

    try:
        with open(key_path, 'r') as f:
            private_key = f.read()
            
        if pub_key_id and pub_key_path and os.path.exists(pub_key_path):
             with open(pub_key_path, 'r') as f:
                wechatpay_public_key = f.read()
             wxpay = WeChatPay(
                wechatpay_type=WeChatPayType.NATIVE,
                mchid=mchid,
                private_key=private_key,
                cert_serial_no=cert_serial_no,
                apiv3_key=v3_key,
                appid=appid,
                public_key=wechatpay_public_key,
                public_key_id=pub_key_id
            )
        else:
            wxpay = WeChatPay(
                wechatpay_type=WeChatPayType.NATIVE,
                mchid=mchid,
                private_key=private_key,
                cert_serial_no=cert_serial_no,
                apiv3_key=v3_key,
                appid=appid,
                cert_dir=None
            )
        logger.info("✅ WeChatPay object created successfully.")
        
        # 尝试获取证书 (验证网络和签名)
        logger.info("Attempting to fetch platform certificates from WeChat...")
        # 内部会调用 GET /v3/certificates
        # 如果初始化没报错,说明证书下载(或握手)基本没问题
        logger.info("✅ If you see this, the initial handshake and certificate fetching logic likely worked.")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize WeChatPay: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_config()
