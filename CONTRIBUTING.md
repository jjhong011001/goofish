# 贡献指南

感谢你对本项目的关注！我们欢迎任何形式的贡献。

## 如何贡献

### 报告 Bug

如果你发现了 bug，请创建一个 Issue 并包含以下信息：

- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（操作系统、Python 版本等）
- 相关日志或截图

### 提出新功能

如果你有新功能建议：

1. 先检查 Issues 中是否已有类似建议
2. 创建新 Issue 描述功能需求和使用场景
3. 等待维护者反馈后再开始开发

### 提交代码

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的修改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8 Python 代码风格
- 添加必要的注释和文档字符串
- 保持代码简洁易读
- 确保现有测试通过

### 提交信息规范

使用清晰的提交信息：

- `feat: 添加新功能`
- `fix: 修复 bug`
- `docs: 更新文档`
- `style: 代码格式调整`
- `refactor: 代码重构`
- `test: 添加测试`
- `chore: 构建或辅助工具变动`

## 开发环境设置

```bash
# 克隆你的 fork
git clone https://github.com/Ray-Yuan21/xianyu-price-tracker.git
cd xianyu-price-tracker

# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 运行测试
python main.py login
python main.py search "测试" --pages 1
```

## 问题讨论

如有任何疑问，欢迎在 Issues 中讨论。

再次感谢你的贡献！
