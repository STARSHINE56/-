package com.yunx.app.data.download

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
}
