<template>
  <div class="sign-page" :class="{ 'mobile-layout': isMobile, 'landscape': isLandscape }">
    <div class="header" v-if="!isMobile">
      <h2>{{ $t('sign.title') }}</h2>
      <div class="status-tag" :class="statusClass">{{ displayStatusText }}</div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else class="content">
      <!-- Accordion for Row Data -->
      <el-collapse v-model="activeNames" class="data-accordion" ref="accordionRef">
        <el-collapse-item :title="$t('sign.view_details')" name="1">
          <div class="data-list">
            <div v-for="(value, key) in filteredRowData" :key="key" class="data-item">
              <span class="data-label">{{ key }}:</span>
              <span class="data-value">{{ formatValue(key, value) }}</span>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>

      <!-- 需求11: 已签字状态 - 展示签名图片 -->
      <div v-if="statusText === '已签字'" class="signed-section">
        <el-alert
          :title="$t('sign.already_signed_alert')"
          type="success"
          :closable="false"
          show-icon
        />
        
        <div class="signature-images">
          <div v-for="(img, index) in signatureImages" :key="index" class="signature-image-item">
            <el-image 
              :src="img.url" 
              :preview-src-list="signatureImages.map(i => i.url)"
              fit="contain"
              style="width: 200px; height: 150px;"
            >
              <template #error>
                <div class="image-error">{{ $t('sign.load_fail') }}</div>
              </template>
            </el-image>
            <p class="image-label">{{ $t('common.success') }} {{ index + 1 }}</p>
          </div>
        </div>

        <el-button type="default" size="large" class="submit-btn" @click="closeWindow">
          {{ $t('common.close') }}
        </el-button>
      </div>

      <!-- 未签字/签字中状态 - 显示签字画板 -->
      <div v-else class="signature-container-wrapper" style="flex: 1; display: flex; flex-direction: column;">
        <!-- Signature Area -->
        <div class="signature-section">
          <div class="canvas-wrapper" :style="isMobile ? { height: canvasHeight + 'px' } : {}">
            <VueSignaturePad 
              width="100%" 
              height="100%" 
              ref="signaturePad" 
              :options="{ penColor: '#000', backgroundColor: '#f5f7fa', onBegin: handleBegin }" 
            />
            <!-- 需求: 提示文字 (桌面端/移动端通用, 样式区分) -->
            <div class="signature-tip" v-if="!hasInteracted">
              {{ $t('sign.sign_here_tip') }}
            </div>
            <!-- 需求13: 开始签字后隐藏提示 -->
            <div class="canvas-placeholder" v-if="!hasInteracted">
              
            </div>
          </div>
        </div>

        <!-- Submit Actions -->
        <div class="submit-actions" ref="actionsRef">
          <el-button size="large" class="submit-btn" @click="clear">{{ $t('sign.clear_btn') }}</el-button>
          
          <el-button type="primary" size="large" class="submit-btn" @click="submit('new')" :loading="submitting">
            {{ $t('sign.submit_btn') }}
          </el-button>
          
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';

const { t, locale } = useI18n();

const signaturePad = ref(null);
const accordionRef = ref(null);
const actionsRef = ref(null);
const canvasHeight = ref(300); // 默认高度

const loading = ref(true);
const submitting = ref(false);
const activeNames = ref([]);
const hasInteracted = ref(false);
const isMobile = ref(false);
const isLandscape = ref(false);

const rowData = ref({});
const canReuse = ref(false);
const historyToken = ref('');
const statusText = ref('待签字');
const signatureImages = ref([]); // 需求11: 存储已签字的图片列表

// 状态文本国际化映射
const statusMap = {
  '待签字': 'sign.status_pending',
  '已签字': 'sign.status_signed',
  '签字中': 'sign.status_signing'
};

const displayStatusText = computed(() => {
  const key = statusMap[statusText.value] || statusText.value;
  return t(key);
});

const filteredRowData = computed(() => {
  const excludedKeys = ['签字二维码', '签字状态', '签字确认', '签字附件'];
  const data = {};
  for (const key in rowData.value) {
    if (!excludedKeys.includes(key)) {
      data[key] = rowData.value[key];
    }
  }
  return data;
});

