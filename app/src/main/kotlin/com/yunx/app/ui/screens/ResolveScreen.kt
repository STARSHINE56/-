/*
 * YunX (云析) - A network drive share-link parser and high-speed downloader for Android.
 * Copyright (C) 2026 CYQawa
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */

package com.yunx.app.ui.screens

import android.content.ClipboardManager
import android.content.Context
import android.os.Build
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.ContentPaste
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Link
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarScrollBehavior
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.yunx.app.data.network.ShareLinkParser
import com.yunx.app.data.network.SharePlatform
import com.yunx.app.data.prefs.ResolveHistoryItem
import com.yunx.app.data.prefs.ResolveHistoryRepository
import com.yunx.app.ui.SnackbarController
import com.yunx.app.ui.resolve.DownloadLinkDialog
import com.yunx.app.ui.resolve.ShareDetailScreen
import com.yunx.app.ui.viewmodel.BaiduCloudViewModel
import com.yunx.app.ui.viewmodel.C139CloudViewModel
import com.yunx.app.ui.viewmodel.Pan123CloudViewModel
import com.yunx.app.ui.viewmodel.QuarkCloudViewModel
import com.yunx.app.ui.viewmodel.ResolveUiState
import com.yunx.app.ui.viewmodel.ResolveViewModel
import com.yunx.app.ui.viewmodel.UCCoudViewModel
import com.yunx.app.ui.viewmodel.XunleiCloudViewModel

