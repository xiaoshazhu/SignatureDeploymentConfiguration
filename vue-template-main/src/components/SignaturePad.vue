<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElLoading } from 'element-plus';
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
  
  const loadingInstance = ElLoading.service({ text: '正在应用签名...' });
  try {
    const success = await saveToCurrentSelection(savedSignature.value);
    if (success) ElMessage.success('签名已应用！');
  } catch (e) {
    ElMessage.error('应用失败: ' + e.message);
  } finally {
    loadingInstance.close();
  }
};

// 动作：保存新签名
const saveNewSignature = async () => {
  const { isEmpty, data } = signaturePad.value.saveSignature();
  if (isEmpty) {
    ElMessage.warning('请先写下您的名字');
    return;
  }

  const loadingInstance = ElLoading.service({ text: '正在上传并存档...' });
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
      ElMessage.success('签名保存成功！');
      // 更新本地缓存
      savedSignature.value = file; // 实际上这里应该存 Token，刷新后才会变成 Token
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message);
  } finally {
    loadingInstance.close();
  }
};
</script>

<template>
  <div class="container">
    <div class="header">
      <h3>✍️ 在线电子签名</h3>
      <p class="sub-text">签名将自动保存到附件列</p>
    </div>

    <div v-if="mode === 'preview'" class="preview-area">
      <el-alert title="检测到您有常用签名" type="success" :closable="false" show-icon />
      <div class="img-wrapper">
        <div class="placeholder-sig">
          [ 您的历史签名存档 ]
        </div>
      </div>
      <div class="btn-group">
        <el-button type="primary" size="large" @click="useOldSignature">
          ✅ 使用此签名
        </el-button>
        <el-button size="large" @click="switchToDraw">
          ✏️ 重新手写
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
      <div class="tips">请在上方空白区域书写</div>
      <div class="btn-group">
        <el-button @click="clear">清空</el-button>
        <el-button type="primary" @click="saveNewSignature">确认保存</el-button>
        <el-button v-if="savedSignature" link @click="mode = 'preview'">返回</el-button>
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