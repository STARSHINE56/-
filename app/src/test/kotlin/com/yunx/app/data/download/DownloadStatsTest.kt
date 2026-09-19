package com.yunx.app.data.download

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
