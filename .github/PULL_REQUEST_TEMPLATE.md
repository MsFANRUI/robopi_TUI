---
name: Pull Request
about: 提交代码变更 / Submit a code change
---

<!-- 请勾选类型 / Check the PR type -->
- [ ] 🐛 Bug fix 修复
- [ ] ✨ New feature 新功能
- [ ] 📦 Packaging 打包（debian/ 变更）
- [ ] 📝 Docs 文档
- [ ] 🔧 CI / workflow 变更

## 变更说明 / Description

<!-- 简述改了什么 / Briefly describe what this PR does -->

## 版本检查 / Version check

<!-- 如果这会影响包的版本，请确认 / Confirm if version is affected -->

- [ ] 本次变更不需要改版本号 / This change does NOT bump version
- [ ] 已更新 debian/changelog

## 测试 / Testing

- [ ] 格式检查通过 / Plugin format check passes: `python3 loader/plugin_validator.py`
- [ ] 测试通过 / Tests pass: `python3 -m unittest discover -s loader/tests -v`
- [ ] 构建通过 / Build passes: `dpkg-buildpackage -us -uc -b`
- [ ] 已在 arm64 上测试 / Tested on arm64
- [ ] 电机使能和 CAN 发帧功能仍保持锁定 / Motor enable and CAN transmission remain locked
- [ ] 其他说明 / Notes:

> ⚠️ **禁止使用 AI 生成 PR 描述。AI 生成的 PR 将被直接关闭。**
> **Do not use AI to generate PR descriptions. AI-generated PRs will be closed immediately.**
