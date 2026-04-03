<template>
  <div class="config-panel">

    <el-form ref="formRef" class="config-form" :model="config" label-position="top">
      <!-- 配额状态看板 -->
      <el-card class="quota-card" shadow="never" :body-style="{ padding: '12px 16px' }">
        <div class="quota-header">
          <div class="quota-title">
            <el-icon><CreditCard /></el-icon>
            <span>{{ $t('common.quota_title') }}</span>
          </div>
          <div class="quota-actions">
            <el-button type="primary" size="small" plain @click="showPricing = true">{{ $t('common.recharge_btn') }}</el-button>
          </div>
        </div>
        <div class="quota-stats">
          <div class="stat-item">
            <span class="stat-label">{{ $t('common.total_quota') }}:</span>
            <span class="stat-value">{{ quotaInfo.total }}{{ $t('common.times') }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">{{ $t('common.used_quota') }}:</span>
            <span class="stat-value">{{ quotaInfo.used }}{{ $t('common.times') }}</span>
          </div>
          <div class="stat-item highlight">
            <span class="stat-label">{{ $t('common.remaining_quota') }}:</span>
            <span class="stat-value">{{ quotaInfo.remaining }}{{ $t('common.times') }}</span>
          </div>
        </div>
      </el-card>

      <!-- 温馨提示 -->
      <el-alert
        :title="$t('common.tips_title')"
        type="info"
        :closable="false"
        class="compact-tips"
      >
        <template #default>
          <div class="tips-content">
            <p>1、{{ $t('common.tip_switch_table') }}</p>
            <p>2、{{ $t('common.tip_consume_quota') }}</p>
            <p>3、{{ $t('common.tip_batch_new_only') }}</p>
          </div>
        </template>
      </el-alert>

      <!-- 批量配置区域 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <span>{{ $t('config.batch_title') }}</span>
        </template>

        <el-form-item :label="$t('config.sign_mode')">
          <el-radio-group v-model="config.signMode" @change="onConfigChange">
            <el-radio label="或签">{{ $t('config.any_sign') }}</el-radio>
            <el-radio label="会签">{{ $t('config.all_sign') }}</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item :label="$t('config.sign_count')" v-if="config.signMode === '会签'">
          <el-input-number 
            v-model="config.signCount" 
            :min="1" 
            :max="10"
            @change="onConfigChange"
          />
        </el-form-item>

        <!-- 未初始化时:显示生成二维码开关 -->
        <el-form-item :label="$t('config.enable_qrcode')" v-if="!isInitialized">
          <el-switch 
            v-model="config.enableQRCode"
            @change="onConfigChange"
          />
          <span class="form-tip">{{ $t('config.qrcode_tip') }}</span>
        </el-form-item>



        <el-divider />

        <!-- 批量操作按钮 -->
        <div class="action-section">
          <!-- 未初始化时显示初始化按钮 -->
          <template v-if="!isInitialized">
            <el-button 
              type="primary" 
              size="large" 
              :loading="initializing"
              @click="initializeTable"
              class="action-btn"
            >
              {{ initializing ? $t('config.initializing') : $t('config.init_btn') }}
            </el-button>
            <p class="tip-text">{{ $t('config.init_tip_first') }}</p>
          </template>

          <!-- 已初始化后显示批量生成 -->
          <template v-else>
            <el-button 
              type="primary" 
              size="large"
              :loading="generating"
              @click="batchGenerateLinks"
              class="action-btn"
            >
              {{ generating ? $t('config.generating') : $t('config.batch_btn') }}
            </el-button>

            <!-- 更多操作折叠 - 只在已初始化后显示 -->
            <el-collapse v-model="activeCollapse" style="margin-top: 16px;">
              <el-collapse-item :title="$t('config.more_actions')" name="more">
                <!-- 生成二维码开关 -->
                <el-form-item :label="$t('config.enable_qrcode')">
                  <el-switch 
                    v-model="config.enableQRCode"
                    @change="onQRCodeChange"
                  />
                  <span class="form-tip">{{ $t('config.qrcode_tip') }}</span>
                </el-form-item>

                <!-- 重新初始化按钮 - 只有二维码开关变更时才可点击 -->
                <el-button 
                  type="warning"
                  plain
                  size="large"
                  :loading="initializing"
                  :disabled="!qrcodeChanged"
                  @click="reinitializeTable"
                  class="action-btn"
                >
                  {{ initializing ? $t('config.initializing') : $t('config.init_btn') }}
                </el-button>
                <p class="tip-text" v-if="qrcodeChanged">
                  ⚠️ {{ $t('config.qrcode_change_warn') }}
                </p>
                <p class="tip-text" v-else>
                  💡 {{ $t('config.qrcode_no_change') }}
                </p>
              </el-collapse-item>
            </el-collapse>
          </template>
        </div>
      </el-card>

      <!-- 单行操作区域 -->
      <el-card v-if="isInitialized" class="config-card" shadow="never">
        <template #header>
          <span>{{ $t('config.single_row_title') }}</span>
        </template>

        <el-form-item :label="$t('config.sign_mode')">
          <el-radio-group v-model="singleRowConfig.mode">
            <el-radio label="或签">{{ $t('config.any_sign') }}</el-radio>
            <el-radio label="会签">{{ $t('config.all_sign') }}</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item :label="$t('config.sign_count')" v-if="singleRowConfig.mode === '会签'">
          <el-input-number 
            v-model="singleRowConfig.count" 
            :min="1" 
            :max="10"
          />
        </el-form-item>

        <el-divider />

        <div class="action-section">
          <el-button 
            type="success" 
            size="large"
            :disabled="!hasSelectedRecord"
            :loading="generatingSingle"
            @click="generateSingleRowLink"
            class="action-btn"
          >
            {{ generatingSingle ? $t('config.single_generating') : $t('config.single_btn') }}
          </el-button>
          <p class="tip-text" v-if="!hasSelectedRecord">
            💡 {{ $t('config.select_row_hint') }}
          </p>
          <p class="tip-text" v-else>
            ✅ {{ $t('config.record_selected_hint') }}
          </p>
        </div>
      </el-card>

      <!-- 单行配置对话框 - 删除,不再需要 -->

      <!-- 反馈与支持 -->
      <el-card class="config-card feedback-card" shadow="never">
        <template #header>
          <div class="feedback-header">
            <el-icon><ChatDotRound /></el-icon>
            <span>{{ $t('feedback.title') }}</span>
          </div>
        </template>
        <div class="feedback-content">
          <p class="feedback-desc">{{ $t('feedback.desc') }}</p>
          <div class="feedback-actions">
            <el-button
              type="primary"
              plain
              size="default"
              class="feedback-btn"
              @click="openFeedbackGroup"
            >
              <el-icon><ChatLineSquare /></el-icon>
              {{ $t('feedback.join_group') }}
            </el-button>
          </div>
          <p class="feedback-tip">{{ $t('feedback.tip') }}</p>
        </div>
      </el-card>

    </el-form>

    <!-- 充值续费对话框 -->
    <el-dialog v-model="showPricing" :title="$t('pay.title')" width="90%" class="pricing-dialog" append-to-body>
      <div class="pricing-grid">
        <div v-for="item in pricingPlans" :key="item.quota" class="plan-card" @click="handleRecharge(item)">
          <div class="plan-quota">{{ item.quota }}{{ $t('common.times') }}</div>
          <div class="plan-tag" v-if="item.isTest">{{ $t('pay.test_tag') }}</div>
          <div class="plan-price">{{ item.price }}</div>
          <div class="plan-desc" v-if="item.quota >= 500">约 {{ (parseFloat(item.price.replace('元','')) / item.quota).toFixed(3) }} 元/次</div>
          <el-button type="primary" size="small">{{ $t('pay.buy_now') }}</el-button>
        </div>
      </div>
      <template #footer>
        <div class="pricing-footer">
          <p>{{ $t('pay.footer_tip') }}</p>
        </div>
      </template>
    </el-dialog>

    <!-- 微信支付模拟弹窗 (Native Pay) -->
    <el-dialog v-model="showPayment" :title="$t('pay.modal_title')" width="80%" center class="payment-modal" append-to-body>
      <div class="payment-content">
        <div class="order-info">
          <p>{{ $t('pay.order_id') }}：{{ currentOrder.id }}</p>
          <p>{{ $t('pay.amount') }}：<span class="price-text">{{ currentOrder.price }}</span></p>
          <p>{{ $t('pay.recharge_quota') }}：{{ currentOrder.quota }}{{ $t('common.times') }}</p>
        </div>
        <div class="qr-box">
          <!-- 模拟二维码 -->
          <img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://pay.weixin.qq.com" alt="QR Code" />
          <p class="qr-tip">{{ $t('pay.scan_tip') }}</p>
        </div>
        <div class="test-notice" v-if="currentOrder.isTest">
          <el-alert :title="$t('pay.test_mode_notice')" type="warning" :closable="false" center />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { CreditCard, ChatDotRound, ChatLineSquare } from '@element-plus/icons-vue';
import { bitable, FieldType } from '@lark-base-open/js-sdk';

const { t, locale } = useI18n();
import { getAppToken } from '../utils/bitableHelper';
import { 
  ElMessage, 
  ElMessageBox,
  ElForm,
  ElFormItem,
  ElCard,
  ElRadioGroup,
  ElRadio,
  ElInputNumber,
  ElSwitch,
  ElDivider,
  ElCollapse,
  ElCollapseItem,
  ElButton,
  ElAlert,
  ElDialog
} from 'element-plus';

// 配置数据
const config = ref({
  signMode: '或签',
  signCount: 3,
  enableQRCode: true
});

// 状态
const isInitialized = ref(false);
const initializing = ref(false);
const generating = ref(false);
const activeCollapse = ref([]);

// 二维码开关变更检测
const initialQRCodeState = ref(true); // 记录初始化时的二维码状态
const qrcodeChanged = ref(false); // 二维码开关是否变更

// 单行操作相关
const hasSelectedRecord = ref(false); // 是否选中了记录
const selectedRecordId = ref(''); // 选中的记录ID
const generatingSingle = ref(false); // 单行生成中
const singleRowConfig = ref({
  mode: '或签',
  count: 3
});

// 当前表格信息
const currentTableId = ref('');
const currentAppToken = ref('');
const tenantKey = ref('');

// 配额信息
const quotaInfo = ref({ total: 0, used: 0, remaining: 0 });
const showPricing = ref(false);
const showPayment = ref(false);
const currentOrder = ref({});
const pricingPlans = [
  { quota: 10, price: '0.1元', isTest: true },
  { quota: 500, price: '19.9元' },
  { quota: 1000, price: '35.0元' },
  { quota: 5000, price: '119.0元' },
  { quota: 10000, price: '209.0元' },
  { quota: 50000, price: '939.0元' },
  { quota: 100000, price: '1739.0元' },
  { quota: 200000, price: '3199.0元' }
];

// 获取配额信息
const fetchQuota = async () => {
  if (!tenantKey.value) {
    try {
      tenantKey.value = await bitable.bridge.getTenantKey();
    } catch (e) {
      console.warn('获取租户标识失败,无法管理配额', e);
      return;
    }
  }

  try {
    const apiBase = import.meta.env.VITE_API_BASE || '';
    const res = await fetch(`${apiBase}/quota/status?tenant_key=${tenantKey.value}`);
    const result = await res.json();
    if (result.code === 0) {
      quotaInfo.value = result.data;
    }
  } catch (e) {
    console.error('获取额度失败:', e);
  }
};

// 支付流程控制 (模拟)
const handleRecharge = async (plan) => {
  showPricing.value = false;
  
  // 1. 生成模拟订单
  currentOrder.value = {
    id: 'ORD' + Date.now().toString().slice(-8),
    price: plan.price,
    quota: plan.quota,
    isTest: plan.isTest
  };
  
  // 2. 显示支付二维码
  showPayment.value = true;
  
  // 3. 模拟微信支付成功后的回调 (仅用于Demo展示)
  // 在真实环境中,后端收到微信回调后更新数据库,前端轮询接口发现余额更新后关闭弹窗
  setTimeout(async () => {
    try {
      const apiBase = import.meta.env.VITE_API_BASE || '';
      const res = await fetch(`${apiBase}/quota/recharge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenant_key: tenantKey.value,
          package_name: `${plan.quota}次套餐`,
          added_quota: plan.quota,
          amount: parseFloat(plan.price.replace('元',''))
        })
      });
      const result = await res.json();
      if (result.code === 0) {
        ElMessage.success(t('pay.pay_success'));
        showPayment.value = false;
        fetchQuota(); // 刷新余额
      }
    } catch (e) {
      ElMessage.error(t('pay.pay_fail'));
    }
  }, 3000);
};

// 加入反馈群聊
const openFeedbackGroup = () => {
  window.open('https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=9c2s5ba7-0b14-4f90-b6aa-4a1a8834c672', '_blank');
};

// 测试用: 强制设为3次
const setTestLowQuota = async () => {
  try {
    const apiBase = import.meta.env.VITE_API_BASE || '';
    const res = await fetch(`${apiBase}/quota/test/set-low`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tenant_key: tenantKey.value
      })
    });
    const result = await res.json();
    if (result.code === 0) {
      ElMessage.info(t('msg.setting_success'));
      fetchQuota();
    }
  } catch (e) {
    ElMessage.error(t('msg.setting_fail'));
  }
};

// 配置变更时保存
const onConfigChange = () => {
  // TODO: 实现配置持久化到独立配置表
};

// 二维码开关变更时检测
const onQRCodeChange = () => {
  qrcodeChanged.value = config.value.enableQRCode !== initialQRCodeState.value;
};

// 检查表格是否已初始化
const checkInitialized = async () => {
  try {
    const selection = await bitable.base.getSelection();
    if (!selection.tableId) {
      return false;
    }

    currentTableId.value = selection.tableId;
    const table = await bitable.base.getTableById(selection.tableId);
    const fieldList = await table.getFieldMetaList();
    
    // 检查是否存在必要的字段(只检查新名称)
    const hasSignEntry = fieldList.some(f => f.name === '签字确认');
    const hasStatus = fieldList.some(f => f.name === '签字状态');
    const hasAttachment = fieldList.some(f => f.name === '签字附件');
    const hasQRCode = fieldList.some(f => f.name === '签字二维码');
    
    isInitialized.value = hasSignEntry && hasStatus && hasAttachment;
    
    // 记录初始二维码状态
    if (isInitialized.value) {
      initialQRCodeState.value = hasQRCode;
      config.value.enableQRCode = hasQRCode;
      qrcodeChanged.value = false;
    }
    
    return isInitialized.value;
  } catch (error) {
    console.error('检查初始化状态失败:', error);
    return false;
  }
};

// 初始化表格
const initializeTable = async () => {
  try {
    initializing.value = true;


    const selection = await bitable.base.getSelection();
    if (!selection.tableId) {
      ElMessage.warning(t('config.select_row_tip'));
      return;
    }

    const table = await bitable.base.getTableById(selection.tableId);
    const fieldList = await table.getFieldMetaList();
    const existingFields = fieldList.map(f => f.name);

    // 创建必要的字段
    const fieldsToCreate = [];

    if (!existingFields.includes('签字确认')) {
      fieldsToCreate.push({ name: '签字确认', type: FieldType.Url });
    }

    if (!existingFields.includes('签字状态')) {
      fieldsToCreate.push({ 
        name: '签字状态', 
        type: FieldType.SingleSelect,
        property: {
          options: [
            { name: '未签字' },
            { name: '已签字' }
          ]
        }
      });
    }

    if (!existingFields.includes('签字附件')) {
      fieldsToCreate.push({ name: '签字附件', type: FieldType.Attachment });
    }

    // 根据二维码开关状态,新增或删除二维码列
    const hasQRCodeField = existingFields.includes('签字二维码');
    
    if (config.value.enableQRCode && !hasQRCodeField) {
      // 开关打开且列不存在,则新增
      fieldsToCreate.push({ name: '签字二维码', type: FieldType.Attachment });
    } else if (!config.value.enableQRCode && hasQRCodeField) {
      // 开关关闭且列存在,则删除
      const qrCodeField = fieldList.find(f => f.name === '签字二维码');
      if (qrCodeField) {
        await table.deleteField(qrCodeField.id);
      }
    }

    // 创建字段
    for (const field of fieldsToCreate) {
      await table.addField(field);

    }

    if (fieldsToCreate.length === 0) {
      ElMessage.info('所有必要字段已存在');
    } else {
      ElMessage.success(`成功创建 ${fieldsToCreate.length} 个字段`);
    }

    isInitialized.value = true;
    // 重置二维码变更状态
    initialQRCodeState.value = config.value.enableQRCode;
    qrcodeChanged.value = false;


  } catch (error) {
    console.error('初始化失败:', error);

    ElMessage.error(`初始化失败: ${error.message}`);
  } finally {
    initializing.value = false;
  }
};

// 重新初始化表格
const reinitializeTable = async () => {
  try {
    const selection = await bitable.base.getSelection();
    if (!selection.tableId) {
      ElMessage.warning(t('config.select_row_tip'));
      return;
    }

    const table = await bitable.base.getTableById(selection.tableId);
    const fieldList = await table.getFieldMetaList();
    const existingFields = fieldList.map(f => f.name);

    // 检测字段变更
    const requiredFields = ['签字确认', '签字状态', '签字附件'];
    if (config.value.enableQRCode) {
      requiredFields.push('签字二维码');
    }

    const missingFields = requiredFields.filter(f => !existingFields.includes(f));
    
    let message = '确定要重新初始化表格结构吗?';
    if (missingFields.length > 0) {
      message += `\n\n将新增以下字段:\n${missingFields.join(', ')}`;
    } else {
      message = '\n\n将删除二维码字段及现存二维码数据。';
    }

    await ElMessageBox.confirm(message, '确认重新初始化', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });

    await initializeTable();

  } catch (error) {
    if (error !== 'cancel') {
      console.error('重新初始化失败:', error);
      ElMessage.error(`操作失败: ${error.message}`);
    }
  }
};

// 批量生成签字链接
const batchGenerateLinks = async () => {
  try {
    generating.value = true;


    const selection = await bitable.base.getSelection();
    if (!selection.tableId) {
      ElMessage.warning('请先选择一个数据表');
      return;
    }

    // 确保有 app_token
    if (!currentAppToken.value) {
       currentAppToken.value = await getAppToken();
    }
    
    if (!currentAppToken.value) {
      ElMessage.error(t('msg.no_app_token'));

      return;
    }
    
    // 调用后端API批量生成
    const frontendHost = import.meta.env.VITE_FRONTEND_HOST || window.location.origin;
    const apiBase = import.meta.env.VITE_API_BASE || '';

    const response = await fetch(`${apiBase}/batch/generate-links`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        app_token: currentAppToken.value,
        tenant_key: tenantKey.value,
        table_id: selection.tableId,
        frontend_host: frontendHost,
        sign_mode: config.value.signMode,
        sign_count: config.value.signCount,
        enable_qrcode: config.value.enableQRCode,
        lang: locale.value
      })
    });

    const result = await response.json();

    if (result.code === 0) {
      const { total, success, skipped, quota_skipped, failed } = result.data;
      
      if (quota_skipped > 0) {
        ElMessage.warning({
          message: t('msg.batch_partial_success', { success, quota_skipped }),
          duration: 5000
        });
        showPricing.value = true; // 引导充值
      } else {
        ElMessage.success(t('msg.batch_success', { success }));
      }
      fetchQuota(); // 刷新余额展示
    } else {
      if (result.code === 403) {
        ElMessage.error(t('pay.insufficient_quota'));
        showPricing.value = true;
      } else {
        throw new Error(result.msg || '批量生成失败');
      }
    }

  } catch (error) {
    console.error('批量生成失败:', error);

    ElMessage.error(`批量生成失败: ${error.message}`);
  } finally {
    generating.value = false;
  }
};

// 监听选中记录变化
const watchSelection = async () => {
  try {
    const selection = await bitable.base.getSelection();
    hasSelectedRecord.value = !!selection.recordId;
    selectedRecordId.value = selection.recordId || '';
  } catch (error) {
    console.error('获取选中记录失败:', error);
    hasSelectedRecord.value = false;
    selectedRecordId.value = '';
  }
};

// 生成单行签字链接
const generateSingleRowLink = async () => {
  try {
    generatingSingle.value = true;


    const selection = await bitable.base.getSelection();
    if (!selection.tableId || !selection.recordId) {
      ElMessage.warning(t('config.select_row_hint'));
      return;
    }

    // 确保有 app_token
    if (!currentAppToken.value) {
       currentAppToken.value = await getAppToken();
    }
    
    if (!currentAppToken.value) {
      ElMessage.error(t('msg.no_app_token'));

      return;
    }

    // 调用后端API生成单行链接(复用批量生成逻辑)
    const frontendHost = import.meta.env.VITE_FRONTEND_HOST || window.location.origin;
    const apiBase = import.meta.env.VITE_API_BASE || '';

    const response = await fetch(`${apiBase}/batch/generate-single-link`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        app_token: currentAppToken.value,
        tenant_key: tenantKey.value,
        table_id: selection.tableId,
        record_id: selection.recordId,
        frontend_host: frontendHost,
        sign_mode: singleRowConfig.value.mode,
        sign_count: singleRowConfig.value.count,
        enable_qrcode: config.value.enableQRCode,
        lang: locale.value
      })
    });

    const result = await response.json();

    if (result.code === 0) {
      ElMessage.success(t('msg.single_success'));
      fetchQuota(); // 更新余额
    } else {
      if (result.code === 403) {
        ElMessage.error(t('pay.insufficient_quota'));
        showPricing.value = true;
      } else {
        throw new Error(result.msg || '生成失败');
      }
    }

  } catch (error) {
    console.error('生成单行链接失败:', error);

    ElMessage.error(`生成失败: ${error.message}`);
  } finally {
    generatingSingle.value = false;
  }
};

// 组件挂载时检查初始化状态
onMounted(async () => {
  await checkInitialized();
  await fetchQuota(); // 获取配额
  // 监听选中记录变化
  await watchSelection();
  
  // 监听选中变化事件
  bitable.base.onSelectionChange(async () => {
    await watchSelection();
  });
});
</script>

<style scoped>
.config-panel {
  padding: 16px 20px;
  max-width: 800px;
  margin: 0 auto;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 需求3: 紧凑样式的温馨提示 */
.compact-tips {
  font-size: 12px;
}

.compact-tips :deep(.el-alert__content) {
  padding: 0;
}

.tips-content {
  line-height: 1.5;
}

.tips-content p {
  margin: 2px 0;
  font-size: 12px;
}

.config-card,
.action-card,
.log-card {
  border: 1px solid #ebeef5;
}

.form-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

/* 配额卡片样式 */
.quota-card {
  margin-bottom: 16px;
  background-color: #f0f7ff;
  border: 1px solid #d9ecff;
}

.quota-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.quota-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quota-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
  color: #409eff;
}

.quota-stats {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.stat-item .stat-label {
  color: #606266;
  margin-right: 4px;
}

.stat-item .stat-value {
  font-weight: 500;
  color: #303133;
}

.stat-item.highlight .stat-value {
  color: #f56c6c;
  font-size: 15px;
  font-weight: bold;
}

/* 价格表格样式 */
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.plan-card {
  padding: 16px;
  border: 1px solid #eee;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.plan-card:hover {
  border-color: #409eff;
  background-color: #f0f7ff;
}

.plan-quota {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 4px;
}

.plan-price {
  font-size: 18px;
  color: #f56c6c;
  font-weight: bold;
  margin-bottom: 4px;
}

.plan-tag {
  font-size: 10px;
  background-color: #fef0f0;
  color: #f56c6c;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  margin-bottom: 4px;
}

.plan-desc {
  font-size: 11px;
  color: #909399;
  margin-bottom: 10px;
}

.pricing-footer {
  text-align: center;
  font-size: 12px;
  color: #909399;
}

/* 支付弹窗样式 */
.payment-content {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 10px;
}

.order-info {
  background-color: #f8f8f8;
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  text-align: left;
}

.order-info p {
  margin: 4px 0;
}

.price-text {
  color: #f56c6c;
  font-size: 18px;
  font-weight: bold;
}

.qr-box {
  padding: 20px;
  border: 1px solid #efefef;
  border-radius: 8px;
}

.qr-box img {
  width: 150px;
  height: 150px;
}

.qr-tip {
  margin-top: 10px;
  font-size: 12px;
  color: #606266;
}

.action-btn {
  width: 100%;
  margin-bottom: 10px;
}

.tip-text {
  margin: 10px 0 0 0;
  font-size: 13px;
  color: #909399;
  text-align: center;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-list {
  max-height: 300px;
  overflow-y: auto;
}

.log-item {
  padding: 8px 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  font-size: 13px;
  display: flex;
  gap: 12px;
}

.log-item.info {
  background-color: #f4f4f5;
  color: #606266;
}

.log-item.success {
  background-color: #f0f9ff;
  color: #67c23a;
}

.log-item.warning {
  background-color: #fdf6ec;
  color: #e6a23c;
}

.log-item.error {
  background-color: #fef0f0;
  color: #f56c6c;
}

.log-time {
  flex-shrink: 0;
  color: #909399;
  font-size: 12px;
}

.log-message {
  flex: 1;
}

/* 反馈卡片样式 */
.feedback-card {
  margin-top: 8px;
  border: 1px solid #e6e8eb;
  background: linear-gradient(135deg, #f5f7fa 0%, #f0f2f5 100%);
}

.feedback-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #606266;
  font-weight: 500;
}

.feedback-content {
  text-align: center;
}

.feedback-desc {
  font-size: 13px;
  color: #606266;
  margin: 0 0 14px 0;
  line-height: 1.6;
}

.feedback-actions {
  margin-bottom: 12px;
}

.feedback-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.feedback-tip {
  font-size: 11px;
  color: #909399;
  margin: 0;
}
</style>
