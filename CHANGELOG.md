# 更新记录

## 0.1.1

- 调整固定俯拍机位和视场角，默认地面扩大到 20×20 米；新增 `rocks.placement_radius`，使岩石摆放范围独立于地面尺寸。
- 新增 `terrain.texture_size`，统一控制贴图物理尺度；整套纹理一致旋转和平移，加入共享几何微起伏、细颗粒凹凸及局部粗糙度变化。
- 调整太阳照明与渲染采样，天空增加低强度环境底色，改善地平线下方的纯黑背景。
- 新增 `output.format`（目前仅支持 `yolo`）、`output.save_config` 和 `output.yolo.split`；停止生成 `samples.jsonl`。
- YOLO 数据集按场景划分 train/val/test，同一场景的全部视角保持在一起；比例取整后使用 seed 确定归属，场景数不足时在渲染前报错。
- 更新配置、资产与输出文档，补充配置校验、纹理高度采样、微地形和数据划分测试。

使用说明：省略 split 时只导出 train；仓库示例配置为 2 个场景，train/val 各 50%。`save_config` 默认为 `true`。需要验证或测试集时应配置足够的场景数和对应比例。旧输出目录保持不变，新生成需使用空目录。

## 0.1.0

- 建立轻量的岩石场景生成流程：目录扫描资产、固定多视角、BlenderProc 渲染、直接导出 YOLO segmentation。
- 统一 ReSyRIS 岩石为内嵌贴图的单网格 `.blend`，地表使用标准命名贴图；移除 manifest 依赖、Spec 描述层和独立输出检查脚本。
