from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app/src/main"
DL = APP / "kotlin/com/yunx/app/data/download"
DB = APP / "kotlin/com/yunx/app/data/db"
PREFS = APP / "kotlin/com/yunx/app/data/prefs"
UI = APP / "kotlin/com/yunx/app/ui"
SCREENS = UI / "screens"
TEST = ROOT / "app/src/test/kotlin/com/yunx/app/data/download"


def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly 1 match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_settings_repository():
    path = PREFS / "SettingsRepository.kt"
    old = '''    /** 锁屏后保持下载：开启后下载时获取 WakeLock，并可引导加入「忽略电池优化」白名单（默认开启） */
    var keepDownloadWhenLocked: Boolean
'''
    new = '''    /** 仅 Wi-Fi 下载：开启后移动网络不会开始/继续大文件下载，切回 Wi-Fi 自动续传。 */
    var wifiOnlyDownload: Boolean
        get() = prefs.getBoolean("wifi_only_download", false)
        set(value) {
            prefs.edit().putBoolean("wifi_only_download", value).apply()
        }

    /** 锁屏后保持下载：开启后下载时获取 WakeLock，并可引导加入「忽略电池优化」白名单（默认开启） */
    var keepDownloadWhenLocked: Boolean
'''
    replace_once(path, old, new)


def patch_settings_screen():
    path = SCREENS / "SettingsScreen.kt"

    replace_once(
        path,
        '''import androidx.compose.material.icons.outlined.Tune
''',
        '''import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material.icons.outlined.Wifi
'''
    )

    old_state = '''    var keepLocked by remember {
        mutableStateOf(settingsRepo.keepDownloadWhenLocked)
    }
'''
    new_state = '''    var wifiOnly by remember {
        mutableStateOf(settingsRepo.wifiOnlyDownload)
    }
    var keepLocked by remember {
        mutableStateOf(settingsRepo.keepDownloadWhenLocked)
    }
'''
    replace_once(path, old_state, new_state)

    old_ui = '''        SettingsItem(
            icon = Icons.Outlined.Power,
            title = "锁屏后保持下载",
'''
    new_ui = '''        SettingsItem(
            icon = Icons.Outlined.Wifi,
            title = "仅 Wi-Fi 下载",
            description = if (wifiOnly) {
                "仅连接 Wi-Fi 时下载；切换到移动网络会等待 Wi-Fi，恢复后自动续传"
            } else {
                "Wi-Fi 和移动网络均可下载"
            },
            onClick = {
                wifiOnly = !wifiOnly
                settingsRepo.wifiOnlyDownload = wifiOnly
            },
            trailing = {
                Switch(
                    checked = wifiOnly,
                    onCheckedChange = null
                )
            }
        )

        Spacer(modifier = Modifier.height(8.dp))

        SettingsItem(
            icon = Icons.Outlined.Power,
            title = "锁屏后保持下载",
'''
    replace_once(path, old_ui, new_ui)


def patch_dao():
    path = DB / "DownloadTaskDao.kt"
    old = '''    @Query("SELECT * FROM download_task WHERE status = 0 OR status = 1 ORDER BY createTime ASC")
    suspend fun getInterruptedTasks(): List<DownloadTaskEntity>

'''
    new = old + '''    @Query("SELECT id FROM download_task")
    suspend fun getAllTaskIds(): List<Long>

'''
    replace_once(path, old, new)


