import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElLoading } from 'element-plus';

const { t } = useI18n();
import { getCurrentUserId, findUserSignature, saveToCurrentSelection, saveSignatureToConfig } from '../utils/bitableOps';
import { bitable } from '@lark-base-open/js-sdk';

// 状态管理
const signaturePad = ref(null);
const loading = ref(false);
const savedSignature = ref(null); // 存储上次的签名对象 (Token)
const mode = ref('draw'); // 'draw' (手写) | 'preview' (预览旧签名)

// 初始化
onMounted(async () => {
  await checkUserHistory();
  // 监听选中变化，可以在这里做自动刷新逻辑，暂时略过
});

// 检查历史签名
const checkUserHistory = async () => {
  loading.value = true;
  try {
    const userId = await getCurrentUserId();
    const historySig = await findUserSignature(userId);
    if (historySig) {
      savedSignature.value = historySig;
      mode.value = 'preview'; // 只有找到存档才进入预览模式
    }
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

// 动作：清空画板
const clear = () => {
  signaturePad.value.clearSignature();
};

// 动作：切换到重写模式
const switchToDraw = () => {
  mode.value = 'draw';
};

// 动作：使用旧签名
const useOldSignature = async () => {
  if (!savedSignature.value) return;
  
  const loadingInstance = ElLoading.service({ text: t('pad.loading_apply') });
  try {
    const success = await saveToCurrentSelection(savedSignature.value);
    if (success) ElMessage.success(t('pad.apply_success'));
  } catch (e) {
    ElMessage.error(t('pad.apply_fail') + ': ' + e.message);
  } finally {
    loadingInstance.close();
  }
};

// 动作：保存新签名
const saveNewSignature = async () => {
  const { isEmpty, data } = signaturePad.value.saveSignature();
  if (isEmpty) {
    ElMessage.warning(t('pad.sign_hint'));
    return;
  }

  const loadingInstance = ElLoading.service({ text: t('pad.loading_save') });
  try {
    // 1. base64 转 File 对象
    const blob = await (await fetch(data)).blob();
    const file = new File([blob], "signature.png", { type: "image/png" });

    // 2. 写入当前业务表
    const success = await saveToCurrentSelection(file);
    
    // 3. 异步存档到配置表（不阻塞主流程）
    if (success) {
      const userId = await getCurrentUserId();
      saveSignatureToConfig(userId, file); // 这里的 file 最好是上传后返回的 token，但 SDK 允许直接存 File，为了简化逻辑先这样
      ElMessage.success(t('pad.save_success'));
      // 更新本地缓存
      savedSignature.value = file; // 实际上这里应该存 Token，刷新后才会变成 Token
    }
  } catch (e) {
    ElMessage.error(t('pad.save_fail') + ': ' + e.message);
  } finally {
    loadingInstance.close();
  }
};
</script>

<template>
  <div class="container">
    <div class="header">
      <h3>{{ $t('pad.title') }}</h3>
      <p class="sub-text">{{ $t('pad.sub_text') }}</p>
    </div>

    <div v-if="mode === 'preview'" class="preview-area">
      <el-alert :title="$t('pad.history_alert')" type="success" :closable="false" show-icon />
      <div class="img-wrapper">
        <div class="placeholder-sig">
          {{ $t('pad.history_title') }}
        </div>
      </div>
      <div class="btn-group">
        <el-button type="primary" size="large" @click="useOldSignature">
          {{ $t('pad.use_history') }}
        </el-button>
        <el-button size="large" @click="switchToDraw">
          {{ $t('pad.redraw') }}
        </el-button>
      </div>
    </div>

    <div v-else class="draw-area">
      <div class="pad-wrapper">
        <VueSignaturePad
          ref="signaturePad"
          width="100%"
          height="200px"
          :options="{ penColor: '#000000', backgroundColor: 'rgba(255,255,255,0)' }"
        />
      </div>
      <div class="tips">{{ $t('pad.draw_placeholder') }}</div>
      <div class="btn-group">
        <el-button @click="clear">{{ $t('pad.clear_btn') }}</el-button>
        <el-button type="primary" @click="saveNewSignature">{{ $t('pad.confirm_btn') }}</el-button>
        <el-button v-if="savedSignature" link @click="mode = 'preview'">{{ $t('pad.back_btn') }}</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.pad-wrapper {
  border: 2px dashed #ddd;
  border-radius: 8px;
  background: #f9f9f9; /* 浅灰底色突出画板 */
}
.tips {
  font-size: 12px;
  color: #999;
  text-align: center;
  margin-top: -10px;
  margin-bottom: 10px;
}
.img-wrapper {
  height: 120px;
  background: #f0f9eb;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid #e1f3d8;
  color: #67c23a;
  font-weight: bold;
}
.btn-group {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.btn-group .el-button {
  flex: 1;
}
</style>