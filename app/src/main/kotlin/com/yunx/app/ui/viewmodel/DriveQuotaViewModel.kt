package com.yunx.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.yunx.app.data.network.BaiduApi
import com.yunx.app.data.network.C139Api
import com.yunx.app.data.network.Pan123Api
import com.yunx.app.data.network.QuarkApi
import com.yunx.app.data.network.UCApi
import com.yunx.app.data.network.XunleiApi
import com.yunx.app.data.network.model.QuotaInfo
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * 已保存登录凭证的检测状态。
 *
 * SUSPECT 表示接口检测失败。
 * 可能是登录凭证失效，也可能只是临时网络或网盘接口异常，
 * 因此不会自动删除账号或退出登录。
 */
enum class DriveLoginState {
    LOGGED_OUT,
    CHECKING,
    HEALTHY,
    SUSPECT
}

/**
 * 网盘容量与账号健康检测。
 *
 * 六个平台并发检测，互不阻塞。
 */
class DriveQuotaViewModel(
    private val quarkApi: QuarkApi,
    private val quarkCookie: suspend () -> String?,
    private val ucApi: UCApi,
    private val ucCookie: suspend () -> String?,
    private val xunleiApi: XunleiApi,
    private val xunleiToken: suspend () -> String?,
    private val xunleiDeviceId: suspend () -> String?,
    private val xunleiCaptcha: suspend () -> String?,
    private val baiduApi: BaiduApi,
    private val baiduCookie: suspend () -> String?,
    private val c139Api: C139Api,
    private val c139Cookie: suspend () -> String?,
    private val pan123Api: Pan123Api,
    private val pan123Token: suspend () -> String?
) : ViewModel() {

    private val _quarkQuota =
        MutableStateFlow<QuotaInfo?>(null)

    val quarkQuota: StateFlow<QuotaInfo?> =
        _quarkQuota.asStateFlow()

    private val _ucQuota =
        MutableStateFlow<QuotaInfo?>(null)

    val ucQuota: StateFlow<QuotaInfo?> =
        _ucQuota.asStateFlow()

    private val _xunleiQuota =
        MutableStateFlow<QuotaInfo?>(null)

    val xunleiQuota: StateFlow<QuotaInfo?> =
        _xunleiQuota.asStateFlow()

    private val _baiduQuota =
        MutableStateFlow<QuotaInfo?>(null)

    val baiduQuota: StateFlow<QuotaInfo?> =
        _baiduQuota.asStateFlow()

    private val _c139Quota =
        MutableStateFlow<QuotaInfo?>(null)

    val c139Quota: StateFlow<QuotaInfo?> =
        _c139Quota.asStateFlow()

    private val _pan123Quota =
        MutableStateFlow<QuotaInfo?>(null)

    val pan123Quota: StateFlow<QuotaInfo?> =
        _pan123Quota.asStateFlow()

    private val _quarkLoginState =
        MutableStateFlow(
            DriveLoginState.LOGGED_OUT
        )

    val quarkLoginState =
        _quarkLoginState.asStateFlow()

    private val _ucLoginState =
        MutableStateFlow(
            DriveLoginState.LOGGED_OUT
        )

    val ucLoginState =
        _ucLoginState.asStateFlow()

    private val _xunleiLoginState =
        MutableStateFlow(
            DriveLoginState.LOGGED_OUT
        )

    val xunleiLoginState =
        _xunleiLoginState.asStateFlow()

    private val _baiduLoginState =
        MutableStateFlow(
            DriveLoginState.LOGGED_OUT
        )

    val baiduLoginState =
        _baiduLoginState.asStateFlow()

    private val _c139LoginState =
        MutableStateFlow(
            DriveLoginState.LOGGED_OUT
        )

    val c139LoginState =
        _c139LoginState.asStateFlow()

    private val _pan123LoginState =
        MutableStateFlow(
            DriveLoginState.LOGGED_OUT
        )

    val pan123LoginState =
        _pan123LoginState.asStateFlow()

    val loading =
        MutableStateFlow(false)

    fun loadAll() {
        if (loading.value) {
            return
        }

        loading.value = true

        viewModelScope.launch {
            try {
                coroutineScope {
                    launch {
                        val cookie =
                            runCatching {
                                quarkCookie()
                            }.getOrNull()

                        if (cookie.isNullOrBlank()) {
                            _quarkQuota.value = null
                            _quarkLoginState.value =
                                DriveLoginState.LOGGED_OUT

                            return@launch
                        }

                        _quarkLoginState.value =
                            DriveLoginState.CHECKING

                        runCatching {
                            quarkApi.getQuota(cookie)
                        }.onSuccess {
                            _quarkQuota.value = it
                            _quarkLoginState.value =
                                DriveLoginState.HEALTHY
                        }.onFailure {
                            _quarkQuota.value = null
                            _quarkLoginState.value =
                                DriveLoginState.SUSPECT
                        }
                    }

                    launch {
                        val cookie =
                            runCatching {
                                ucCookie()
                            }.getOrNull()

                        if (cookie.isNullOrBlank()) {
                            _ucQuota.value = null
                            _ucLoginState.value =
                                DriveLoginState.LOGGED_OUT

                            return@launch
                        }

                        _ucLoginState.value =
                            DriveLoginState.CHECKING

                        runCatching {
                            ucApi.getQuota(cookie)
                        }.onSuccess {
                            _ucQuota.value = it
                            _ucLoginState.value =
                                DriveLoginState.HEALTHY
                        }.onFailure {
                            _ucQuota.value = null
                            _ucLoginState.value =
                                DriveLoginState.SUSPECT
                        }
                    }

                    launch {
                        val token =
                            runCatching {
                                xunleiToken()
                            }.getOrNull()

                        if (token.isNullOrBlank()) {
                            _xunleiQuota.value = null
                            _xunleiLoginState.value =
                                DriveLoginState.LOGGED_OUT

                            return@launch
                        }

                        _xunleiLoginState.value =
                            DriveLoginState.CHECKING

                        val deviceId =
                            runCatching {
                                xunleiDeviceId()
                            }.getOrNull()
                                .orEmpty()

                        val captcha =
                            runCatching {
                                xunleiCaptcha()
                            }.getOrNull()
                                .orEmpty()

                        runCatching {
                            xunleiApi.getQuota(
                                token,
                                deviceId,
                                captcha
                            )
                        }.onSuccess {
                            _xunleiQuota.value = it
                            _xunleiLoginState.value =
                                DriveLoginState.HEALTHY
                        }.onFailure {
                            _xunleiQuota.value = null
                            _xunleiLoginState.value =
                                DriveLoginState.SUSPECT
                        }
                    }

                    launch {
                        val cookie =
                            runCatching {
                                baiduCookie()
                            }.getOrNull()

                        if (cookie.isNullOrBlank()) {
                            _baiduQuota.value = null
                            _baiduLoginState.value =
                                DriveLoginState.LOGGED_OUT

                            return@launch
                        }

                        _baiduLoginState.value =
                            DriveLoginState.CHECKING

                        runCatching {
                            baiduApi.getQuota(cookie)
                        }.onSuccess {
                            _baiduQuota.value = it
                            _baiduLoginState.value =
                                DriveLoginState.HEALTHY
                        }.onFailure {
                            _baiduQuota.value = null
                            _baiduLoginState.value =
                                DriveLoginState.SUSPECT
                        }
                    }

                    launch {
                        val cookie =
                            runCatching {
                                c139Cookie()
                            }.getOrNull()

                        if (cookie.isNullOrBlank()) {
                            _c139Quota.value = null
                            _c139LoginState.value =
                                DriveLoginState.LOGGED_OUT

                            return@launch
                        }

                        _c139LoginState.value =
                            DriveLoginState.CHECKING

                        runCatching {
                            c139Api.getQuota(cookie)
                        }.onSuccess {
                            _c139Quota.value = it
                            _c139LoginState.value =
                                DriveLoginState.HEALTHY
                        }.onFailure {
                            _c139Quota.value = null
                            _c139LoginState.value =
                                DriveLoginState.SUSPECT
                        }
                    }

                    launch {
                        val token =
                            runCatching {
                                pan123Token()
                            }.getOrNull()

                        if (token.isNullOrBlank()) {
                            _pan123Quota.value = null
                            _pan123LoginState.value =
                                DriveLoginState.LOGGED_OUT

                            return@launch
                        }

                        _pan123LoginState.value =
                            DriveLoginState.CHECKING

                        runCatching {
                            pan123Api.getQuota(token)
                        }.onSuccess {
                            _pan123Quota.value = it
                            _pan123LoginState.value =
                                DriveLoginState.HEALTHY
                        }.onFailure {
                            _pan123Quota.value = null
                            _pan123LoginState.value =
                                DriveLoginState.SUSPECT
                        }
                    }
                }
            } finally {
                loading.value = false
            }
        }
    }

    class Factory(
        private val quarkApi: QuarkApi,
        private val quarkCookie:
            suspend () -> String?,
        private val ucApi: UCApi,
        private val ucCookie:
            suspend () -> String?,
        private val xunleiApi: XunleiApi,
        private val xunleiToken:
            suspend () -> String?,
        private val xunleiDeviceId:
            suspend () -> String?,
        private val xunleiCaptcha:
            suspend () -> String?,
        private val baiduApi: BaiduApi,
        private val baiduCookie:
            suspend () -> String?,
        private val c139Api: C139Api,
        private val c139Cookie:
            suspend () -> String?,
        private val pan123Api: Pan123Api,
        private val pan123Token:
            suspend () -> String?
    ) : ViewModelProvider.Factory {

        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(
            modelClass: Class<T>
        ): T =
            DriveQuotaViewModel(
                quarkApi,
                quarkCookie,
                ucApi,
                ucCookie,
                xunleiApi,
                xunleiToken,
                xunleiDeviceId,
                xunleiCaptcha,
                baiduApi,
                baiduCookie,
                c139Api,
                c139Cookie,
                pan123Api,
                pan123Token
            ) as T
    }
}
