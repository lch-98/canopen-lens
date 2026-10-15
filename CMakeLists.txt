cmake_minimum_required(VERSION 3.15...3.29)
project(${SKBUILD_PROJECT_NAME} VERSION ${SKBUILD_PROJECT_VERSION} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_core
    src/core/parser.cpp
    src/core/analyzer.cpp
    src/core/trace.cpp
    src/core/bindings.cpp)
target_include_directories(_core PRIVATE src/core)
if(MSVC)
    target_compile_options(_core PRIVATE /W4 /utf-8)
else()
    target_compile_options(_core PRIVATE -Wall -Wextra)
endif()

install(TARGETS _core DESTINATION canopen_lens)