def patch_manager():
    path = DL / "DownloadManager.kt"

    old_stats = '''data class DownloadStats(
    val speed: Long = 0L,        // 字节/秒
    val remainMillis: Long = -1L, // 剩余时间（毫秒），未知为 -1
    val chunkCount: Int = 1       // 分片（线程）数
)
'''
    new_stats = '''data class DownloadStats(
    val speed: Long = 0L,         // 字节/秒
    val remainMillis: Long = -1L, // 剩余时间（毫秒），未知为 -1
    val chunkCount: Int = 1,      // 分片（线程）数
    val phase: String = ""         // 等待队列 / 等待网络 / 重新获取链接 / 下载中 / 合并中 / 保存中
)
'''
    replace_once(path, old_stats, new_stats)

    old_ctor = '''    /** 锁屏后保持下载开关（开启时获取 WakeLock 维持 Wi-Fi/CPU） */
    private val keepWhenLockedProvider: () -> Boolean = { true },
'''
    new_ctor = '''    /** 仅 Wi-Fi 下载开关；开启时移动网络进入等待，切回 Wi-Fi 自动续传。 */
    private val wifiOnlyProvider: () -> Boolean = { false },
    /** 锁屏后保持下载开关（开启时获取 WakeLock 维持 Wi-Fi/CPU） */
    private val keepWhenLockedProvider: () -> Boolean = { true },
'''
    replace_once(path, old_ctor, new_ctor)

    old_flow = '''    private val _stats = MutableStateFlow<Map<Long, DownloadStats>>(emptyMap())
    val stats: StateFlow<Map<Long, DownloadStats>> = _stats.asStateFlow()

'''
    new_flow = '''    private val _stats = MutableStateFlow<Map<Long, DownloadStats>>(emptyMap())
    val stats: StateFlow<Map<Long, DownloadStats>> = _stats.asStateFlow()

    private fun updatePhase(id: Long, phase: String) {
        _stats.update { current ->
            val old = current[id] ?: DownloadStats()
            current + (id to old.copy(phase = phase))
        }
    }

'''
    replace_once(path, old_flow, new_flow)

    old_start = '''            val deferred = CompletableDeferred<Job>()
            activeJobs[id] = deferred
            val job = scope.launch {
'''
    new_start = '''            val deferred = CompletableDeferred<Job>()
            activeJobs[id] = deferred
            updatePhase(id, "等待队列")
            val job = scope.launch {
'''
    replace_once(path, old_start, new_start)

    old_network = '''    private fun isNetworkAvailable(): Boolean {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return true
        val network = manager.activeNetwork ?: return false
        val capabilities = manager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

'''
    new_network = '''    private fun isNetworkAvailable(): Boolean {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return true
        val network = manager.activeNetwork ?: return false
        val capabilities = manager.getNetworkCapabilities(network) ?: return false
        val validated = capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        if (!validated) return false
        return !wifiOnlyProvider() ||
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    private fun networkWaitText(): String =
        if (wifiOnlyProvider()) "仅 Wi-Fi 下载：等待 Wi-Fi…" else "网络已断开，等待网络恢复…"

    private fun networkWaitPhase(): String =
        if (wifiOnlyProvider()) "等待 Wi-Fi" else "等待网络"

'''
    replace_once(path, old_network, new_network)

    old_wait = '''        while (isTaskActive() && !isNetworkAvailable()) {
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
'''
    new_wait = '''        while (isTaskActive() && !isNetworkAvailable()) {
            if (!waiting) {
                waiting = true
                dao.updateError(id, networkWaitText())
                updatePhase(id, networkWaitPhase())
                Log.d(TAG, "networkWait: id=$id waiting")
            }
            delay(1000L)
        }
        if (waiting && isTaskActive()) {
            dao.updateError(id, "")
            updatePhase(id, "等待队列")
            Log.d(TAG, "networkWait: id=$id recovered")
        }
'''
    replace_once(path, old_wait, new_wait)

    old_slot = '''    private suspend fun awaitConcurrencySlot() {
        val max = concurrencyProvider().coerceAtLeast(1)
        while (isTaskActive() && activeDownloads.get() >= max) {
            delay(300)
        }
    }
'''
    new_slot = '''    private suspend fun awaitConcurrencySlot(id: Long) {
        val max = concurrencyProvider().coerceAtLeast(1)
        var queued = false
        while (isTaskActive() && activeDownloads.get() >= max) {
            if (!queued) {
                queued = true
                updatePhase(id, "等待队列")
            }
            delay(300)
        }
        if (isTaskActive()) updatePhase(id, "检查下载源")
    }
'''
    replace_once(path, old_slot, new_slot)
    replace_once(path, '''            awaitConcurrencySlot()
''', '''            awaitConcurrencySlot(id)
''')

    old_fail_network = '''                        dao.updateError(id, "网络已断开，等待网络恢复…")
                        Log.d(TAG, "runTaskWithRetry: id=$id 网络断开，等待恢复后续传")
'''
    new_fail_network = '''                        dao.updateError(id, networkWaitText())
                        updatePhase(id, networkWaitPhase())
                        Log.d(TAG, "runTaskWithRetry: id=$id 网络不可用，等待恢复后续传")
'''
    replace_once(path, old_fail_network, new_fail_network)

    old_refresh = '''        val refreshed = runCatching { sourceRefresher(task) }
'''
    new_refresh = '''        updatePhase(id, "重新获取链接")
        val refreshed = runCatching { sourceRefresher(task) }
'''
    replace_once(path, old_refresh, new_refresh)

    old_refresh_done = '''        Log.d(TAG, "refreshSource: id=$id reason=$reason count=${task.refreshCount + 1}")
        return true
'''
    new_refresh_done = '''        Log.d(TAG, "refreshSource: id=$id reason=$reason count=${task.refreshCount + 1}")
        updatePhase(id, "检查下载源")
        return true
'''
    replace_once(path, old_refresh_done, new_refresh_done)

    old_run = '''        dao.updateStatus(id, DownloadTaskEntity.STATUS_DOWNLOADING)
        taskStartTimes[id] = System.currentTimeMillis()
'''
    new_run = '''        dao.updateStatus(id, DownloadTaskEntity.STATUS_DOWNLOADING)
        updatePhase(id, "下载中")
        taskStartTimes[id] = System.currentTimeMillis()
'''
    replace_once(path, old_run, new_run)

    old_stats_update = '''        _stats.update { it + (id to DownloadStats(0L, -1L, effectiveWorkers)) }
'''
    new_stats_update = '''        _stats.update {
            val phase = it[id]?.phase.orEmpty().ifBlank { "下载中" }
            it + (id to DownloadStats(0L, -1L, effectiveWorkers, phase))
        }
'''
    replace_once(path, old_stats_update, new_stats_update)

    old_hls_stats = '''        _stats.update { it + (id to DownloadStats(0L, -1L, 1)) }
'''
    new_hls_stats = '''        _stats.update { it + (id to DownloadStats(0L, -1L, 1, "下载中")) }
'''
    replace_once(path, old_hls_stats, new_hls_stats)

    old_finish_start = '''        // 2) 合并
        // ★ 合并产物放内部缓存（data 分区，非 FUSE 挂载）：大文件 IO 快得多；保存完成即删
        val merged = File(context.cacheDir, "merged_$id")
'''
    new_finish_start = '''        // 2) 合并
        updatePhase(id, "合并中")
        // ★ 合并产物放内部缓存（data 分区，非 FUSE 挂载）：大文件 IO 快得多；保存完成即删
        val merged = File(context.cacheDir, "merged_$id")
'''
    replace_once(path, old_finish_start, new_finish_start)

    old_save = '''        val savedPath = withContext(Dispatchers.IO) {
            DownloadSaver.save(context, fileName, merged, saveDirProvider())
        }
'''
    new_save = '''        updatePhase(id, "保存中")
        val savedPath = withContext(Dispatchers.IO) {
            DownloadSaver.save(context, fileName, merged, saveDirProvider())
        }
'''
    replace_once(path, old_save, new_save)

    old_hls_save = '''        val savedPath = withContext(Dispatchers.IO) {
            DownloadSaver.save(context, task.fileName, hlsFile, saveDirProvider())
        }
'''
    new_hls_save = '''        updatePhase(id, "保存中")
        val savedPath = withContext(Dispatchers.IO) {
            DownloadSaver.save(context, task.fileName, hlsFile, saveDirProvider())
        }
'''
    replace_once(path, old_hls_save, new_hls_save)

    old_complete_hls = '''        completeWithAvg(id, savedPath, hlsTotal)
        Log.d(TAG, "hlsDownload: id=$id 下载完成 savedPath=$savedPath size=${hlsFile.length()}")
'''
    new_complete_hls = '''        completeWithAvg(id, savedPath, hlsTotal)
        DownloadService.notifyCompleted(context, task.fileName)
        Log.d(TAG, "hlsDownload: id=$id 下载完成 savedPath=$savedPath size=${hlsFile.length()}")
'''
    replace_once(path, old_complete_hls, new_complete_hls)

    old_complete_normal = '''        completeWithAvg(id, savedPath, total)
        Log.d(TAG, "finishDownload: id=$id 下载完成 savedPath=$savedPath size=${merged.length()}")
'''
    new_complete_normal = '''        completeWithAvg(id, savedPath, total)
        DownloadService.notifyCompleted(context, fileName)
        Log.d(TAG, "finishDownload: id=$id 下载完成 savedPath=$savedPath size=${merged.length()}")
'''
    replace_once(path, old_complete_normal, new_complete_normal)

    old_recover = '''    suspend fun recoverInterruptedTasks() {
        cleanupOrphanTempFiles()
        val interrupted = dao.getInterruptedTasks()
'''
    # 第五批已有 cleanupOrphanTempFiles 时保持；没有则后面补。
    text = path.read_text(encoding="utf-8")
    if old_recover not in text:
        old_recover = '''    suspend fun recoverInterruptedTasks() {
        val interrupted = dao.getInterruptedTasks()
'''
        new_recover = '''    suspend fun recoverInterruptedTasks() {
        cleanupOrphanTempFiles()
        val interrupted = dao.getInterruptedTasks()
'''
        replace_once(path, old_recover, new_recover)

    old_cache = '''    /** 分片临时文件目录：cacheBase()/download_tmp/$id */
    private fun chunkDirOf(id: Long): File = File(cacheBase(), "download_tmp/$id")

'''
    text = path.read_text(encoding="utf-8")
    if "private suspend fun cleanupOrphanTempFiles()" not in text:
        new_cache = '''    /**
     * 只清理“不再对应任何数据库任务”的孤儿缓存，绝不删除仍存在任务的 part/seg。
     */
    private suspend fun cleanupOrphanTempFiles() = withContext(Dispatchers.IO) {
        val liveIds = runCatching { dao.getAllTaskIds().toSet() }.getOrElse { return@withContext }
        val root = File(cacheBase(), "download_tmp")
        root.listFiles()?.forEach { child ->
            val id = child.name.toLongOrNull()
            if (id != null && id !in liveIds) {
                runCatching { child.deleteRecursively() }
            }
        }

        context.cacheDir.listFiles()?.forEach { file ->
            val id = when {
                file.name.startsWith("merged_") ->
                    file.name.removePrefix("merged_").toLongOrNull()
                file.name.startsWith("hls_") ->
                    file.name.removePrefix("hls_").toLongOrNull()
                else -> null
            }
            if (id != null && id !in liveIds) {
                runCatching { file.deleteRecursively() }
            }
        }
    }

    /** 分片临时文件目录：cacheBase()/download_tmp/$id */
    private fun chunkDirOf(id: Long): File = File(cacheBase(), "download_tmp/$id")

'''
        replace_once(path, old_cache, new_cache)


