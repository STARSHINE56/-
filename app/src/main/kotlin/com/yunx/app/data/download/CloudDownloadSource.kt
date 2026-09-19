package com.yunx.app.data.download

data class CloudDownloadSource(
    val url: String,
    val fileName: String,
    val fileSize: Long = -1L,
    val headers: Map<String, String> = emptyMap(),
    val platform: String = DownloadPlatform.GENERIC,
    val sourceFileId: String = "",
    val sourceType: String = "",
    val sourceContext: String = "",
    val urlExpiresAt: Long = 0L,
    val etag: String = "",
    val lastModified: String = ""
)

object DownloadSourceType {
    const val SHARE = "share"
    const val CLOUD = "cloud"
    const val GENERIC = "generic"
}
