# RockSynth

当前版本：`0.1.2`，变更见 [更新记录](CHANGELOG.md)。

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
- `rocks.placement_radius` 为岩石摆放圆形区域的半径（米），默认 3.5。它独立于地面尺寸，扩大 `terrain.size` 不会把岩石分布一起扩大。岩石按面积均匀摆放，再通过刚体沉降落地；岩石放置数量不等于每张图可见数量。
- 默认地面为 20×20 米，固定相机以 50° 水平视场角俯拍中心区域，减少地表边界进入画面。
- `terrain.relief` 为相对零平面的最大绝对高度，包含大尺度起伏与细小颗粒；设为 0 时几何地面保持平坦。渲染与物理使用同一份地形网格。
- `terrain.texture_size` 为一张地表贴图覆盖的边长（米），默认 4。每个场景随机旋转、平移整套纹理，颜色、法线与位移保持对齐。
- `lighting.random: false` 使用固定侧上方太阳光，适合比较材质；开启时在有限角度和强度范围内随机。天空带有低强度环境底色，避免地平线以下纯黑。
- 未填写字段使用内部默认值；未知字段报错。配置相对路径统一相对仓库根目录。
- 每场景使用 `seed + 场景序号`。输出目录必须为空，避免混入或覆盖已有数据。

输出格式通过 `output.format` 选择，目前仅支持 `yolo`。不生成 `samples.jsonl`；`output.save_config` 控制是否保存 `config.yaml`，默认 `true`。`output.metadata.asset_id` 控制是否记录每个已导出实例对应的岩石资产，默认 `false`；开启时额外保存 `metadata/<图片ID>.json`，包含 `image_id` 和 `instances`，每个实例记录 `instance_id` 与 `asset_id`（例如 `resyris/01`）。

例如，100 个场景按 80% / 10% / 10% 分为训练、验证、测试集：

```yaml
num_scenes: 100
output:
  directory: output/dataset
  resolution: [640, 480]
  format: yolo
  save_config: false
  metadata:
    asset_id: false
  yolo:
    split:
      train: 0.8
      val: 0.1
      test: 0.1
```

划分按场景进行，同一场景的全部视角始终在同一集合中。比例须非负、总和为 1，设为 0 可禁用对应集合；省略 split 时仅导出 train。仓库的 `configs/default.yaml` 示例配置为 2 个场景、train/val 各 50%，每个集合得到 1 个场景、3 张图。场景数按最大余数法取整，并使用 `seed` 打乱归属，确保可复现；如果某个非零比例的集合分不到场景，会在渲染前报错。

划分使用独立随机数生成器，不扰动场景生成。相同 seed、场景数量和比例得到相同划分；修改共用的 `seed` 会同时改变划分归属和合成场景内容。

输出为 `images/{train,val,test}/*.png`、`labels/{train,val,test}/*.txt` 和 `data.yaml`，只创建启用的集合。图片命名为 `场景ID-视角ID`，见 [输出格式](docs/output-schema.md)。需要训练验证时请启用 val 划分，或另外指定真实验证集。不默认输出 HDF5、深度、物理属性或 mask 文件。

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
