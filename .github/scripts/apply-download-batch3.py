from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_DIR = ROOT / "app/src/main/kotlin/com/yunx/app/data/db"
DL_DIR = ROOT / "app/src/main/kotlin/com/yunx/app/data/download"
VM_DIR = ROOT / "app/src/main/kotlin/com/yunx/app/ui/viewmodel"
MAIN = ROOT / "app/src/main/kotlin/com/yunx/app/ui/MainScreen.kt"
TEST_DIR = ROOT / "app/src/test/kotlin/com/yunx/app/data/download"


def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly 1 match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_entity():
    path = DB_DIR / "DownloadTaskEntity.kt"
    old = '''    /** 来源类型：share / cloud / generic。 */
    @ColumnInfo(defaultValue = "''")
    val sourceType: String = "",
    /** 临时下载 URL 预计过期时间（Unix 毫秒）；0 表示未知。 */
'''
    new = '''    /** 来源类型：share / cloud / generic。 */
    @ColumnInfo(defaultValue = "''")
    val sourceType: String = "",
    /** 来源补充信息：仅保存重新取链所需的非敏感文件元数据。 */
    @ColumnInfo(defaultValue = "''")
    val sourceContext: String = "",
    /** 临时下载 URL 预计过期时间（Unix 毫秒）；0 表示未知。 */
'''
    replace_once(path, old, new)


def patch_database():
    path = DB_DIR / "AppDatabase.kt"
    replace_once(path, "    version = 15,\n", "    version = 16,\n")
    replace_once(
        path,
        '''                        MIGRATION_13_14,
                        MIGRATION_14_15
''',
        '''                        MIGRATION_13_14,
                        MIGRATION_14_15,
                        MIGRATION_15_16
'''
    )
    old = '''        private val MIGRATION_14_15 = object : Migration(14, 15) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE download_task ADD COLUMN sourceFileId TEXT NOT NULL DEFAULT ''")
                db.execSQL("ALTER TABLE download_task ADD COLUMN sourceType TEXT NOT NULL DEFAULT ''")
                db.execSQL("ALTER TABLE download_task ADD COLUMN urlExpiresAt INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE download_task ADD COLUMN etag TEXT NOT NULL DEFAULT ''")
                db.execSQL("ALTER TABLE download_task ADD COLUMN lastModified TEXT NOT NULL DEFAULT ''")
                db.execSQL("ALTER TABLE download_task ADD COLUMN manualPaused INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE download_task ADD COLUMN refreshCount INTEGER NOT NULL DEFAULT 0")
            }
        }
'''
    new = old + '''\n        private val MIGRATION_15_16 = object : Migration(15, 16) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE download_task ADD COLUMN sourceContext TEXT NOT NULL DEFAULT ''")
            }
        }
'''
    replace_once(path, old, new)


def patch_dao():
    path = DB_DIR / "DownloadTaskDao.kt"
    old = '''    @Query("UPDATE download_task SET requestHeadersJson = :encryptedHeaders WHERE id = :id")
    suspend fun updateRequestHeaders(id: Long, encryptedHeaders: String)

'''
    new = old + '''    @Query(
        "UPDATE download_task SET " +
            "url = :url, requestHeadersJson = :encryptedHeaders, " +
            "sourceContext = :sourceContext, urlExpiresAt = :urlExpiresAt, " +
            "etag = :etag, lastModified = :lastModified, " +
            "refreshCount = refreshCount + 1, errorMsg = '' " +
            "WHERE id = :id"
    )
    suspend fun updateRefreshedSource(
        id: Long,
        url: String,
        encryptedHeaders: String,
        sourceContext: String,
        urlExpiresAt: Long,
        etag: String,
        lastModified: String
    )

'''
    replace_once(path, old, new)


def patch_cloud_source():
    path = DL_DIR / "CloudDownloadSource.kt"
    old = '''    val sourceFileId: String = "",
    val sourceType: String = "",
    val urlExpiresAt: Long = 0L,
'''
    new = '''    val sourceFileId: String = "",
    val sourceType: String = "",
    val sourceContext: String = "",
    val urlExpiresAt: Long = 0L,
'''
    replace_once(path, old, new)


