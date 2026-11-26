# Kiwi Next

这是一个独立的 Kiwi Browser 复活项目，不是 Kiwi Browser 官方续版。优先保留手机上的浏览体验和桌面扩展能力，同时基于近期 Chromium 维护内核，而不是把历史 APK 重新包装。

**当前阶段：源码与构建入口。没有可安装的 Kiwi Next APK。**

- 历史参考：Kiwi Browser 官方 [2025 年 1 月公开快照](https://github.com/kiwibrowser/src.next/releases/tag/12867802748)，上游还提供 [4 月下载](https://github.com/kiwibrowser/src.next/releases/tag/14310011181)。发布页的版本标签与源码中的 `105.0.5195.24` 不同；没有从标签反推 APK 内核，历史源码只用于还原功能。
- 第一轮构建候选：Chromium `158.0.8127.92`，Google 在 2026-11-23 公告的 Android 常规更新。同期 159 是小流量 Early Stable。真正发版本前要重新核对最新 Android Stable，不把这里的锁定当作一直安全的版本。
- 构建候选沿用 Chromium 自有 Android 扩展支持，不引入第三方浏览器远控桥、捆绑扩展或 Kiwi 的签名密钥。

## 当前能跑的检查

```sh
python3 -m unittest discover -s tests -v
python3 tools/kiwi.py verify
python3 tools/kiwi.py preflight /path/to/build-volume
```

`verify` 从公开官方源核对两个 Git 标签、完整提交和关键文件的 Git blob 哈希。GitHub Actions 只跑此类轻量检查，不宣称构建或测试了 Android 应用。

下一步：[从固定源码生成测试 APK 并验收](docs/android.md)。上游来源和许可证：[源码归属](docs/upstream.md)。
