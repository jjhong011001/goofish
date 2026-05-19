# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中
- 添加更多筛选条件（价格区间、成色等）
- 支持批量关键词搜索
- 数据可视化图表
- 定时任务和监控

## [1.0.0] - 2026-03-13

### 新增
- CLI 命令行工具
  - `login` 命令：浏览器登录并保存会话
  - `search` 命令：关键词搜索和数据导出
- Web 界面
  - 实时搜索进度显示（SSE）
  - 会话状态检查
  - 在线登录和搜索
- 核心功能
  - Playwright 浏览器自动化
  - 网络请求拦截和数据提取
  - CSV/Excel 导出
  - 价格统计分析
  - 地区筛选
  - 自定义字段导出
- AI 分析功能（可选）
  - 商品描述分析
  - 价格合理性评估

### 文档
- README.md 中文文档
- CONTRIBUTING.md 贡献指南
- SECURITY.md 安全提示
- LICENSE MIT 许可证
- GitHub Issue 和 PR 模板

[Unreleased]: https://github.com/Ray-Yuan21/xianyu-price-tracker/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Ray-Yuan21/xianyu-price-tracker/releases/tag/v1.0.0
