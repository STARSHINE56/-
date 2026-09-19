from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app/src/main"
DL = APP / "kotlin/com/yunx/app/data/download"
DB = APP / "kotlin/com/yunx/app/data/db"
UI = APP / "kotlin/com/yunx/app/ui"
TEST = ROOT / "app/src/test/kotlin/com/yunx/app/data/download"


def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly 1 match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def add_failure_policy():
    path = DL / "DownloadFailurePolicy.kt"
    path.write_text('''package com.yunx.app.data.download

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
''', encoding="utf-8")


def patch_manifest():
    path = APP / "AndroidManifest.xml"
    text = path.read_text(encoding="utf-8")
    permission = '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />\n'
    if "android.permission.ACCESS_NETWORK_STATE" not in text:
        anchor = '    <uses-permission android:name="android.permission.INTERNET" />\n'
        if anchor not in text:
            raise RuntimeError("AndroidManifest.xml: INTERNET permission anchor not found")
        text = text.replace(anchor, anchor + permission, 1)
        path.write_text(text, encoding="utf-8")


def patch_dao():
    path = DB / "DownloadTaskDao.kt"
    old = '''    @Query("SELECT * FROM download_task WHERE id = :id")
    suspend fun get(id: Long): DownloadTaskEntity?

'''
    new = old + '''    @Query("SELECT * FROM download_task WHERE status = 0 OR status = 1 ORDER BY createTime ASC")
    suspend fun getInterruptedTasks(): List<DownloadTaskEntity>

'''
    replace_once(path, old, new)


def patch_manager():
    path = DL / "DownloadManager.kt"

    replace_once(
        path,
        '''import android.content.Context
import android.util.Log
''',
        '''import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
'''
    )

    # 用户可读错误，不再把底层异常原样展示到任务卡片。
    replace_once(
        path,
        '''                        dao.updateError(id, e.message ?: e.javaClass.simpleName)
''',
        '''                        dao.updateError(id, DownloadFailurePolicy.userMessage(e))
'''
    )

    # 在并发槽位前等待网络恢复；等待期间不占 activeDownloads 配额。
    replace_once(
        path,
        '''        while (true) {
            // 并发许可：排队等待，直到有空闲下载槽位（或任务被暂停/取消）
            awaitConcurrencySlot()
''',
        '''        while (true) {
            // 无网络时保持任务并等待；网络恢复后从现有 part/seg 继续，不消耗普通失败重试次数。
            awaitNetworkIfNeeded(id)
            if (!isTaskActive()) return
            // 并发许可：排队等待，直到有空闲下载槽位（或任务被暂停/取消）
            awaitConcurrencySlot()
'''
    )

    # 网络中断不烧重试次数，释放本轮 activeDownloads 后回到顶部等待网络。
    replace_once(
        path,
        '''                    attempts++
                    if (isTaskActive() && attempts <= maxRetries) {
''',
        '''                    if (DownloadFailurePolicy.isNetworkFailure(e) && !isNetworkAvailable()) {
                        dao.updateError(id, "网络已断开，等待网络恢复…")
                        Log.d(TAG, "runTaskWithRetry: id=$id 网络断开，等待恢复后续传")
                        continue
                    }
                    attempts++
                    if (isTaskActive() && attempts <= maxRetries) {
'''
    )

    # 已知大小后做临时空间预检，避免 GB 级文件下到最后才因临时空间不足失败。
    replace_once(
        path,
        '''        Log.d(TAG, "getTotalSize: id=$id total=$total origin=${LogRedactor.url(task.url)}")
        dao.updateProgress(id, DownloadTaskEntity.STATUS_DOWNLOADING, task.downloadedSize, total)
''',
        '''        Log.d(TAG, "getTotalSize: id=$id total=$total origin=${LogRedactor.url(task.url)}")
        ensureTempSpace(total, task.downloadedSize)
        dao.updateProgress(id, DownloadTaskEntity.STATUS_DOWNLOADING, task.downloadedSize, total)
'''
    )

    # 在内部实现区加入网络等待 / 重启恢复。
    marker = '''    /** 当前协程是否仍活跃（暂停/删除触发取消后为 false） */
    private suspend fun isTaskActive(): Boolean = coroutineContext[Job]?.isActive == true

'''
    addition = marker + '''    private fun isNetworkAvailable(): Boolean {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return true
        val network = manager.activeNetwork ?: return false
        val capabilities = manager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    /**
     * 网络断开时等待系统恢复网络；用户暂停/删除会取消当前协程并立即退出等待。
     * 等待阶段不消耗失败重试次数。
     */
    private suspend fun awaitNetworkIfNeeded(id: Long) {
        var waiting = false
        while (isTaskActive() && !isNetworkAvailable()) {
            if (!waiting) {
                waiting = true
                dao.updateError(id, "网络已断开，等待网络恢复…")
                Log.d(TAG, "networkWait: id=$id waiting")
            }
            delay(1000L)
        }
        if (waiting && isTaskActive()) {
            dao.updateError(id, "")
            Log.d(TAG, "networkWait: id=$id recovered")
        }
    }

    /**
     * App 进程被系统结束后，Room 中可能残留 PENDING / DOWNLOADING。
     * 再次进入应用时把这些任务恢复到安全状态，并自动续传非手动暂停任务。
     */
    suspend fun recoverInterruptedTasks() {
        val interrupted = dao.getInterruptedTasks()
        if (interrupted.isEmpty()) return
        Log.d(TAG, "recoverInterruptedTasks: count=${interrupted.size}")
        interrupted.forEach { task ->
            dao.updateProgress(
                task.id,
                DownloadTaskEntity.STATUS_PAUSED,
                task.downloadedSize,
                task.totalSize
            )
        }
        interrupted
            .filter { !it.manualPaused }
            .forEach { task -> start(task.id) }
    }

'''
    replace_once(path, marker, addition)

    # 空间检查靠近 cacheBase/chunkDir，便于维护。
    old_cache = '''    /** 下载临时文件缓存根目录：外部缓存（/storage/emulated/0/Android/data/com.yunx.app/cache），
     *  与最终保存目录解耦，系统可自动清理；外部存储不可用时回退内部缓存目录。 */
    private fun cacheBase(): File = context.externalCacheDir ?: context.cacheDir

    /** 分片临时文件目录：cacheBase()/download_tmp/$id */
'''
    new_cache = '''    /** 下载临时文件缓存根目录：外部缓存（/storage/emulated/0/Android/data/com.yunx.app/cache），
     *  与最终保存目录解耦，系统可自动清理；外部存储不可用时回退内部缓存目录。 */
    private fun cacheBase(): File = context.externalCacheDir ?: context.cacheDir

    /**
     * 已知文件大小时提前检查临时空间。
     * 当前下载流程需要保存 part/seg，并在完成阶段生成 merged 文件，所以分别检查两处缓存空间。
     */
    private fun ensureTempSpace(total: Long, downloaded: Long) {
        if (total <= 0L) return
        val reserve = 64L * 1024 * 1024
        val remaining = (total - downloaded.coerceAtLeast(0L)).coerceAtLeast(0L)
        val partBase = cacheBase()
        val mergedBase = context.cacheDir

        val sameBase = runCatching {
            partBase.canonicalPath == mergedBase.canonicalPath
        }.getOrDefault(partBase.absolutePath == mergedBase.absolutePath)

        if (sameBase) {
            val need = remaining + total + reserve
            val free = partBase.usableSpace
            if (free > 0L && free < need) {
                throw IllegalStateException(
                    "临时空间不足：至少还需要 ${need - free} 字节可用空间"
                )
            }
        } else {
            val partNeed = remaining + reserve
            val partFree = partBase.usableSpace
            if (partFree > 0L && partFree < partNeed) {
                throw IllegalStateException(
                    "下载临时空间不足：至少还需要 ${partNeed - partFree} 字节可用空间"
                )
            }

            val mergeNeed = total + reserve
            val mergeFree = mergedBase.usableSpace
            if (mergeFree > 0L && mergeFree < mergeNeed) {
                throw IllegalStateException(
                    "合并文件临时空间不足：至少还需要 ${mergeNeed - mergeFree} 字节可用空间"
                )
            }
        }
    }

    /** 分片临时文件目录：cacheBase()/download_tmp/$id */
'''
    replace_once(path, old_cache, new_cache)