/**
 * 解析页：
 * 输入分享链接与提取码 → 解析 → 展示分享详情 → 获取下载直链。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResolveScreen(
    scrollBehavior: TopAppBarScrollBehavior,
    viewModel: ResolveViewModel,

    /** 夸克云盘浏览 ViewModel */
    quarkCloudViewModel: QuarkCloudViewModel,

    /** 迅雷云盘浏览 ViewModel */
    xunleiCloudViewModel: XunleiCloudViewModel,

    /** 百度网盘浏览 ViewModel */
    baiduCloudViewModel: BaiduCloudViewModel,

    /** 移动云盘浏览 ViewModel */
    c139CloudViewModel: C139CloudViewModel,

    /** UC 网盘浏览 ViewModel */
    ucCloudViewModel: UCCoudViewModel,

    /** 123 云盘浏览 ViewModel */
    pan123CloudViewModel: Pan123CloudViewModel,

    modifier: Modifier = Modifier
) {
    val state = viewModel.uiState
    val downloadLink = viewModel.downloadLink
    val downloadError = viewModel.downloadError

    val context = LocalContext.current

    // -----------------------------
    // 最近解析记录
    // -----------------------------

    val historyRepository = remember {
        ResolveHistoryRepository(
            context.applicationContext
        )
    }

    var recentHistory by remember {
        mutableStateOf(
            historyRepository.load()
        )
    }

    fun resolveAndRemember(
        rawLink: String,
        password: String?
    ) {
        val parsed =
            ShareLinkParser.parse(rawLink)

        if (parsed != null) {
            recentHistory =
                historyRepository.add(
                    rawLink,
                    password ?: parsed.pwd
                )
        }

        viewModel.startResolve(
            rawLink,
            password
        )
    }

    // -----------------------------
    // 详情页滚动状态
    // -----------------------------

    val detailListState =
        rememberLazyListState()

    val detailScrollPositions =
        remember {
            mutableStateMapOf<String, Int>()
        }

    // -----------------------------
    // 输入状态
    // -----------------------------

    var link by rememberSaveable {
        mutableStateOf("")
    }

    var pwd by rememberSaveable {
        mutableStateOf("")
    }

    var pwdEdited by rememberSaveable {
        mutableStateOf(false)
    }

    // -----------------------------
    // 剪贴板自动检测
    // -----------------------------

    var clipboardSuggestion by rememberSaveable {
        mutableStateOf<String?>(null)
    }

    var ignoredClipboard by rememberSaveable {
        mutableStateOf<String?>(null)
    }

    val maybeSuggestClipboard: () -> Unit = {
        val text =
            readClipboardSafely(context)

        if (
            text != null &&
            state is ResolveUiState.Idle &&
            text.isNotBlank() &&
            text != link &&
            text != ignoredClipboard &&
            ShareLinkParser.parse(text) != null
        ) {
            clipboardSuggestion = text
        }
    }

    val lifecycleOwner =
        LocalLifecycleOwner.current

    val clipboard =
        context.getSystemService(
            Context.CLIPBOARD_SERVICE
        ) as ClipboardManager

    DisposableEffect(
        lifecycleOwner,
        clipboard
    ) {
        val clipListener =
            ClipboardManager.OnPrimaryClipChangedListener {

                maybeSuggestClipboard()

                // 部分 ROM 剪贴板更新稍有延迟
                android.os.Handler(
                    android.os.Looper.getMainLooper()
                ).postDelayed(
                    {
                        maybeSuggestClipboard()
                    },
                    300
                )
            }

        clipboard.addPrimaryClipChangedListener(
            clipListener
        )

        val observer =
            LifecycleEventObserver { _, event ->

                if (
                    event ==
                    Lifecycle.Event.ON_RESUME
                ) {
                    maybeSuggestClipboard()
                }
            }

        lifecycleOwner.lifecycle.addObserver(
            observer
        )

        // 冷启动立即检测一次
        maybeSuggestClipboard()

        onDispose {
            clipboard
                .removePrimaryClipChangedListener(
                    clipListener
                )

            lifecycleOwner.lifecycle
                .removeObserver(observer)
        }
    }

    // Android 11 及以下轮询兜底
    if (
        Build.VERSION.SDK_INT <
        Build.VERSION_CODES.S
    ) {
        LaunchedEffect(Unit) {
            while (true) {
                kotlinx.coroutines.delay(2000)

                maybeSuggestClipboard()
            }
        }
    }

    // -----------------------------
    // 链接改变后自动识别提取码
    // -----------------------------

    LaunchedEffect(link) {
        if (
            !pwdEdited &&
            pwd.isEmpty()
        ) {
            ShareLinkParser
                .parse(link)
                ?.pwd
                ?.let {
                    pwd = it
                }
        }
    }

    // -----------------------------
    // 下载错误提示
    // -----------------------------

    LaunchedEffect(downloadError) {
        downloadError?.let {

            SnackbarController.show(it)

            viewModel.consumeDownloadError()
        }
    }

    // -----------------------------
    // 页面主体
    // -----------------------------

    Box(
        modifier =
            modifier.fillMaxSize()
    ) {
        AnimatedContent(
            targetState = state,
            transitionSpec = {
                fadeIn(
                    tween(200)
                ) togetherWith
                    fadeOut(
                        tween(140)
                    )
            },
            label = "resolveState"
        ) { currentState ->

            when (currentState) {

                is ResolveUiState.Detail -> {
                    ShareDetailScreen(
                        session =
                            currentState.session,

                        files =
                            currentState.files,

                        viewModel =
                            viewModel,

                        quarkCloudViewModel =
                            quarkCloudViewModel,

                        xunleiCloudViewModel =
                            xunleiCloudViewModel,

                        baiduCloudViewModel =
                            baiduCloudViewModel,

                        c139CloudViewModel =
                            c139CloudViewModel,

                        ucCloudViewModel =
                            ucCloudViewModel,

                        pan123CloudViewModel =
                            pan123CloudViewModel,

                        scrollBehavior =
                            scrollBehavior,

                        listState =
                            detailListState,

                        scrollPositions =
                            detailScrollPositions,

                        onExit = {
                            viewModel.backToInput()
                        },

                        onBack = {
                            viewModel.navigateBack()
                        }
                    )
                }

                is ResolveUiState.Loading -> {
                    LoadingContent()
                }

                else -> {
                    ResolveInputContent(
                        scrollBehavior =
                            scrollBehavior,

                        state =
                            currentState,

                        link =
                            link,

                        onLinkChange = {
                            link = it
                        },

                        pwd =
                            pwd,

                        onPwdChange = {
                            pwd = it
                            pwdEdited = true
                        },

                        onClearLink = {
                            link = ""
                            pwd = ""
                            pwdEdited = false
                        },

                        onClearPwd = {
                            pwd = ""
                            pwdEdited = true
                        },

                        onPasteClipboard = {
                            val clipboardText =
                                readClipboardSafely(
                                    context
                                )

                            if (
                                clipboardText
                                    .isNullOrBlank()
                            ) {
                                SnackbarController.show(
                                    "剪贴板为空"
                                )
                            } else {
                                val parsed =
                                    ShareLinkParser.parse(
                                        clipboardText
                                    )

                                if (parsed == null) {
                                    SnackbarController.show(
                                        "未检测到支持的分享链接"
                                    )
                                } else {
                                    link =
                                        clipboardText

                                    pwd =
                                        parsed.pwd
                                            .orEmpty()

                                    pwdEdited = true

                                    clipboardSuggestion =
                                        null

                                    ignoredClipboard =
                                        clipboardText

                                    SnackbarController.show(
                                        "已识别${platformLabel(parsed.platform)}分享链接"
                                    )
                                }
                            }
                        },

                        recentHistory =
                            recentHistory,

                        onStartResolve = {
                                rawLink,
                                password ->

                            resolveAndRemember(
                                rawLink,
                                password
                            )
                        },

                        onHistorySelect = {
                                item ->

                            link =
                                item.link

                            pwd =
                                item.password

                            pwdEdited = true

                            resolveAndRemember(
                                item.link,
                                item.password
                                    .ifBlank {
                                        null
                                    }
                            )
                        },

                        onClearHistory = {
                            historyRepository.clear()

                            recentHistory =
                                emptyList()
                        }
                    )
                }
            }
        }

        // -----------------------------
        // 自动检测到剪贴板分享链接
        // -----------------------------

        var animatedSuggestion by remember {
            mutableStateOf<String?>(null)
        }

        LaunchedEffect(
            clipboardSuggestion
        ) {
            clipboardSuggestion?.let {
                animatedSuggestion = it
            }
        }

        AnimatedVisibility(
            visible =
                state is ResolveUiState.Idle &&
                    clipboardSuggestion != null,

            enter =
                fadeIn(
                    tween(200)
                ) +
                    slideInVertically(
                        tween(250)
                    ) {
                        -it / 2
                    } +
                    scaleIn(
                        tween(
                            250,
                            delayMillis = 60
                        )
                    ),

            exit =
                fadeOut(
                    tween(150)
                ) +
                    slideOutVertically(
                        tween(200)
                    ) {
                        -it / 2
                    } +
                    scaleOut(
                        tween(200)
                    ),

            modifier =
                Modifier
                    .align(
                        Alignment.TopCenter
                    )
                    .fillMaxWidth()
                    .padding(16.dp)
        ) {
            animatedSuggestion?.let {
                    suggestion ->

                val parsed =
                    ShareLinkParser.parse(
                        suggestion
                    )

                ClipboardSuggestCard(
                    platformName =
                        parsed
                            ?.platform
                            ?.let {
                                platformLabel(it)
                            }
                            ?: "网盘",

                    onPaste = {
                        link =
                            suggestion

                        pwd =
                            parsed
                                ?.pwd
                                .orEmpty()

                        pwdEdited = true

                        ignoredClipboard =
                            suggestion

                        clipboardSuggestion =
                            null

                        SnackbarController.show(
                            "链接已填入解析框"
                        )
                    },

                    onDismiss = {
                        ignoredClipboard =
                            suggestion

                        clipboardSuggestion =
                            null
                    }
                )
            }
        }
    }

    // -----------------------------
    // 获取下载链接加载弹窗
    // -----------------------------

    if (
        viewModel
            .isFetchingDownloadLink
    ) {
        AlertDialog(
            onDismissRequest = { },

            confirmButton = { },

            title = {
                Text(
                    "获取下载链接"
                )
            },

            text = {
                Row(
                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    CircularProgressIndicator(
                        modifier =
                            Modifier.size(24.dp),

                        strokeWidth =
                            2.dp
                    )

                    Spacer(
                        modifier =
                            Modifier.width(12.dp)
                    )

                    Text(
                        text =
                            "正在获取下载链接，请稍候…",

                        style =
                            MaterialTheme
                                .typography
                                .bodyMedium
                    )
                }
            }
        )
    }

    // -----------------------------
    // 下载直链弹窗
    // -----------------------------

    downloadLink?.let {
            download ->

        DownloadLinkDialog(
            link =
                download,

            onDownload = {
                viewModel.startDownload(
                    download
                )
            },

            onDismiss = {
                viewModel
                    .dismissDownloadDialog()
            }
        )
    }
}

