# wiliwili for Apple tvOS（非官方移植）

将第三方 B 站客户端 [wiliwili](https://github.com/xfangfang/wiliwili) 移植到 Apple TV（tvOS 14+）的补丁集与 CI 构建流水线。

**当前状态：可日常使用。** 真机（Apple TV 4K）+ 蓝牙游戏手柄实测：浏览、搜索、扫码登录、视频/弹幕播放、设置均正常；App 图标与 Top Shelf 已就位。Siri Remote 遥控器的原生交互适配尚未开展（见 Roadmap）。

> 本项目为个人学习与自用性质的社区移植，与 bilibili 及 wiliwili 官方无关。安装到真机需自备 Apple ID 开发者签名。

## 它是如何工作的

本仓库**不含 wiliwili 源码**。CI（GitHub Actions macOS runner）在构建时：

1. 拉取 wiliwili 上游 `yoga` 分支（含 borealis 等子模块）
2. 依序应用 `patches/` 下的补丁（tvOS 使能与适配，全部以 `TVOS` 宏隔离，不影响其他平台）
3. 从 [MPVKit](https://github.com/mpvkit/MPVKit) 获取 tvOS 版 libmpv/FFmpeg 及 22 个第三方静态库并装配链接
4. `cmake -DPLATFORM_TVOS=ON`（真机 `-DPLATFORM=TVOS` / 模拟器 `SIMULATORARM64_TVOS`）+ xcodebuild
5. actool 编译分层图标（Brand Assets）并合入 .app；模拟器目标附带启动冒烟测试

## 构建

- **模拟器版**：push 自动触发，或 Actions 页手动 Run workflow（target=simulator）。产物 `wiliwili-tvos-simulator-app`，`xcrun simctl install` 即可。
- **真机版**：Run workflow 选 target=device。产物 `wiliwili-tvos-device-app` 为未签名 .app，用 `scripts/deploy-tvos-device.sh` 在 Mac 上签名并经 devicectl 推送安装（需先用 Xcode 配对 Apple TV 并生成开发证书，免费 Apple ID 可用，7 天有效期后重签）。

## 补丁清单

| 补丁 | 作用树 | 内容 |
|---|---|---|
| 0002 | wiliwili | tvOS 构建使能：CMake 分支、tvOS Info.plist、源码级 `TVOS` 宏隔离（含修复上游 `ios_bundle` 参数错位） |
| 0003 | wiliwili | 默认启用自带 TV 模式（自动全屏 + TV 版播放 OSD） |
| 0004 | borealis | SDL tvOS 输入 hint（遥控器暴露为手柄、禁用旋转） |
| 0005 | wiliwili | 渲染循环 60fps 兜底限帧（修模拟器无 vsync 阻塞时 CPU 100%） |
| 0006 | borealis | 顶层按 B 直接退出回主屏（tvOS 无"退出应用"范式，原确认框逻辑会卡白屏） |
| 0007 | wiliwili | 配置原子写入 + 崩溃标记自愈（保登录态重置设置，杜绝崩溃后黑屏死循环） |
| 0009 | wiliwili | 退出路径清理 |

移植全程的踩坑记录（依赖装配矩阵、CMake pkg-config 吞 `-framework`、actool Brand Assets 结构、curl 交叉编译 try_run 等）见 `docs/`。

## Roadmap / 非目标

- Siri Remote 目前仅基础可用；原生遥控交互经评估需重写表现层，不在本项目范围（可复用的业务层资产清单见 docs）
- 不上架 App Store，不提供绕过签名的分发

## 致谢

- **[xfangfang](https://github.com/xfangfang) 及 [wiliwili](https://github.com/xfangfang/wiliwili) 全体贡献者** —— 本项目的全部基础。wiliwili 出色的跨平台架构（尤其 iOS 移植与 borealis 中预留的 tvOS 脚手架）让这次移植成为"沿着铺好一半的路走完"，而非从零开工
- **[borealis](https://github.com/xfangfang/borealis)**（natinusala / XITRIX / xfangfang 分支）—— 手柄优先的跨平台 UI 框架
- **[MPVKit](https://github.com/mpvkit/MPVKit)** —— 现成的 tvOS 版 mpv/FFmpeg 全家桶，本项目播放能力的来源
- **[blbl](https://github.com/cat3399/blbl)** 与 BBLL —— TV 遥控交互设计的参考蓝本（映射规范已完成，留待后续遥控适配）
- [bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) 社区

## 协议

GPL-3.0（与上游一致）。本仓库补丁为 wiliwili（GPL-3.0）的衍生作品；构建产物包含 GPL 代码，对应完整源码 = 上游仓库 + 本仓库补丁。见 [LICENSE](LICENSE)。
