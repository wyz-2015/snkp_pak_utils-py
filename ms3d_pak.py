#!/usr/bin/env python3

import numpy as np
import sys
from pathlib import Path
import argparse
from typing import IO
import json
import pprint as pp


class PAK():
    PAK_Head = np.dtype([
        ("magic", "S4"),
        ("unknown0", np.uint32),
        ("unknown1", np.uint32),
        ("fileCount", np.uint32)  # 这个数值是有意义的偏移值和占位0的uint32数总个数
    ])

    def __init__(self, pakFilePath: Path):
        self.pakFilePath = pakFilePath
        self.pakFile: IO[bytes] = None

        # 例如MS7、KOF Rev A里就出现了偏移表中有0占位的情况
        self.offsetList = []
        self.offsetListPadding = False  # 偏移表是否对齐到0x10

        # fileCount包括占位0，所以也引入“_real”版作辅助
        (self.fileCount, self.fileCount_real) = (0, 0)

        self.magic = ""
        (self.unknown0, self.unknown1) = (0, 0)

        # 这里引入“_real”主要是因为对于一些末尾有0x00的文件，pak直接截断，导致总包大小 < 偏移表中的理论值
        (self.fileLen, self.fileLen_real) = (0, 0)

        # self.subFilePathList = []

        self.subFileMetaList = dict()  # 对subFilePathList、offsetList的综合

    def __offsetListPadding_check__(self) -> bool:
        """
        检查偏移表后是否有填充
        原理：读完pak头和偏移表后的文件指针t，偏移表中第一个非0值o
        若t == o，则没有填充
        所以这个函数只能在读完偏移表与pak包总长后立刻使用
        """
        for o in self.offsetList:
            if (o):
                return o != self.pakFile.tell()

    def read_head(self):
        self.pakFile = open(self.pakFilePath, "rb")

        head_bin = np.fromfile(self.pakFile, dtype=self.PAK_Head, count=1)[0]
        self.magic = head_bin["magic"].decode("utf-8")
        self.unknown0 = int(head_bin["unknown0"])
        self.unknown1 = int(head_bin["unknown1"])
        self.fileCount = int(head_bin["fileCount"])

        self.offsetList = np.fromfile(
            self.pakFile, dtype=np.uint32, count=self.fileCount).tolist()

        # 0项也在索引号内([a, 0, b, ...], index = 0, 1, 2, ...)。这样编real表既保留原始索引又去除0偏移项
        for i in range(self.fileCount):
            if (self.offsetList[i]):
                # self.offsetList_real.append(self.offsetList[i])
                self.subFileMetaList[i] = {
                    "offset": self.offsetList[i],
                    "subFilePath": "{0:s}_{1:03n}".format(self.pakFilePath.stem, i)
                }
        self.fileCount_real = len(self.subFileMetaList)

        self.fileLen = int(np.fromfile(
            self.pakFile, dtype=np.uint32, count=1)[0])
        self.fileLen_real = self.pakFilePath.stat().st_size

        self.offsetListPadding = self.__offsetListPadding_check__()

    def get_meta_dict(self) -> dict:
        return {
            "magic": self.magic,
            "unknown0": self.unknown0,
            "unknown1": self.unknown1,
            "fileCount": self.fileCount,
            "fileCount_real": self.fileCount_real,

            # "offsetList": self.offsetList,
            # "offsetList_real": self.offsetList_real,

            "fileLen": self.fileLen,
            "fileLen_real": self.fileLen_real,

            "offsetListPadding": self.offsetListPadding,
            # "subFilePathList": self.subFilePathList
            "subFileMetaList": self.subFileMetaList
        }

    def extract_subFile(self, outDir: Path):
        # offsetList_temp = self.offsetList + [min(self.fileLen, self.fileLen_real)]
        subFileMetaList_temp = sorted(self.subFileMetaList.items())
        subFileMetaList_temp.append(
            (-1, {"offset": min(self.fileLen, self.fileLen_real)})
        )

        for i in range(len(subFileMetaList_temp) - 1):
            (start, end) = (
                subFileMetaList_temp[i][-1]["offset"], subFileMetaList_temp[i + 1][-1]["offset"])
            subFilePath = outDir / subFileMetaList_temp[i][-1]["subFilePath"]

            self.pakFile.seek(start, 0)
            outFile = open(subFilePath, "wb")
            outFile.write(self.pakFile.read(end - start))
            outFile.close()

    def save_mata_json(self, outDir: Path):
        jsonFilePath = outDir / "{0:s}.json".format(self.pakFilePath.stem)
        jsonFile = open(jsonFilePath, "wt")
        json.dump(self.get_meta_dict(), jsonFile,
                  ensure_ascii=False, indent='\t')
        jsonFile.close()

    def load_meta_json(self, inJsonPath: Path):
        jsonFile = open(inJsonPath, "rt")
        d_dict = json.load(jsonFile)
        jsonFile.close()

        # 这部分是可以直接抄的
        self.magic = d_dict["magic"]
        self.unknown0 = d_dict["unknown0"]
        self.unknown1 = d_dict["unknown1"]
        self.fileCount = d_dict["fileCount"]

        self.offsetListPadding = d_dict["offsetListPadding"]

        # 这部分的需要随实际文件更新
        self.subFileMetaList = {int(k): v for (  # json无法以纯数字为键，会自动转为str
            k, v) in d_dict["subFileMetaList"].items()}
        # self.fileCount = max(self.subFileMetaList.keys()) + 1
        self.fileCount_real = len(self.subFileMetaList)

        inDir = inJsonPath.parent
        p = self.PAK_Head.itemsize + 4 * self.fileCount + 4 * 1  # 假设的文件指针
        # 头长 + 偏移表长 + 文件总长
        if (self.offsetListPadding):
            while (p % 0x10 != 0):
                p += 4
        subFileMetaList_temp = sorted(self.subFileMetaList.items())
        for (index, subFile) in subFileMetaList_temp:
            subFile["offset"] = p

            p += (inDir / subFile["subFilePath"]).stat().st_size

        (self.fileLen, self.fileLen_real) = (p, p)

    def build_pakfile(self, inJsonPath: Path):
        self.pakFile = open(self.pakFilePath, "wb")

        # 写头
        head_bin = np.zeros(1, dtype=self.PAK_Head)[0]
        head_bin["magic"] = self.magic
        head_bin["unknown0"] = self.unknown0
        head_bin["unknown1"] = self.unknown1
        head_bin["fileCount"] = self.fileCount
        head_bin.tofile(self.pakFile)

        # 构造带空隙的偏移表，并写入
        offsetList_bin = np.zeros(self.fileCount, dtype=np.uint32)
        for (index, subFile) in self.subFileMetaList.items():
            offsetList_bin[index] = subFile["offset"]
        offsetList_bin.tofile(self.pakFile)

        np.uint32(self.fileLen).tofile(self.pakFile)  # 写文件总长值

        if (self.offsetListPadding):  # 填充0
            while (self.pakFile.tell() % 0x10 != 0):
                np.uint32(0).tofile(self.pakFile)

        # 装入文件内容
        inDir = inJsonPath.parent
        subFileMetaList_temp = sorted(self.subFileMetaList.items())
        for (index, subFile) in subFileMetaList_temp:
            subFile2 = open(inDir / subFile["subFilePath"], "rb")
            self.pakFile.write(subFile2.read())
            subFile2.close()

    def close(self):
        self.pakFile.close()


