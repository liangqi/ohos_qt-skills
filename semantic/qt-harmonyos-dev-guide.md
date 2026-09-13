---
id: semantic-qt-harmonyos-dev-guide
type: semantic
domain: tech
tags: [qt, harmonyos, dev-guide, lifecycle, window, qml, deployment, floating, continuation, sharing]
created: 2026-06-02
updated: 2026-06-02
status: archived
audience: public
archive_date: 2026-06-03
archive_reason: A pure link index page; 12 of its 13 topics have been distilled into the lifecycle/window-model/build pages, and the wiki URL paths have changed
superseded_by: semantic-qt-harmonyos-lifecycle
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-api, semantic-qt-ohos-extras]
summary: >
  Index of the Qt-on-HarmonyOS development guides: application lifecycle, main/subwindow development, embedded subwindows,
  background child processes, using QOhosWant, passing arguments, QML deployment, dark/light mode, fullscreen launch,
  floating windows, continuation/handoff, sharing, and DevEco CMake cross-compilation.
---

# Index of the Qt for HarmonyOS development guides

> Source: [User Development Guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide)

## Guide list

| Topic | Wiki link | Summary |
|-------|-----------|---------|
| DevEco CMake cross-compilation | [deveco_cmake_guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/deveco_cmake_guide_cross_compile) | Building Qt applications with CMake in DevEco Studio |
| Application lifecycle and interaction | [application_lifecycle_guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/application_lifecycle_guide) | Ability lifecycle, launch/exit, Want interaction |
| Main window and subwindows | [mainwindow_subwindow](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/mainwindow_and_subwindow_guide) | Conventions for main window / subwindow development |
| Embedded subwindows | [embedded_subwindow](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/embedded_subwindow_guide) | Guide to developing embedded subwindows |
| Background child processes | [uiless_child_process](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_start_uiless_child_process) | Starting a UI-less background child process |
| Using QOhosWant | [QOhosWant](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_use_QOhosWant) | Using Want for cross-Ability communication |
| Passing arguments to main() | [pass_args_to_main](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_pass_args_to_main_guide) | How to pass arguments to Qt's main() |
| Deploying QML applications | [deploy_qml_app](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_deply_qml_app) | How to deploy a QML application |
| Dark/light mode | [color_theme](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/qt_for_harmonyos_color_theme) | Adapting to the system dark/light theme |
| Fullscreen main window launch | [fullscreen_main_window](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/qt_for_harmonyos_fullscreen_main_window) | Launching the main window fullscreen |
| Floating window development | [floating_window](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/floating_window_guide) | Guide to developing floating windows |
| Application continuation | [continuation](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/application_continuation_guild) | Cross-device application handoff |
| Application sharing | [sharing](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/application_share_guild) | Developing application sharing features |

## Key things to watch for

### Device type configuration
`module.deviceTypes` in the project's `entry/src/main/module.json5` needs adjusting:
- Sample projects usually only list `"phone"`
- To support tablets/PCs, add `"tablet"` and `"2in1"`

### Main window vs. subwindow
- **Main window**: corresponds to the main interface of a HarmonyOS Ability and has a system-level lifecycle
- **Subwindow**: a popup, dialog, or similar created internally by Qt; its lifecycle depends on the main window
- The two behave very differently with respect to modality, minimizing, fullscreen, `hide()`, and so on

## References

- [User Development Guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide)
- [HarmonyOS Development Fundamentals](https://wiki.qt.io/HarmonyOS_Development_Fundamentals)
