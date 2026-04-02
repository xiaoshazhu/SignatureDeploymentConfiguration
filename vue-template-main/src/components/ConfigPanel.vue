<template>
  <div class="config-panel">

    <el-form ref="formRef" class="config-form" :model="config" label-position="top">
      <!-- 温馨提示 -->
      <el-alert
        title="温馨提示"
        type="info"
        :closable="false"
        class="compact-tips"
      >
        <template #default>
          <div class="tips-content">
            <p>1、切换数据表格之后,请重新打开插件页面</p>
            <p>2、当点击操作按钮之后,在操作完成之前请勿改动表格内容</p>
            <p>3、批量生成只针对未生成签字链接的数据行</p>
          </div>
        </template>
      </el-alert>

      <!-- 批量配置区域 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <span>批量配置</span>
        </template>

        <el-form-item label="签字模式">
          <el-radio-group v-model="config.signMode" @change="onConfigChange">
            <el-radio label="或签">或签(任意一人签字即可)</el-radio>
            <el-radio label="会签">会签(所有人都需签字)</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="需签字人数" v-if="config.signMode === '会签'">
          <el-input-number 
            v-model="config.signCount" 
            :min="1" 
            :max="10"
            @change="onConfigChange"
          />
        </el-form-item>

        <!-- 未初始化时:显示生成二维码开关 -->
        <el-form-item label="生成二维码" v-if="!isInitialized">
          <el-switch 
            v-model="config.enableQRCode"
            @change="onConfigChange"
          />
          <span class="form-tip">为签字链接生成二维码</span>
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
              {{ initializing ? '正在初始化...' : '初始化表格结构' }}
            </el-button>
            <p class="tip-text">首次使用需要初始化表格,将自动创建必要的字段</p>
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
              {{ generating ? '正在批量生成中...' : '批量生成签字链接' }}
            </el-button>

            <!-- 更多操作折叠 - 只在已初始化后显示 -->
            <el-collapse v-model="activeCollapse" style="margin-top: 16px;">
              <el-collapse-item title="更多操作" name="more">
                <!-- 生成二维码开关 -->
                <el-form-item label="生成二维码">
                  <el-switch 
                    v-model="config.enableQRCode"
                    @change="onQRCodeChange"
                  />
                  <span class="form-tip">为签字链接生成二维码</span>
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
                  {{ initializing ? '正在初始化...' : '初始化表格结构' }}
                </el-button>
                <p class="tip-text" v-if="qrcodeChanged">
                  ⚠️ 检测到二维码开关变更,需要重新初始化表格
                </p>
                <p class="tip-text" v-else>
                  💡 只有修改了二维码开关才需要重新初始化
                </p>
              </el-collapse-item>
            </el-collapse>
          </template>
        </div>
      </el-card>

      <!-- 单行操作区域 -->
      <el-card v-if="isInitialized" class="config-card" shadow="never">
        <template #header>
          <span>单行操作</span>
        </template>

        <el-form-item label="签字模式">
          <el-radio-group v-model="singleRowConfig.mode">
            <el-radio label="或签">或签(任意一人签字即可)</el-radio>
            <el-radio label="会签">会签(所有人都需签字)</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="需签字人数" v-if="singleRowConfig.mode === '会签'">
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
            {{ generatingSingle ? '正在生成中...' : '为选中行生成链接' }}
          </el-button>
          <p class="tip-text" v-if="!hasSelectedRecord">
            💡 请先选中一行记录
          </p>
          <p class="tip-text" v-else>
            ✅ 已选中记录,点击按钮为该行生成签字链接
          </p>
        </div>
      </el-card>

      <!-- 单行配置对话框 - 删除,不再需要 -->


    </el-form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { bitable, FieldType } from '@lark-base-open/js-sdk';
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
      ElMessage.warning('请先选择一个数据表');
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
      ElMessage.warning('请先选择一个数据表');
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
      ElMessage.error('无法获取 App Token，请确保在飞书多维表格环境中运行');

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
        table_id: selection.tableId,
        frontend_host: frontendHost,
        sign_mode: config.value.signMode,
        frontend_host: frontendHost,
        sign_mode: config.value.signMode,
        sign_count: config.value.signCount,
        enable_qrcode: config.value.enableQRCode // 需求: 传递二维码开关状态
      })
    });

    const result = await response.json();

    if (result.code === 0) {
      const { total, success, skipped, failed } = result.data;

      ElMessage.success(`成功生成 ${success} 条签字链接`);
    } else {
      throw new Error(result.msg || '批量生成失败');
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
      ElMessage.warning('请先选择一行记录');
      return;
    }

    // 确保有 app_token
    if (!currentAppToken.value) {
       currentAppToken.value = await getAppToken();
    }
    
    if (!currentAppToken.value) {
      ElMessage.error('无法获取 App Token，请确保在飞书多维表格环境中运行');

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
        table_id: selection.tableId,
        record_id: selection.recordId,
        frontend_host: frontendHost,
        sign_mode: singleRowConfig.value.mode,  // 单行配置
        sign_mode: singleRowConfig.value.mode,  // 单行配置
        sign_count: singleRowConfig.value.count,  // 单行配置
        enable_qrcode: config.value.enableQRCode // 需求: 传递二维码开关状态
      })
    });

    const result = await response.json();

    if (result.code === 0) {

      ElMessage.success('签字链接已生成');
    } else {
      throw new Error(result.msg || '生成失败');
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
  // 监听选中记录变化
  await watchSelection();
  
  // 监听选中变化事件
  bitable.base.onSelectionChange(async () => {
    await watchSelection();
  });
  
  // TODO: 加载保存的配置
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
</style>
