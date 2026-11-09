# snkp\_pak\_utils-py

对[老仓库](https://github.com/wyz-2015/ms_pak_utils)的修正与Python3重制。

一组针对SNKP的Metal Slug 3D、6、7、XX、KOF MI Regulation A等多部游戏的资源文件中几种特定`PAK`打包格式的解包、打包工具，及其中出现的一种特有的被称为`PK`的文件的解码工具。 

命令行工具，交互操作设计上有意模仿`GNU tar`、`xz`或`zstd`。

## 与过去的版本相比

1. 用法更简洁。也去掉了一些没有什么意义的设计。
2. 对相关游戏资源机制的理解更进一步，因此打包解包的一些逻辑更贴近原游戏。例如`MS3D PAK`的空条目处理(这种`PAK`在MS3D里并没有，但是在MS7、KOF MI RA里有出现)机制、`MSXX PAK`解包文件命名机制，等。
3. 但是由于换用Python3编写，还依赖了`numpy`，没有纯C版本那么轻量化了。

总的来说，还是更推荐使用这个新版本。

## 致谢

礼赞Bilibili UP主[aikika](https://space.bilibili.com/3405001/)、Bilibili UP主兼群友[信标先生](https://space.bilibili.com/34243531/)。

回望过去，他们及他们的贡献已然也成了我的“万恶之源”……233

## 工具使用

## ms3d\_pak

一开始只知道这套方法能处理MS3D的`PAK`文件，后面发现MS6、7中也存在此类文件。程序名保留`ms3d_`前缀，是“以MS3D为代表”之意。

```
usage: ms3d_pak.py [-h] [-C DIRECTORY] -f FILE [-c] [-x] [-t] [-T INJSONPATH]

options:
  -h, --help            show this help message and exit
  -C, --directory DIRECTORY
                        改变至指定目录
  -f, --file FILE       操作目标PAK ARCHIVE文件
  -c, --create          创建一个新归档(此模式下-C无效)
  -x, --extract         创建一个新归档
  -t, --list            列出归档内容
  -T, --files-from INJSONPATH
                        构建pak包所用索引json文件(-c模式专用)
```

例子：(假设调用程序的指令是`./ms3d_pak.py`)

```
# 不解包，查看./pl01.pak中的各文件的序号、所在偏移、文件长
$ ./ms3d_pak.py --list -f ./pl01.pak

# 解包./pl01.pak，并将解出的文件放到目录./pl01/下
$ ./ms3d_pak.py -xf ./pl01.pak -C ./pl01

# 注意，./pl01/下将出现一个“pl01.json”，这个是记载着元数据的文件。它并不是pak中原有的文件，但是请让它和解出的文件们待在一起。

# 将“散装”的pl01/重新打包，输出为当前目录下的a.pak
$ ./ms3d_pak.py -cf ./a.pak --files-from ./pl01/pl01.json
```

### msxx\_pak

其在`msxx_pak/`下。

```
usage: msxx_pak.py [-h] [-C DIR] -f PAKPATH [-c] [-x] [-t] [-T INMETAJSONPATH]

options:
  -h, --help            show this help message and exit
  -C, --directory DIR   输出文件至指定目录(-x模式专用)
  -f, --file PAKPATH    指定文件
  -c, --create          创建一个新归档(此模式下必须配合-T选项)(重要提示：由于程序根据文件名定位所对应关卡部分，新建的归档名最好和原档名一致)
  -x, --extract         从归档中解出文件
  -t, --list            列出归档内容
  -T, --files-from INMETAJSONPATH
                        构建pak包所用索引json文件(-c模式专用)
```

例：

```
# 解包并生成列表文件：
$ mkdir ./COMMON/
$ ./msxx_pak.py -xf ./COMMON.PAK -C ./COMMON

# 打包：
$ ./msxx_pak.py -cvf another_path/COMMON.PAK --files-from ./COMMON/COMMON.json
```

### pk

```
usage: pk.py [-h] [-d] [-e] -o OUTFILEPATH [-t {0,1,2}] inFile

一款支持 解码 Metal Slug 3D、7 等SNK(P)游戏 中出现的被称为“PK”的特有单文件已编码格式文件 的工具。

positional arguments:
  inFile                传入文件路径

options:
  -h, --help            show this help message and exit
  -d, --decode          解码
  -e, --encode          编码
  -o, --out-file OUTFILEPATH
                        输出文件路径
  -t, --type {0,1,2}    强行指定编解码类型(适用于KOF MI RA等未按理论方案编码pk文件的情况)
```

例子：(假设调用程序的指令是`./pk.py`)

```
# 解压./sl02.dff.pk，输出文件命名为“sl02.dff”
$ ./pk.py -d ./sl02.dff.pk -o ./sl02.dff

# 经过调查，发现./pl1.pk虽然头部信息显示它使用02型编码，实际上却是直接保存的原始数据流(即00型)
# 那么：
$ ./pk.py -d ./pl2.pk -o ./pl2 -t 0

# 将./ddd.txt制成./d/dd.pk文件(实际上完全未压缩，因为压缩程序没有实现)
$ ./pk.py -e ./ddd.txt -o ./d/dd.pk
```

## 依赖

`python3-numpy`

## 许可证

`LGPL >= 3`

----

—— wyz\_2015