/**
 * 解析输入页
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ResolveInputContent(
    scrollBehavior: TopAppBarScrollBehavior,
    state: ResolveUiState,

    link: String,
    onLinkChange: (String) -> Unit,

    pwd: String,
    onPwdChange: (String) -> Unit,

    onClearLink: () -> Unit,
    onClearPwd: () -> Unit,

    onPasteClipboard: () -> Unit,

    recentHistory: List<ResolveHistoryItem>,

    onStartResolve: (
        String,
        String?
    ) -> Unit,

    onHistorySelect: (
        ResolveHistoryItem
    ) -> Unit,

    onClearHistory: () -> Unit
) {
    val isLoading =
        state is ResolveUiState.Loading

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .nestedScroll(
                    scrollBehavior
                        .nestedScrollConnection
                )
                .verticalScroll(
                    rememberScrollState()
                )
                .padding(
                    horizontal = 16.dp,
                    vertical = 12.dp
                ),

        verticalArrangement =
            Arrangement.spacedBy(14.dp)
    ) {

        // -----------------------------
        // 页面说明
        // -----------------------------

        Column(
            verticalArrangement =
                Arrangement.spacedBy(4.dp)
        ) {
            Text(
                text =
                    "粘贴分享链接",

                style =
                    MaterialTheme
                        .typography
                        .titleMedium,

                fontWeight =
                    FontWeight.SemiBold
            )

            Text(
                text =
                    "支持夸克、百度、迅雷、UC、123、移动云盘",

                style =
                    MaterialTheme
                        .typography
                        .bodySmall,

                color =
                    MaterialTheme
                        .colorScheme
                        .onSurfaceVariant
            )
        }

        // -----------------------------
        // 分享链接主卡片
        // -----------------------------

        Card(
            modifier =
                Modifier.fillMaxWidth(),

            shape =
                MaterialTheme
                    .shapes
                    .extraLarge,

            colors =
                CardDefaults.cardColors(
                    containerColor =
                        MaterialTheme
                            .colorScheme
                            .surfaceContainerLow
                )
        ) {
            Column(
                modifier =
                    Modifier.padding(14.dp),

                verticalArrangement =
                    Arrangement.spacedBy(10.dp)
            ) {

                Row(
                    modifier =
                        Modifier.fillMaxWidth(),

                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector =
                            Icons.Outlined.Link,

                        contentDescription =
                            null,

                        tint =
                            MaterialTheme
                                .colorScheme
                                .primary
                    )

                    Spacer(
                        modifier =
                            Modifier.width(8.dp)
                    )

                    Text(
                        text =
                            "分享链接",

                        modifier =
                            Modifier.weight(1f),

                        style =
                            MaterialTheme
                                .typography
                                .titleSmall,

                        fontWeight =
                            FontWeight.Medium
                    )

                    if (
                        link.isNotEmpty()
                    ) {
                        IconButton(
                            onClick =
                                onClearLink
                        ) {
                            Icon(
                                imageVector =
                                    Icons.Filled.Close,

                                contentDescription =
                                    "清空链接"
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value =
                        link,

                    onValueChange =
                        onLinkChange,

                    modifier =
                        Modifier.fillMaxWidth(),

                    placeholder = {
                        Text(
                            "粘贴网盘分享链接"
                        )
                    },

                    minLines = 3,
                    maxLines = 5,

                    shape =
                        MaterialTheme
                            .shapes
                            .large
                )

                Row(
                    modifier =
                        Modifier.fillMaxWidth(),

                    horizontalArrangement =
                        Arrangement.End,

                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    FilledTonalButton(
                        onClick =
                            onPasteClipboard
                    ) {
                        Icon(
                            imageVector =
                                Icons.Outlined
                                    .ContentPaste,

                            contentDescription =
                                null,

                            modifier =
                                Modifier.size(18.dp)
                        )

                        Spacer(
                            modifier =
                                Modifier.width(6.dp)
                        )

                        Text(
                            "粘贴"
                        )
                    }
                }
            }
        }

        // -----------------------------
        // 提取码
        // -----------------------------

        OutlinedTextField(
            value =
                pwd,

            onValueChange =
                onPwdChange,

            modifier =
                Modifier.fillMaxWidth(),

            label = {
                Text(
                    "提取码（可选）"
                )
            },

            placeholder = {
                Text(
                    "自动识别或手动输入"
                )
            },

            trailingIcon = {
                if (
                    pwd.isNotEmpty()
                ) {
                    IconButton(
                        onClick =
                            onClearPwd
                    ) {
                        Icon(
                            imageVector =
                                Icons.Filled.Close,

                            contentDescription =
                                "清空提取码"
                        )
                    }
                }
            },

            singleLine = true,

            shape =
                MaterialTheme
                    .shapes
                    .large
        )

        // -----------------------------
        // 开始解析按钮
        // -----------------------------

        Button(
            onClick = {
                onStartResolve(
                    link,
                    pwd.ifBlank {
                        null
                    }
                )
            },

            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(54.dp),

            enabled =
                link.isNotBlank() &&
                    !isLoading,

            shape =
                MaterialTheme
                    .shapes
                    .large
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier =
                        Modifier.size(18.dp),

                    strokeWidth =
                        2.dp
                )

                Spacer(
                    modifier =
                        Modifier.width(8.dp)
                )

                Text(
                    "解析中…"
                )
            } else {
                Text(
                    text =
                        "开始解析",

                    style =
                        MaterialTheme
                            .typography
                            .titleSmall,

                    fontWeight =
                        FontWeight.SemiBold
                )
            }
        }

        // -----------------------------
        // 最近解析
        // -----------------------------

        if (
            recentHistory
                .isNotEmpty()
        ) {
            Column(
                verticalArrangement =
                    Arrangement.spacedBy(
                        8.dp
                    )
            ) {

                Row(
                    modifier =
                        Modifier.fillMaxWidth(),

                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    Text(
                        text =
                            "最近解析",

                        modifier =
                            Modifier.weight(1f),

                        style =
                            MaterialTheme
                                .typography
                                .titleMedium,

                        fontWeight =
                            FontWeight.SemiBold
                    )

                    TextButton(
                        onClick =
                            onClearHistory
                    ) {
                        Text(
                            "清空"
                        )
                    }
                }

                recentHistory
                    .take(3)
                    .forEach {
                            item ->

                        HistoryCard(
                            item =
                                item,

                            onClick = {
                                onHistorySelect(
                                    item
                                )
                            }
                        )
                    }

                if (
                    recentHistory.size > 3
                ) {
                    Text(
                        text =
                            "仅显示最近 3 条，共 ${recentHistory.size} 条记录",

                        style =
                            MaterialTheme
                                .typography
                                .bodySmall,

                        color =
                            MaterialTheme
                                .colorScheme
                                .onSurfaceVariant
                    )
                }
            }
        } else {

            // -----------------------------
            // 没有历史时显示支持平台
            // -----------------------------

            Card(
                modifier =
                    Modifier.fillMaxWidth(),

                shape =
                    MaterialTheme
                        .shapes
                        .large,

                colors =
                    CardDefaults.cardColors(
                        containerColor =
                            MaterialTheme
                                .colorScheme
                                .surfaceContainerLow
                    )
            ) {
                Column(
                    modifier =
                        Modifier.padding(14.dp),

                    verticalArrangement =
                        Arrangement.spacedBy(
                            6.dp
                        )
                ) {
                    Text(
                        text =
                            "支持网盘",

                        style =
                            MaterialTheme
                                .typography
                                .titleSmall,

                        fontWeight =
                            FontWeight.Medium
                    )

                    Text(
                        text =
                            "夸克 · 百度 · 迅雷 · UC · 123 · 移动云盘",

                        style =
                            MaterialTheme
                                .typography
                                .bodySmall,

                        color =
                            MaterialTheme
                                .colorScheme
                                .onSurfaceVariant
                    )
                }
            }
        }

        // -----------------------------
        // 错误提示
        // -----------------------------

        if (
            state is
                ResolveUiState.Error
        ) {
            Card(
                modifier =
                    Modifier.fillMaxWidth(),

                colors =
                    CardDefaults.cardColors(
                        containerColor =
                            MaterialTheme
                                .colorScheme
                                .errorContainer
                    )
            ) {
                Row(
                    modifier =
                        Modifier.padding(12.dp),

                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector =
                            Icons.Outlined
                                .ErrorOutline,

                        contentDescription =
                            null,

                        tint =
                            MaterialTheme
                                .colorScheme
                                .onErrorContainer
                    )

                    Spacer(
                        modifier =
                            Modifier.width(8.dp)
                    )

                    Text(
                        text =
                            state.message,

                        style =
                            MaterialTheme
                                .typography
                                .bodyMedium,

                        color =
                            MaterialTheme
                                .colorScheme
                                .onErrorContainer
                    )
                }
            }
        }

        Spacer(
            modifier =
                Modifier.height(8.dp)
        )
    }
}

/**
 * 最近解析单条卡片
 */
