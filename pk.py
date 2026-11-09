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
        1: "块式256节点树编码",
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
        写模式下，这个函数要先调用
        """
        self.type = _type
        print("已强行设定编码模式为：0x{0:02x} {1:s}".format(
            self.type, self.Type_Note[self.type]))

    #############################
    # 解码

    def read_head(self):
        self.pkFile = open(self.pkFilePath, "rb")

        head_bin = np.fromfile(
            self.pkFile, dtype=self.Struct_PK_Head, count=1)[0]

        self.magic = head_bin["magic"].decode("utf-8")
        if (self.magic != "PK"):
            raise ValueError("不正确的魔术头：{0:s}".format(self.magic))

        self.reversed0 = int(head_bin["reversed0"])
        self.type = int(head_bin["type"])

        self.decodeSize = int(head_bin["decodeSize"])

        self.reversed1 = head_bin["reversed1"].tolist()

        print("编码类型：0x{0:02x} {1:s}\n解码后理论大小：{2:n}".format(
            self.type, self.Type_Note[self.type], self.decodeSize))

    ################################
    # type 2

    def __read_flag_bit__(self, pkFile: IO[bytes], flag: np.uint8, bitPos: np.uint8) -> tuple[np.uint8, np.uint8, np.uint8]:
        if (bitPos > 7):
            bitPos -= 8
            flag = np.fromfile(pkFile, dtype=np.uint8, count=1)[0]

        bit = (flag >> (7 - bitPos)) & 0b00000001

        bitPos += 1
        return (flag, bitPos, bit)

    def __copy_match__(self, outFile: IO[bytes], distance: np.uint16, length: np.uint32):
        startOffset = outFile.tell() - int(distance)
        b = None
        for i in range(length):
            outFile.seek(startOffset + i, 0)
            b = outFile.read(1)

            outFile.seek(0, 2)
            outFile.write(b)

    def decompress_lzss_like(self, outFile: IO[bytes]):
        pkFileLen = self.pkFilePath.stat().st_size

        bitPos = np.uint8(0)
        flag = np.fromfile(self.pkFile, dtype=np.uint8, count=1)[0]
        while (self.pkFile.tell() < pkFileLen):
            (flag, bitPos, bit) = self.__read_flag_bit__(
                self.pkFile, flag, bitPos)
            if (bit == 1):  # 读控制位发现第1位是1，则拷贝1 Byte
                outFile.write(self.pkFile.read(1))

                continue

            (flag, bitPos, bit) = self.__read_flag_bit__(
                self.pkFile, flag, bitPos)
            if (bit == 1):  # 若上面读控制位发现第1位是0，则不会continue。到此检测第2位
                packedHeader = np.fromfile(
                    self.pkFile, dtype=">u2", count=1)[0]  # 读一个大端uint16

                distance = 0x800 - (packedHeader >> 5)
                lengthCode = np.uint8(packedHeader & 0x1f)

                length = None
                if (lengthCode == 0):
                    extension = np.fromfile(
                        self.pkFile, dtype=np.uint8, count=1)[0]

                    if (extension == 0):  # 长引用长度扩展值为0时，是整个type 2数据流的结束标记。
                        return

                    length = np.uint32(extension) + 1

                else:
                    length = np.uint32(lengthCode) + 2

                # outFile.seek(-distance, 1)
                # py版没有c版fread()的没能读满就舍弃已有全部变0的特性
                # tempBuffer = outFile.read(length)
                # outFile.seek(0, 2)
                # outFile.write(tempBuffer)

                # 上述做法仍然是不行的。它预设即将拷贝的数据都是拷贝开始前已有的，实际上的情况是，可能拷贝的数据是刚刚才写入的，如distance = 1，length > 1
                self.__copy_match__(outFile, distance, length)

            elif (bit == 0):
                (flag, bitPos, bit1) = self.__read_flag_bit__(
                    self.pkFile, flag, bitPos)
                (flag, bitPos, bit2) = self.__read_flag_bit__(
                    self.pkFile, flag, bitPos)
                lengthBits = (bit1 << 1) | bit2

                length = np.uint32(lengthBits) + 2
                offsetByte = np.fromfile(
                    self.pkFile, dtype=np.uint8, count=1)[0]

                distance = 0x100 - np.uint16(offsetByte)
                self.__copy_match__(outFile, distance, length)

    ##################################
    # type 1

    def decompress_tree_stream(self, outFile: IO[bytes]):
        while (outFile.tell() < self.decodeSize):
            node = np.arange(0, 256, dtype=np.uint8)
            child = np.zeros(256, dtype=np.uint8)
            stack = []

            entryCount = int(np.fromfile(
                self.pkFile, dtype=np.uint8, count=1)[0])
            usedNodes = 0
            while (True):
                if (entryCount > 0x7f):
                    usedNodes += entryCount - 0x7f
                    entryCount = 0

                if (usedNodes == 256):
                    break

                for i in range(0, entryCount + 1):
                    symbol = np.fromfile(
                        self.pkFile, dtype=np.uint8, count=1)[0]

                    node[usedNodes] = symbol

                    # usedNodes != node[usedNodes] 说明该节点是内部节点。
                    # 内部节点除了node[usedNodes]外，还需要再读一个字节作为child[usedNodes]。
                    if (usedNodes != node[usedNodes]):
                        child[usedNodes] = np.fromfile(
                            self.pkFile, dtype=np.uint8, count=1)[0]

                    usedNodes += 1

                if (usedNodes == 256):
                    break

                entryCount = int(np.fromfile(
                    self.pkFile, dtype=np.uint8, count=1)[0])

            rootCount = int(np.fromfile(self.pkFile, dtype=">i4", count=1)[0])

            while (True):
                rootCount_old = rootCount
                stackSize_old = len(stack)

                if (not stack):
                    rootCount -= 1

                    if (rootCount_old == 0):
                        break

                    index = int(np.fromfile(
                        self.pkFile, dtype=np.uint8, count=1)[0])

                else:
                    index = stack.pop()

                if (index == node[index]):
                    np.uint8(index).tofile(outFile)
                else:
                    stackSize_old = len(stack)
                    stack.append(int(child[index]))

                    stack.append(int(node[index]))

    def decode(self, outFilePath: Path):
        match (self.type):
            case 0:  # 直接复制
                outFile = open(outFilePath, "wb")

                self.pkFile.seek(self.Struct_PK_Head.itemsize, 0)
                shutil.copyfileobj(self.pkFile, outFile)

                outFile.close()
            case 1:  # 块式256节点树编码
                outFile = open(outFilePath, "wb")
                self.decompress_tree_stream(outFile)
                outFile.close()
            case 2:  # LESS变种解压缩
                outFile = open(outFilePath, "wb+")
                self.decompress_lzss_like(outFile)
                outFile.close()
            case _:
                raise ValueError("未知类型代号：{0:n}".format(self.type))

    ##########################
    # 编码

    def write_head(self, inFilePath: Path):
        match (self.type):  # 在这里就检测类型，若有问题，也不用打开文件指针
            case 0:
                print("编码类型：{0:n} {1:s}".format(
                    self.type, self.Type_Note[self.type]))
            case 1 | 2:
                raise ValueError(
                    "暂不打算支持生成1、2型编码方式的PK文件。当前指定编码方式：{0:n} {1:s}".format(self.type, self.Type_Note[self.type]))
            case _:
                raise ValueError("未知编码方式代号：{0:n}".format(self.type))

        self.pkFile = open(self.pkFilePath, "wb")

        self.magic = "PK"
        self.reversed0 = 0
        self.reversed1 = [0, 0]

        if (inFilePath.is_file()):
            self.decodeSize = inFilePath.stat().st_size
        else:
            raise TypeError("{0}不是一个“文件”".format(inFilePath))

        head = np.zeros(1, dtype=self.Struct_PK_Head)[0]
        head["magic"] = self.magic.encode("utf-8")
        head["reversed0"] = self.reversed0
        head["decodeSize"] = self.decodeSize
        head["reversed1"] = self.reversed1

        head["type"] = self.type

        head.tofile(self.pkFile)

    def encode(self, inFilePath: Path):
        if (self.type == 0):
            inFile = open(inFilePath, "rb")
            shutil.copyfileobj(inFile, self.pkFile)

            inFile.close()

    def clear(self):
        self.pkFile.close()


def main():
    cmdParser = argparse.ArgumentParser(
        description="一款支持 解码 Metal Slug 3D、7 等SNK(P)游戏 中出现的被称为“PK”的特有单文件已编码格式文件 的工具。")
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
            pk = PK(args.outFilePath)
            if (args.forceType is not None):
                pk.set_type(args.forceType)
            pk.write_head(args.inFile)
            pk.encode(args.inFile)
            pk.clear()
        case 'd':
            pk = PK(args.inFile)
            pk.read_head()
            if (args.forceType is not None):
                pk.set_type(args.forceType)
            pk.decode(args.outFilePath)
            pk.clear()
        case _:
            raise ValueError("未知模式代号：{0:s}".format(mode))


if (__name__ == "__main__"):
    sys.exit(main())
