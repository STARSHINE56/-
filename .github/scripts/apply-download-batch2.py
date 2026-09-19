from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
VM_DIR = ROOT / "app/src/main/kotlin/com/yunx/app/ui/viewmodel"

CLOUD_VM_FILES = [
    VM_DIR / "QuarkCloudViewModel.kt",
    VM_DIR / "UCCoudViewModel.kt",
    VM_DIR / "XunleiCloudViewModel.kt",
    VM_DIR / "BaiduCloudViewModel.kt",
    VM_DIR / "C139CloudViewModel.kt",
    VM_DIR / "Pan123CloudViewModel.kt",
]

PLATFORM_BY_FILE = {
    "QuarkCloudViewModel.kt": "QUARK",
    "UCCoudViewModel.kt": "UC",
    "XunleiCloudViewModel.kt": "XUNLEI",
    "BaiduCloudViewModel.kt": "BAIDU",
    "C139CloudViewModel.kt": "C139",
    "Pan123CloudViewModel.kt": "PAN123",
}

SOURCE_ID_BY_FILE = {
    "QuarkCloudViewModel.kt": "file.fid",
    "UCCoudViewModel.kt": "file.fid",
    "XunleiCloudViewModel.kt": "file.fid",
    "BaiduCloudViewModel.kt": "file.fidToken",
    "C139CloudViewModel.kt": "file.fid",
    "Pan123CloudViewModel.kt": "file.fid",
}

def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected 1 match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def patch_source_type():
    path = ROOT / "app/src/main/kotlin/com/yunx/app/data/download/CloudDownloadSource.kt"
    text = path.read_text(encoding="utf-8")
    if "object DownloadSourceType" not in text:
        text = text.rstrip() + """

object DownloadSourceType {
    const val SHARE = "share"
    const val CLOUD = "cloud"
    const val GENERIC = "generic"
}
"""
        path.write_text(text, encoding="utf-8")

def patch_pending():
    path = VM_DIR / "PendingDownload.kt"
    path.write_text(
        """package com.yunx.app.ui.viewmodel

/**
 * 待确认下载参数：网盘页「单文件下载」先弹下载确认弹窗（对齐解析页行为），
 * 用户点「开始下载」后再用本数据入队。
 */
internal data class PendingDownload(
    val url: String,
    val fileName: String,
    val size: Long,
    val headers: Map<String, String>,
    val sourceFileId: String = "",
    val sourceType: String = ""
)
""",
        encoding="utf-8",
    )

def add_pending_identity(text: str, filename: str) -> str:
    pattern = re.compile(
        r"pendingDownload = PendingDownload\(\n(?P<body>.*?)\n\s{16}\)",
        re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"{filename}: PendingDownload constructor count={len(matches)}")

    m = matches[0]
    body = m.group("body")
    if "sourceFileId =" in body:
        return text

    source_expr = SOURCE_ID_BY_FILE[filename]
    lines = body.splitlines()

    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            lines[i] = lines[i].rstrip()
            if not lines[i].endswith(","):
                lines[i] += ","
            break

    lines.append(f"                    sourceFileId = {source_expr},")
    lines.append("                    sourceType = com.yunx.app.data.download.DownloadSourceType.CLOUD")

    new_body = "\n".join(lines)
    return text[:m.start("body")] + new_body + text[m.end("body"):]

def patch_cloud_vm(path: Path):
    platform = PLATFORM_BY_FILE[path.name]
    source_expr = SOURCE_ID_BY_FILE[path.name]
    text = path.read_text(encoding="utf-8")

    text = add_pending_identity(text, path.name)

    single_old = f"""                    platform = DownloadPlatform.{platform},
                    headers = pd.headers
"""
    single_new = f"""                    platform = DownloadPlatform.{platform},
                    sourceFileId = pd.sourceFileId,
                    sourceType = pd.sourceType,
                    headers = pd.headers
"""
    if text.count(single_old) != 1:
        raise RuntimeError(
            f"{path.name}: single-file enqueue count={text.count(single_old)}"
        )
    text = text.replace(single_old, single_new, 1)

    pattern = re.compile(
        rf"(platform = DownloadPlatform\.{platform},\n)"
        rf"(\s+headers = downloadHeaders(?:\([^\n]*\)|\(\)))"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 2:
        raise RuntimeError(
            f"{path.name}: folder/batch enqueue count={len(matches)}"
        )

    def repl(match):
        indent = "                            "
        return (
            match.group(1)
            + f"{indent}sourceFileId = {source_expr},\n"
            + f"{indent}sourceType = com.yunx.app.data.download.DownloadSourceType.CLOUD,\n"
            + match.group(2)
        )

    text = pattern.sub(repl, text)

    if text.count("sourceFileId =") < 4:
        raise RuntimeError(f"{path.name}: incomplete source identity wiring")

    path.write_text(text, encoding="utf-8")

def patch_resolve():
    path = VM_DIR / "ResolveViewModel.kt"
    text = path.read_text(encoding="utf-8")

    if "sourceFileId = link.fid" in text:
        return

    old = """            size = link.size,
            platform = platform
        ) {
"""
    new = """            size = link.size,
            platform = platform,
            sourceFileId = link.fid,
            sourceType = com.yunx.app.data.download.DownloadSourceType.SHARE
        ) {
"""
    if text.count(old) != 1:
        raise RuntimeError(
            f"{path}: ResolveViewModel enqueue patch count={text.count(old)}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def add_test():
    test_dir = ROOT / "app/src/test/kotlin/com/yunx/app/data/download"
    test_dir.mkdir(parents=True, exist_ok=True)

    (test_dir / "DownloadSourceTypeTest.kt").write_text(
        """package com.yunx.app.data.download

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
""",
        encoding="utf-8",
    )

def validate():
    pending = (VM_DIR / "PendingDownload.kt").read_text(encoding="utf-8")
    if '\\"' in pending:
        raise RuntimeError("PendingDownload.kt contains escaped quote corruption")

    baidu = (VM_DIR / "BaiduCloudViewModel.kt").read_text(encoding="utf-8")
    if "sourceFileId = file.fid," in baidu:
        raise RuntimeError("Baidu source identity must use fidToken")

def main():
    patch_source_type()
    patch_pending()

    for path in CLOUD_VM_FILES:
        patch_cloud_vm(path)

    patch_resolve()
    add_test()
    validate()

    print("download batch2 v2 identity wiring applied successfully")

if __name__ == "__main__":
    main()
