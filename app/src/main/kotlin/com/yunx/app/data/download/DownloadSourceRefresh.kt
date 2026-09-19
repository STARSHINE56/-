package com.yunx.app.data.download

import com.yunx.app.data.db.DownloadTaskEntity

typealias DownloadSourceRefresher =
    suspend (DownloadTaskEntity) -> CloudDownloadSource?

object DownloadSourceRefreshPolicy {
    const val MAX_REFRESH_COUNT = 3

    fun isExpiredHttpStatus(code: Int): Boolean =
        code == 401 || code == 403 || code == 404 || code == 410
}
