from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "app/src/main/kotlin/com/yunx/app/ui"
SCREENS = UI / "screens"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def replace_once(path: Path, old: str, new: str, label: str):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match in {path}, got {count}")
    write(path, text.replace(old, new, 1))


def patch_main_topbar():
    path = UI / "MainScreen.kt"

    old = '''            actions = {
                // 解析页标题右上角：收藏网盘链接入口
                if (currentTab == MainTab.Resolve) {
                    IconButton(onClick = { showDownloadHistory = true }) {
                        Icon(Icons.Outlined.History, contentDescription = "下载历史")
                    }
                    IconButton(onClick = { showBookmarks = true }) {
                        Icon(Icons.Outlined.Bookmarks, contentDescription = "收藏网盘链接")
                    }
                }
            },
'''
    new = '''            actions = {
                // 顶部栏只展示与当前页面直接相关的入口，避免解析页按钮过多。
                when (currentTab) {
                    MainTab.Resolve -> {
                        IconButton(onClick = { showBookmarks = true }) {
                            Icon(
                                Icons.Outlined.Bookmarks,
                                contentDescription = "收藏网盘链接"
                            )
                        }
                    }

                    MainTab.Download -> {
                        IconButton(onClick = { showDownloadHistory = true }) {
                            Icon(
                                Icons.Outlined.History,
                                contentDescription = "下载历史"
                            )
                        }
                    }

                    else -> Unit
                }
            },
'''
    replace_once(path, old, new, "top bar actions")


def patch_download_screen():
    path = SCREENS / "DownloadScreen.kt"

    replace_once(
        path,
        '''        Column(modifier = Modifier.padding(14.dp)) {
''',
        '''        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
''',
        "download card padding"
    )

    old_status = '''                    Text(
                        text = stats?.phase?.takeIf { it.isNotBlank() } ?: taskStatusLine(task),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
'''
    new_status = '''                    Text(
                        text = buildString {
                            val phase = stats?.phase?.takeIf { it.isNotBlank() }
                                ?: taskStatusLine(task)
                            append(phase)

                            if (isDownloading && stats != null && stats.speed > 0) {
                                append(" · ")
                                append(formatSpeed(stats.speed))
                                if (stats.remainMillis >= 0) {
                                    append(" · 剩余 ")
                                    append(formatRemain(stats.remainMillis))
                                }
                            }
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = when (task.status) {
                            DownloadTaskEntity.STATUS_FAILED ->
                                MaterialTheme.colorScheme.error
                            DownloadTaskEntity.STATUS_COMPLETED ->
                                MaterialTheme.colorScheme.secondary
                            else ->
                                MaterialTheme.colorScheme.onSurfaceVariant
                        },
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
'''
    replace_once(path, old_status, new_status, "download status line")

    old_realtime = '''                Column {
                    if (isDownloading && stats != null && stats.speed > 0) {
                        Text(
                            text = buildString {
                                if (stats.phase.isNotBlank()) append("${stats.phase} · ")
                                append("${formatSpeed(stats.speed)} · 剩余 ${formatRemain(stats.remainMillis)} · ${stats.chunkCount} 线程")
                            },
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                    }
                    LinearProgressIndicator(
'''
    new_realtime = '''                Column {
                    LinearProgressIndicator(
'''
    replace_once(path, old_realtime, new_realtime, "duplicate realtime stats")

    old_completed = '''                    text = if (task.status == DownloadTaskEntity.STATUS_COMPLETED) {
                        if (task.avgSpeed > 0) {
                            "平均 ${formatSpeed(task.avgSpeed)} · ${formatSize(task.totalSize)}"
                        } else {
                            formatSize(task.totalSize)
                        }
                    } else {
                        progressText(task)
                    },
'''
    new_completed = '''                    text = if (task.status == DownloadTaskEntity.STATUS_COMPLETED) {
                        "已完成 · ${formatSize(task.totalSize)}"
                    } else {
                        progressText(task)
                    },
'''
    replace_once(path, old_completed, new_completed, "completed task summary")

    old_bottom_row = '''                Text(
                    text = if (task.status == DownloadTaskEntity.STATUS_COMPLETED) {
                        "已完成 · ${formatSize(task.totalSize)}"
                    } else {
                        progressText(task)
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f)
                )
                TextButton(onClick = onRemove) {
                    Icon(
                        imageVector = Icons.Outlined.Delete,
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = MaterialTheme.colorScheme.error
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("删除", color = MaterialTheme.colorScheme.error)
                }
'''
    new_bottom_row = '''                Text(
                    text = if (task.status == DownloadTaskEntity.STATUS_COMPLETED) {
                        "已完成 · ${formatSize(task.totalSize)}"
                    } else {
                        progressText(task)
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f)
                )
'''
    replace_once(path, old_bottom_row, new_bottom_row, "download bottom delete action")

    replace_once(
        path,
        '''                vertical = 2.dp
''',
        '''                vertical = 0.dp
''',
        "batch bar vertical padding"
    )

    replace_once(
        path,
        '''            text = "解析分享后点击文件即可加入下载队列\\n也可点击右下角按钮手动添加",
''',
        '''            text = "解析文件后可直接加入下载\\n也可点击右下角手动添加任务",
''',
        "download empty state copy"
    )