def patch_main_screen():
    path = UI / "MainScreen.kt"
    old = '''            // 锁屏保持下载 / 通知栏速度开关
            keepWhenLockedProvider = { settings.keepDownloadWhenLocked },
'''
    new = '''            // Wi-Fi only / 锁屏保持下载 / 通知栏速度开关
            wifiOnlyProvider = { settings.wifiOnlyDownload },
            keepWhenLockedProvider = { settings.keepDownloadWhenLocked },
'''
    replace_once(path, old, new)


def patch_download_screen():
    path = SCREENS / "DownloadScreen.kt"

    old = '''                    Text(
                        text = taskStatusLine(task),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
'''
    new = '''                    Text(
                        text = stats?.phase?.takeIf { it.isNotBlank() } ?: taskStatusLine(task),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
'''
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f"{path}: status block not found")
    pos = text.rfind(old)
    text = text[:pos] + new + text[pos + len(old):]
    path.write_text(text, encoding="utf-8")

    old_speed = '''                            text = "${formatSpeed(stats.speed)} · 剩余 ${formatRemain(stats.remainMillis)} · ${stats.chunkCount} 线程",
'''
    new_speed = '''                            text = buildString {
                                if (stats.phase.isNotBlank()) append("${stats.phase} · ")
                                append("${formatSpeed(stats.speed)} · 剩余 ${formatRemain(stats.remainMillis)} · ${stats.chunkCount} 线程")
                            },
'''
    replace_once(path, old_speed, new_speed)