const formatValue = (key, value) => {
  if (!value) return '';
  
  // 如果是数字（可能是时间戳），尝试转换
  if (typeof value === 'number') {
    // 假设是毫秒级时间戳，且大于 1970 年（避免误判普通数字）
    if (value > 946684800000) { // > 2000-01-01
       const date = new Date(value);
       if (!isNaN(date.getTime())) {
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          const hours = String(date.getHours()).padStart(2, '0');
          const minutes = String(date.getMinutes()).padStart(2, '0');
          const seconds = String(date.getSeconds()).padStart(2, '0');
          
          if (hours === '00' && minutes === '00' && seconds === '00') {
             return `${year}-${month}-${day}`;
          }
          return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
       }
    }
    return value;
  }

  // 如果是字符串
  if (typeof value === 'string') {
    // 匹配 "YYYY-MM-DD HH:mm:ss" 或 "YYYY/MM/DD HH:mm:ss"
    // 简单检查是否包含 00:00:00
    if (value.includes('00:00:00')) {
      return value.replace(' 00:00:00', '').replace('T00:00:00', '');
    }
  }
  
  return value;
};

const statusClass = computed(() => {
  if (statusText.value.includes('已签字')) return 'status-success';
  if (statusText.value.includes('签字中')) return 'status-warning';
  return 'status-pending';
});

// Get params
const getParams = () => {
  const params = new URLSearchParams(window.location.search);
  return {
    appToken: params.get('app_token'),
    tableId: params.get('table_id'),
    recordId: params.get('record_id'),
    userId: params.get('user_id'),
    mode: params.get('mode'),
    count: params.get('count')
  };
};

const initPage = async () => {
  // 检查是否是加密参数
  const urlParams = new URLSearchParams(window.location.search);
  const encryptedParam = urlParams.get('p');
  
  if (encryptedParam) {
    // 新版加密链接:直接将加密参数传递给后端
    try {
      const apiBase = import.meta.env.VITE_API_BASE;
      const res = await fetch(`${apiBase}/sign/info?p=${encodeURIComponent(encryptedParam)}`);
      
      if (!res.ok) throw new Error('Failed to fetch data');
      
      const result = await res.json();
      
      if (result.code === 0) {
        const data = result.data;
        rowData.value = data.row_data || {};
        canReuse.value = !!data.history_signature;
        historyToken.value = data.history_signature;
        statusText.value = data.status || '待签字';
        
        // 如果已签字,获取签名图片列表
        if (statusText.value === '已签字' && data.signature_images) {
          signatureImages.value = data.signature_images.map(img => {
            if (img.url && !img.url.startsWith('http')) {
              return {
                ...img,
                url: `${apiBase}/${img.url}`
              };
            }
            return img;
          });
        }
        } else {
        throw new Error(result.msg || t('sign.load_fail'));
      }
    } catch (e) {
      console.error('获取签字信息失败:', e);
      
      // 区分错误类型提供更明确的提示
      let errorMessage = t('sign.load_fail');
      
      if (e.name === 'TypeError' && (e.message.includes('fetch') || e.message.includes('Failed to fetch'))) {
        errorMessage = t('sign.net_error');
      } else if (e.message && e.message.includes('400')) {
        errorMessage = t('sign.param_error');
      } else if (e.message && (e.message.includes('401') || e.message.includes('403'))) {
        errorMessage = t('sign.auth_error');
      } else if (e.message && e.message.includes('404')) {
        errorMessage = t('sign.not_found');
      } else if (e.message && e.message.includes('500')) {
        errorMessage = t('sign.server_error');
      } else if (e.message) {
        errorMessage = e.message;
      }
      
      ElMessage.error(errorMessage);
      statusText.value = t('sign.load_fail');
      
      // 生产环境不使用 Mock 数据
      if (import.meta.env.MODE === 'development') {
        rowData.value = {
          '合同编号': 'HT-2023-001',
          '客户名称': '测试科技有限公司',
          '金额': '¥ 50,000.00',
          '申请人': '张三'
        };
        canReuse.value = true;
      }
    } finally {
      loading.value = false;
      nextTick(() => {
        calculateCanvasHeight();
      });
    }
    return;
  }
  
  // 旧版明文参数:向后兼容
  const { appToken, tableId, recordId, userId, mode, count } = getParams();
  if (!tableId || !recordId) {
    ElMessage.error('链接无效:缺少参数');
    loading.value = false;
    return;
  }

  try {
    // 调用后端 API 获取签字页数据
    const apiBase = import.meta.env.VITE_API_BASE; 
    const params = new URLSearchParams({
      table_id: tableId,
      record_id: recordId
    });
    
    if (appToken) params.append('app_token', appToken);
    if (userId) params.append('user_id', userId);
    if (mode) params.append('mode', mode);
    if (count) params.append('count', count);
    
    const res = await fetch(`${apiBase}/sign/info?${params.toString()}`);
    
    if (!res.ok) throw new Error('Failed to fetch data');
    
    const result = await res.json();
    
    if (result.code === 0) {
      const data = result.data;
      rowData.value = data.row_data || {};
      canReuse.value = !!data.history_signature;
      historyToken.value = data.history_signature;
      statusText.value = data.status || '待签字';
      
      // 需求11: 如果已签字,获取签名图片列表
      if (statusText.value === '已签字' && data.signature_images) {
        signatureImages.value = data.signature_images.map(img => {
          // 如果是相对路径(proxy/image),拼接 API Base
          if (img.url && !img.url.startsWith('http')) {
             return {
               ...img,
               url: `${apiBase}/${img.url}`
             };
          }
          return img;
        });
      }
    } else {
      throw new Error(result.msg || '获取数据失败');
    }

  } catch (e) {
    console.error('获取签字信息失败:', e);
    
    // 区分错误类型提供更明确的提示
    let errorMessage = '获取数据失败';
    
    if (e.name === 'TypeError' && (e.message.includes('fetch') || e.message.includes('Failed to fetch'))) {
      errorMessage = '网络连接失败,请检查网络后重试';
    } else if (e.message && e.message.includes('400')) {
      errorMessage = '链接参数无效或已被篡改';
    } else if (e.message && (e.message.includes('401') || e.message.includes('403'))) {
      errorMessage = '链接已过期或无权访问';
    } else if (e.message && e.message.includes('404')) {
      errorMessage = '记录不存在或已被删除';
    } else if (e.message && e.message.includes('500')) {
      errorMessage = '服务器内部错误,请稍后重试';
    } else if (e.message) {
      errorMessage = e.message;
    }
    
    ElMessage.error(errorMessage);
    statusText.value = '加载失败';
    
    // 生产环境不使用 Mock 数据
    if (import.meta.env.MODE === 'development') {
      // 开发环境使用 Mock 数据方便调试
      rowData.value = {
        '合同编号': 'HT-2023-001',
        '客户名称': '测试科技有限公司',
        '金额': '￥ 50,000.00',
        '申请人': '张三'
      };
      canReuse.value = true;
    }
  } finally {
    loading.value = false;
    // 数据加载完成后重新计算高度
    nextTick(() => {
      calculateCanvasHeight();
    });
  }
};