def add_refresh_policy():
    (DL_DIR / "DownloadSourceRefresh.kt").write_text(
        '''package com.yunx.app.data.download

import com.yunx.app.data.db.DownloadTaskEntity

typealias DownloadSourceRefresher =
    suspend (DownloadTaskEntity) -> CloudDownloadSource?

object DownloadSourceRefreshPolicy {
    const val MAX_REFRESH_COUNT = 3

    fun isExpiredHttpStatus(code: Int): Boolean =
        code == 401 || code == 403 || code == 404 || code == 410
}
''',
        encoding="utf-8"
    )


def patch_chunk_downloader():
    path = DL_DIR / "ChunkDownloader.kt"
    replace_once(
        path,
        '''    /** 任务 id → 该任务当前所有分片请求 */
    private val activeCalls = ConcurrentHashMap<Long, MutableSet<Call>>()
''',
        '''    /** 任务 id → 该任务当前所有分片请求 */
    private val activeCalls = ConcurrentHashMap<Long, MutableSet<Call>>()

    /** 任务 id → 最近一次疑似临时直链失效的 HTTP 状态；由 DownloadManager 消费。 */
    private val sourceExpiryFailures = ConcurrentHashMap<Long, Int>()

    fun consumeSourceExpiryFailure(taskId: Long): Int? =
        sourceExpiryFailures.remove(taskId)

    private fun markSourceExpiryFailure(taskId: Long, code: Int) {
        sourceExpiryFailures[taskId] = code
    }
'''
    )

    replace_once(
        path,
        '''            return call.execute().use { response ->
                // 防盗链/广告回退页：直接判失败
                if (response.header("Content-Type").orEmpty().contains("text/html", ignoreCase = true)) {
                    Log.w(TAG, "downloadChunk: task=$taskId 返回 text/html（疑似广告/错误页），终止")
                    return@use ChunkResult.FAILED
                }
                when (val code = response.code) {
''',
        '''            return call.execute().use { response ->
                val statusCode = response.code
                if (DownloadSourceRefreshPolicy.isExpiredHttpStatus(statusCode)) {
                    markSourceExpiryFailure(taskId, statusCode)
                    Log.w(TAG, "downloadChunk: task=$taskId 临时直链可能失效 HTTP $statusCode")
                    return@use ChunkResult.FAILED
                }
                // 防盗链/过期回退页：记录后交由上层尝试重新取链
                if (response.header("Content-Type").orEmpty().contains("text/html", ignoreCase = true)) {
                    markSourceExpiryFailure(taskId, statusCode)
                    Log.w(TAG, "downloadChunk: task=$taskId 返回 text/html（疑似过期/错误页），终止")
                    return@use ChunkResult.FAILED
                }
                when (val code = statusCode) {
'''
    )

    replace_once(
        path,
        '''            call.execute().use { response ->
                // ★ 最终响应若是 HTML（防盗链/过期/错误页），直接失败，绝不存盘
                if (response.header("Content-Type").orEmpty().contains("text/html", ignoreCase = true)) {
                    Log.w(TAG, "downloadFull: task=$taskId 返回 text/html（疑似过期/防盗链/错误页），终止")
                    throw IllegalStateException("下载失败：链接已失效或需要 Referer（返回 HTML 页）")
                }
                if (!response.isSuccessful) throw IllegalStateException("下载失败 HTTP ${response.code}")
''',
        '''            call.execute().use { response ->
                val statusCode = response.code
                if (DownloadSourceRefreshPolicy.isExpiredHttpStatus(statusCode)) {
                    markSourceExpiryFailure(taskId, statusCode)
                    throw IllegalStateException("下载链接可能已失效 HTTP $statusCode")
                }
                // ★ 最终响应若是 HTML（防盗链/过期/错误页），直接失败，绝不存盘
                if (response.header("Content-Type").orEmpty().contains("text/html", ignoreCase = true)) {
                    markSourceExpiryFailure(taskId, statusCode)
                    Log.w(TAG, "downloadFull: task=$taskId 返回 text/html（疑似过期/防盗链/错误页），终止")
                    throw IllegalStateException("下载失败：链接已失效或需要 Referer（返回 HTML 页）")
                }
                if (!response.isSuccessful) throw IllegalStateException("下载失败 HTTP $statusCode")
'''
    )


