# 项目内部资产格式

资产按目录管理，不使用来源记录或全局清单。岩石按集合分组，启动时递归、排序扫描 `.blend` 文件。

## 从 ReSyRIS 导入

这里导入的是 ReSyRIS 的三维岩石模型和地表贴图，用于重新生成场景。准备以下目录结构，其中 `/path/to/resyris` 表示 ReSyRIS 根目录：

```text
/path/to/resyris/
├── stone_models/
│   ├── 01/
│   │   ├── texturedMesh.obj
│   │   ├── texturedMesh.mtl
│   │   └── texture_1001.png
│   ├── 02/
│   └── ...                 # 36 个岩石目录
└── oaisys/
    └── volcano/
        ├── volcano_diff_4k.png
        ├── volcano_nor_dx_4k.png
        └── volcano_disp_4k.png
```

保留 OBJ 对应的 MTL 和贴图文件，使模型导入时可以正确找到材质。目录中同时存在 OBJ 和 BLEND 时，工具优先使用 OBJ。

在 `rock-synth` 仓库根目录执行，将两个占位路径替换为实际目录；Blender 安装目录中应包含 `blender` 可执行文件：

```bash
/path/to/blender/blender --background \
  --python scripts/import_assets.py -- \
  --rocks /path/to/resyris/stone_models --collection resyris \
  --surface /path/to/resyris/oaisys/volcano
```

`--rocks` 指定原始岩石目录，`--collection resyris` 指定项目内部的集合名称，`--surface` 指定一套地表贴图。两类资产也可以分别导入，单独保留 `--rocks ... --collection resyris` 或 `--surface ...` 即可。路径含空格时请使用引号。

工具规范化模型并内嵌贴图，将地表复制为标准通道名，翻转 DirectX 法线的绿色通道以转换为 OpenGL。原始目录保持不变，已有目标文件或地表目录不会被覆盖。导入结果如下，之后生成无需访问 ReSyRIS 原目录：

```text
assets/
├── rocks/
│   └── resyris/
│       ├── 01.blend
│       ├── 02.blend
│       └── ...            # 共 36 个岩石文件
└── surfaces/
    └── volcano/
        ├── basecolor.png
        ├── normal.png
        └── displacement.png
```

## 岩石

每个 `.blend` 文件是一块岩石，包含且仅包含一个名为 `rock` 的网格对象：

- Z-up，包围盒中心为原点，最长边规范化为 1，位置旋转为零、缩放为一。
- 保留 UV、材质；图像依赖打包进 blend，移动目录后仍可加载。
- 无相机、灯光、LOD、collider；碰撞凸包由生成时建立。
- 实际米制尺寸由 `rocks.diameter` 指定，不依赖原扫描单位。
- 不要求闭合网格，不输出精确体积或表面积。

导入工具接受根目录下的一层岩石子目录；每个子目录放一个源模型和所需材质贴图。优先读取 OBJ，然后 GLB、GLTF、BLEND。同种格式存在多个模型时报错。源模型应已经是单块岩石、Z-up；工具合并多个组成网格，不猜测哪个对象是 LOD。

```bash
blender --background --python scripts/import_assets.py -- \
  --rocks /path/to/raw_rocks --collection my_rocks
```

导入结果为 `assets/rocks/my_rocks/<原子目录名>.blend`。不指定 `--collection` 时使用原始根目录名。已有文件时报错，不自动覆盖；不生成 `source.json`。不同集合可使用相同文件名。配置 `rocks.directory` 可以指向所有集合的根目录，也可以只指向一个集合。

## 地表

每个子目录使用固定通道名，支持 PNG、JPG、JPEG、EXR、TIF、TIFF：

| 文件名（扩展名可不同） | 要求 |
|---|---|
| `basecolor.png` | 必需，sRGB |
| `roughness.png` | 可选，Non-Color；缺失时使用高粗糙度的细微随机变化 |
| `normal.png` | 可选，Non-Color，OpenGL (+Y) 切线空间 |
| `displacement.png` | 可选，Non-Color；用于细微几何位移及 bump |

`terrain.texture_size` 控制一张贴图覆盖的实际边长，默认 4 米。每个场景对整套 UV 做一致的旋转和平移，使颜色、切线法线与几何高度保持对齐。位移贴图按原始数值读取、使用稳健范围归一化后，参与厘米级地形起伏；更细的纹理通过法线与 bump 表现。地形网格在默认 20 米边长下间距约 5 厘米，最大分辨率为 513×513。渲染与物理碰撞共用该网格，最终总高度由 `terrain.relief` 限制；`relief: 0` 禁用几何起伏，但保留材质凹凸。

```bash
blender --background --python scripts/import_assets.py -- --surface /path/to/volcano
```

工具识别 `basecolor/diff/color`、`roughness/rough`、`normal/nor_`、`displacement/disp/height`；同一通道匹配多图时报错。文件名包含 `_dx` 或 `directx` 的法线会翻转绿色通道，其余应已经是 OpenGL。

当前岩石集合为 `resyris`，地表为 `volcano`。岩石的贴图内嵌在 `.blend` 中，地表贴图为项目内的普通文件；没有项目外部文件依赖，也不附带来源记录。

导入产物不进入 Git；搬迁项目时应一并复制 `assets/rocks` 和 `assets/surfaces`，或重新导入。
