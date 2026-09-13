---
id: procedural-kde-app-harmonyos-kfshim
type: procedural
domain: workflow
tags: [kde, kf5, kf6, harmonyos, ohos, porting, shim, kconfig, kxmlgui, qt6, cmake]
created: 2026-09-13
updated: 2026-09-13
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-third-party-libs, semantic-qt-harmonyos-qt6-status, episodic-projects-gallery-qt6-harmonyos-port]
summary: >
  KDE 应用鸿蒙化的 kfshim 方法：不交叉编译 KDE Frameworks，而是用一个薄 shim 层
  在 Qt 之上重实现应用真正用到的那几个 KF 类（KXmlGuiWindow/KStandardAction/
  KConfigDialog/KConfigSkeleton/KColorButton 等），并用脚本替代 kconfig_compiler
  从 .kcfg 生成设置类。上游源码的 KF 调用点一处不改，构建走独立的 ohos/CMakeLists.txt。
  含接触面量化方法、六步流程、六个实测坑（WA_DeleteOnClose 最隐蔽）和 KCalc 真机实证。
---

# KDE 应用鸿蒙化：kfshim 方法

> 把依赖 KDE Frameworks 的 Qt Widgets 应用移植到 HarmonyOS，**绕开 KF 交叉编译**。
> 通用 Qt 鸿蒙化流程见 [[qt-app-harmonyos-migration]]，本页只解决"KF 依赖怎么办"。

---

## 触发条件

- 目标应用 `find_package(KF5 ...)` / `find_package(KF6 ...)`，链接 `KF5::XmlGui`、`KF5::ConfigWidgets` 等。
- 目标平台只有 Qt6 鸿蒙 kit（现状），而应用是 KF5/Qt5 代码。
- 不想、也没必要把十几个 KF 框架搬到鸿蒙上。

---

## 为什么不交叉编译 KF6

| 路线 | 代价 | 风险 |
|------|------|------|
| 交叉编译 KF6 | ECM + 10~12 个框架，`KXmlGui` 依赖链含 `KWindowSystem` / `KGlobalAccel` / `KIconThemes`；`KCrash`、`KNotifications` 带 X11 / D-Bus | 鸿蒙上**无先例**，有被卡死的实际风险；工作量以周计 |
| **kfshim** | 重实现应用**实际调用**的那部分 KF API | 接触面可 grep 量化；上游 KF 调用点零改动 |

关键判断依据：**大多数 KDE 应用的 KF 接触面远比 `target_link_libraries` 看起来浅。**
KCalc 链接 8 个 KF 框架，实际调用点只有十几处（见 §1 的量化方法）。

> **shim 的设计红线**：shim 沿用 KF 的**类名、头文件名（含 CamelCase 转发头）和语义**，
> 让上游源码以为自己还在用 KF。一旦开始改上游的 KF 调用点，就说明该重新评估路线了。

---

## 决策门槛

先跑 §1 的量化，再按下表选：

| 量化结果 | 选择 |
|----------|------|
| KF 类 < ~20 个，且不含 KIO / KParts / KTextEditor / Akonadi / KRunner | ✅ kfshim |
| 用到 KIO（网络透明 IO）、KParts（组件嵌入）、KTextEditor（KATE 编辑器组件） | ❌ 这些本身就是大型框架，shim 不现实——考虑换应用或裁功能 |
| 依赖 KWindowSystem 做实质窗口管理（而非仅被传递性拉入） | ⚠️ 鸿蒙窗口模型不同，见 [[qt-harmonyos-window-model]]，先评估语义能否映射 |
| 依赖 D-Bus 做进程间通信 | ❌ 见 [[qt-harmonyos-modules]]，鸿蒙无 D-Bus |

---

## 步骤

### 1. 量化 KF 接触面

