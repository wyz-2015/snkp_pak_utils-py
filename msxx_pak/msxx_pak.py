#!/usr/bin/env python3

import sys
import numpy as np
import shutil
import argparse
from pathlib import Path
from typing import IO
import json
import pprint as pp

import builtin_str as bs


class PAK():
    Struct_Head = np.dtype([
        ("reversed", np.uint32, (3,)),
        ("fileCount", np.uint32)
    ])

    Struct_SubFile_Menu = np.dtype([
        ("type", np.uint32),
        ("index", np.uint32),
        ("offset", np.uint32),
        ("size", np.uint32)
    ])

    Typename = {
        0x01: "cmp",
        0x02: "anm",
        0x03: "frm",
        0x04: "chr",
        0x05: ["obj_pal.bin", "obj_pal01.dat", "obj_palxx.dat", "obj_pal05.dat"],
        0x06: "ms4_data.bin",
        0x07: "ms4_scrl.bin",
        0x08: "fix_tex.bin",
        0x09: "sebank",
        0x0a: "voice.acx",
        0x0b: ["MS7", "Atr.bin"],
        0x0c: "eset",
        0x0d: "eset_sur",
        0x0e: "es2p",
        0x0f: ["map", "Hinf.bin"],
        0x10: ["map", "Htbl.bin"],
        0x11: "tex",
        0x12: "pal",
        0x13: "over"

    }

    def __init__(self, pakPath: Path):
        self.pakPath = pakPath

        self.pak: IO[bytes] = None

        self.fileCount = 0
        self.reversed = []

        self.subFileList = []

        # (0, 0)为COMMON，其余按PAK名的"%d%d" % (mission, stage)
        (self.mission, self.stage) = (None, None)

    ###############################
    # read

    def __split_mission_stage__(self, src: str) -> tuple(int, int):
        """
        将“MS7MSTxxyy”形式的字符串剥离成(mission = xx, stage = yy)的形式
        """
        src = src.removeprefix("MS7MST")

        return (int(src[0:2]), int(src[2:4]))

    def __get_subFile_name__(self, subFile_bin: np.void) -> str:
        (_type, index) = (int(subFile_bin["type"]), int(subFile_bin["index"]))
        name = ""

        if (self.Typename.get(_type, None)):
            if (0x01 <= _type <= 0x04):
                return "{0:s}_{1:s}.bin".format(
                    self.Typename[_type],
                    bs.unitList[index]
                )

            elif (_type == 0x05):
                if (0 <= index < 4):
                    return self.Typename[_type][index]

            elif (0x06 <= _type <= 0x08):
                return self.Typename[_type]

            elif (_type == 0x09):
                return "{0:s}{1:n}.acx".format(self.Typename[_type], index)

            elif (_type == 0x0a):
                return self.Typename[_type]

            elif (_type == 0x0b):
                if ((self.mission, self.stage) != (0, 0)):
                    return "{0:s}_{1:02n}{2:02n}_{3:s}".format(
                        self.Typename[_type][0],
                        self.mission,
                        self.stage,
                        self.Typename[_type][-1]
                    )

            elif (0x0c <= _type <= 0x0e):
                if ((self.mission, self.stage) != (0, 0)):
                    return "{0:s}_{1:02n}{2:02n}.bin".format(
                        self.Typename[_type],
                        self.mission,
                        self.stage
                    )

            elif (0x0f <= _type <= 0x10):
                if ((self.mission, self.stage) != (0, 0)):
                    subTypeList = "CBA"
                    return "{0:s}_{1:s}{2:s}{3:s}".format(
                        self.Typename[_type][0],
                        self.pakPath.stem,
                        (subTypeList[index] if (0 <= index < 3)
                         else "{0:02n}".format(index)),
                        self.Typename[_type][-1]
                    )

            elif (0x11 <= _type <= 0x12):
                if ((self.mission, self.stage) != (0, 0)):
                    return "{0:s}.{1:s}".format(
                        self.pakPath.stem,
                        self.Typename[_type]
                    )

            elif (_type == 0x13):
                if (0 < self.mission <= 7):
                    return "{0:s}{1:02n}.bin".format(
                        self.Typename[_type],
                        (self.mission - 1)
                    )

            # 0x14开始是借用区，这里私自作一个命名改动：文件名前加一个'_'，和MS6的SE命名倒是类似
            elif (_type == 0x14):  # 0x07
                (_mission, _stage) = self.__split_mission_stage__(
                    bs.stageCloneDict[bs.stageList[17]])
                return "_{0:s}_{1:02n}{2:02n}_{3:s}".format(
                    self.Typename[0x0b][0],
                    _mission,
                    _stage,
                    self.Typename[0x0b][-1]
                )

            elif (_type == 0x15):  # 0x0f
                if ((self.mission, self.stage) != (0, 0)):
                    subTypeList = "CBA"
                    return "_{0:s}_{1:s}{2:s}{3:s}".format(
                           self.Typename[0x0f][0],
                           bs.stageCloneDict[self.pakPath.stem],
                           subTypeList[index],
                           self.Typename[0x0f][-1],
                    )

            elif (_type == 0x16):  # 0x10
                if ((self.mission, self.stage) != (0, 0)):
                    subTypeList = "CBA"
                    return "_{0:s}_{1:s}{2:s}{3:s}".format(
                           self.Typename[0x0f][0],
                           bs.stageCloneDict[self.pakPath.stem],
                           subTypeList[index],
                           self.Typename[0x10][-1],
                    )

            elif (_type == 0x17):  # 0x11
                if ((self.mission, self.stage) != (0, 0)):
                    return "_{0:s}.{1:s}".format(
                        bs.stageCloneDict[self.pakPath.stem],
                        self.Typename[0x11]
                    )

            elif (_type == 0x18):  # 0x12
                if ((self.mission, self.stage) != (0, 0)):
                    return "_{0:s}.{1:s}".format(
                        bs.stageCloneDict[self.pakPath.stem],
                        self.Typename[0x12]
                    )

        # 兜底分支，当上面的分支一个都没return时
        return "{0:s}_{1:02x}_{2:02x}".format(self.pakPath.stem, _type, index)

    def read_head(self):
        # 根据文件名推测(mission, stage)
        if (self.pakPath.name == "COMMON.PAK"):
            (self.mission, self.stage) = (0, 0)
        else:
            (self.mission, self.stage) = self.__split_mission_stage__(
                self.pakPath.stem)

        head_bin = np.fromfile(self.pak, dtype=self.Struct_Head, count=1)[0]
        self.reversed = head_bin["reversed"].tolist()
        self.fileCount = int(head_bin["fileCount"])

        subFileArray = np.fromfile(
            self.pak, dtype=self.Struct_SubFile_Menu, count=self.fileCount)
        for subFile_bin in subFileArray:
            self.subFileList.append({
                "type": int(subFile_bin["type"]),
                "index": int(subFile_bin["index"]),
                "offset": int(subFile_bin["offset"]),
                "size": int(subFile_bin["size"]),
                "name": self.__get_subFile_name__(subFile_bin)
            })
        # pp.pprint(self.subFileList)

    def extract_file(self, outDir: Path):
        for subFile in self.subFileList:
            binFilePath = outDir / subFile["name"]
            binFile = open(binFilePath, "wb")

            self.pak.seek(subFile["offset"], 0)
            binFile.write(self.pak.read(subFile["size"]))

            binFile.close()

    def __get_metaDict__(self) -> dict:
        metaDict = dict()

        metaDict["fileCount"] = self.fileCount
        metaDict["reversed"] = self.reversed

        metaDict["mission"] = self.mission
        metaDict["stage"] = self.stage

        metaDict["subFileList"] = self.subFileList

        return metaDict

    def save_metadata(self, outDir: Path):
        jsonFilePath = outDir / "{0:s}.json".format(self.pakPath.stem)
        jsonFile = open(jsonFilePath, "wt")
        json.dump(self.__get_metaDict__(), jsonFile,
                  ensure_ascii=False, indent='\t')
        jsonFile.close()

    def read(self, outDir: Path):
        self.pak = open(self.pakPath, "rb")
        self.read_head()
        self.extract_file(outDir)
        self.save_metadata(outDir)

    def list(self):
        self.pak = open(self.pakPath, "rb")
        self.read_head()

        pp.pprint(self.__get_metaDict__())

    ######################################
    # write

    def load_meta_json(self, inMetaJsonPath: Path) -> int:
        """
        最后返回的数为将要构建的PAK文件的总长
        """
        jsonFile = open(inMetaJsonPath, "rt")
        d_dict = json.load(jsonFile)
        jsonFile.close()

        self.reversed = d_dict["reversed"]

        # 更新文件数
        self.fileCount = len(d_dict["subFileList"])
        if (self.fileCount != d_dict["fileCount"]):
            print("发现元数据列表中有{0:n}条记录，与声称数据{1:n}不符，以实际为准".format(
                self.fileCount, d_dict["fileCount"]))

        # 更新各子文件实际大小
        self.subFileList = d_dict["subFileList"]
        inDir = inMetaJsonPath.parent
        for subFile in self.subFileList:
            subFile_path = inDir / subFile["name"]

            size_real = subFile_path.stat().st_size
            if (size_real != subFile["size"]):
                print("文件{0}的实际大小{1:n} B，与记载大小{2:n} B不符，以实际为准".format(
                    subFile_path, size_real, subFile["size"]))
            subFile["size"] = size_real

        # 重算各文件偏移
        p = self.Struct_Head.itemsize + self.fileCount * \
            self.Struct_SubFile_Menu.itemsize  # 虚设偏移

        for subFile in self.subFileList:
            subFile["offset"] = p

            p += subFile["size"]

            while (p % 0x10 != 0):  # 强制0x10 B对齐
                p += 1

        return p

    def build_file(self, inMetaJsonPath: Path, pakLen: int):
        np.zeros(pakLen, dtype=np.uint8).tofile(self.pak)  # 先全部填0，再写入内容

        self.pak.seek(0, 0)

        head_bin = np.zeros(1, dtype=self.Struct_Head)[0]
        head_bin["fileCount"] = self.fileCount
        head_bin["reversed"] = self.reversed

        head_bin.tofile(self.pak)

        for subFile in self.subFileList:
            subFile_bin = np.zeros(1, dtype=self.Struct_SubFile_Menu)[0]

            subFile_bin["type"] = subFile["type"]
            subFile_bin["index"] = subFile["index"]
            subFile_bin["offset"] = subFile["offset"]
            subFile_bin["size"] = subFile["size"]

            subFile_bin.tofile(self.pak)

        inDir = inMetaJsonPath.parent
        for subFile in self.subFileList:
            self.pak.seek(subFile["offset"], 0)

            binFile = open(inDir / subFile["name"], "rb")
            shutil.copyfileobj(binFile, self.pak)
            binFile.close()

    def write(self, inMetaJsonPath: Path):
        self.pak = open(self.pakPath, "wb+")
        pakLen = self.load_meta_json(inMetaJsonPath)
        self.build_file(inMetaJsonPath, pakLen)

    def clear(self):
        self.pak.close()


