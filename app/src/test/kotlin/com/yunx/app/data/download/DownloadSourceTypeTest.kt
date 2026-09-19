package com.yunx.app.data.download

import org.junit.Assert.assertEquals
import org.junit.Test

class DownloadSourceTypeTest {
    @Test
    fun sourceTypesAreStableForPersistence() {
        assertEquals("share", DownloadSourceType.SHARE)
        assertEquals("cloud", DownloadSourceType.CLOUD)
        assertEquals("generic", DownloadSourceType.GENERIC)
    }

    @Test
    fun identitySurvivesCloudDownloadSource() {
        val source = CloudDownloadSource(
            url = "https://example.com/file",
            fileName = "file.bin",
            platform = DownloadPlatform.QUARK,
            sourceFileId = "fid-001",
            sourceType = DownloadSourceType.CLOUD
        )
        assertEquals("fid-001", source.sourceFileId)
        assertEquals(DownloadSourceType.CLOUD, source.sourceType)
    }
}