```bash
# 实际 include 了哪些 KF 头（这是真正的接触面，不是 CMake 里链接的框架数）
grep -rhE '^#include <[Kk]' --include='*.cpp' --include='*.h' . | sort | uniq -c | sort -rn

# .ui 文件里的 KF 自定义控件（uic 会按 <header> 生成 include）
grep -h -A3 '<customwidget>' *.ui | grep -E '<class>|<header' | paste - -

# 生成类的调用点数量（决定"重写访问器"还是"写生成器"）
grep -rhoE '<生成类名>::[a-zA-Z0-9_]+' --include='*.cpp' . | sort -u | wc -l

# 顺带做 Qt5→Qt6 预检
grep -rn 'QRegExp\|QDesktopWidget\|QStringRef\|qSort\|QLinkedList\|QTextCodec' --include='*.cpp' --include='*.h' .
```

> **量化时看 include 而不是看 `target_link_libraries`**：KF 框架之间大量传递性依赖，
> 链接 8 个框架不代表调用了 8 个框架的 API。

### 2. 搭 shim 骨架

shim 单独一个仓库（理由见 §3 末），应用侧只留一个薄壳工程：

```
kfshim/                    # 独立仓库，跨应用复用
  include/
    klocalizedstring.h  kxmlguiwindow.h  kconfigskeleton.h  ...   # 小写实名头
    KLocalizedString    KXmlGuiWindow    KConfigSkeleton    ...   # CamelCase 转发头
  src/*.cpp
  tools/kcfgc_lite.py      # kconfig_compiler 替代
  cmake/KFShimMacros.cmake # kfshim_add_kcfg_files()
  tests/                   # 不依赖任何应用的自测
  CMakeLists.txt           # add_library(kfshim STATIC ...)

<app>/ohos/CMakeLists.txt  # 薄壳：add_subdirectory(${KFSHIM_ROOT}) + 引用上游源码
```

CamelCase 转发头一行生成（KF 的两种 include 风格上游都会用）：

```bash
while read -r camel lower; do printf '#include "%s"\n' "$lower" > "$camel"; done <<'EOF'
KAboutData kaboutdata.h
KXmlGuiWindow kxmlguiwindow.h
...
EOF
```

### 3. 逐组件替换

实测可行的映射（KCalc 全量）：

| KF 组件 | shim 实现 |
|---------|-----------|
| `KLocalizedString` / `i18n()` / `i18nc()` / `I18N_NOOP` | 变参模板套 `QCoreApplication::translate()`，`%1` 用 `.arg()` 链式展开 |
| `KXmlGuiWindow` | `QMainWindow` + 迷你 XMLGUI：用 `QDomDocument` 解析 `.rc` 建菜单栏 |
| `KActionCollection` | name→`QAction` 注册表，`add<T>(name)` 模板 |
| `KStandardAction` | 按 KF 的 action name 建标准动作（`file_quit` / `edit_copy` / `options_configure`…）——**名字必须对**，`.rc` 按名字引用 |
| `KToggleAction` / `KToolBar` | `QAction`（setCheckable）/ `QToolBar` 子类 |
| `KXMLGUIFactory` | 只需 `showConfigureShortcutsDialog()`，做成只读快捷键列表 |
| `KConfigSkeleton` | `QSettings` 后端 + `KConfigSkeletonItem` 列表（name/key/group/default/min/max） |
| `KConfigDialog` | `QTabWidget` + 按 **USER property** 绑定 `kcfg_*` 控件 |
| `KColorButton` / `KFontRequester` / `KSqueezedTextLabel` | `QPushButton`(+`QColorDialog`) / `QWidget`(+`QFontDialog`) / `QLabel`(+`elidedText`) |
| `KColorScheme` | `QPalette` 角色查表（View→Base/Text，Button→Button/ButtonText） |
| `KColorMimeData` | `QMimeData::hasColor()` / `colorData()` |
| `KCrash` | no-op（鸿蒙有自己的 faultlog） |
| `KNotification::beep()` | `QApplication::beep()` |
| `KAboutData` | 字段容器 + `Help > About` 对话框 |
| `KAcceleratorManager` | no-op |
| `Kdelibs4ConfigMigrator` | 上游通常已被 `QT_VERSION < 6` 包住，直接不管 |