const clear = () => {
  signaturePad.value.clearSignature();
  hasInteracted.value = false;
};

const submit = async (type) => {
  // 检查是否是加密参数
  const urlParams = new URLSearchParams(window.location.search);
  const encryptedParam = urlParams.get('p');
  
  let payload = {
    sign_type: type
  };
  
  if (encryptedParam) {
    // 新版加密链接:将加密参数传递给后端
    payload.encrypted_params = encryptedParam;
  } else {
    // 旧版明文参数:向后兼容
    const { appToken, tableId, recordId, userId, mode, count } = getParams();
    payload.app_token = appToken;
    payload.table_id = tableId;
    payload.record_id = recordId;
    payload.user_id = userId;
    payload.sign_mode = mode;
    payload.sign_count = count;
  }

  if (type === 'new') {
    const { isEmpty, data } = signaturePad.value.saveSignature();
    if (isEmpty) {
      ElMessage.warning(t('sign.sign_placeholder_tip'));
      return;
    }
    
    // 需求: 移动端自动旋转图片 (仅在竖屏时旋转)
    if (isMobile.value && !isLandscape.value) {
      try {
        payload.image_base64 = await rotateImage(data);
      } catch (e) {
        console.error('Rotate image failed:', e);
        payload.image_base64 = data; // 降级处理
      }
    } else {
      payload.image_base64 = data;
    }
  } else {
    payload.file_token = historyToken.value;
  }

  submitting.value = true;
  try {
    const apiBase = import.meta.env.VITE_API_BASE;
    const res = await fetch(`${apiBase}/sign/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await res.json();
    if (result.code === 0) {
      ElMessage.success(t('sign.submit_success'));
      statusText.value = '已签字';
      setTimeout(() => {
        window.close();
      }, 1500);
    } else {
      // 需求12: 检测是否已被他人签署
      if (result.code === 409 || result.msg.includes('已签')) {
        ElMessage.warning(t('sign.already_signed_others'));
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } else {
        throw new Error(result.msg || 'Unknown error');
      }
    }
  } catch (e) {
    console.error('提交签名失败:', e);
    
    // 区分错误类型
    let errorMessage = '提交失败';
    
    if (result && result.code === 409) {
      errorMessage = '此记录已被他人签署,请刷新页面查看';
      ElMessage.warning(errorMessage);
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } else if (result && result.msg && result.msg.includes('已签')) {
      errorMessage = '此记录已被他人签署,请刷新页面查看';
      ElMessage.warning(errorMessage);
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } else if (e.name === 'TypeError' && e.message.includes('fetch')) {
      errorMessage = '网络连接失败,请检查网络后重试';
      ElMessage.error(errorMessage);
    } else if (e.message) {
      ElMessage.error(`提交失败: ${e.message}`);
    } else {
      ElMessage.error(errorMessage);
    }
  } finally {
    submitting.value = false;
  }
};

// 关闭窗口
const closeWindow = () => {
  window.close();
};

const checkMobile = () => {
  const userAgent = navigator.userAgent.toLowerCase();
  const isMobileDevice = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
  
  // 如果是移动设备，无论宽度如何都视为移动端布局(保持全屏体验)
  // 或者宽度小于768
  isMobile.value = isMobileDevice || window.innerWidth <= 768;
  
  // 检测横屏
  isLandscape.value = window.innerWidth > window.innerHeight;
  
  calculateCanvasHeight();
};

// 计算画板高度
const calculateCanvasHeight = () => {
  if (!isMobile.value) return;
  
  // 确保 DOM 元素存在
  if (!accordionRef.value?.$el && !document.querySelector('.data-accordion')) return;
  
  const windowHeight = window.innerHeight;
  // 获取各个部分的高度
  const accordionEl = accordionRef.value?.$el || document.querySelector('.data-accordion');
  const actionsEl = actionsRef.value || document.querySelector('.submit-actions');
  
  const accordionHeight = accordionEl ? accordionEl.offsetHeight : 0;
  const actionsHeight = actionsEl ? actionsEl.offsetHeight : 0;
  
  // 预留间距: 顶部padding(10) + 底部padding(10) + 组件间距(10) + 底部安全区(20)
  const margins = 50; 
  
  // 计算剩余空间
  const remainingHeight = windowHeight - accordionHeight - actionsHeight - margins;
  
  // 设置最小高度防止太小
  canvasHeight.value = Math.max(remainingHeight, 200);

  // 重新调整 Canvas 分辨率以匹配显示尺寸
  nextTick(() => {
    resizeCanvas();
  });
};

// 调整 Canvas 分辨率
const resizeCanvas = () => {
  if (signaturePad.value) {
    const canvas = signaturePad.value.$el.querySelector('canvas');
    if (canvas) {
      const ratio = Math.max(window.devicePixelRatio || 1, 1);
      // 保存当前内容 (如果需要保留，但通常 resize 会清空)
      // 这里直接重置，因为是在初始化或 resizing 时
      canvas.width = canvas.offsetWidth * ratio;
      canvas.height = canvas.offsetHeight * ratio;
      canvas.getContext('2d').scale(ratio, ratio);
      // 清除可能存在的偏移或旧内容
      signaturePad.value.clearSignature(); 
    }
  }
};

// 旋转图片 -90度 (逆时针90度)
const rotateImage = (base64) => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      // 交换宽高
      canvas.width = img.height;
      canvas.height = img.width;
      
      // 旋转上下文
      ctx.translate(0, canvas.height);
      ctx.rotate(-90 * Math.PI / 180);
      
      ctx.drawImage(img, 0, 0);
      
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = reject;
    img.src = base64;
  });
};

const handleBegin = () => {
  hasInteracted.value = true;
};

onMounted(() => {
  // 语言检测逻辑
  const urlParams = new URLSearchParams(window.location.search);
  const lang = urlParams.get('lang');
  if (lang) {
    if (lang.startsWith('zh')) locale.value = 'zh';
    else if (lang.startsWith('ja')) locale.value = 'ja';
    else locale.value = 'en';
  } else {
    // 降级使用浏览器语言
    const browserLang = navigator.language.toLowerCase();
    if (browserLang.startsWith('zh')) locale.value = 'zh';
    else if (browserLang.startsWith('ja')) locale.value = 'ja';
    else locale.value = 'en';
  }

  initPage();
  
  // 检测移动端
  checkMobile();
  window.addEventListener('resize', checkMobile);
  window.addEventListener('orientationchange', checkMobile);
});
</script>

<style scoped>
.sign-page {
  padding: 20px;
  max-width: 600px;
  margin: 0 auto;
  background: #fff;
  min-height: 100vh;
}
.header {
  text-align: center;
  margin-bottom: 20px;
}
.status-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  margin-top: 8px;
  background: #eee;
}
.status-success { background: #f0f9eb; color: #67c23a; }
.status-warning { background: #fdf6ec; color: #e6a23c; }

.data-accordion {
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.data-list {
  padding: 10px;
}
.data-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}
.data-label {
  color: #909399;
  flex-shrink: 0;
  margin-right: 10px;
}
.data-value {
  color: #303133;
  text-align: right;
}

.signature-section {
  margin-bottom: 30px;
}
.canvas-wrapper {
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  position: relative;
  overflow: hidden;
  height: 400px; /* 需求1: 增加画板高度 */
}
.canvas-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #c0c4cc;
  pointer-events: none;
}
/* .canvas-actions removed as button moved to bottom */

.submit-actions {
  display: flex;
  flex-direction: row; /* 需求2: 按钮左右布局 */
  justify-content: center;
  gap: 20px; /* 增加间距 */
}
.submit-btn {
  flex: 1; /* 按钮平分宽度 */
  margin-left: 0 !important;
}

/* 需求11: 已签字状态样式 */
.signed-section {
  padding: 20px 0;
}

.signature-images {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin: 20px 0;
  justify-content: center;
}

.signature-image-item {
  text-align: center;
}

.image-label {
  margin-top: 8px;
  font-size: 14px;
  color: #606266;
}

.image-error {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: #f5f7fa;
  color: #909399;
}

/* 移动端适配样式 */
.mobile-layout {
  padding: 10px;
  display: flex;
  flex-direction: column;
  height: 100vh;
  box-sizing: border-box;
  overflow: hidden; /* 防止滚动 */
}

.mobile-layout .content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mobile-layout .data-accordion {
  margin-bottom: 10px;
  flex-shrink: 0; /* 防止被压缩 */
}

/* 签字区域 */
.mobile-layout .signature-section {
  display: flex;
  flex-direction: column;
  margin: 10px 10px; /* 增加左右间距 */
  flex-shrink: 0;
}

.mobile-layout .canvas-wrapper {
  width: 100%;
  border: 2px dashed #409EFF; /* 移动端加重边框提示 */
  background: #f9f9f9;
  border-radius: 8px; /* 圆角优化 */
  box-sizing: border-box; /* 确保边框在宽度内 */
  /* height 由 inline style 控制 */
}

/* 强制覆盖 vue-signature-pad 的 canvas 样式 */
.mobile-layout .canvas-wrapper :deep(canvas) {
  height: 100% !important;
  width: 100% !important;
  touch-action: none; /* 防止触摸滚动 */
  border-radius: 8px;
}

/* 底部按钮区域 */
.mobile-layout .submit-actions {
  flex-shrink: 0;
  padding-top: 0;
  display: flex;
  flex-direction: row; /* 按钮并排 */
  gap: 15px; /* 增加按钮间距 */
  margin-bottom: 20px; /* 底部增加间距 */
  padding-bottom: env(safe-area-inset-bottom); /* 适配全面屏底部 */
}

.mobile-layout .submit-btn {
  flex: 1;
}

/* 需求3: 提示文字样式 */
.signature-tip {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 24px; /* 电脑端字体稍小 */
  color: #e0e0e0;
  pointer-events: none;
  font-weight: bold;
  opacity: 0.6;
  white-space: nowrap;
}

/* 移动端提示文字特殊处理 - 竖屏 */
.mobile-layout .signature-tip {
  font-size: 40px;
  letter-spacing: 10px;
  transform: translate(-50%, -50%) rotate(90deg);
}

/* 移动端提示文字特殊处理 - 横屏 */
.mobile-layout.landscape .signature-tip {
  transform: translate(-50%, -50%); /* 不旋转 */
  writing-mode: vertical-rl; /* 竖排文字 */
  text-orientation: upright; /* 文字直立 */
  white-space: normal;
  letter-spacing: 5px;
}
</style>
```
