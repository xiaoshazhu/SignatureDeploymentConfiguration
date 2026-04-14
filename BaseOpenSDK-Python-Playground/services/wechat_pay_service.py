import os
import logging
from wechatpayv3 import WeChatPay, WeChatPayType
from uuid import uuid4
from datetime import datetime

logger = logging.getLogger(__name__)

class WechatPayService:
    def __init__(self):
        self.mchid = os.getenv('WECHAT_MCH_ID')
        self.v3_key = os.getenv('WECHAT_API_V3_KEY')
        self.cert_serial_no = os.getenv('WECHAT_CERT_SERIAL_NO')
        self.cert_path = os.getenv('WECHAT_CERT_PATH')
        self.key_path = os.getenv('WECHAT_KEY_PATH')
        self.appid = os.getenv('WECHAT_APP_ID')
        self.notify_url = os.getenv('WECHAT_NOTIFY_URL')
        
        # 新增:公钥模式支持
        self.pub_key_id = os.getenv('WECHAT_PUB_KEY_ID')
        self.pub_key_path = os.getenv('WECHAT_PUB_KEY_PATH')

        # 如果没有 key 文件,先记录警告
        if not os.path.exists(self.key_path):
            logger.warning(f"WeChat Private Key file not found at {self.key_path}. Native Pay will fail.")
            self.wxpay = None
        else:
            try:
                # 初始化微信支付对象
                # 注意: 我们需要读取私钥内容
                with open(self.key_path, 'r') as f:
                    private_key = f.read()
                
                if self.pub_key_id and self.pub_key_path and os.path.exists(self.pub_key_path):
                    # 公钥模式 (Wechat Pay Public Key Mode)
                    with open(self.pub_key_path, 'r') as f:
                        wechatpay_public_key = f.read()
                    
                    self.wxpay = WeChatPay(
                        wechatpay_type=WeChatPayType.NATIVE,
                        mchid=self.mchid,
                        private_key=private_key,
                        cert_serial_no=self.cert_serial_no,
                        apiv3_key=self.v3_key,
                        appid=self.appid,
                        notify_url=self.notify_url,
                        public_key=wechatpay_public_key,
                        public_key_id=self.pub_key_id
                    )
                    logger.info("WeChatPay service initialized in [PUBLIC KEY MODE]")
                else:
                    # 证书模式 (Certificate Mode)
                    self.wxpay = WeChatPay(
                        wechatpay_type=WeChatPayType.NATIVE,
                        mchid=self.mchid,
                        private_key=private_key,
                        cert_serial_no=self.cert_serial_no,
                        apiv3_key=self.v3_key,
                        appid=self.appid,
                        notify_url=self.notify_url,
                        cert_dir=None
                    )
                    logger.info("WeChatPay service initialized in [CERTIFICATE MODE]")
                logger.info(f"WeChatPay service initialized successfully for APPID: {self.appid}")
            except Exception as e:
                logger.error(f"Failed to initialize WeChatPay service: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                self.wxpay = None

    def create_native_order(self, order_id, amount, description):
        """
        创建 Native 支付订单 (扫码支付)
        amount: 金额,单位为元 (内部会转为分)
        """
        if not self.wxpay:
            logger.error("WeChatPay not initialized. Check your credentials and private key.")
            return None

        # 微信支付金额单位是分
        amount_fen = int(amount * 100)

        try:
            # 调用 Native 下单接口
            # 这里的参数根据 wechatpayv3 库的文档
            code, message = self.wxpay.pay(
                description=description,
                out_trade_no=order_id,
                amount={'total': amount_fen},
                pay_type=WeChatPayType.NATIVE
            )
            
            if code == 200:
                import json
                data = json.loads(message)
                return data.get('code_url')  # 二维码链接
            else:
                logger.error(f"WeChat Pay order creation failed: {code} - {message}")
                return None
        except Exception as e:
            logger.error(f"Exception during WeChat Pay order creation: {e}")
            return None

    def verify_callback(self, headers, body):
        """
        验证回调通知
        """
        if not self.wxpay:
            return None
            
        try:
            # 使用库提供的回调解析
            result = self.wxpay.callback(headers, body)
            if result and result.get('event_type') == 'TRANSACTION.SUCCESS':
                return result.get('resource')
            return None
        except Exception as e:
            logger.error(f"WeChat callback verification failed: {e}")
            return None