def patch_manager():
    path = DL_DIR / "DownloadManager.kt"
    replace_once(
        path,
        '''    var storagePermissionProvider: suspend () -> Boolean = { true }

''',
        '''    var storagePermissionProvider: suspend () -> Boolean = { true }

    /** 临时下载直链刷新器：仅使用任务持久化的合法来源身份重新调用对应网盘 API。 */
    var sourceRefresher: DownloadSourceRefresher = { null }

'''
    )
    replace_once(
        path,
        '''        sourceFileId: String = "",
        sourceType: String = "",
        urlExpiresAt: Long = 0L,
''',
        '''        sourceFileId: String = "",
        sourceType: String = "",
        sourceContext: String = "",
        urlExpiresAt: Long = 0L,
'''
    )
    replace_once(
        path,
        '''                sourceFileId = sourceFileId,
                sourceType = sourceType,
                urlExpiresAt = urlExpiresAt,
''',
        '''                sourceFileId = sourceFileId,
                sourceType = sourceType,
                sourceContext = sourceContext,
                urlExpiresAt = urlExpiresAt,
'''
    )
    replace_once(
        path,
        '''        sourceFileId = source.sourceFileId,
        sourceType = source.sourceType,
        urlExpiresAt = source.urlExpiresAt,
''',
        '''        sourceFileId = source.sourceFileId,
        sourceType = source.sourceType,
        sourceContext = source.sourceContext,
        urlExpiresAt = source.urlExpiresAt,
'''
    )
    replace_once(
        path,
        '''            sourceFileId = task.sourceFileId,
            sourceType = task.sourceType,
            urlExpiresAt = task.urlExpiresAt,
''',
        '''            sourceFileId = task.sourceFileId,
            sourceType = task.sourceType,
            sourceContext = task.sourceContext,
            urlExpiresAt = task.urlExpiresAt,
'''
    )
    replace_once(
        path,
        '''    private suspend fun runTaskWithRetry(id: Long, headers: Map<String, String>) {
        var attempts = 0
        val maxRetries = retryCountProvider().coerceIn(0, 10)
        while (true) {
''',
        '''    private suspend fun runTaskWithRetry(id: Long, headers: Map<String, String>) {
        var attempts = 0
        var currentHeaders = headers
        val maxRetries = retryCountProvider().coerceIn(0, 10)
        while (true) {
'''
    )
    replace_once(
        path,
        '''                    runTask(id, headers)
                    return
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    attempts++
                    if (isTaskActive() && attempts <= maxRetries) {
''',
        '''                    val taskBeforeRun = dao.get(id)
                    if (
                        taskBeforeRun != null &&
                        taskBeforeRun.urlExpiresAt > 0L &&
                        System.currentTimeMillis() >= taskBeforeRun.urlExpiresAt &&
                        tryRefreshSource(id, "expiresAt")
                    ) {
                        currentHeaders = loadPersistedHeaders(id)
                    }
                    runTask(id, currentHeaders)
                    return
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    val expiredStatus = downloader.consumeSourceExpiryFailure(id)
                    if (
                        expiredStatus != null &&
                        isTaskActive() &&
                        tryRefreshSource(id, "HTTP $expiredStatus")
                    ) {
                        currentHeaders = loadPersistedHeaders(id)
                        attempts = 0
                        Log.d(TAG, "runTaskWithRetry: id=$id 已刷新临时直链，保留分片继续下载")
                        continue
                    }
                    attempts++
                    if (isTaskActive() && attempts <= maxRetries) {
'''
    )

    marker = '''    private suspend fun runTask(id: Long, headers: Map<String, String>) {
'''
    helper = '''    private suspend fun tryRefreshSource(id: Long, reason: String): Boolean {
        val task = dao.get(id) ?: return false
        if (task.sourceType != DownloadSourceType.CLOUD) return false
        if (task.sourceFileId.isBlank()) return false
        if (task.refreshCount >= DownloadSourceRefreshPolicy.MAX_REFRESH_COUNT) {
            Log.w(TAG, "refreshSource: id=$id 已达到刷新上限 ${task.refreshCount}")
            return false
        }

        val refreshed = runCatching { sourceRefresher(task) }
            .onFailure { Log.w(TAG, "refreshSource: id=$id 重新取链失败：${it.message}") }
            .getOrNull()
            ?: return false

        if (refreshed.url.isBlank()) return false

        val oldSize = task.totalSize.takeIf { it > 0 }
        val newSize = refreshed.fileSize.takeIf { it > 0 }
        if (oldSize != null && newSize != null && oldSize != newSize) {
            Log.w(TAG, "refreshSource: id=$id 文件大小变化 old=$oldSize new=$newSize，拒绝续传")
            return false
        }

        val encryptedHeaders = encodeHeaders(refreshed.headers)
        dao.updateRefreshedSource(
            id = id,
            url = refreshed.url,
            encryptedHeaders = encryptedHeaders,
            sourceContext = refreshed.sourceContext.ifBlank { task.sourceContext },
            urlExpiresAt = refreshed.urlExpiresAt,
            etag = refreshed.etag,
            lastModified = refreshed.lastModified
        )
        taskHeaders[id] = refreshed.headers
        if (newSize != null) taskSizes[id] = newSize
        dao.updateError(id, "")
        Log.d(TAG, "refreshSource: id=$id reason=$reason count=${task.refreshCount + 1}")
        return true
    }

'''
    text = path.read_text(encoding="utf-8")
    if text.count(marker) != 1:
        raise RuntimeError(f"{path}: runTask marker count={text.count(marker)}")
    path.write_text(text.replace(marker, helper + marker, 1), encoding="utf-8")


