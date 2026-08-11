-- 创建电子签名插件专属物理数据库
CREATE DATABASE IF NOT EXISTS `electronic_signature` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `electronic_signature`;

-- 1. 租户授权与配额表
DROP TABLE IF EXISTS `tenant_quota`;
CREATE TABLE `tenant_quota` (
  `tenant_key` varchar(64) NOT NULL COMMENT '飞书企业租户唯一 Key',
  `total_quota` int DEFAULT '0' COMMENT '授权最大配额次',
  `used_quota` int DEFAULT '0' COMMENT '已用配额次数',
  `expire_time` datetime DEFAULT NULL COMMENT '授权到期截止时间',
  `billing_type` varchar(32) DEFAULT 'quota' COMMENT '计费机制',
  `personal_base_token` varchar(512) DEFAULT NULL COMMENT '租户专属多维表格个人授权码',
  `has_claimed_trial` tinyint DEFAULT '0' COMMENT '是否领取过免费试用',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`tenant_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 2. 飞书 Bitable 绑定关系表
DROP TABLE IF EXISTS `app_token_mapping`;
CREATE TABLE `app_token_mapping` (
  `app_token` varchar(64) NOT NULL COMMENT '多维表格 App Token',
  `tenant_key` varchar(64) NOT NULL COMMENT '关联的企业租户 Key',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`app_token`),
  KEY `idx_tenant` (`tenant_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 3. 充值购买历史
DROP TABLE IF EXISTS `purchase_history`;
CREATE TABLE `purchase_history` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键自增',
  `tenant_key` varchar(64) NOT NULL COMMENT '租户 Key',
  `package_name` varchar(128) NOT NULL COMMENT '购买套餐名称',
  `added_quota` int DEFAULT '0' COMMENT '充值增加额度',
  `amount` decimal(10,2) DEFAULT '0.00' COMMENT '支付金额',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_ph_tenant` (`tenant_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 4. 支付预备订单表
DROP TABLE IF EXISTS `payment_orders`;
CREATE TABLE `payment_orders` (
  `order_id` varchar(64) NOT NULL COMMENT '系统唯一订单号',
  `tenant_key` varchar(64) NOT NULL COMMENT '企业租户 Key',
  `package_id` varchar(64) NOT NULL COMMENT '购买套餐规格 ID',
  `pay_type` varchar(32) DEFAULT NULL COMMENT '支付渠道 (如 wechat)',
  `amount` decimal(10,2) DEFAULT '0.00' COMMENT '实际付款金额',
  `added_quota` int DEFAULT '0' COMMENT '充值增加额度',
  `added_days` int DEFAULT '0' COMMENT '充值增加天数',
  `status` varchar(32) NOT NULL DEFAULT 'PENDING' COMMENT '订单状态 (PENDING, SUCCESS, FAILED)',
  `transaction_id` varchar(128) DEFAULT NULL COMMENT '微信支付流水交易号',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`order_id`),
  KEY `idx_po_tenant` (`tenant_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 5. platform_license_view (管理端核对视图)
CREATE OR REPLACE VIEW platform_license_view AS
SELECT 
    tenant_key,
    billing_type,
    used_quota,
    total_quota AS max_quota,
    expire_time
FROM tenant_quota;

-- 6. platform_order_view (管理端财务对账视图)
CREATE OR REPLACE VIEW platform_order_view AS
SELECT 
    order_id,
    tenant_key,
    package_id AS plan,
    amount,
    CASE 
        WHEN status = 'SUCCESS' THEN 'PAID'
        WHEN status = 'PENDING' THEN 'PENDING'
        WHEN status = 'REFUNDED' THEN 'REFUNDED'
        ELSE 'FAILED'
    END AS status,
    UNIX_TIMESTAMP(created_at) * 1000 AS created_at,
    updated_at AS updated_at_raw,
    UNIX_TIMESTAMP(updated_at) * 1000 AS updated_at,
    transaction_id AS third_party_no,
    '微信支付' AS pay_channel,
    added_quota AS quota,
    added_days AS days
FROM payment_orders;