def patch_service():
    path = DL / "DownloadService.kt"
    old_comp = '''        /** 全部任务结束：停止前台服务（stopService 无后台启动限制，安全） */
        fun stop(context: Context) {
            context.stopService(Intent(context, DownloadService::class.java))
        }
'''
    new_comp = '''        /** 下载完成后发一条非常驻通知；点击回到应用。 */
        fun notifyCompleted(context: Context, fileName: String) {
            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                nm.getNotificationChannel(CHANNEL_ID) == null
            ) {
                nm.createNotificationChannel(
                    NotificationChannel(CHANNEL_ID, "下载任务", NotificationManager.IMPORTANCE_LOW)
                )
            }

            val contentIntent = PendingIntent.getActivity(
                context,
                fileName.hashCode(),
                Intent(context, MainActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                Notification.Builder(context, CHANNEL_ID)
            } else {
                @Suppress("DEPRECATION")
                Notification.Builder(context)
            }

            val notification = builder
                .setSmallIcon(R.drawable.icon)
                .setContentTitle("下载完成")
                .setContentText(fileName)
                .setContentIntent(contentIntent)
                .setAutoCancel(true)
                .setOnlyAlertOnce(true)
                .build()

            nm.notify(2000 + (fileName.hashCode() and 0x3FFF), notification)
        }

        /** 全部任务结束：停止前台服务（stopService 无后台启动限制，安全） */
        fun stop(context: Context) {
            context.stopService(Intent(context, DownloadService::class.java))
        }
'''
    replace_once(path, old_comp, new_comp)


def add_tests():
    path = TEST / "DownloadStatsTest.kt"
    path.write_text('''package com.yunx.app.data.download

import org.junit.Assert.assertEquals
import org.junit.Test

class DownloadStatsTest {
    @Test
    fun phaseDefaultsToEmptyAndCanBeCopied() {
        val initial = DownloadStats()
        assertEquals("", initial.phase)
        assertEquals("等待队列", initial.copy(phase = "等待队列").phase)
    }
}
''', encoding="utf-8")


patch_settings_repository()
patch_settings_screen()
patch_dao()
patch_manager()
patch_main_screen()
patch_download_screen()
patch_service()
add_tests()
print("download batch6 UX patch applied successfully")
