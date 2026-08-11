"""
URL参数加密工具模块

使用AES-256-GCM对称加密保护URL参数,防止参数被破解和篡改。
密钥仅存储在服务器端,确保安全性。
"""

import os
import json
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class URLEncryptor:
    """URL参数加密器"""
    
    def __init__(self, key=None):
        """
        初始化加密器
        
        Args:
            key: 32字节的加密密钥,如果为None则从环境变量读取
        """
        if key is None:
            key = os.getenv('ENCRYPTION_KEY')
            if not key:
                raise ValueError("未配置加密密钥,请在.env中设置ENCRYPTION_KEY")
        
        # 确保密钥是32字节
        if isinstance(key, str):
            # 如果是十六进制字符串,转换为bytes
            if len(key) == 64:  # 32字节的十六进制表示
                key = bytes.fromhex(key)
            else:
                # 否则使用UTF-8编码并填充/截断到32字节
                key = key.encode('utf-8')
                key = key[:32].ljust(32, b'\0')
        
        if len(key) != 32:
            raise ValueError(f"加密密钥必须是32字节,当前长度: {len(key)}")
        
        self.aesgcm = AESGCM(key)
    
    def encrypt_params(self, params_dict):
        """
        加密URL参数字典
        
        Args:
            params_dict: 参数字典,如 {"app_token": "xxx", "table_id": "yyy"}
            
        Returns:
            str: URL安全的加密字符串
        """
        try:
            # 1. 序列化为JSON
            json_str = json.dumps(params_dict, ensure_ascii=False)
            plaintext = json_str.encode('utf-8')
            
            # 2. 生成随机nonce (12字节)
            nonce = os.urandom(12)
            
            # 3. AES-GCM加密
            ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
            
            # 4. 组合 nonce + ciphertext
            encrypted_data = nonce + ciphertext
            
            # 5. Base64编码并转换为URL安全格式
            encoded = base64.urlsafe_b64encode(encrypted_data).decode('ascii')
            
            logger.debug(f"参数加密成功,原始长度: {len(json_str)}, 加密后长度: {len(encoded)}")
            return encoded
            
        except Exception as e:
            logger.error(f"参数加密失败: {e}")
            raise
    
    def decrypt_params(self, encrypted_str):
        """
        解密URL参数
        
        Args:
            encrypted_str: 加密的字符串
            
        Returns:
            dict: 解密后的参数字典
            
        Raises:
            ValueError: 解密失败或参数被篡改
        """
        try:
            # 1. Base64解码
            encrypted_data = base64.urlsafe_b64decode(encrypted_str.encode('ascii'))
            
            # 2. 分离nonce和ciphertext
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # 3. AES-GCM解密
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
            
            # 4. JSON反序列化
            json_str = plaintext.decode('utf-8')
            params_dict = json.loads(json_str)
            
            logger.debug(f"参数解密成功,参数数量: {len(params_dict)}")
            return params_dict
            
        except Exception as e:
            logger.error(f"参数解密失败: {e}")
            raise ValueError("无效的链接参数或参数已被篡改")


def generate_encryption_key():
    """
    生成新的加密密钥(32字节)
    
    Returns:
        str: 十六进制格式的密钥字符串
    """
    key = os.urandom(32)
    hex_key = key.hex()
    print(f"生成的加密密钥(请保存到.env文件):")
    print(f"ENCRYPTION_KEY={hex_key}")
    return hex_key


# 全局加密器实例(延迟初始化)
_encryptor = None


def get_encryptor():
    """获取全局加密器实例"""
    global _encryptor
    if _encryptor is None:
        _encryptor = URLEncryptor()
    return _encryptor


def encrypt_url_params(params_dict):
    """
    加密URL参数(便捷函数)
    
    Args:
        params_dict: 参数字典
        
    Returns:
        str: 加密后的字符串
    """
    return get_encryptor().encrypt_params(params_dict)


def decrypt_url_params(encrypted_str):
    """
    解密URL参数(便捷函数)
    
    Args:
        encrypted_str: 加密的字符串
        
    Returns:
        dict: 解密后的参数字典
    """
    return get_encryptor().decrypt_params(encrypted_str)


if __name__ == '__main__':
    # 测试代码
    print("=== URL参数加密工具测试 ===\n")
    
    # 生成密钥
    print("1. 生成加密密钥:")
    test_key = generate_encryption_key()
    print()
    
    # 测试加密解密
    print("2. 测试加密解密:")
    encryptor = URLEncryptor(test_key)
    
    test_params = {
        "app_token": "bascnCqNbEhr4lZdEES8PabcdefG",
        "table_id": "tblxxx123456",
        "record_id": "recyyy789012",
        "mode": "会签",
        "count": "3"
    }
    
    print(f"原始参数: {test_params}")
    
    encrypted = encryptor.encrypt_params(test_params)
    print(f"加密后: {encrypted}")
    print(f"加密后长度: {len(encrypted)} 字符")
    
    decrypted = encryptor.decrypt_params(encrypted)
    print(f"解密后: {decrypted}")
    
    # 验证
    if test_params == decrypted:
        print("\n✅ 加密解密测试通过!")
    else:
        print("\n❌ 加密解密测试失败!")
    
    # 测试篡改检测
    print("\n3. 测试篡改检测:")
    try:
        tampered = encrypted[:-5] + "XXXXX"
        encryptor.decrypt_params(tampered)
        print("❌ 篡改检测失败!")
    except ValueError as e:
        print(f"✅ 成功检测到篡改: {e}")