def patch_settings_screen():
    path = SCREENS / "SettingsScreen.kt"

    replace_once(
        path,
        '''                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
''',
        '''                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
''',
        "settings item padding"
    )

    replace_once(
        path,
        '''            Spacer(
                modifier = Modifier.width(16.dp)
            )
''',
        '''            Spacer(
                modifier = Modifier.width(12.dp)
            )
''',
        "settings icon gap"
    )

    replace_once(
        path,
        '''                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Medium
''',
        '''                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Medium
''',
        "settings title typography"
    )

    replace_once(
        path,
        '''                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
''',
        '''                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2
''',
        "settings description typography"
    )

    old_section = '''private fun SectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(
            start = 4.dp,
            bottom = 8.dp
        )
    )
}
'''
    new_section = '''private fun SectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.SemiBold,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(
            start = 4.dp,
            bottom = 8.dp
        )
    )
}
'''
    replace_once(path, old_section, new_section, "settings section label")

    text = read(path)
    count = text.count("Spacer(modifier = Modifier.height(8.dp))")
    if count < 8:
        raise RuntimeError(
            f"settings spacing: expected at least 8 matches in {path}, got {count}"
        )
    write(path, text.replace(
        "Spacer(modifier = Modifier.height(8.dp))",
        "Spacer(modifier = Modifier.height(6.dp))"
    ))


def patch_resolve_screen():
    path = SCREENS / "ResolveScreen.kt"

    old = '''    // -----------------------------
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

'''
    new = '''    // -----------------------------
    // 获取下载链接：非阻塞式轻量状态提示
    // -----------------------------

    AnimatedVisibility(
        visible = viewModel.isFetchingDownloadLink,
        enter = fadeIn(tween(180)),
        exit = fadeOut(tween(140)),
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
    ) {
        Card(
            shape = MaterialTheme.shapes.large,
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.secondaryContainer
            )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp
                )

                Spacer(modifier = Modifier.width(10.dp))

                Text(
                    text = "正在获取下载链接…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSecondaryContainer
                )
            }
        }
    }

'''
    replace_once(path, old, new, "resolve nonblocking download-link loading")

    replace_once(
        path,
        '''                    shape =
                        RoundedCornerShape(
                            20.dp
                        )
''',
        '''                    shape =
                        MaterialTheme.shapes.large
''',
        "resolve button shape"
    )

    replace_once(
        path,
        '''                                .heightIn(
                                min = 145.dp
                            ),
''',
        '''                                .heightIn(
                                min = 128.dp
                            ),
''',
        "resolve input min height"
    )

    replace_once(
        path,
        '''                            shape =
                                RoundedCornerShape(
                                    12.dp
                                ),
''',
        '''                            shape =
                                MaterialTheme.shapes.medium,
''',
        "paste button shape"
    )


def verify_history_screen():
    path = SCREENS / "DownloadHistoryScreen.kt"
    text = read(path)
    if "DownloadHistoryScreen" not in text:
        raise RuntimeError("download history screen marker missing")


def verify_core_paths():
    for p in [
        ROOT / "app/src/main/kotlin/com/yunx/app/data/network",
        ROOT / "app/src/main/kotlin/com/yunx/app/data/download",
        ROOT / "app/src/main/kotlin/com/yunx/app/data/db",
    ]:
        if not p.exists():
            raise RuntimeError(f"core path missing: {p}")


verify_core_paths()
patch_main_topbar()
patch_download_screen()
patch_settings_screen()
patch_resolve_screen()
verify_history_screen()

print("UI comprehensive optimization patch applied successfully")
