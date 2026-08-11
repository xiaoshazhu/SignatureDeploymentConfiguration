import time
import uuid
import requests
import base64
from Cryptodome.Signature import pkcs1_15
from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey import RSA
import os
from dotenv import load_dotenv

def get_auth_header(mchid, serial_no, private_key_path, method, url, body=""):
    timestamp = str(int(time.time()))
    nonce_str = str(uuid.uuid4()).replace('-', '')
    
    with open(private_key_path, 'r') as f:
        private_key = RSA.import_key(f.read())
        
    # 构造签名串
    message = f"{method}\n{url}\n{timestamp}\n{nonce_str}\n{body}\n"
    hash_obj = SHA256.new(message.encode('utf-8'))
    signature = pkcs1_15.new(private_key).sign(hash_obj)
    signature_base64 = base64.b64encode(signature).decode('utf-8')
    
    auth_str = (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",'
        f'nonce_str="{nonce_str}",'
        f'signature="{signature_base64}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{serial_no}"'
    )
    return auth_str

def debug_fetch_certs():
    load_dotenv()
    mchid = os.getenv('WECHAT_MCH_ID')
    serial_no = os.getenv('WECHAT_CERT_SERIAL_NO')
    key_path = os.getenv('WECHAT_KEY_PATH')
    
    url = "/v3/certificates"
    full_url = "https://api.mch.weixin.qq.com" + url
    
    auth_header = get_auth_header(mchid, serial_no, key_path, "GET", url)
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    print(f"Requesting {full_url}...")
    print(f"Auth Header: {auth_header[:50]}...")
    
    response = requests.get(full_url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")

if __name__ == "__main__":
    debug_fetch_certs()
