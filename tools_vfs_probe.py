# -*- coding: utf-8 -*-
"""VFS 探测脚本：解析 EnigmaVB 打包 exe 的虚拟文件系统表，
打印指定文件的 original_size/stored_size（判断是否压缩）。
算法移植自 evbunpack 0.2.6 (Apache-2.0, mos9527) 的 pe_external_tree。"""
import os
import struct
import sys
from mmap import mmap, ACCESS_READ

EVB_MAGIC = b"EVB\x00"

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


def make_fmt(struct, *args):
    fmt, desc = zip(*filter(lambda p: isinstance(p, tuple), struct))
    fmt = ("<" if type(struct[-1]) != str else struct[-1]) + ("".join(fmt)) % args
    return fmt, desc


def unpack(struct_, buffer, *args, **extra):
    fmt, desc = make_fmt(struct_, *args)
    up = struct.unpack_from(fmt, buffer, 0)
    return {**{k: v for k, v in zip(desc, up) if k}, **extra}


def size_of(struct_):
    return struct.calcsize(make_fmt(struct_)[0])


def read_named_node(src):
    blk = bytearray()
    p = src.read(2)
    while p[0] != 0 or p[1] != 0:
        blk.extend(p)
        p = src.read(2)
    block = blk + src.read(1)
    return unpack(EVB_NODE_NAMED, block, len(blk), offset=src.tell())


def walk_vfs(fd, wanted, limit=None):
    """Yield (path, node) for files whose path matches `wanted` (set of suffixes)."""
    magic = -1
    with mmap(fd.fileno(), offset=0, length=os.fstat(fd.fileno()).st_size, access=ACCESS_READ) as mm:
        magic = mm.find(EVB_MAGIC)
    assert magic >= 0, "EVB magic not found — not an Enigma VB packed file"
    fd.seek(magic)
    hdr = unpack(EVB_PACK_HEADER, fd.read(size_of(EVB_PACK_HEADER)))
    assert hdr["signature"] == EVB_MAGIC, "bad signature"
    main_node = unpack(EVB_NODE_MAIN, fd.read(size_of(EVB_NODE_MAIN)))
    abs_offset = fd.tell() + main_node["size"] - 12
    fd.seek(-1, 1)
    total_files = 0
    matched = 0
    while True:
        try:
            header_node = unpack(EVB_HEADER_NODE, fd.read(size_of(EVB_HEADER_NODE)))
            named_node = read_named_node(fd)
        except struct.error:
            return  # EOF
        if named_node["type"] == NODE_TYPE_FILE:
            opt = unpack(EVB_NODE_OPTIONAL_FILE, fd.read(size_of(EVB_NODE_OPTIONAL_FILE)))
            opt["offset"] = abs_offset
            abs_offset += opt["stored_size"]
            total_files += 1
            name = named_node["name"].decode("utf-16-le")
            if any(name.endswith(w) for w in wanted):
                matched += 1
                yield name, opt
        elif named_node["type"] == NODE_TYPE_FOLDER:
            fd.seek(25, 1)
        else:
            return
        if limit and matched >= limit:
            return


if __name__ == "__main__":
    exe = sys.argv[1] if len(sys.argv) > 1 else r"游戏/原版1.6/Game.exe"
    wanted = sys.argv[2:] if len(sys.argv) > 2 else [
        "EventInformation.js", "main.js", "plugins.js", "package.json"]
    with open(exe, "rb") as fd:
        for name, opt in walk_vfs(fd, wanted):
            comp = "COMPRESSED" if opt["stored_size"] != opt["original_size"] else "raw"
            print(f"{name:60s} orig={opt['original_size']:>10} stored={opt['stored_size']:>10}  {comp}  offset=0x{opt['offset']:x}")
