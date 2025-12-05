import { bitable } from '@lark-base-open/js-sdk';

/**
 * 获取当前多维表格的 App Token (Base ID)
 * @returns {Promise<string>} app_token
 */
export async function getAppToken() {
    try {
        // 1. 获取当前的选择上下文（这是官方获取 BaseId 的标准方式）
        const selection = await bitable.base.getSelection();

        // selection.baseId 就是我们要找的 app_token
        if (selection && selection.baseId) {
            return selection.baseId;
        }

        // 2. 兜底方案：如果 selection 里没有，尝试通过 table 获取
        // 注意：通常 getSelection 就足够了，这里是为了双重保险
        const table = await bitable.base.getActiveTable();
        // 有些旧版本 SDK 或特定环境下，可能需要通过其他方式，但 selection.baseId 是最稳的

        throw new Error("SDK 未返回有效的 Base ID");

    } catch (error) {
        console.error('❌ 获取 App Token 失败:', error);
        // 开发环境提示：如果在浏览器直接打开 localhost 而不是在飞书插件里，肯定获取不到
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.warn('⚠️ 提示：请确保你是在飞书多维表格的“插件面板”中运行此页面，而不是直接在浏览器打开 localhost。');
        }
        return null;
    }
}

/**
 * 获取完整的上下文信息（AppToken, TableId, RecordId）
 */
export async function getContext() {
    const selection = await bitable.base.getSelection();
    return {
        appToken: selection?.baseId,
        tableId: selection?.tableId,
        viewId: selection?.viewId,
        recordId: selection?.recordId
    };
}
