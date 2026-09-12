#!/usr/bin/env python3
"""Compile the optional experiment shaders with the shaderc C API."""
import ctypes
import ctypes.util
from pathlib import Path
import sys


def api(library, name, result, arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


def compile_shader(source, destination, fused=False):
    pointer = ctypes.c_void_p
    string = ctypes.c_char_p
    size = ctypes.c_size_t
    library = ctypes.CDLL(ctypes.util.find_library("shaderc") or "libshaderc.so.1")
    initialize = api(library, "shaderc_compiler_initialize", pointer, [])
    compile_spv = api(library, "shaderc_compile_into_spv", pointer,
                      [pointer, string, size, ctypes.c_int, string, string, pointer])
    code = source.read_bytes()
    compiler = initialize()
    if not compiler:
        raise RuntimeError("shaderc compiler initialization failed")
    result = None
    options = None
    try:
        options = api(library, "shaderc_compile_options_initialize", pointer, [])()
        if not options:
            raise RuntimeError("shaderc options initialization failed")
        api(library, "shaderc_compile_options_set_optimization_level", None,
            [pointer, ctypes.c_int])(options, 2)
        if fused:
            api(library, "shaderc_compile_options_add_macro_definition", None,
                [pointer, string, size, string, size])(options, b"FUSED", 5, b"1", 1)
        result = compile_spv(compiler, code, len(code), 2, str(source).encode(), b"main", options)
        write_result(library, result, destination)
    finally:
        if result:
            api(library, "shaderc_result_release", None, [pointer])(result)
        api(library, "shaderc_compile_options_release", None, [pointer])(options)
        api(library, "shaderc_compiler_release", None, [pointer])(compiler)


def write_result(library, result, destination):
    pointer = ctypes.c_void_p
    if not result:
        raise RuntimeError("shaderc returned no result")
    status = api(library, "shaderc_result_get_compilation_status", ctypes.c_int, [pointer])
    if status(result):
        message = api(library, "shaderc_result_get_error_message", ctypes.c_char_p, [pointer])
        raise RuntimeError(message(result).decode())
    length = api(library, "shaderc_result_get_length", ctypes.c_size_t, [pointer])(result)
    data = api(library, "shaderc_result_get_bytes", pointer, [pointer])(result)
    destination.write_bytes(ctypes.string_at(data, length))


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != "fused"):
        sys.exit("usage: compile_vulkan_shader.py source.comp output.spv [fused]")
    compile_shader(Path(sys.argv[1]), Path(sys.argv[2]), len(sys.argv) == 4)