def patch_pending_download():
    path = VM_DIR / "PendingDownload.kt"
    replace_once(
        path,
        '''    val sourceFileId: String = "",
    val sourceType: String = ""
''',
        '''    val sourceFileId: String = "",
    val sourceType: String = "",
    val sourceContext: String = ""
'''
    )


def patch_pan123():
    path = VM_DIR / "Pan123CloudViewModel.kt"
    text = path.read_text(encoding="utf-8")

    old = '''                    sourceFileId = file.fid,
                    sourceType = com.yunx.app.data.download.DownloadSourceType.CLOUD
'''
    new = '''                    sourceFileId = file.fid,
                    sourceType = com.yunx.app.data.download.DownloadSourceType.CLOUD,
                    sourceContext = file.fidToken
'''
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: Pan123 pending identity count={text.count(old)}")
    text = text.replace(old, new, 1)

    old = '''                    sourceFileId = pd.sourceFileId,
                    sourceType = pd.sourceType,
                    headers = pd.headers
'''
    new = '''                    sourceFileId = pd.sourceFileId,
                    sourceType = pd.sourceType,
                    sourceContext = pd.sourceContext,
                    headers = pd.headers
'''
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: Pan123 startDownload count={text.count(old)}")
    text = text.replace(old, new, 1)

    old = '''                            sourceFileId = file.fid,
                            sourceType = com.yunx.app.data.download.DownloadSourceType.CLOUD,
                            headers = downloadHeaders()
'''
    new = '''                            sourceFileId = file.fid,
                            sourceType = com.yunx.app.data.download.DownloadSourceType.CLOUD,
                            sourceContext = file.fidToken,
                            headers = downloadHeaders()
'''
    if text.count(old) != 2:
        raise RuntimeError(f"{path}: Pan123 folder/batch count={text.count(old)}")
    text = text.replace(old, new)

    path.write_text(text, encoding="utf-8")


