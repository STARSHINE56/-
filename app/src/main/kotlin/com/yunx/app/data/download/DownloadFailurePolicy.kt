package com.yunx.app.data.download

import java.io.IOException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

/**
 * 下载失败分类：只负责把底层异常转换成用户可理解的中文原因，
 * 不改变权限、认证或来源校验逻辑。
 */
object DownloadFailurePolicy {

    fun isNetworkFailure(error: Throwable): Boolean {
        val chain = generateSequence(error as Throwable?) { it.cause }
        return chain.any {
            it is UnknownHostException ||
                it is SocketTimeoutException ||
                it is IOException && (
                    it.message.orEmpty().contains("failed to connect", ignoreCase = true) ||
                    it.message.orEmpty().contains("connection reset", ignoreCase = true) ||
                    it.message.orEmpty().contains("network is unreachable", ignoreCase = true) ||
                    it.message.orEmpty().contains("software caused connection abort", ignoreCase = true)
                )
        }
    }

    fun userMessage(error: Throwable): String {
        val raw = generateSequence(error as Throwable?) { it.cause }
            .mapNotNull { it.message }
            .firstOrNull { it.isNotBlank() }
            .orEmpty()

        return when {
            raw.contains("No space left", ignoreCase = true) ||
                raw.contains("ENOSPC", ignoreCase = true) ||
                raw.contains("空间不足") ->
                "存储空间不足，请清理空间后继续下载"

            raw.contains("permission", ignoreCase = true) ||
                raw.contains("EACCES", ignoreCase = true) ||
                raw.contains("未授予存储权限") ->
                "没有保存文件所需的存储权限"

            raw.contains("401") ->
                "登录状态或下载授权已失效，请重新登录后重试"

            raw.contains("403") ->
                "下载链接已失效或当前账号无权访问，请重新获取链接"

            raw.contains("404") || raw.contains("410") ->
                "下载源已失效或文件已不存在"

            raw.contains("文件大小变化") ||
                raw.contains("文件大小校验失败") ->
                "文件内容已发生变化，为避免损坏已停止续传"

            raw.contains("Range", ignoreCase = true) ->
                "服务器暂不支持当前断点下载方式，已尝试兼容处理"

            isNetworkFailure(error) ->
                "网络连接异常，请检查网络后重试"

            raw.isNotBlank() -> raw
            else -> "下载失败，请稍后重试"
        }
    }
}