@Composable
private fun HistoryCard(
    item: ResolveHistoryItem,
    onClick: () -> Unit
) {
    Card(
        onClick =
            onClick,

        modifier =
            Modifier.fillMaxWidth(),

        shape =
            MaterialTheme
                .shapes
                .large,

        colors =
            CardDefaults.cardColors(
                containerColor =
                    MaterialTheme
                        .colorScheme
                        .surfaceContainerLow
            )
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(14.dp),

            verticalAlignment =
                Alignment.CenterVertically
        ) {
            Box(
                modifier =
                    Modifier
                        .size(40.dp),

                contentAlignment =
                    Alignment.Center
            ) {
                Icon(
                    imageVector =
                        Icons.Outlined.Link,

                    contentDescription =
                        null,

                    tint =
                        MaterialTheme
                            .colorScheme
                            .primary
                )
            }

            Spacer(
                modifier =
                    Modifier.width(10.dp)
            )

            Column(
                modifier =
                    Modifier.weight(1f),

                verticalArrangement =
                    Arrangement.spacedBy(
                        3.dp
                    )
            ) {
                Text(
                    text =
                        buildString {

                            append(
                                item.platformName
                            )

                            if (
                                item.password
                                    .isNotBlank()
                            ) {
                                append(
                                    " · 提取码 "
                                )

                                append(
                                    item.password
                                )
                            }
                        },

                    style =
                        MaterialTheme
                            .typography
                            .titleSmall,

                    fontWeight =
                        FontWeight.Medium,

                    maxLines = 1,

                    overflow =
                        TextOverflow.Ellipsis
                )

                Text(
                    text =
                        item.link,

                    style =
                        MaterialTheme
                            .typography
                            .bodySmall,

                    color =
                        MaterialTheme
                            .colorScheme
                            .onSurfaceVariant,

                    maxLines = 1,

                    overflow =
                        TextOverflow.Ellipsis
                )
            }
        }
    }
}

