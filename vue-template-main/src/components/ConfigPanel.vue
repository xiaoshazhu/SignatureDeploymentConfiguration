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
            <el-badge :is-dot="!isTokenSet" type="danger">
              <el-button size="small" :type="!isTokenSet ? 'danger' : ''" :plain="isTokenSet" @click="showSetup = true">
                <el-icon><Setting /></el-icon>
                <span>{{ $t('common.setup_btn') }}</span>
              </el-button>
            </el-badge>
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
        :type="isTokenSet ? 'info' : 'error'"
        :closable="false"
        class="compact-tips"
      >
        <template #default>
          <div class="tips-content">
            <p class="tip-mandatory">{{ $t('common.tip_setup_mandatory') }}</p>
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
            <el-tooltip :content="$t('config.init_disabled_tip')" :disabled="isTokenSet" placement="top">
              <el-button 
                type="primary" 
                size="large" 
                :loading="initializing"
                :disabled="!isTokenSet"
                @click="initializeTable"
                class="action-btn"
              >
                {{ initializing ? $t('config.initializing') : $t('config.init_btn') }}
              </el-button>
            </el-tooltip>
            <p class="tip-text" v-if="!isTokenSet" style="color: #f56c6c;">🔒 {{ $t('config.init_disabled_tip') }}</p>
            <p class="tip-text" v-else>{{ $t('config.init_tip_first') }}</p>
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

    <!-- 微信支付真实弹窗 (Native Pay) -->
    <el-dialog v-model="showPayment" :title="$t('pay.modal_title')" width="80%" center class="payment-modal" append-to-body>
      <div class="payment-content">
        <div class="order-info">
          <p>{{ $t('pay.order_id') }}：{{ currentOrder.id }}</p>
          <p>{{ $t('pay.amount') }}：<span class="price-text">{{ currentOrder.price }}</span></p>
          <p>{{ $t('pay.recharge_quota') }}：{{ currentOrder.quota }}{{ $t('common.times') }}</p>
        </div>
        <div class="qr-box">
          <!-- 动态生成二维码 -->
          <img 
            v-if="currentOrder.code_url"
            :src="`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(currentOrder.code_url)}`" 
            alt="WeChat Pay QR" 
          />
          <p class="qr-tip">{{ $t('pay.scan_tip') }}</p>
        </div>
      </div>
    </el-dialog>
    
    <!-- 系统配置对话框 -->
    <el-dialog v-model="showSetup" :title="$t('config.setup_title')" width="90%" center :close-on-click-modal="false" append-to-body>
      <div class="setup-content">
        <el-alert
          :title="$t('config.setup_tip')"
          type="warning"
          :closable="false"
          style="margin-bottom: 16px;"
        />
        <el-form label-position="top">
          <el-form-item :label="$t('config.token_label')">
            <el-input 
              v-model="tempToken" 
              type="password" 
              show-password 
              placeholder="请输入飞书个人授权码 (Personal Base Token)" 
            />
          </el-form-item>
        </el-form>
        <div class="setup-help">
          <h3>{{ $t('config.setup_help_title') }}</h3>
          <div class="setup-steps">
            <div class="step-item">
              <span class="step-num">1</span>
              <p>{{ $t('config.setup_step_1') }}</p>
              <div class="step-img-box">
                <img src="/feishu001.jpeg" alt="Step 1" @click="previewImage('/feishu001.jpeg')">
              </div>
            </div>
            <div class="step-item">
              <span class="step-num">2</span>
              <p>{{ $t('config.setup_step_2') }}</p>
              <div class="step-img-box">
                <img src="/feishu002.jpeg" alt="Step 2" @click="previewImage('/feishu002.jpeg')">
              </div>
            </div>
            <div class="step-item">
              <span class="step-num">3</span>
              <p>{{ $t('config.setup_step_3') }}</p>
              <div class="step-img-box">
                <img src="/feishu003.jpeg" alt="Step 3" @click="previewImage('/feishu003.jpeg')">
              </div>
            </div>
            <div class="step-item">
              <span class="step-num">4</span>
              <p>{{ $t('config.setup_step_4') }}</p>
              <div class="step-img-box">
                <img src="/feishu004.jpeg" alt="Step 4" @click="previewImage('/feishu004.jpeg')">
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showSetup = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="savingToken" @click="saveToken">
          {{ $t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { CreditCard, ChatDotRound, ChatLineSquare, Setting } from '@element-plus/icons-vue';
import { bitable, FieldType } from '@lark-base-open/js-sdk';
import { ElMessage, ElMessageBox } from 'element-plus';

const { t, locale } = useI18n();
import { getAppToken } from '../utils/bitableHelper';

// 图片预览相关
const previewImage = (url) => {
  ElMessageBox.alert(
    `<img src="${url}" style="width: 100%; max-height: 80vh; object-fit: contain;" />`,
    t('config.setup_help_title'),
    {
      dangerouslyUseHTMLString: true,
      customClass: 'image-preview-dialog',
      confirmButtonText: t('common.confirm')
    }
  );
};

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
const pollingTimer = ref(null);

// 系统配置相关
const showSetup = ref(false);
const tempToken = ref('');
const savingToken = ref(false);
const isTokenSet = ref(false);

const checkConfig = async () => {
  try {
    const apiBase = import.meta.env.VITE_API_BASE || '';
    const res = await fetch(`${apiBase}/config/check`);
    const result = await res.json();
    if (result.code === 0) {
      isTokenSet.value = !!result.data.token_set;
      if (!result.data.token_set) {
        showSetup.value = true;
      }
    }
  } catch (e) {
    console.error('检查配置失败:', e);
  }
};

const saveToken = async () => {
  if (!tempToken.value) {
    ElMessage.warning('请输入有效的授权码');
    return;
  }
  
  try {
    savingToken.value = true;
    const apiBase = import.meta.env.VITE_API_BASE || '';
    const res = await fetch(`${apiBase}/config/set-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ personal_base_token: tempToken.value })
    });
    const result = await res.json();
    if (result.code === 0) {
      ElMessage.success('配置保存成功');
      showSetup.value = false;
      tempToken.value = '';
      isTokenSet.value = true;
      // 配置保存后刷新其他状态
      fetchQuota();
      checkInitialized();
    } else {
      ElMessage.error(result.msg || '保存失败');
    }
  } catch (e) {
    ElMessage.error('网络连接失败');
  } finally {
    savingToken.value = false;
  }
};

const pricingPlans = [
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

// 轮询订单状态
const startPolling = (orderId) => {
  if (pollingTimer.value) clearInterval(pollingTimer.value);
  
  const apiBase = import.meta.env.VITE_API_BASE || '';
  pollingTimer.value = setInterval(async () => {
    try {
      const res = await fetch(`${apiBase}/pay/status/${orderId}`);
      const result = await res.json();
      if (result.code === 0 && result.status === 'SUCCESS') {
        clearInterval(pollingTimer.value);
        pollingTimer.value = null;
        ElMessage.success(t('pay.pay_success'));
        showPayment.value = false;
        fetchQuota(); // 刷新余额
      }
    } catch (e) {
      console.error('轮询订单状态失败:', e);
    }
  }, 3000);
};

// 真实支付流程
const handleRecharge = async (plan) => {
  try {
    showPricing.value = false;
    const apiBase = import.meta.env.VITE_API_BASE || '';
    
    // 1. 调用后端创建真实订单
    const res = await fetch(`${apiBase}/pay/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tenant_key: tenantKey.value,
        package_id: `plan_${plan.quota}`, // 使用额度作为标识
        quota: plan.quota,
        amount: parseFloat(plan.price.replace('元','')),
        pay_type: 'wechat'
      })
    });
    
    const result = await res.json();
    if (result.code === 0) {
      // 2. 这里的 data 包含 order_id 和 code_url
      currentOrder.value = {
        id: result.data.order_id,
        price: plan.price,
        quota: plan.quota,
        code_url: result.data.code_url
      };
      
      // 3. 显示支付弹窗
      showPayment.value = true;
      
      // 4. 开始轮询状态
      startPolling(result.data.order_id);
    } else {
      ElMessage.error(result.msg || '下单失败');
    }
  } catch (e) {
    console.error('充值请求失败:', e);
    ElMessage.error('网络错误,请重试');
  }
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
  await checkConfig(); // 检查是否有授权码
  await checkInitialized();
  await fetchQuota(); // 获取配额
  // 监听选中记录变化
  await watchSelection();
  
  // 监听选中变化事件
  bitable.base.onSelectionChange(async () => {
    await watchSelection();
  });
});

onUnmounted(() => {
  if (pollingTimer.value) clearInterval(pollingTimer.value);
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

.tip-mandatory {
  font-weight: bold;
  color: #f56c6c;
  font-size: 13px !important;
  margin-bottom: 6px !important;
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

/* 系统配置教程样式 */
.setup-content {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 8px;
}

.setup-help {
  margin-top: 24px;
  border-top: 1px solid #eee;
  padding-top: 16px;
}

.setup-help h3 {
  font-size: 16px;
  margin-bottom: 16px;
  color: #303133;
}

.setup-steps {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step-item {
  position: relative;
  padding-left: 32px;
}

.step-num {
  position: absolute;
  left: 0;
  top: 0;
  width: 24px;
  height: 24px;
  background-color: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.step-item p {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #606266;
  line-height: 24px;
}

.step-img-box {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
  cursor: zoom-in;
  transition: all 0.3s;
}

.step-img-box:hover {
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
  border-color: #409eff;
}

.step-img-box img {
  width: 100%;
  display: block;
}

:deep(.image-preview-dialog) {
  width: 90% !important;
  max-width: 800px;
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