def patch_main_screen():
    path = MAIN
    marker = '''    // Android 9- 写公共 Download 需要 WRITE_EXTERNAL_STORAGE 运行时授权：
'''
    block = '''    // 临时直链刷新：仅对个人网盘 cloud 来源生效；分享链接来源需要额外会话上下文，暂不自动刷新。
    downloadManager.sourceRefresher = refresher@{ task ->
        if (task.sourceType != com.yunx.app.data.download.DownloadSourceType.CLOUD) {
            return@refresher null
        }

        when (task.platform) {
            com.yunx.app.data.download.DownloadPlatform.QUARK -> {
                val cookie = repository.getFreshCookie() ?: return@refresher null
                val link = api.getDownloadLink(task.sourceFileId, cookie) ?: return@refresher null
                com.yunx.app.data.download.CloudDownloadSource(
                    url = com.yunx.app.data.network.QuarkCdn.fastest(link.downloadUrl, cookie),
                    fileName = task.fileName,
                    fileSize = link.size,
                    headers = mapOf(
                        "Cookie" to cookie,
                        "User-Agent" to com.yunx.app.data.network.QuarkConstants.API_USER_AGENT,
                        "Referer" to com.yunx.app.data.network.QuarkConstants.DOWNLOAD_REFERER
                    ),
                    platform = task.platform,
                    sourceFileId = task.sourceFileId,
                    sourceType = task.sourceType,
                    sourceContext = task.sourceContext
                )
            }

            com.yunx.app.data.download.DownloadPlatform.UC -> {
                val cookie = ucRepository.getFreshCookie() ?: return@refresher null
                val link = ucApi.cloudGetDownloadLink(task.sourceFileId, cookie) ?: return@refresher null
                com.yunx.app.data.download.CloudDownloadSource(
                    url = link.downloadUrl,
                    fileName = task.fileName,
                    fileSize = link.size,
                    headers = mapOf(
                        "Cookie" to cookie,
                        "User-Agent" to com.yunx.app.data.network.UCConstants.USER_AGENT,
                        "Referer" to com.yunx.app.data.network.UCConstants.DOWNLOAD_REFERER,
                        "Origin" to com.yunx.app.data.network.UCConstants.WEB_ORIGIN
                    ),
                    platform = task.platform,
                    sourceFileId = task.sourceFileId,
                    sourceType = task.sourceType,
                    sourceContext = task.sourceContext
                )
            }

            com.yunx.app.data.download.DownloadPlatform.XUNLEI -> {
                val account = xunleiRepository.getAccount() ?: return@refresher null
                val link = xunleiApi.getFileDetail(
                    task.sourceFileId,
                    account.accessToken,
                    account.deviceId,
                    account.captchaToken
                ) ?: return@refresher null
                com.yunx.app.data.download.CloudDownloadSource(
                    url = link.downloadUrl,
                    fileName = task.fileName,
                    fileSize = link.size,
                    headers = mapOf(
                        "User-Agent" to com.yunx.app.data.network.XunleiConstants.APP_UA
                    ),
                    platform = task.platform,
                    sourceFileId = task.sourceFileId,
                    sourceType = task.sourceType,
                    sourceContext = task.sourceContext
                )
            }

            com.yunx.app.data.download.DownloadPlatform.BAIDU -> {
                val account = baiduRepository.getAccount() ?: return@refresher null
                val url = baiduApi.locateDownload(task.sourceFileId, account.cookie)
                com.yunx.app.data.download.CloudDownloadSource(
                    url = url,
                    fileName = task.fileName,
                    fileSize = task.totalSize,
                    headers = mapOf(
                        "Cookie" to account.cookie,
                        "User-Agent" to com.yunx.app.data.network.BaiduConstants.UA_NETDISK
                    ),
                    platform = task.platform,
                    sourceFileId = task.sourceFileId,
                    sourceType = task.sourceType,
                    sourceContext = task.sourceContext
                )
            }

            com.yunx.app.data.download.DownloadPlatform.C139 -> {
                val account = c139Repository.getAccount() ?: return@refresher null
                val link = c139Api.getDownloadUrl(task.sourceFileId, account.cookie) ?: return@refresher null
                com.yunx.app.data.download.CloudDownloadSource(
                    url = link.downloadUrl,
                    fileName = task.fileName,
                    fileSize = link.size,
                    headers = mapOf(
                        "User-Agent" to com.yunx.app.data.network.C139Constants.PC_UA,
                        "Referer" to "https://yun.139.com/"
                    ),
                    platform = task.platform,
                    sourceFileId = task.sourceFileId,
                    sourceType = task.sourceType,
                    sourceContext = task.sourceContext
                )
            }

            com.yunx.app.data.download.DownloadPlatform.PAN123 -> {
                if (task.sourceContext.isBlank()) return@refresher null
                val account = pan123Repository.getAccount() ?: return@refresher null
                val file = com.yunx.app.data.network.model.ShareFile(
                    fid = task.sourceFileId,
                    fname = task.fileName.substringAfterLast('/'),
                    fsize = task.totalSize,
                    isdir = false,
                    pdirFid = "",
                    fidToken = task.sourceContext
                )
                val link = pan123Api.getDownloadLink(file, account.accessToken) ?: return@refresher null
                com.yunx.app.data.download.CloudDownloadSource(
                    url = link.downloadUrl,
                    fileName = task.fileName,
                    fileSize = link.size,
                    headers = mapOf(
                        "User-Agent" to com.yunx.app.data.network.Pan123Constants.WEB_UA,
                        "Referer" to com.yunx.app.data.network.Pan123Constants.DOWNLOAD_REFERER
                    ),
                    platform = task.platform,
                    sourceFileId = task.sourceFileId,
                    sourceType = task.sourceType,
                    sourceContext = task.sourceContext
                )
            }

            else -> null
        }
    }

'''
    text = path.read_text(encoding="utf-8")
    if "downloadManager.sourceRefresher = refresher@" in text:
        raise RuntimeError("MainScreen already contains batch3 refresher")
    if text.count(marker) != 1:
        raise RuntimeError(f"{path}: MainScreen marker count={text.count(marker)}")
    path.write_text(text.replace(marker, block + marker, 1), encoding="utf-8")


