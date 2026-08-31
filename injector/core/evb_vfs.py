# -*- coding: utf-8 -*-
"""EnigmaVB 虚拟文件系统（VFS）选择性提取。

文件表解析逻辑移植自 evbunpack 0.2.6（Apache License 2.0）：
    https://github.com/mos9527/evbunpack
    Copyright (c) mos9527 (greats3an@gmail.com)

用途：打包版游戏中 originals 无法从磁盘获得（解包目录不存在）时，
直接从 Game.exe 的 VFS 提取原版文件（如 EventInformation.js）。

当前仅支持未压缩文件（stored_size == original_size）。
压缩文件（aPLib 分块压缩）暂不支持，会记录错误并返回 False ——
此时 bootstrap 的 try/catch 保证 MOD 插件仍然加载，只是该原版
文件对应的游戏插件缺失。
"""
import os
import struct
from mmap import mmap, ACCESS_READ

EVB_MAGIC = b"EVB\x00"

# ── EVB 文件表结构（来自 evbunpack const.py） ──
EVB_PACK_HEADER = [("4s", "signature"), ("60s", ""), ]
EVB_HEADER_NODE = [("I", "size"), ("8s", ""), ("I", "objects_count"), ]
EVB_NODE_MAIN = [("I", "size"), ("8s", ""), ("I", "objects_count"), ]
EVB_NODE_NAMED = [("%ds", "name"), ("B", "type"), ]
EVB_NODE_OPTIONAL_FILE = [
    ("2s", ""), ("I", "original_size"), ("4s", ""),
    ("8s", "filetime1"), ("8s", "filetime2"), ("8s", "filetime3"),
    ("15s", ""), ("I", "stored_size"),
]

NODE_TYPE_MAIN = 0
NODE_TYPE_FILE = 2
NODE_TYPE_FOLDER = 3


def _make_fmt(struct_, *args):
    fmt, desc = zip(*filter(lambda p: isinstance(p, tuple), struct_))
    fmt = ("<" if type(struct_[-1]) != str else struct_[-1]) + ("".join(fmt)) % args
    return fmt, desc


def _unpack(struct_, buffer, *args, **extra):
    fmt, desc = _make_fmt(struct_, *args)
    up = struct.unpack_from(fmt, buffer, 0)
    return {**{k: v for k, v in zip(desc, up) if k}, **extra}


def _size_of(struct_):
    return struct.calcsize(_make_fmt(struct_)[0])


def _read_named_node(src):
    """Read a UTF-16-LE name (2-byte chars, 0-terminated) + 1 type byte."""
    blk = bytearray()
    p = src.read(2)
    while p[0] != 0 or p[1] != 0:
        blk.extend(p)
        p = src.read(2)
    block = blk + src.read(1)
    return _unpack(EVB_NODE_NAMED, block, len(blk), offset=src.tell())


def _find_magic(fd) -> int:
    size = os.fstat(fd.fileno()).st_size
    with mmap(fd.fileno(), offset=0, length=size, access=ACCESS_READ) as mm:
        return mm.find(EVB_MAGIC)


def extract_files(exe_path: str, wanted: set, dest_dir: str) -> dict:
    """从 EnigmaVB 打包的 exe 中提取指定文件。

    wanted: 目标文件名（basename）集合，如 {"EventInformation.js"}
    dest_dir: 输出目录（文件直接写入该目录，按 basename 命名）
    返回 {basename: bool} —— True=成功（或已存在），False=失败。
    """
    results = {name: False for name in wanted}
    if not wanted:
        return results

    found = {}  # basename -> {"offset": ..., "stored": ..., "orig": ...}

    with open(exe_path, "rb") as fd:
        magic = _find_magic(fd)
        if magic < 0:
            raise ValueError(f"{exe_path} 不是 EnigmaVB 打包文件（未找到 EVB 魔数）")
        fd.seek(magic)

        # ── 第一遍：遍历文件表，收集匹配节点 ──
        hdr = _unpack(EVB_PACK_HEADER, fd.read(_size_of(EVB_PACK_HEADER)))
        if hdr["signature"] != EVB_MAGIC:
            raise ValueError("EVB 签名无效")
        main_node = _unpack(EVB_NODE_MAIN, fd.read(_size_of(EVB_NODE_MAIN)))
        abs_offset = fd.tell() + main_node["size"] - 12
        fd.seek(-1, 1)

        while len(found) < len(wanted):
            try:
                header_node = _unpack(EVB_HEADER_NODE, fd.read(_size_of(EVB_HEADER_NODE)))
                named_node = _read_named_node(fd)
            except struct.error:
                break  # EOF / 表结束
            if named_node["type"] == NODE_TYPE_FILE:
                opt = _unpack(EVB_NODE_OPTIONAL_FILE,
                              fd.read(_size_of(EVB_NODE_OPTIONAL_FILE)))
                opt["offset"] = abs_offset
                abs_offset += opt["stored_size"]
                name = named_node["name"].decode("utf-16-le")
                base = name.replace("\\", "/").split("/")[-1]
                if base in wanted:
                    found[base] = opt
            elif named_node["type"] == NODE_TYPE_FOLDER:
                fd.seek(25, 1)
            else:
                break  # NODE_TYPE_MAIN 或未知 → 结束

        # ── 第二遍：提取匹配文件 ──
        file_size = os.fstat(fd.fileno()).st_size
        os.makedirs(dest_dir, exist_ok=True)
        for base, opt in found.items():
            dest = os.path.join(dest_dir, base)
            if os.path.isfile(dest):
                results[base] = True
                continue
            if opt["stored_size"] != opt["original_size"]:
                # 压缩文件：aPLib 分块压缩，暂不支持
                continue
            if opt["offset"] + opt["stored_size"] > file_size:
                continue  # 偏移越界，表可能解析错误
            fd.seek(opt["offset"])
            data = fd.read(opt["stored_size"])
            if len(data) != opt["stored_size"]:
                continue
            try:
                with open(dest, "wb") as out:
                    out.write(data)
                results[base] = True
            except OSError:
                continue

    return results
