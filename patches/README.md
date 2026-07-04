# WP3 tvOS 使能补丁说明

本目录补丁使 wiliwili 能在 Mac 上生成可编译的 tvOS Xcode 工程：
`cmake -B build -G Xcode -DPLATFORM_TVOS=ON`。

所有 tvOS 逻辑均以 CMake 的 `PLATFORM_TVOS` 与 C++ 的 `TVOS` 宏隔离，不影响
现有 iOS / macOS / Switch / PS4 / PSV / Windows 构建路径。

补丁基线 commit：
- wiliwili：`88e5876`（yoga 分支 HEAD 快照）
- borealis 子模块：`5f08b28`（wiliwili 锁定 commit）

---

## 0001-borealis-tvos.patch —— 省略（borealis 无需改动）

**结论：borealis-pinned（5f08b28）无需任何改动，故不产出该补丁。**

理由（依 WP2 与实读源码）：
1. borealis 的 tvOS 底座已就绪：`library/cmake/commonOption.cmake` 定义
   `option(PLATFORM_TVOS)`；`library/cmake/toolchain.cmake:20-41` 已按
   `PLATFORM_IOS OR PLATFORM_TVOS` 走 iOS toolchain / SDL2 / GLES3 / libromfs；
   `library/CMakeLists.txt:207-221` 现编 SDL 并注入 `-DTVOS` 宏；
   `library/cmake/ios.toolchain.cmake` 已支持 `PLATFORM=TVOS`（`appletvos`
   SDK、`arm64-apple-tvos` 三元组）。平台层 C++ 已大量写成 `IOS || TVOS`。
2. **关于 WP2 P1「ios_bundle 签名不一致」的最终裁决**：借由实读源码确认，
   `library/cmake/toolchain.cmake:165` 的 `ios_bundle(iosStoryBoard assets
   plist name version)` 为 **5 参**定义；borealis demo `CMakeLists.txt:153-167`
   的 **PLATFORM_IOS 与 PLATFORM_TVOS 两个分支各自以 5 参正确调用**（各传对应
   storyboard）。即 borealis 侧本身自洽、没有 bug。
   真正错位的是 **wiliwili 调用处以 6 参调用**（传了 tvos + iphoneos 两个
   storyboard）。依 Spec「Plan 已定决策」：**borealis 定义保持 5 参不动**，
   改 wiliwili 调用处为 IOS/TVOS 双分支、各传 5 参（见 0002 补丁）。

> 若未来上游 borealis 变更 `ios_bundle` 签名，需重新评估；当前锁定 commit 下
> 无需改动。

---

## 0002-wiliwili-tvos.patch

改动文件（9 个）：

| 文件 | 改动 | 对应 WP2 补丁项 |
|---|---|---|
| `CMakeLists.txt` | framework 链接 `PLATFORM_IOS` → `PLATFORM_IOS OR PLATFORM_TVOS`；ios_bundle 调用改为 IOS/TVOS 双分支各 5 参 | P3 / P1 |
| `library/CMakeLists.txt` | cpr `CPR_SKIP_CA_BUNDLE_SEARCH` 分支、OpenCC 禁用条件扩到 TVOS | P3 |
| `scripts/ios/tvOSBundleInfo.plist.in`（新增） | tvOS 专用 Info.plist（`UIDeviceFamily=3` 等） | P4 |
| `wiliwili/source/main.cpp` | `#ifdef IOS` → `IOS \|\| TVOS`（SDL_main 入口） | P2 |
| `wiliwili/source/view/mpv_core.cpp` | `default_framebuffer=1`（GLES 无系统 fb）扩到 TVOS | P2 |
| `wiliwili/source/utils/config_helper.cpp` | 9 处 iOS 条件扩到 TVOS（路径/沙盒/窗口/硬解/隐藏底栏等） | P2 |
| `wiliwili/source/utils/dialog_helper.cpp` | quitApp 内 `#ifndef IOS` → `!IOS && !TVOS` | P2 |
| `wiliwili/source/utils/version_helper.cpp` | 平台名返回 "iOS" 分支扩到 TVOS | P2 |
| `wiliwili/source/activity/setting_activity.cpp` | 隐藏"退出 App"按钮、隐藏 OpenCC 开关扩到 TVOS | P2 |

### 关键设计说明

- **ios_bundle 修复（P1/P3）**：wiliwili 原 6 参调用是参数错位 bug。现拆为：
  - `elseif (PLATFORM_IOS)` → iphoneos/Splash.storyboard + iOSBundleInfo.plist.in（5 参）
  - `elseif (PLATFORM_TVOS)` → tvos/Splash.storyboard + tvOSBundleInfo.plist.in（5 参）
  与 borealis demo 的双分支模式一致，可原样向上游提 PR。

- **不给 tvOS 定义 IOS 宏（P2 关键约束）**：若让 tvOS 也定义 `IOS`，会误启用
  borealis `ios_darwin.mm` 的 `UIDevice.batteryState` 电池 API——tvOS 的
  `UIDevice` 无 batteryMonitoring，会取到无效值。故所有条件均逐处写成显式
  `defined(IOS) || defined(TVOS)`。

- **config_helper.cpp 9 处**：均为「tvOS 需与 iOS 相同行为」——沙盒路径
  （CoreFoundation）、无窗口概念（跳过 loadHomeWindowState / setWindowSizeLimits
  / saveHomeWindowState）、无可写路径（跳过 gamecontrollerdb）、无法自重启进程
  （禁 RESTART_APP）、大屏默认隐藏底栏、VideoToolbox 硬解默认开。

### 风险与需真机验证项

| 项 | 风险 | 状态 |
|---|---|---|
| `OpenGLES.framework` 在 tvOS 为 deprecated（但存在可链接） | 中 | **需真机验证** 运行期告警 / 审核策略 |
| CoreMedia/CoreText/VideoToolbox 在 appletvos SDK 可链接性 | 低 | **需真机验证** |
| tvOS 分层图标（Brand Assets 400×240 / 1280×768 + Top Shelf 1920×720） | 高 | **未提供**——需 Xcode Asset Catalog 制作。当前 plist 中 `CFBundleIcons` 段注释占位，见下 |
| libmpv/ffmpeg 的 appletvos 预编译包 + VideoToolbox 硬解 | 中-高 | 用户在 Mac 交叉编译，见 docs/BUILD-tvos.md |
| SDL2 子模块在 appletvos SDK 下 configure | 中 | **需真机验证**（SDL 官方支持 tvOS） |
| 全量编译期是否全绿 | 低-中 | **需真机验证** |

### 图标占位说明（P4 TODO）

`tvOSBundleInfo.plist.in` 中 `CFBundleIcons` 段以注释占位。tvOS 不接受 iOS 扁平
图标（现有 `Images.xcassets/AppIcon.appiconset` 均为扁平尺寸）。真机出包前需：
1. 在 Xcode 新建 tvOS Asset Catalog，添加 **App Icon（Brand Assets，多图层
   400×240 与 1280×768）** 与 **Top Shelf Image 1920×720**；
2. 取消 plist 中 `CFBundleIcons` 注释并指向该图标名；
3. 在 `ios_bundle` 的 `XCODE_ATTRIBUTE_ASSETCATALOG_COMPILER_APPICON_NAME`
   （borealis toolchain.cmake:192，值 "AppIcon"）侧确认名称一致。

未提供图标时仍可生成 **未签名/未上架** 的可编译工程用于验证。

## 应用顺序

```bash
cd wiliwili
git apply patches/0002-wiliwili-tvos.patch
```
（0001 省略，borealis 子模块无需 patch。）
