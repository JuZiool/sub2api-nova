# Sub2API Nova 项目协作规则

## Git 提交与推送

- 每完成一组独立的代码、配置或部署文件修改后，必须创建一次 Git commit。
- commit 标题和正文必须使用中文，准确说明本次操作实际处理了什么。
- 禁止使用 `update`、`changes`、`misc`、`fix stuff` 等无法说明内容的笼统提交信息。
- 推荐使用以下中文类型作为标题开头：`功能：`、`修复：`、`重构：`、`样式：`、`配置：`、`文档：`、`测试：`。
- 提交正文应在需要时补充以下内容：修改范围、保留或兼容的现有功能、验证方式及验证结果。
- 提交前运行 `git diff --check`。
- 不要把无关修改、环境变量、密钥、运行数据、依赖缓存或构建产物混入提交。
- 不要为了提交而创建空 commit；没有实际改动时不创建提交。
- 代码修改完成并通过提交前检查后，必须推送到当前远程分支，等待 GitHub Actions 完成镜像打包。
- 禁止使用强制推送覆盖远程历史，除非用户明确要求并确认目标分支。

## 镜像构建与本地部署验证

- 改完代码后，先按中文规范创建 commit 并推送到当前远程分支。
- 推送后等待 GitHub Actions 将项目打包为 GitHub Container Registry（GHCR）镜像；不得直接使用本地源码构建镜像代替该流程。
- GitHub 镜像打包完成后，使用 GitHub 打包好的镜像进行本地 Docker 容器部署验证。
- 本地部署应使用项目既有的 Compose 配置，并通过 `SUB2API_IMAGE` 指定对应的 GHCR 镜像版本或提交 SHA 标签，例如：

  `cd deploy && docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml pull sub2api && docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml up -d`

- 如果构建、拉取、启动、健康检查或功能验证发现问题，继续修改代码，重新执行中文提交、推送、等待镜像打包和本地部署流程，直到问题解决或明确无法继续。
- 部署和健康检查没有问题后，告知用户部署状态和访问地址，由用户进行页面与功能测试；除非用户另有要求，不代替用户做最终界面验收。

## 提交示例

```text
样式：重做管理员账户列表页面

- 调整账户列表布局和筛选区域
- 保留二开项目现有账户管理功能
- 验证：推送后等待 GitHub 镜像打包，并使用 GHCR 镜像完成本地 Docker 部署验证
```
