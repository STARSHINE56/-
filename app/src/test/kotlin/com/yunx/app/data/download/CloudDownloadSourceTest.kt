package com.yunx.app.data.download

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
