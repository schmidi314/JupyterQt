cmake_minimum_required(VERSION 3.16)
project(JupyterQt VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Network WebSockets)

set(SOURCES
    src/main.cpp
    src/models/CellModel.cpp
    src/models/NotebookModel.cpp
    src/models/KernelState.cpp
    src/jupyter/JupyterMessage.cpp
    src/jupyter/ExecutionTracker.cpp
    src/jupyter/KernelClient.cpp
    src/network/RestClient.cpp
    src/controllers/NotebookController.cpp
    src/controllers/AppController.cpp
    src/ui/MainWindow.cpp
    src/ui/WorkspaceWidget.cpp
    src/ui/EditorPane.cpp
    src/ui/NotebookTab.cpp
    src/ui/CellWidget.cpp
    src/ui/OutputArea.cpp
    src/ui/FileBrowser.cpp
    src/ui/ConnectionDialog.cpp
    src/ui/KernelStatusWidget.cpp
    src/ui/renderers/TextRenderer.cpp
    src/ui/renderers/ImageRenderer.cpp
    src/ui/renderers/HtmlRenderer.cpp
    src/ui/renderers/ErrorRenderer.cpp
)

set(HEADERS
    src/config/ServerConfig.h
    src/models/CellModel.h
    src/models/NotebookModel.h
    src/models/KernelState.h
    src/jupyter/JupyterMessage.h
    src/jupyter/ExecutionTracker.h
    src/jupyter/KernelClient.h
    src/network/RestClient.h
    src/controllers/NotebookController.h
    src/controllers/AppController.h
    src/ui/MainWindow.h
    src/ui/WorkspaceWidget.h
    src/ui/EditorPane.h
    src/ui/NotebookTab.h
    src/ui/CellWidget.h
    src/ui/OutputArea.h
    src/ui/FileBrowser.h
    src/ui/ConnectionDialog.h
    src/ui/KernelStatusWidget.h
    src/ui/renderers/TextRenderer.h
    src/ui/renderers/ImageRenderer.h
    src/ui/renderers/HtmlRenderer.h
    src/ui/renderers/ErrorRenderer.h
)

add_executable(JupyterQt ${SOURCES} ${HEADERS})

target_include_directories(JupyterQt PRIVATE src)

target_link_libraries(JupyterQt PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::Network
    Qt6::WebSockets
)

if(WIN32)
    set_target_properties(JupyterQt PROPERTIES WIN32_EXECUTABLE TRUE)
endif()