/**
 * 全屏加载
 */
@Composable
private fun LoadingContent() {
    Box(
        modifier =
            Modifier.fillMaxSize(),

        contentAlignment =
            Alignment.Center
    ) {
        Column(
            horizontalAlignment =
                Alignment.CenterHorizontally
        ) {
            CircularProgressIndicator(
                modifier =
                    Modifier.size(28.dp),

                strokeWidth =
                    3.dp
            )

            Spacer(
                modifier =
                    Modifier.height(12.dp)
            )

            Text(
                text =
                    "加载中…",

                style =
                    MaterialTheme
                        .typography
                        .bodyMedium,

                color =
                    MaterialTheme
                        .colorScheme
                        .onSurfaceVariant
            )
        }
    }
}

/**
 * 安全读取剪贴板文字。
 */
private fun readClipboardSafely(
    context: Context
): String? =
    runCatching {

        val clipboardManager =
            context.getSystemService(
                Context.CLIPBOARD_SERVICE
            ) as ClipboardManager

        clipboardManager
            .primaryClip
            ?.takeIf {
                it.itemCount > 0
            }
            ?.getItemAt(0)
            ?.coerceToText(context)
            ?.toString()

    }.getOrNull()

/**
 * 网盘显示名称。
 */
private fun platformLabel(
    platform: SharePlatform
): String =
    when (platform) {

        SharePlatform.QUARK ->
            "夸克网盘"

        SharePlatform.UC ->
            "UC 网盘"

        SharePlatform.XUNLEI ->
            "迅雷网盘"

        SharePlatform.BAIDU ->
            "百度网盘"

        SharePlatform.C139 ->
            "移动云盘"

        SharePlatform.PAN123 ->
            "123云盘"
    }