> **把 shim 做成独立库，别 vendor 进应用**：shim 与具体应用无关，做成一个独立
> git 仓库（`add_library(kfshim STATIC ...)` + `target_include_directories(... PUBLIC include)`），
> 应用侧 `add_subdirectory()` 即可。理由很实际——§坑 1 那种缺陷一旦在两份拷贝之间分叉，
> 就是"A 应用修好了、B 应用还在静默丢设置"。
>
> 库化时要把 shim 里的应用名硬编码拔掉：KF 的 `KStandardAction::preferences` 文案本来就是
> `i18n("&Configure %1...", componentName)`，shim 照做即可（取 `applicationDisplayName()`，
> 回退 `applicationName()`）；`KLocalizedString::applicationDomain()` 未设置时也回退到应用名。

### 4. 替代 kconfig_compiler

`kconfig_add_kcfg_files()` 从 `.kcfg` + `.kcfgc` 生成设置类。写个脚本产出**同名访问器**的类，
上游那上百处 `XxxSettings::foo()` / `setFoo()` 就一处不用改。

需要支持的 `.kcfg` 构造（覆盖典型 KDE 应用）：

- 类型 `Bool` / `Int` / `UInt` / `String` / `Color` / `Font` / `Enum`
- `<default>` 字面量 与 `<default code="true">` C++ 表达式
- `<code>` 块（原样搬进构造函数，供 `code="true"` 的默认值引用）
- `<min>` / `<max>`（在 setter 里 clamp）
- `<parameter>` 索引项（`nameConstant$(ConstIndex)` → `setNameConstant(int i, ...)`）
- `.kcfgc` 的 `Singleton` / `Mutators` / `UseEnumTypes`

再包一个 CMake 函数对齐 KDE 的用法，应用侧调用形态就完全一致：

```cmake
# 对标 KDE 的 kconfig_add_kcfg_files()
kfshim_add_kcfg_files(myapp myapp.kcfg myapp_settings.kcfgc)
```

两个生成细节：

- **枚举必须以 `int` 存进 QVariant**：`QVariant::fromValue(EnumFoo::type)` 得到的是未注册的
  自定义 metatype，`toInt()` 取不出来。生成 `QVariant::fromValue<int>(static_cast<int>(v))`。
- **默认值按声明类型收窄**：`QVariant::fromValue<uint>(12)` 而不是 `fromValue(12)`，
  否则 `load()` 的类型回转会在 int/uint 之间来回抖。

### 5. 独立 CMakeLists，不碰上游

放在 `ohos/CMakeLists.txt`，用 `list(TRANSFORM ... PREPEND "${KCALC_SRC_DIR}/")` 引用上游源码。
上游那份 ECM+KF5 的 `CMakeLists.txt` 原样保留。

必须项（其余见 [[qt-harmonyos-golden-rules]]）：

```cmake
project(<app> LANGUAGES CXX C)          # check_type_size 要 C；只写 CXX 会报 "Unknown extension .c"
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)                   # B10
set(CMAKE_AUTOUIC_SEARCH_PATHS "${SRC_DIR}")
if(CMAKE_CROSSCOMPILING)
    set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)   # B1
endif()

# 宿主机上的交叉编译产物（GMP/MPFR 等），必须跳过 sysroot 重定根
find_library(GMP_LIBRARY NAMES gmp PATHS "${PREFIX}/lib" NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
```

原生依赖（GMP/MPFR/…）编成**静态 PIC 库**，HAP 里就不用多带 .so：

```bash
# GMP 的 config.sub 不认 'ohos'（报 OS 'ohos' not recognized）。
# --host 只决定汇编风格，CC 已经指向鸿蒙 clang，所以填 gnu 三元组即可。
./configure --host=aarch64-unknown-linux-gnu --prefix=$PREFIX \
            --disable-shared --enable-static --with-pic
```

### 6. 先 host 自测，再真机

同一份 `ohos/CMakeLists.txt` 也能为 macOS/Linux 配置——**这是验证 shim 最便宜的手段**，
迭代一轮几秒，不用签名装机。建一个 `KCALC_BUILD_TESTS` 开关，离屏跑：