def main():
    cmdParser = argparse.ArgumentParser(
        description="一款支持 解包、罗列、打包 Metal Slug XX (PSP)中出现的.pak特有打包格式文件 的工具。")
    cmdParser.add_argument("-C", "--directory", help="输出文件至指定目录(-x模式专用)",
                           type=Path, required=False, default=Path("./"), dest="dir")
    cmdParser.add_argument("-f", "--file", help="指定文件",
                           type=Path, required=True, dest="pakPath")
    cmdParser.add_argument("-c", "--create", help="创建一个新归档(此模式下必须配合-T选项)",
                           required=False, action="store_const", const='c', dest="create", default=None)
    cmdParser.add_argument("-x", "--extract", help="从归档中解出文件",
                           required=False, action="store_const", const='x', dest="extract", default=None)
    cmdParser.add_argument("-t", "--list", help="列出归档内容",
                           required=False, action="store_const", const='t', dest="list", default=None)
    cmdParser.add_argument("-T", "--files-from", help="构建pak包所用索引json文件(-c模式专用)",
                           required=False, type=Path, default=None, dest="inMetaJsonPath")

    args = cmdParser.parse_args()
    print(args)

    mode = tuple(m for m in (args.extract, args.create, args.list) if (m))
    if (len(mode) != 1):
        raise Exception("-t -c -x能且只能存在其中之一")
    else:
        mode = mode[0]

    pak = PAK(args.pakPath)
    match (mode):
        case 'x':
            pak.read(args.dir)
        case 't':
            pak.list()
        case 'c':
            pak.write(args.inMetaJsonPath)

    pak.clear()


if (__name__ == "__main__"):
    sys.exit(main())
