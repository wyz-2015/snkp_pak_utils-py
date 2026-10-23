#!/usr/bin/env python3

import sys
import numpy as np
from pathlib import Path
import argparse
from typing import IO
import shutil


class PK():
    Struct_PK_Head = np.dtype([
        ("magic", "S2"),
        ("reversed0", np.uint8),
        ("type", np.uint8),

        ("decodeSize", np.uint32),

        ("reversed1", np.uint32, (2,))
    ])

    Type_Note = {
        0: "原始数据",
        1: "...",
        2: "LZSS变种压缩算法"
    }

    def __init__(self, pkFilePath: Path):
        self.pkFilePath = pkFilePath
        self.pkFile: IO[bytes] = None

        self.magic = ""
        self.reversed0 = 0
        self.type = 0

        self.decodeSize = 0

        self.reversed1 = []

    def set_type(self, _type: int):
        """
        强行设定type，覆盖读头所得
        """
        self.type = _type

    def read_head(self):
        self.pkFile = open(self.pkFilePath, "rb")

        head_bin = np.fromfile(
            self.pkFile, dtype=self.Struct_PK_Head, count=1)[0]

        self.magic = head_bin["magic"].decode("utf-8")
        if (self.magic != "PK"):
            raise ValueError("不正确的魔术头：{0:s}".format(self.magic))

        self.reversed0 = int(head_bin["reversed"])
        self.type = int(head_bin["type"])

        self.decodeSize = int(head_bin["decodeSize"])

        self.reversed1 = head_bin["reversed1"].tolist()

        print("编码类型：0x{0:02x} {1:s}\n解码后理论大小：{2:n}".format(
            self.type, self.Type_Note[self.type], self.decodeSize))

    def decompress_lzss_like(self, outFile: IO[bytes]):
        pass  # TODO

    def decode(self, outFilePath: Path):
        match (self.type):
            case 0:  # 直接复制
                outFile = open(outFilePath, "wb")

                self.pkFile.seek(self.Struct_PK_Head.itemsize,0)
                shutil.copyfileobj(self.pkFile,outFile)

                outFile.close()
            case 1:
                pass  # TODO
            case 2:  # LESS变种解压缩
                outFile = open(outFilePath, "wb+")
                self.decompress_lzss_like(outFile)
                outFile.close()
            case _:
                raise ValueError("未知类型代号：{0:n}".format(self.type))

    def clear(self):
        self.pkFile.close()


def main():
    cmdParser = argparse.ArgumentParser(
        description="一款支持 解码 Metal Slug 3D、7 等SNK游戏 中出现的被称为“PK”的特有单文件已编码格式文件 的工具。")
    cmdParser.add_argument("inFile", help="传入文件路径", type=Path)
    cmdParser.add_argument("-d", "--decode", help="解码", required=False,
                           action="store_const", const='d', default=None)
    cmdParser.add_argument("-e", "--encode", help="编码", required=False,
                           action="store_const", const='e', default=None)  # 先不实现这个
    cmdParser.add_argument("-o", "--out-file", help="输出文件路径",
                           required=True, type=Path, dest="outFilePath")
    cmdParser.add_argument("-t", "--type", help="强行指定编解码类型(适用于KOF MI RA等未按理论方案编码pk文件的情况)",
                           choices={0, 1, 2}, type=int, default=None, required=False, dest="forceType")

    args = cmdParser.parse_args()
    print(args)

    mode = tuple(m for m in (args.decode, args.encode) if (m))
    if (len(mode) != 1):
        raise Exception("-d -e能且只能选择其中之一")
    mode = mode[0]

    match (mode):
        case 'e':
            pass
        case 'd':
            pk = PK(args.inFile)
            if (args.forceType is not None):
                pk.set_type(args.forceType)
            pk.decode(args.outFilePath)
            pk.clear()
        case _:
            raise ValueError("未知模式代号：{0:s}".format(mode))


if (__name__ == "__main__"):
    sys.exit(main())