def main():
    cmdParser = argparse.ArgumentParser(
        description="一款支持 解包、罗列、打包 Metal Slug 3D、6、7中出现的.pak特有打包格式文件 的工具。")
    cmdParser.add_argument("-C", "--directory", help="改变至指定目录",
                           required=False, type=Path, dest="directory", default=Path("./"))
    cmdParser.add_argument(
        "-f", "--file", help="操作目标PAK ARCHIVE文件", required=True, type=Path)
    cmdParser.add_argument("-c", "--create", help="创建一个新归档(此模式下-C无效)", required=False,
                           action="store_const", const='c', dest="create", default=None)
    cmdParser.add_argument("-x", "--extract", help="创建一个新归档", required=False,
                           action="store_const", const='x', dest="extract", default=None)
    cmdParser.add_argument("-t", "--list", help="列出归档内容", required=False,
                           action="store_const", const='t', dest="list", default=None)
    cmdParser.add_argument("-T", "--files-from", help="构建pak包所用索引json文件(-c模式专用)",
                           type=Path, default=None, dest="inJsonPath", required=False)

    args = cmdParser.parse_args()
    print(args)

    mode = tuple(m for m in (args.create, args.extract, args.list) if (m))
    if (len(mode) != 1):
        raise Exception("-t -c -x能且只能存在其中之一")
    else:
        mode = mode[0]

    pak = PAK(args.file)
    match (mode):
        case 'c':
            if (args.inJsonPath is None):
                raise ValueError("-c模式下，必须引入一个索引文件")
            pak.load_meta_json(args.inJsonPath)
            pak.build_pakfile(args.inJsonPath)
        case 'x':
            pak.read_head()
            pak.extract_subFile(args.directory)
            pak.save_mata_json(args.directory)
        case 't':
            pak.read_head()
            pp.pprint(pak.get_meta_dict())

    pak.close()


if (__name__ == "__main__"):
    sys.exit(main())
