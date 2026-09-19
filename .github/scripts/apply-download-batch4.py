from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DL = ROOT / "app/src/main/kotlin/com/yunx/app/data/download"
VM = ROOT / "app/src/main/kotlin/com/yunx/app/ui/viewmodel"
TEST = ROOT / "app/src/test/kotlin/com/yunx/app/data/download"


def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly 1 match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_policy():
    path = DL / "DownloadSourceRefresh.kt"
    old = '''object DownloadSourceRefreshPolicy {
    const val MAX_REFRESH_COUNT = 3

    fun isExpiredHttpStatus(code: Int): Boolean =
        code == 401 || code == 403 || code == 404 || code == 410
}
'''
    new = '''object DownloadSourceRefreshPolicy {
    const val MAX_REFRESH_COUNT = 3

    /** 已知直链过期时间时，提前 60 秒换链，避免分片刚启动就撞上过期。 */
    const val REFRESH_SKEW_MS = 60_000L

    fun isExpiredHttpStatus(code: Int): Boolean =
        code == 401 || code == 403 || code == 404 || code == 410

    fun shouldRefreshBeforeStart(
        expiresAt: Long,
        now: Long = System.currentTimeMillis()
    ): Boolean =
        expiresAt > 0L && now >= expiresAt - REFRESH_SKEW_MS
}
'''
    replace_once(path, old, new)


def patch_manager():
    path = DL / "DownloadManager.kt"

    old_redownload = '''    /**
     * 重新下载：用原直链新建任务（任务卡长按菜单「重新下载」）。
     * 先做 Range 探测校验直链有效性：403/404/网络错误视为直链已过期，返回 false 由 UI 提示。
     */
    suspend fun redownload(id: Long): Boolean {
        val task = dao.get(id) ?: return false
        val headers = loadPersistedHeaders(id)
        val valid = runCatching { downloader.getTotalSize(task.url, headers) != null }.getOrDefault(false)
        if (!valid) return false
        enqueue(
            url = task.url,
            fileName = task.fileName,
            headers = headers,
            size = task.totalSize,
            platform = task.platform,
            sourceFileId = task.sourceFileId,
            sourceType = task.sourceType,
            sourceContext = task.sourceContext,
            urlExpiresAt = task.urlExpiresAt,
            etag = task.etag,
            lastModified = task.lastModified
        )
        return true
    }
'''
    new_redownload = '''    /**
     * 重新下载：优先复用仍有效的直链；个人网盘直链已失效时自动重新取链后再新建任务。
     * 分享链接目前缺少完整分享会话上下文，仍保持安全失败，不猜测/绕过来源校验。
     */
    suspend fun redownload(id: Long): Boolean {
        var task = dao.get(id) ?: return false
        var headers = loadPersistedHeaders(id)

        var probedSize = runCatching { downloader.getTotalSize(task.url, headers) }.getOrNull()
        if (
            probedSize == null &&
            task.sourceType == DownloadSourceType.CLOUD &&
            task.sourceFileId.isNotBlank() &&
            tryRefreshSource(id, "redownload")
        ) {
            task = dao.get(id) ?: return false
            headers = loadPersistedHeaders(id)
            probedSize = runCatching { downloader.getTotalSize(task.url, headers) }.getOrNull()
        }

        if (probedSize == null) return false

        enqueue(
            url = task.url,
            fileName = task.fileName,
            headers = headers,
            size = probedSize.takeIf { it > 0 } ?: task.totalSize,
            platform = task.platform,
            sourceFileId = task.sourceFileId,
            sourceType = task.sourceType,
            sourceContext = task.sourceContext,
            urlExpiresAt = task.urlExpiresAt,
            etag = task.etag,
            lastModified = task.lastModified
        )
        return true
    }
'''
    replace_once(path, old_redownload, new_redownload)

    old_start = '''            val deferred = CompletableDeferred<Job>()
            activeJobs[id] = deferred
            val job = scope.launch {
                try {
                    // 任务开始：有任务在下载时保持前台服务（避免切后台限速/进程被杀）
                    onTaskStarted(id)
'''
    new_start = '''            val deferred = CompletableDeferred<Job>()
            activeJobs[id] = deferred
            val job = scope.launch {
                try {
                    // 用户明确开始/恢复：清除“手动暂停”标志和上一次失败文案。
                    // 避免恢复后 DB 仍残留 manualPaused=true / 旧 errorMsg。
                    dao.updateManualPaused(id, false)
                    dao.updateError(id, "")
                    // 任务开始：有任务在下载时保持前台服务（避免切后台限速/进程被杀）
                    onTaskStarted(id)
'''
    replace_once(path, old_start, new_start)

    old_expiry = '''                    if (
                        taskBeforeRun != null &&
                        taskBeforeRun.urlExpiresAt > 0L &&
                        System.currentTimeMillis() >= taskBeforeRun.urlExpiresAt &&
                        tryRefreshSource(id, "expiresAt")
                    ) {
                        currentHeaders = loadPersistedHeaders(id)
                    }
'''
    new_expiry = '''                    if (
                        taskBeforeRun != null &&
                        DownloadSourceRefreshPolicy.shouldRefreshBeforeStart(taskBeforeRun.urlExpiresAt) &&
                        tryRefreshSource(id, "expiresAt/preemptive")
                    ) {
                        currentHeaders = loadPersistedHeaders(id)
                    }
'''
    replace_once(path, old_expiry, new_expiry)


def patch_viewmodel_message():
    path = VM / "DownloadViewModel.kt"
    old = '''            SnackbarController.show(if (ok) "已重新加入下载" else "下载链接已失效，请重新解析后下载")
'''
    new = '''            SnackbarController.show(
                if (ok) "已重新加入下载"
                else "下载源已失效且无法自动刷新，请重新解析后下载"
            )
'''
    replace_once(path, old, new)


def patch_tests():
    path = TEST / "DownloadSourceRefreshPolicyTest.kt"
    text = path.read_text(encoding="utf-8")
    marker = '''    @Test
    fun refreshCountIsBounded() {
        assertTrue(DownloadSourceRefreshPolicy.MAX_REFRESH_COUNT in 1..5)
    }
'''
    replacement = marker + '''

    @Test
    fun proactivelyRefreshesNearExpiry() {
        val now = 1_000_000L
        assertFalse(DownloadSourceRefreshPolicy.shouldRefreshBeforeStart(0L, now))
        assertFalse(
            DownloadSourceRefreshPolicy.shouldRefreshBeforeStart(
                now + DownloadSourceRefreshPolicy.REFRESH_SKEW_MS + 1L,
                now
            )
        )
        assertTrue(
            DownloadSourceRefreshPolicy.shouldRefreshBeforeStart(
                now + DownloadSourceRefreshPolicy.REFRESH_SKEW_MS,
                now
            )
        )
        assertTrue(
            DownloadSourceRefreshPolicy.shouldRefreshBeforeStart(
                now - 1L,
                now
            )
        )
    }
'''
    if marker not in text:
        raise RuntimeError(f"{path}: refreshCountIsBounded marker not found")
    if "proactivelyRefreshesNearExpiry" not in text:
        path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")


patch_policy()
patch_manager()
patch_viewmodel_message()
patch_tests()
print("download batch4 reliability patch applied successfully")
