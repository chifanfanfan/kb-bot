# 部署：没有服务器也能拿出"能访问的地址"

> 这一章解决一个现实问题：**面试要看你部署过，但你手上没有服务器。**

## 一、三条路，按成本排

| 方案 | 成本 | 地址是否稳定 | 适合 |
|---|---|---|---|
| **A. Hugging Face Spaces**（推荐） | 免费 | ✅ 永久 `*.hf.space` | 面试官点开就能用 |
| B. GitHub Actions 跑容器 | 免费 | ❌ 只验证，不长期在线 | 证明"镜像能构建、能启动" |
| C. 云服务器 2C2G | 30~60 元/月 | ✅ 固定 IP | 想真上生产 |

没有服务器时，**A + B 组合**已经足够讲清楚"我能部署"：
- B 证明 `docker build && docker run` 在干净环境里能跑通（含健康检查）；
- A 给面试官一个真实可点的地址。

## 二、方案 A：Hugging Face Spaces（免费永久地址）

### 步骤

1. 注册 https://huggingface.co （邮箱即可，不要信用卡）；
2. 右上角 **New → Space**：
   - Name：`kb-bot`
   - SDK：**Docker**
   - Hardware：**CPU basic（免费）**
   - 可见性：Public
3. 建好后，把本仓库文件推到 Space 仓库：

   ```bash
   # 先克隆 Space（地址在 Space 页面 → 三点菜单 → Clone repository）
   git clone https://huggingface.co/spaces/<你的用户名>/kb-bot hf-space
   cd hf-space

   # 复制项目文件（exclude .venv / models / chroma）
   robocopy ..\kb-bot . /E /XD .venv models chroma .git data
   # 用 deploy/huggingface/README.md 覆盖根目录 README.md（它带 Spaces 的配置头）
   copy ..\kb-bot\deploy\huggingface\README.md README.md

   git add -A
   git commit -m "deploy: kb-bot on Spaces"
   git push
   ```

4. Space 页面 **Settings → Variables and secrets** 加：
   - `DEEPSEEK_API_KEY` = 你的 key（选 Secret）

5. 等构建（约 8-15 分钟，要下 306 MB 模型），完成后地址是：
   `https://<你的用户名>-kb-bot.hf.space`

### 注意

- 免费 CPU 很慢：一次问答 10-20 秒，别拿去压测；
- 冷启动第一次会更慢（Space 闲置会休眠）；
- **一定要把 key 设成 Secret**，不要写进代码；
- Space 默认只有 2 vCPU / 16 GB 内存，跑 bge-small + reranker 够用。

## 三、方案 B：GitHub Actions 真跑容器（零成本验证）

仓库里已经有 [`.github/workflows/docker.yml`](../.github/workflows/docker.yml)：

```yaml
- docker build -t kb-bot .
- docker run -d -p 8000:8000 kb-bot
- 轮询 curl http://127.0.0.1:8000/api/stats 直到返回 200
- 打印日志、清理容器
```

**它证明了什么**：

- 镜像在干净环境里能构建（不只是"我写了 Dockerfile"）；
- 容器启动后 `/api/stats` 真的能返回数据；
- 启动失败会打印 `docker logs` 并让 CI 变红。

**它没证明什么**（诚实标注）：没有长期在线、没有域名、没有并发。

> 面试话术："我在 CI 里跑了 `docker build` 和 `docker run`，健康检查通过；
> 长期在线的那个是 Hugging Face Spaces 上跑的，地址是 xxx。"

## 四、方案 C：云服务器（如果以后有）

```bash
# 1. 装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 拉代码、构建
git clone https://github.com/<你>/kb-bot.git && cd kb-bot
docker build -t kb-bot .
docker run -d --restart=always -p 8000:8000 \
  -e DEEPSEEK_API_KEY=sk-xxx \
  --name kb kb-bot

# 3. nginx 反代 + 证书（可选）
```

systemd 方式见 `deploy/kb-bot.service`。

## 五、面试怎么讲（三段式）

> "部署我没租服务器，用两条路解决的：
> 一是 CI 里跑 `docker build` + `docker run` + 健康检查，证明镜像能起；
> 二是把它放到了 Hugging Face Spaces 免费实例上，地址是 xxx，您现在可以点开。
> 免费实例只有 2C，一次问答要十几秒，所以它不是性能测试环境——
> 真要上生产我会用 2C4G 的云服务器 + nginx 反代，文档里写了。"

**关键**：把"没有服务器"讲成"我用免费资源解决了演示需求"，
并且**明确区分演示环境和生产环境**——这比含糊说"部署过"专业得多。