- 设置项的 `QSettings` save/load 往返（各类型都要覆盖：bool/uint/QColor/QFont/枚举/索引项）
- `<min>` / `<max>` clamp
- **所有 `kcfg_` 控件都绑上了**（shim 对绑不上的控件 `qWarning`，测试里捕获消息断言为空）
- **`createGUI()` 产出的菜单栏顺序**（见 §坑 2）

> 如果上游 `main()` 在同一个 .cpp 里，用 `#ifndef APP_NO_MAIN` 包住，测试目标就能链接主窗口类。

shim 库本身还应带一份**不依赖任何应用**的自测：自带一个小 `.kcfg`、一个 `.rc`、
一个手搓的设置页，覆盖上面四类断言。这样换下一个应用时，先跑库自测就能把"是 shim 的问题
还是新应用的问题"分开。

真机验证按 [[qt-ohos-run-test]]；打包/签名/依赖闭包按 [[gallery-qt6-harmonyos-port]]。

---

## 六个实测坑

### 坑 1 🟠 `WA_DeleteOnClose` —— 最隐蔽，静默丢功能

`KMainWindow` 构造时会 `setAttribute(Qt::WA_DeleteOnClose)`。很多 KDE 应用**靠析构函数保存设置**：

```cpp
KCalculator::~KCalculator() { KCalcSettings::self()->save(); }
// main(): auto calc = new KCalculator(nullptr); calc->show(); return app.exec();
```

主窗口是 `new` 出来且从不 `delete` 的，只有 `WA_DeleteOnClose` 才让析构跑起来。
shim 的 `KXmlGuiWindow` 漏了这一条 → **所有设置改动退出即丢，且不报任何错**。

```cpp
KXmlGuiWindow::KXmlGuiWindow(QWidget *parent, Qt::WindowFlags flags)
    : QMainWindow(parent, flags)
{
    setAttribute(Qt::WA_DeleteOnClose);   // KMainWindow 的行为，别漏
}
```

鸿蒙侧额外确认过：`QAbility::onDestroy` → `_Exit(0)` **没有**抢在 deferred delete 前面，
真机上配置文件正常回写（实证见下）。

### 坑 2 🟠 `createGUI()` 的菜单栏顺序是 load-bearing

KDE 应用经常按**下标**往菜单栏里插菜单：

```cpp
menuBar()->insertMenu((menuBar()->actions)()[2], constants_menu_);   // KCalc
```

真 KXmlGui 把 app 的 `.rc` 与 `ui_standards.rc` 合并出 `File | Edit | Settings | Help`，
下标 2 正好是 Settings。shim 必须复现同样的顺序：

```
File（file_* 动作） → Edit（edit_* 动作） → .rc 里声明的菜单 → Help
```

顺序错了不会报错，只会把菜单插错位置。**把它写进自测断言**。

### 坑 3 🟢 `kcfg_` 绑定走 USER property，QComboBox 是例外

`KConfigDialogManager` 的绑定机制就是控件的 USER property：
`QCheckBox`→`checked`、`QSpinBox`→`value`、`QLineEdit`→`text`。
自己写的 shim 控件照抄 KF 的声明即可：

```cpp
Q_PROPERTY(QColor color READ color WRITE setColor NOTIFY changed USER true)
```

于是绑定代码是通用的：`widget->metaObject()->userProperty().read/write(widget, value)`。
**唯一要特判 `QComboBox`**——它的 USER property 是 `currentText`，而 kcfg 的 Enum 存的是索引，
要改用 `currentIndex`。

### 坑 4 🟢 `i18n` / `KColorScheme` 是靠 KF 头传递性引进来的

上游 .cpp 常常用了 `i18n()` 却没 `#include <KLocalizedString>`——KF 的其他头帮它引了。
换成 shim 后编译报 `use of undeclared identifier 'i18n'`。补 include 即可，
这属于 IWYU 修正，对上游也是对的。

### 坑 5 🟢 QSettings 会把组名 `General` 写成 `[%General]`

