# YOLO segmentation 输出

```text
dataset/
├── images/
│   ├── train/0000-0000.png
│   ├── val/...
│   └── test/...
├── labels/
│   ├── train/0000-0000.txt
│   ├── val/...
│   └── test/...
├── metadata/               # 可选，output.metadata.asset_id: true 时保存
│   ├── 0000-0000.json
│   └── ...
├── data.yaml
└── config.yaml             # 可选，output.save_config: true 时保存
```

`0000-0000` 表示零起始场景序号和视角序号。同一场景的岩石与光照固定，只改变配置中的相机位姿。总图片数为 `num_scenes × camera.poses 数量`。

## 配置与划分

```yaml
num_scenes: 100
output:
  directory: output/dataset
  resolution: [640, 480]
  format: yolo
  save_config: true
  metadata:
    asset_id: false
  yolo:
    split:
      train: 0.8
      val: 0.1
      test: 0.1
```

- `format` 当前只接受 `yolo`，其他值报错；没有多格式导出框架。
- `save_config` 默认 `true`；设为 `false` 不生成 `config.yaml`。
- `metadata.asset_id` 默认 `false`；设为 `true` 时额外记录每个 YOLO 实例与岩石资产的对应关系，独立于 `save_config` 开关。配置键与目录名统一为 `metadata`。
- `yolo.split` 指定场景比例，各项在 0～1 之间，总和为 1。省略时使用 `{train: 1.0, val: 0.0, test: 0.0}`。仓库提供的 `configs/default.yaml` 显式设置 2 个场景和 `{train: 0.5, val: 0.5, test: 0.0}`，得到训练集、验证集各 3 张图。
- 场景数按比例分配，先向下取整，再按小数余数从大到小分配剩余场景；余数相同时按 train、val、test 顺序处理。最后使用 `seed` 打乱场景归属，不改变每个场景自身的生成 seed。
- 划分使用独立随机数生成器；相同 seed、场景数量和比例得到相同划分。修改共用的 `seed` 会同时改变划分归属和场景内容；每个场景仍使用 `seed + 场景序号`。
- 同一场景的所有视角属于同一集合，避免泄漏。100 个场景、3 个视角、80/10/10 划分得到 240/30/30 张图。
- 比例为 0 的集合不创建目录，也不写入 `data.yaml`；非零比例却分不到场景时，在创建输出、开始渲染之前报错。此时应增大 `num_scenes`、调整比例或禁用该集合。

## 标签

内部仅使用 RGB 和整数实例图：0 为地形/背景，正整数为场景内稳定岩石 ID。文件标签中所有岩石的 YOLO 类别均为 0：

```text
0 x1 y1 x2 y2 ... xn yn
```

坐标分别除以图像宽高归一化；一行对应一块可见岩石。完全遮挡的岩石不输出标签；不能形成有效多边形的极小碎片被忽略。空画面正常保存空标签，不进行可见性筛选。

同一岩石的多个可见区域通过往返的零面积连接边组成一行 polygon，避免重复实例。YOLO 单轮廓无法精确保留孔洞，导出使用外轮廓并填充孔洞。这是格式近似，不是无损 mask。轮廓简化误差上限约 1 像素。

## 实例对应的资产

开启 `output.metadata.asset_id: true` 后，每张图额外生成一个同名 JSON 文件，例如 `metadata/0000-0000.json`：

```json
{
  "image_id": "0000-0000",
  "instances": [
    {"instance_id": 3, "asset_id": "resyris/01"},
    {"instance_id": 7, "asset_id": "resyris/12"}
  ]
}
```

- `image_id`：图片文件名，不含扩展名，与 JSON 文件名一致。
- `instances`：与 YOLO `.txt` 中的标签行一一对应，顺序一致，不额外保存行号。
- `instance_id`：生成时分配的场景级岩石 ID，正整数；同一场景跨视角保持一致，不同场景可重复。它不是 YOLO 类别 ID。
- `asset_id`：相对于 `rocks.directory` 的资产路径，不含 `.blend` 后缀。例如目录为 `assets/rocks` 时得到 `resyris/01`；目录直接指向 `assets/rocks/resyris` 时得到 `01`。

同一资产可生成多个实例，所以不同 `instance_id` 可以对应相同 `asset_id`。仅记录最终导出的实例；完全遮挡或过小而无法形成有效标签的实例不记录，空标签图像对应 `"instances": []`。所有 JSON 平铺在 `metadata/` 下，不按 train/val/test 再分目录；图片 ID 在整个数据集中唯一。不修改标准 YOLO 标签，也不生成 `samples.jsonl`。

## 其他文件

`data.yaml` 声明实际输出目录、启用集合的图片路径及单一 rock 类别（ID 为 0）。如果仅导出 train，训练时需另外提供验证集路径；也可以在生成时直接启用 val 划分。

保留时，`config.yaml` 保存实际配置（包括解析后的绝对路径及 CLI 覆盖值）。不生成 `samples.jsonl`，也不保存深度、mask、完整物理属性或高度场。

遇到无效资产、摆放失败、几何穿透或文件冲突时直接报错，部分结果保留；重新运行请使用新输出目录。