/**
 * 自动检测剪贴板分享链接后的顶部提示卡片。
 *
 * 现在只负责“粘贴”，不直接开始解析。
 */
@Composable
private fun ClipboardSuggestCard(
    platformName: String,
    onPaste: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier =
            modifier.fillMaxWidth(),

        shape =
            MaterialTheme
                .shapes
                .large,

        colors =
            CardDefaults.cardColors(
                containerColor =
                    MaterialTheme
                        .colorScheme
                        .primaryContainer
            )
    ) {
        Column(
            modifier =
                Modifier.padding(14.dp)
        ) {
            Row(
                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                Icon(
                    imageVector =
                        Icons.Outlined.Link,

                    contentDescription =
                        null,

                    tint =
                        MaterialTheme
                            .colorScheme
                            .onPrimaryContainer
                )

                Spacer(
                    modifier =
                        Modifier.width(10.dp)
                )

                Column(
                    modifier =
                        Modifier.weight(1f)
                ) {
                    Text(
                        text =
                            "检测到 $platformName 分享链接",

                        style =
                            MaterialTheme
                                .typography
                                .titleSmall,

                        fontWeight =
                            FontWeight.Medium,

                        color =
                            MaterialTheme
                                .colorScheme
                                .onPrimaryContainer
                    )

                    Text(
                        text =
                            "是否填入解析框？",

                        style =
                            MaterialTheme
                                .typography
                                .bodySmall,

                        color =
                            MaterialTheme
                                .colorScheme
                                .onPrimaryContainer
                    )
                }
            }

            Spacer(
                modifier =
                    Modifier.height(8.dp)
            )

            Row(
                modifier =
                    Modifier.fillMaxWidth(),

                horizontalArrangement =
                    Arrangement.End,

                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                TextButton(
                    onClick =
                        onDismiss
                ) {
                    Text(
                        text =
                            "忽略",

                        color =
                            MaterialTheme
                                .colorScheme
                                .onPrimaryContainer
                    )
                }

                Spacer(
                    modifier =
                        Modifier.width(4.dp)
                )

                Button(
                    onClick =
                        onPaste,

                    colors =
                        ButtonDefaults
                            .buttonColors(
                                containerColor =
                                    MaterialTheme
                                        .colorScheme
                                        .primary,

                                contentColor =
                                    MaterialTheme
                                        .colorScheme
                                        .onPrimary
                            )
                ) {
                    Icon(
                        imageVector =
                            Icons.Outlined
                                .ContentPaste,

                        contentDescription =
                            null,

                        modifier =
                            Modifier.size(18.dp)
                    )

                    Spacer(
                        modifier =
                            Modifier.width(6.dp)
                    )

                    Text(
                        "粘贴"
                    )
                }
            }
        }
    }
}
