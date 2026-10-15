# RockSynth

当前版本：`0.1.0`。

轻量的岩石实例分割合成数据工具。使用 BlenderProc 创建场景，同一场景从配置中的多个位置拍摄，直接保存 RGB 和 YOLO segmentation 标签。

## 环境

```bash
conda env create -f environment.yml
conda activate rock-synth
```

已有环境更新依赖：`python -m pip install -e '.[dev]'`。运行生成脚本必须使用 `blenderproc run`。

BlenderProc 使用独立 Python，还需为它安装导出依赖。将 `/path/to/blender` 替换为 Blender 安装目录（包含 `blender` 可执行文件）：

```bash
blenderproc pip --custom-blender-path /path/to/blender \
  install PyYAML 'Pillow>=10' 'opencv-python-headless>=4.8,<4.12'
```

## 导入 ReSyRIS 资产

准备好 ReSyRIS 目录后，在 `rock-synth` 仓库根目录执行以下命令。将 `/path/to/resyris` 替换为 ReSyRIS 根目录，`/path/to/blender` 替换为 Blender 安装目录：

```bash
/path/to/blender/blender --background \
  --python scripts/import_assets.py -- \
  --rocks /path/to/resyris/stone_models --collection resyris \
  --surface /path/to/resyris/oaisys/volcano
```

导入后，36 块岩石位于 `assets/rocks/resyris/`，地表位于 `assets/surfaces/volcano/`。原始文件不修改；目标已存在时会报错，不会覆盖。

岩石统一为单网格、中心原点、最长边为 1、贴图内嵌的 `.blend`，例如 `assets/rocks/resyris/01.blend`；实际生成尺寸由配置决定。地表贴图统一命名，DirectX 法线转换为 OpenGL。详细输入目录结构与后续其他资产的导入方式见 [ReSyRIS 导入说明与资产格式](docs/assets.md)。无需来源记录、manifest、lock 或数据库。

## 生成

```bash
blenderproc run --custom-blender-path /path/to/blender \
  generate.py --config configs/default.yaml --output output/example
```

`configs/default.yaml` 控制场景数量、岩石尺寸、地形、光照及相机。

- `num_scenes: 10` 与 3 个 `camera.poses` 产生 30 张图；相机不随机采样、不进行可见性筛选。
- `position` 和 `look_at` 均为绝对世界 XYZ（米），Z 向上；`camera.fov` 为水平视场角（度）。
- `rocks.count`、`rocks.diameter` 接受固定值或 `[min, max]`。尺寸为岩石旋转前水平最大边长（米），按对数均匀分布采样。
- 岩石在地形中心圆形区域按面积均匀摆放，再通过刚体沉降落地。场景岩石数量不等于每张图可见数量。
- `terrain.relief` 为相对零平面的最大绝对高度。地表每 2 米重复一次贴图；`lighting.random: false` 使用固定太阳与天空。
- 未填写字段使用内部默认值；未知字段报错。配置相对路径统一相对仓库根目录。
- 每场景使用 `seed + 场景序号`。输出目录必须为空，避免混入或覆盖已有数据。

输出为 `images/train/*.png`、`labels/train/*.txt`、`data.yaml`、配置快照及简短生成记录。图片命名为 `场景ID-视角ID`，见 [输出格式](docs/output-schema.md)。不默认输出 HDF5、深度、物理属性或 mask 文件。

同一场景的视角应始终放在同一数据划分，避免训练/验证泄漏。默认仅导出 train；请使用独立场景或真实数据作为验证集，并在训练配置中设置 `val`。

## 代码结构

```text
generate.py                 配置、场景循环、保存
src/rocksynth/
  config.py                 默认值与配置校验
  assets.py                 资产目录扫描
  scene.py                  岩石摆放、物理沉降、光照
  terrain.py                高度场、地形与地表材质
  camera.py                 position + look_at
  render.py                 RGB 与实例 ID 渲染
  export.py                 YOLO polygon 与图片保存
scripts/import_assets.py    一次性资产规范化
```

Blender 图形调试使用 `blenderproc debug generate.py`。不提供独立的输出检查脚本。

## 测试

```bash
pytest -q
ruff check .
```
