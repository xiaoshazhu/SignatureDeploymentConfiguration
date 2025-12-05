import { bitable, FieldType } from '@lark-base-open/js-sdk';
import { ElMessage } from 'element-plus';

// 配置表的名称，必须与多维表格中创建的表名一致
const CONFIG_TABLE_NAME = '表格';

/**
 * 获取当前操作用户 ID
 */
export async function getCurrentUserId() {
    return await bitable.bridge.getUserId();
}

/**
 * 获取或检查配置表
 */
async function getConfigTable() {
    const tableList = await bitable.base.getTableMetaList();
    const configTableMeta = tableList.find(t => t.name === CONFIG_TABLE_NAME);
    if (!configTableMeta) {
        throw new Error(`未找到名为 "${CONFIG_TABLE_NAME}" 的数据表，请先创建。`);
    }
    return await bitable.base.getTableById(configTableMeta.id);
}

/**
 * 查找用户已保存的签名
 * @param {string} userId
 * @returns {Promise<File|null>} 返回文件 Token 或 null
 */
export async function findUserSignature(userId) {
    try {
        const table = await getConfigTable();
        // 获取所有记录（性能优化：实际生产中建议使用 getRecordIdList + 分页，这里为演示简化）
        // 注意：SDK 目前前端查询能力有限，这里遍历查找
        const recordList = await table.getRecords({
            pageSize: 1000 // 假设用户不超过 1000，否则需要分页
        });

        // 假设配置表结构：字段 "用户" (User) | 字段 "签名" (Attachment)
        // 我们需要先获取字段 ID
        const fieldMetaList = await table.getFieldMetaList();
        const userFieldMeta = fieldMetaList.find(f => f.type === FieldType.User);
        const attachmentFieldMeta = fieldMetaList.find(f => f.type === FieldType.Attachment);

        if (!userFieldMeta || !attachmentFieldMeta) {
            console.warn("配置表缺少【人员】或【附件】字段");
            return null;
        }

        // 查找匹配的记录
        for (const record of recordList.records) {
            const userVal = record.fields[userFieldMeta.id];
            // 人员字段通常是数组 [{id: ...}]
            if (userVal && userVal.some(u => u.id === userId)) {
                const attachVal = record.fields[attachmentFieldMeta.id];
                if (attachVal && attachVal.length > 0) {
                    return attachVal[0]; // 返回第一个附件对象 (包含 token)
                }
            }
        }
        return null;
    } catch (e) {
        console.error("查找签名失败", e);
        return null;
    }
}

/**
 * 将签名保存到配置表（存档）
 */
export async function saveSignatureToConfig(userId, file) {
    try {
        const table = await getConfigTable();
        const fieldMetaList = await table.getFieldMetaList();
        const userFieldMeta = fieldMetaList.find(f => f.type === FieldType.User);
        const attachmentFieldMeta = fieldMetaList.find(f => f.type === FieldType.Attachment);

        if (!userFieldMeta || !attachmentFieldMeta) return;

        // 1. 先检查是否已有记录（更新逻辑），这里简化为直接新增
        // 实际应先 check exist update, else add.
        // 为简化演示，这里直接新增一条记录（会导致一人多条，需自行优化去重逻辑）

        await table.addRecord({
            fields: {
                [userFieldMeta.id]: [{ id: userId }],
                [attachmentFieldMeta.id]: file // SDK 支持直接传 File 对象
            }
        });
        // 签名已存档
        return true;
    } catch (e) {
        console.error("存档失败", e);
    }
}

/**
 * 将签名写入当前选中的单元格
 */
export async function saveToCurrentSelection(fileOrToken) {
    const selection = await bitable.base.getSelection();
    if (!selection.tableId || !selection.recordId) {
        ElMessage.warning('请先选择一行记录');
        return false;
    }

    const table = await bitable.base.getTableById(selection.tableId);

    // 智能判断：写入哪一列？
    // 策略：找当前表中第一个附件列，或者由用户选择（这里简化为找第一个附件列）
    const fieldMetaList = await table.getFieldMetaList();
    const attachmentField = fieldMetaList.find(f => f.type === FieldType.Attachment);

    if (!attachmentField) {
        ElMessage.error('当前数据表没有附件字段，无法保存签名。');
        return false;
    }

    const field = await table.getField(attachmentField.id);

    // 写入数据
    // 如果是 file 对象，SDK 会上传；如果是 token 对象（来自配置表），SDK 会复用
    await field.setValue(selection.recordId, [fileOrToken]);
    return true;
}