def patch_main_screen():
    path = UI / "MainScreen.kt"
    anchor = '''    // Android 9- 写公共 Download 需要 WRITE_EXTERNAL_STORAGE 运行时授权：
'''
    insert = '''    // App 被系统结束/重启后：恢复上次处于等待或下载中的任务。
    // sourceRefresher 已在上方配置完成，因此恢复时遇到过期直链仍可安全重新取链。
    LaunchedEffect(downloadManager) {
        downloadManager.recoverInterruptedTasks()
    }

''' + anchor
    replace_once(path, anchor, insert)


def add_tests():
    path = TEST / "DownloadFailurePolicyTest.kt"
    path.write_text('''package com.yunx.app.data.download

import java.net.SocketTimeoutException
import java.net.UnknownHostException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DownloadFailurePolicyTest {

    @Test
    fun recognizesNetworkFailures() {
        assertTrue(DownloadFailurePolicy.isNetworkFailure(UnknownHostException("dns")))
        assertTrue(DownloadFailurePolicy.isNetworkFailure(SocketTimeoutException("timeout")))
        assertFalse(DownloadFailurePolicy.isNetworkFailure(IllegalStateException("HTTP 403")))
    }

    @Test
    fun givesFriendlyStorageMessage() {
        assertEquals(
            "存储空间不足，请清理空间后继续下载",
            DownloadFailurePolicy.userMessage(IllegalStateException("ENOSPC: No space left on device"))
        )
    }

    @Test
    fun givesFriendlyAuthorizationMessage() {
        assertEquals(
            "下载链接已失效或当前账号无权访问，请重新获取链接",
            DownloadFailurePolicy.userMessage(IllegalStateException("下载失败 HTTP 403"))
        )
    }
}
''', encoding="utf-8")


add_failure_policy()
patch_manifest()
patch_dao()
patch_manager()
patch_main_screen()
add_tests()
print("download batch5 stability patch applied successfully")
