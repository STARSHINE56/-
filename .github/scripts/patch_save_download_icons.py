from pathlib import Path

FILE = Path(
    "app/src/main/kotlin/com/yunx/app/ui/resolve/ShareDetailScreen.kt"
)

if not FILE.exists():
    raise SystemExit(f"找不到文件: {FILE}")

text = FILE.read_text(encoding="utf-8")


# =========================================================
# 1. 添加 CloudUpload 图标
# =========================================================

cloud_import = (
    "import androidx.compose.material.icons.outlined.CloudUpload\n"
)

if cloud_import not in text:
    marker = (
        "import androidx.compose.material.icons.outlined.ChevronRight\n"
    )

    if marker not in text:
        raise SystemExit("找不到 ChevronRight import")

    text = text.replace(
        marker,
        marker + cloud_import,
        1,
    )


# =========================================================
# 2. 替换 ShareFileRow 尾部按钮
#
# 原来：
#   保存 -> SaveAlt
#   最右侧 -> 永远 ChevronRight
#
# 修改：
#   保存 -> CloudUpload
#   文件夹 -> ChevronRight
#   普通文件 -> Download
#
# 下载按钮直接调用原来的 onClick，
# 因此继续使用项目原有下载逻辑。
# =========================================================

old = '''            if (onSave != null) {
                IconButton(onClick = onSave, modifier = Modifier.size(36.dp)) {
                    Icon(
                        imageVector = Icons.Outlined.SaveAlt,
                        contentDescription = "转存",
                        modifier = Modifier.size(18.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
            if (onMore != null) {
                IconButton(onClick = onMore, modifier = Modifier.size(36.dp)) {
                    Icon(
                        imageVector = Icons.Outlined.MoreVert,
                        contentDescription = "更多",
                        modifier = Modifier.size(18.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Icon(
                imageVector = Icons.Outlined.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.outline
            )'''

new = '''            if (onSave != null) {
                IconButton(
                    onClick = onSave,
                    modifier = Modifier.size(40.dp)
                ) {
                    Icon(
                        imageVector = Icons.Outlined.CloudUpload,
                        contentDescription = "保存到网盘",
                        modifier = Modifier.size(21.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
            if (onMore != null) {
                IconButton(onClick = onMore, modifier = Modifier.size(36.dp)) {
                    Icon(
                        imageVector = Icons.Outlined.MoreVert,
                        contentDescription = "更多",
                        modifier = Modifier.size(18.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            if (file.isdir) {
                Icon(
                    imageVector = Icons.Outlined.ChevronRight,
                    contentDescription = "进入文件夹",
                    tint = MaterialTheme.colorScheme.outline
                )
            } else {
                IconButton(
                    onClick = onClick,
                    modifier = Modifier.size(40.dp)
                ) {
                    Icon(
                        imageVector = Icons.Outlined.Download,
                        contentDescription = "下载",
                        modifier = Modifier.size(21.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }'''

if old not in text:
    raise SystemExit(
        "找不到 ShareFileRow 原始按钮代码，"
        "为避免误改源码已主动停止。"
    )

text = text.replace(old, new, 1)

FILE.write_text(
    text,
    encoding="utf-8",
)

print("修改成功")
print("保存到网盘: CloudUpload")
print("普通文件: Download")
print("文件夹: ChevronRight")
