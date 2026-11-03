# 部署：没有服务器也能拿出"能访问的地址"

> 这一章解决一个现实问题：**面试要看你部署过，但你手上没有服务器。**

## 一、结论先行

| 方案 | 成本 | 地址稳定 | 结论 |
|---|---|---|---|
| **GitHub Codespaces** | 免费 60 小时/月 | 用完即弃（可重建） | ✅ **推荐**，最像真服务器 |
| GitHub Actions 跑容器 | 免费 | 只验证 | ✅ 已有 CI，证明镜像能起 |
| Hugging Face Spaces | ⚠️ **Docker 现在要 PRO** | — | ❌ 免费版只剩 Static，跑不了后端 |
| Render 免费层 | 免费 | 会休眠 | ⚠️ 512 MB 内存，要关重排才可能跑得动 |
| 云服务器 2C2G | 30~60 元/月 | ✅ 固定 IP | 有预算时最省心 |

**为什么放弃 HF Spaces**：2026 年 HF 改成 "Gradio and Docker Spaces require a paid plan"，
免费只剩 Static（纯静态站点），**跑不了 Python 后端**。这条方案作废。

## 二、方案 A：GitHub Codespaces（推荐，免费）

仓库里已经加好 `.devcontainer/devcontainer.json`，打开就能跑：

```json
{
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "postCreateCommand": "pip install -r requirements.txt && python scripts/fetch_models.py",
  "postStartCommand": "python server.py --host 0.0.0.0 --port 8000",
  "forwardPorts": [8000]
}
```

### 步骤

1. 仓库页 → 绿色 **Code** 按钮 → **Codespaces** 标签 → **Create codespace on main**
2. 等 5~8 分钟（装依赖 + 下 306 MB 模型，日志在底部终端）
3. 服务自动在 8000 端口起来；VS Code 会提示"Open in Browser"
4. **关键一步**：底部 **PORTS** 面板 → 右键 8000 → **Port Visibility → Public**
5. 拿到地址：`https://<codespace名>-8000.app.github.dev`

把这个地址发给面试官，**只要有 codespace 在跑就能访问**。

### 成本与限制

- 免费额度：**每月 60 核时 / 15 GB 存储**（2 核机器 ≈ 30 小时，够面试用）；
- 闲置 30 分钟自动停止（停止后地址失效，重新打开会换新地址）；
- 内存 8 GB，跑 bge-small + reranker 没问题；
- **别在里面跑压测**，核时烧得很快。

### 面试话术

> "我没租服务器，用 Codespaces 跑的：仓库里有 devcontainer，打开就自动装依赖、
> 下模型、起服务，端口设成 public 就是一个能访问的地址。
> 免费额度 60 核时/月，演示够用；真要上生产我会用 2C4G 云服务器 + nginx。"

## 三、方案 B：GitHub Actions 跑容器（已落地）

`.github/workflows/docker.yml` 每次推送都会：

```yaml
docker build -t kb-bot .
docker run -d --name kb -p 8000:8000 kb-bot
轮询 curl http://127.0.0.1:8000/api/stats 直到 200
docker logs --tail 50
docker rm -f kb
```

**证明了**：镜像能在干净环境构建、容器能启动、接口真通。
**没证明**：长期在线、域名、并发。

## 四、方案 C：云服务器（有预算时）

```bash
# 1. 装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 拉代码、构建、跑
git clone https://github.com/<你>/kb-bot.git && cd kb-bot
docker build -t kb-bot .
docker run -d --restart=always -p 8000:8000 \
  -e DEEPSEEK_API_KEY=sk-xxx --name kb kb-bot
```

systemd 方式见 `deploy/kb-bot.service`。

## 五、方案 D：Render 免费层（备用，要改配置）

- 免费 Web Service：512 MB 内存、闲置 15 分钟休眠
- **512 MB 装不下 reranker（~300 MB）+ 向量模型（~100 MB）**，
  必须在 `kb/config.py` 里 `use_rerank=False` 才可能跑起来
- 休眠后首次访问要等 30~60 秒

## 六、面试怎么讲（三段式）

> "部署我没租服务器，用了两条路：
> 一是 CI 里跑 `docker build` + `docker run` + 健康检查，证明镜像能起；
> 二是用 Codespaces 跑了个真实地址，端口设 public，您能直接点开。
> 这两个都不是生产环境——生产我会用 2C4G 云服务器 + nginx 反代，文档里写了。"

**关键**：说清"演示环境 vs 生产环境"，比含糊说"部署过"专业得多。

## 七、踩过的坑（可以讲）

1. **本机 Docker 跑不起来**：系统保留分区只有 260 MB，装不下 WSL 虚拟化组件，
   报 `0x800f0922`（CBS 在启动阶段回滚）——查到根因后改用 CI 验证。
2. **HF Spaces 免费额度变了**：Docker SDK 需要 PRO，Static 免费但跑不了后端。
3. **模型下载地址写死**：`kb/hf.py` 原来硬编码国内镜像 hf-mirror.com，
   换到海外环境会超时；改成读 `HF_ENDPOINT` 环境变量。
