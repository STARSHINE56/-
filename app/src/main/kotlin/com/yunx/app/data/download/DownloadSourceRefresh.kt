package com.yunx.app.data.download

import com.yunx.app.data.db.DownloadTaskEntity

typealias DownloadSourceRefresher =
    suspend (DownloadTaskEntity) -> CloudDownloadSource?

object DownloadSourceRefreshPolicy {
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