`General` 是 QSettings 的保留组名，用户组叫 `General` 时会转义成 `%General`。
读写往返正确，但**产出的配置文件与 KConfig 的不是字节兼容的**。
自用自读没问题；如果需要和桌面版 KDE 共享配置文件，这条要单独处理。

### 坑 6 🟢 `check_type_size` 需要 `project(... C)`

`config-*.h.cmake` 这类 autotools 遗产常用 `check_type_size` / `check_include_files`，
它们生成 `.c` 探针。`project(foo LANGUAGES CXX)` 会报
`Unknown extension ".c" ... try_compile() works only for enabled languages`。

---

## 沙箱路径实测（Qt 6.12 / HarmonyOS 6.1.0）

`QStandardPaths::AppConfigLocation` → `<沙箱>/preferences`，即
`/data/storage/el2/base/preferences`（hdc 侧看到的是
`/data/app/el2/100/base/<bundle>/preferences/`）。

与 [[gallery-qt6-harmonyos-port]] 实测的 `AppLocalDataLocation` 落点相同，
**两者都映射到 `preferences/`**。目录可写，`QSettings` 的 INI 后端工作正常。

---

## 实证：KCalc 22.03.70

| 项目 | 数据 |
|------|------|
| 源 | KCalc 22.03.70（Qt5 + KF5 ×8：CoreAddons/Crash/Config/ConfigWidgets/GuiAddons/I18n/Notifications/XmlGui） |
| 目标 | HarmonyOS arm64-v8a / Qt 6.12.0 预构建 kit / host macOS |
| shim 规模 | 18 头 + 12 源；`kcfgc_lite.py` 从 38 个 `<entry>` 生成 48 个访问器 |
| **上游 KF 调用点改动** | **0** |
| 上游源码改动 | 仅 Qt5→Qt6 四处：`QRegExp`→`QRegularExpression`、`QLocale::groupSeparator()`/`zeroDigit()`/`decimalPoint()` 返回 `QString`、2 个传递性 include、`main()` 加守卫 |
| 平台条件代码 | 全工程**无任何 `Q_OS_*` 分支**，移植也没新增 |
| 原生依赖 | GMP 6.3.0 + MPFR 4.2.2 交叉编译为静态 PIC 库 |
| HAP | 104.5 MB；27 个 .so，依赖闭包 **0 未解析** |
| 自测 | 应用侧 host 离屏 16 项全过（含 42 个 `kcfg_` 控件全绑定）；shim 库另带 24 项独立自测 |
| **真机** | ✅ HUAWEI HAD-W32 / HarmonyOS 6.1.0(API 24)：渲染正常、深色模式跟随系统、`ohos` style 生效、原生标题栏；`7×8=56` 且 Hex 38 / Oct 70 / Bin 111000 正确；设置跨进程持久化正确回写 |

`QRegExp`→`QRegularExpression` 有个容易漏的语义差：
**`QRegularExpression` 不会把 `capturedTexts()` 补齐到分组数**，
`QRegExp` 时代 `list.size() == N` 的判断会直接失效——改用 `match.captured(n)` 逐个取。

---

## 何时该放弃 shim

- grep 出 `KIO` / `KParts` / `KTextEditor` / `Akonadi` / `KRunner`：这些本身是大型子系统。
- 应用把 KF 当框架而非工具用（大量 `KPluginFactory`、`KConfigGroup` 深度嵌套读写、KAuth 提权）。
- shim 开始需要修改上游 KF 调用点才能编过——这是路线选错的信号。

---

## 参考

- [[qt-app-harmonyos-migration]] — 通用 Qt 鸿蒙化迁移流程（本页是其中"KF 依赖"分支的展开）
- [[qt-harmonyos-golden-rules]] — 构建/窗口/生命周期铁律（B1/B10/B13、W3、L2）
- [[gallery-qt6-harmonyos-port]] — Qt 6.12 预构建 kit 的打包、`QT_HARMONYOS_EXTRA_LIBS`、命令行签名六件套
- [[qt-harmonyos-third-party-libs]] — 三方库（GMP/MPFR 一类）交叉编译与部署
- [[qt-ohos-run-test]] — 真机运行测试闭环
