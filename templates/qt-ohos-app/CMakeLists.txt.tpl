# templates/qt-ohos-app/CMakeLists.txt.tpl
# Minimal CMake glue for building a Qt app against the Qt for HarmonyOS SDK.
# Encodes golden rules B1 (find-root-path mode) and B2 (QPA plugin link).
#
# Usage: instantiate into the HarmonyOS entry module's native build, then
# point -DCMAKE_PREFIX_PATH at your prebuilt Qt OHOS SDK (env.json key
# qt_sdk_prefix). See semantic/qt-harmonyos-project-structure.md for the
# full project structure and B3/B10/B11 for the remaining rules.

cmake_minimum_required(VERSION 3.16)
project({{APP_NAME}} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)   # golden rule B10: qrc resources must be compiled

# golden rule B1: allow find_package to see the OHOS Qt SDK through the
# cross toolchain (default ONLY would hide it)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)

find_package(Qt5 REQUIRED COMPONENTS Core Gui Widgets)

add_library(${CMAKE_PROJECT_NAME} SHARED
    {{SOURCES}}
)

target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE
    Qt5::Core
    Qt5::Gui
    Qt5::Widgets
    # golden rule B2: without the QPA platform plugin the app dies at launch
    # with `dlopen failed: library "libqohos.so" not found` (QOH001)
    Qt5::QOhosPlatformIntegrationPlugin
)
