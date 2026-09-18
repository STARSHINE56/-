from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_DIR = ROOT / "app/src/main/kotlin/com/yunx/app/data/download"
DB_DIR = ROOT / "app/src/main/kotlin/com/yunx/app/data/db"
TEST_DIR = ROOT / "app/src/test/kotlin/com/yunx/app/data/download"

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly 1 match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def main() -> None:
    cloud_source = """package com.yunx.app.data.download

data class CloudDownloadSource(
    val url: String,
    val fileName: String,
    val fileSize: Long = -1L,
    val headers: Map<String, String> = emptyMap(),
    val platform: String = DownloadPlatform.GENERIC,
    val sourceFileId: String = "",
    val sourceType: String = "",
    val urlExpiresAt: Long = 0L,
    val etag: String = "",
    val lastModified: String = ""
)
"""
    (DOWNLOAD_DIR / "CloudDownloadSource.kt").write_text(
        cloud_source,
        encoding="utf-8",
    )

    entity = DB_DIR / "DownloadTaskEntity.kt"
    replace_once(
        entity,
        """    /** 下载来源平台标识（用于按平台应用下载线程数设置）；通用/手动添加为空串 */
    @ColumnInfo(defaultValue = "''")
    val platform: String = "",
    /** 下载完成时的平均速度（字节/秒）；完成态展示用，进行中为 0 */
""",
        """    /** 下载来源平台标识（用于按平台应用下载线程数设置）；通用/手动添加为空串 */
    @ColumnInfo(defaultValue = "''")
    val platform: String = "",
    /** 原网盘文件 ID：临时下载 URL 失效后用于重新获取直链。 */
    @ColumnInfo(defaultValue = "''")
    val sourceFileId: String = "",
    /** 来源类型：share / cloud / generic。 */
    @ColumnInfo(defaultValue = "''")
    val sourceType: String = "",
    /** 临时下载 URL 预计过期时间（Unix 毫秒）；0 表示未知。 */
    @ColumnInfo(defaultValue = "0")
    val urlExpiresAt: Long = 0L,
    /** HTTP ETag。 */
    @ColumnInfo(defaultValue = "''")
    val etag: String = "",
    /** HTTP Last-Modified。 */
    @ColumnInfo(defaultValue = "''")
    val lastModified: String = "",
    /** 是否由用户主动暂停。 */
    @ColumnInfo(defaultValue = "0")
    val manualPaused: Boolean = false,
    /** 临时直链刷新次数。 */
    @ColumnInfo(defaultValue = "0")
    val refreshCount: Int = 0,
    /** 下载完成时的平均速度（字节/秒）；完成态展示用，进行中为 0 */
""",
    )

    dao = DB_DIR / "DownloadTaskDao.kt"
    replace_once(
        dao,
        """    @Query("UPDATE download_task SET status = 2 WHERE status = 1 OR status = 0")
    suspend fun markInterruptedAsPaused()

    @Query("UPDATE download_task SET status = :status WHERE id = :id")
""",
        """    @Query("UPDATE download_task SET status = 2, manualPaused = 0 WHERE status = 1 OR status = 0")
    suspend fun markInterruptedAsPaused()

    @Query("UPDATE download_task SET manualPaused = :manualPaused WHERE id = :id")
    suspend fun updateManualPaused(id: Long, manualPaused: Boolean)

    @Query("UPDATE download_task SET status = :status WHERE id = :id")
""",
    )

    db = DB_DIR / "AppDatabase.kt"
    replace_once(db, "    version = 14,\n", "    version = 15,\n")
    replace_once(
        db,
        "                    .addMigrations(MIGRATION_9_10, MIGRATION_10_11, MIGRATION_11_12, MIGRATION_12_13, MIGRATION_13_14)\n",
        """                    .addMigrations(
                        MIGRATION_9_10,
                        MIGRATION_10_11,
                        MIGRATION_11_12,
                        MIGRATION_12_13,
                        MIGRATION_13_14,
                        MIGRATION_14_15
                    )
""",
    )
    replace_once(
        db,
        """        private val MIGRATION_13_14 = object : Migration(13, 14) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE download_task ADD COLUMN completedTime INTEGER NOT NULL DEFAULT 0")
            }
        }
""",
        """        private val MIGRATION_13_14 = object : Migration(13, 14) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE download_task ADD COLUMN completedTime INTEGER NOT NULL DEFAULT 0")
            }
        }

        private val MIGRATION_14_15 = object : Migration(14, 15) {
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
""",
    )

    manager = DOWNLOAD_DIR / "DownloadManager.kt"
    replace_once(
        manager,
        """    suspend fun enqueue(
        url: String,
        fileName: String,
        headers: Map<String, String> = emptyMap(),
        /** 已知文件大小（字节）；-1 表示未知，需探测 */
        size: Long = -1L,
        /** 下载来源平台标识（按平台应用下载线程数设置）；通用/手动添加传空串 */
        platform: String = "",
        /** 下载成功完成后的清理回调（如删除网盘临时转存文件）；失败/取消不触发 */
        onComplete: suspend () -> Unit = {}
    ): Long {
""",
        """    suspend fun enqueue(
        url: String,
        fileName: String,
        headers: Map<String, String> = emptyMap(),
        /** 已知文件大小（字节）；-1 表示未知，需探测 */
        size: Long = -1L,
        /** 下载来源平台标识（按平台应用下载线程数设置）；通用/手动添加传空串 */
        platform: String = "",
        sourceFileId: String = "",
        sourceType: String = "",
        urlExpiresAt: Long = 0L,
        etag: String = "",
        lastModified: String = "",
        /** 下载成功完成后的清理回调（如删除网盘临时转存文件）；失败/取消不触发 */
        onComplete: suspend () -> Unit = {}
    ): Long {
""",
    )
    replace_once(
        manager,
        """                requestHeadersJson = encodeHeaders(headers),
                platform = platform
""",
        """                requestHeadersJson = encodeHeaders(headers),
                platform = platform,
                sourceFileId = sourceFileId,
                sourceType = sourceType,
                urlExpiresAt = urlExpiresAt,
                etag = etag,
                lastModified = lastModified
""",
    )
    replace_once(
        manager,
        """        start(id, headers)
        return id
    }

    /**
     * 重新下载：用原直链新建任务（任务卡长按菜单「重新下载」）。
""",
        """        start(id, headers)
        return id
    }

    suspend fun enqueue(
        source: CloudDownloadSource,
        onComplete: suspend () -> Unit = {}
    ): Long = enqueue(
        url = source.url,
        fileName = source.fileName,
        headers = source.headers,
        size = source.fileSize,
        platform = source.platform,
        sourceFileId = source.sourceFileId,
        sourceType = source.sourceType,
        urlExpiresAt = source.urlExpiresAt,
        etag = source.etag,
        lastModified = source.lastModified,
        onComplete = onComplete
    )

    /**
     * 重新下载：用原直链新建任务（任务卡长按菜单「重新下载」）。
""",
    )
    replace_once(
        manager,
        """        enqueue(task.url, task.fileName, headers, task.totalSize, task.platform)
        return true
""",
        """        enqueue(
            url = task.url,
            fileName = task.fileName,
            headers = headers,
            size = task.totalSize,
            platform = task.platform,
            sourceFileId = task.sourceFileId,
            sourceType = task.sourceType,
            urlExpiresAt = task.urlExpiresAt,
            etag = task.etag,
            lastModified = task.lastModified
        )
        return true
""",
    )
    replace_once(
        manager,
        """        scope.launch {
            // 等协程真正退出（确保没有半截写入）后，以磁盘 part/seg 真实大小为准回写进度：
""",
        """        scope.launch {
            dao.updateManualPaused(id, true)
            // 等协程真正退出（确保没有半截写入）后，以磁盘 part/seg 真实大小为准回写进度：
""",
    )

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    (TEST_DIR / "CloudDownloadSourceTest.kt").write_text(
        """package com.yunx.app.data.download

import org.junit.Assert.assertEquals
import org.junit.Test

class CloudDownloadSourceTest {
    @Test
    fun defaultsAreBackwardCompatible() {
        val source = CloudDownloadSource(
            url = "https://example.com/file",
            fileName = "file.bin"
        )
        assertEquals("", source.sourceFileId)
        assertEquals("", source.sourceType)
        assertEquals(0L, source.urlExpiresAt)
    }

    @Test
    fun metadataIsPreserved() {
        val source = CloudDownloadSource(
            url = "https://example.com/file",
            fileName = "file.bin",
            platform = DownloadPlatform.PAN123,
            sourceFileId = "file-123",
            sourceType = "cloud"
        )
        assertEquals("file-123", source.sourceFileId)
        assertEquals("cloud", source.sourceType)
    }
}
""",
        encoding="utf-8",
    )

    print("download batch1 patch applied successfully")

if __name__ == "__main__":
    main()