def add_tests():
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    (TEST_DIR / "DownloadSourceRefreshPolicyTest.kt").write_text(
        '''package com.yunx.app.data.download

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DownloadSourceRefreshPolicyTest {
    @Test
    fun refreshesOnlyExpectedExpiredStatuses() {
        assertTrue(DownloadSourceRefreshPolicy.isExpiredHttpStatus(401))
        assertTrue(DownloadSourceRefreshPolicy.isExpiredHttpStatus(403))
        assertTrue(DownloadSourceRefreshPolicy.isExpiredHttpStatus(404))
        assertTrue(DownloadSourceRefreshPolicy.isExpiredHttpStatus(410))
        assertFalse(DownloadSourceRefreshPolicy.isExpiredHttpStatus(400))
        assertFalse(DownloadSourceRefreshPolicy.isExpiredHttpStatus(429))
        assertFalse(DownloadSourceRefreshPolicy.isExpiredHttpStatus(500))
    }

    @Test
    fun refreshCountIsBounded() {
        assertTrue(DownloadSourceRefreshPolicy.MAX_REFRESH_COUNT in 1..5)
    }
}
''',
        encoding="utf-8"
    )


def validate():
    checks = {
        "entity sourceContext": (DB_DIR / "DownloadTaskEntity.kt", "val sourceContext: String"),
        "db v16": (DB_DIR / "AppDatabase.kt", "version = 16"),
        "dao refresh": (DB_DIR / "DownloadTaskDao.kt", "updateRefreshedSource"),
        "manager refresher": (DL_DIR / "DownloadManager.kt", "var sourceRefresher"),
        "manager retry refresh": (DL_DIR / "DownloadManager.kt", "已刷新临时直链"),
        "downloader expiry": (DL_DIR / "ChunkDownloader.kt", "consumeSourceExpiryFailure"),
        "main provider refresh": (MAIN, "downloadManager.sourceRefresher = refresher@"),
        "pan123 context": (VM_DIR / "Pan123CloudViewModel.kt", "sourceContext = file.fidToken"),
    }
    for label, (path, needle) in checks.items():
        if needle not in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"validation failed: {label}")


def main():
    patch_entity()
    patch_database()
    patch_dao()
    patch_cloud_source()
    add_refresh_policy()
    patch_chunk_downloader()
    patch_manager()
    patch_pending_download()
    patch_pan123()
    patch_main_screen()
    add_tests()
    validate()
    print("download batch3 temporary URL refresh applied successfully")


if __name__ == "__main__":
    main()
