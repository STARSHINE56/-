package com.yunx.app.data.download

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
