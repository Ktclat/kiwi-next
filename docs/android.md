# Android 构建与复活验收

只有通过以下各层才可推进。当前仓库提供第一层和测试入口，不包含 Chromium 大源码树、不包含成品。

## 1. 准备独立构建机

用 x86-64 Linux，Chromium 官方要求最低 100 GB 可用空间。实际出包还需要为依赖和构建输出保留余量。按 [Chromium Android 官方构建文档](https://chromium.googlesource.com/chromium/src/+/main/docs/android_build_instructions.md)安装官方 depot_tools、宿主依赖，再在一个空构建目录运行：

```sh
gclient config --name src --unmanaged https://chromium.googlesource.com/chromium/src.git
```

在生成的 `.gclient` 文件末尾增加 `target_os = ['android']`，然后仍在该目录运行：

```sh
gclient sync --nohooks --revision src@aa8057651dc34373e52d0a0cefd7904a11b3e130
cd src
build/install-build-deps.sh --android
gclient runhooks
```

该提交应与本仓库 `sources.lock.json` 的 candidate 一致。记录 depot_tools 版本和构建机配置。除非准备换基线，不要直接更新到 Chromium trunk。不要导入第三方二进制、给构建注入个人账户凭据或关闭安全防护。

## 2. 先编译 Chromium 本身的 Android 扩展候选

在上面固定版本的 checkout 中生成独立的工程测试配置：

```sh
python3 /path/to/kiwi-next/tools/kiwi.py prepare "$PWD" x64
gn gen out/kiwinext-x64
autoninja -C out/kiwinext-x64 chrome_public_apk
```

优先在 x64 Android 模拟器验证，确认后用 `arm64` 和 `out/kiwinext-arm64` 同样构建 ARM64。从日志记录确切提交、ABI、版本、包名及 APK SHA-256，核对签名证书和最终包名 `io.github.ktclat.kiwinext.dev` 后才安装到隔离环境。这个包名和开发签名不替换现有 Kiwi，也不用于承诺迁移原版密码、书签或扩展数据。若 GN、编译或安装失败，先保留精确日志，不关闭 Android/Chromium 安全检查。

## 3. 第一条设备验收线

1. 在干净的手机宽度 Android 模拟器安装候选 APK，检查首次启动、普通网站、本地页、标签页和地址栏。不使用个人账户。
2. 安装 [本地 MV3 测试扩展](../fixtures/mv3-localhost)，只允许访问 127.0.0.1。可在宿主机运行 `python3 -m http.server 8000 --bind 127.0.0.1 --directory fixtures`，用 `adb reverse tcp:8000 tcp:8000` 让测试设备通过 `http://127.0.0.1:8000/fixture.html` 访问该页。安装前应显示 WAITING。安装后刷新应显示 PASS，禁用扩展后刷新应回到 WAITING。最后用 `adb reverse --remove tcp:8000` 恢复环境。
3. 在手机宽度独立验证扩展管理的入口、安装确认、启停和重启持久化。如果手机布局缺入口，保留结果，再做针对性 UI 移植；GN 开关并不代表手机扩展已可用。商店安装和 Manifest V2 分别验证，不把单一 MV3 测试当作全兼容。
4. 先恢复 Kiwi 特色且能独立测试的交互（扩展入口、底部地址栏/手势、夜间网页样式），再决定哪些历史代码值得移植。未验证之前不把旧扩展 API 或浏览器内调试功能列为已完成。
5. 对外发布前需要重核当期 Chromium 安全版本，并完成 APK 实测、权限与隐私审查、许可证合规、可复现来源和独立发布签名。不存在任何自动 APK Release。
