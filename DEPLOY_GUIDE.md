# EviTrack 一步步部署：GitHub → Streamlit Cloud → 提交笔试

## 第一步：准备 GitHub 仓库

1. 在电脑上解压 `EviTrack_部署提交版.zip`。
2. 登录 <https://github.com/new>，Repository name 建议填 `evitrack-evidence-timeline`，选择 **Public**，并创建仓库。
3. 在新仓库页面点击 **uploading an existing file** 或 **Add file → Upload files**。
4. **把解压后的项目文件内容上传到仓库根目录**，尤其是 `app.py`、`engine.py`、`ai_assist.py`、`sample_evidence.json`、`requirements.txt`、`README.md`、`tests/`、`.streamlit/config.toml`。不要只上传压缩包；GitHub 网页上传文件夹时，建议直接拖入解压后文件夹里的文件和子文件夹。检查根目录能直接看到 `app.py`。
5. 点击 **Commit changes**。
6. 你的仓库地址应类似 `https://github.com/<你的GitHub用户名>/evitrack-evidence-timeline`，这里的地址只是格式示例，**不是已创建的真实仓库**。

> 请勿提交任何 API Key、`.env` 或 `.streamlit/secrets.toml`。本项目的 `.env.example` 没有实际密钥。

## 第二步：发布能实际操作的网站

1. 打开 <https://share.streamlit.io/>，使用 GitHub 登录并授权访问刚才创建的仓库。
2. 点击 **Create app → Yup, I have an app**（平台文案可能略有调整）。
3. Repository 选择 `evitrack-evidence-timeline`，Branch 选择 `main`，Main file path 填写 **`app.py`**。
4. 点击 **Deploy**，等待 Streamlit 安装 `requirements.txt` 并启动网页。
5. 复制实际生成的 `https://...streamlit.app` 地址，**不要自己猜网址**。
6. 在无痕窗口打开，确认可以正常交互且不需要招聘方登录。

Streamlit官方部署文档：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## 第三步：现场验收（提交前必做）

- 回放日期设为 **2025-05-06** → “证据不足”。
- 调到 **2025-05-08** → “已宣布，待确认落地”。
- 调到 **2025-05-15** → “已实施（有公开证据）”。
- 开启合成冲突测试 → 报告中出现 1.0 vs 0.5 个百分点矛盾，且明确标明虚构。
- 新增一条讨论“2025年5月降准”的用户证据；确认标为“待核验”，不会自动更改权威状态。
- 检查证据卡片原链接能否打开；导出 JSON 文件能否下载。
- 不配置模型密钥时，模型按钮应明确提示未配置，不能声称实际调用 AI；如希望演示大模型分类，可在 Streamlit **App Settings → Secrets** 私密配置真实 API Key。不要把密钥贴到聊天或公开仓库。

## 第四步：整理笔试最终交付物

必交内容：

1. **公开 Web URL**：真实 Streamlit 网站地址。
2. **GitHub Repository URL**：真实 GitHub 仓库地址；根目录包含 README 和源代码。
3. **AI 使用与验证记录**：`AI_USAGE.md`，需本人核对是否准确描述实际使用过程，并在提交时补充自己修正或测试的细节。
4. **测试说明**：`TEST_PLAN.md`，把实际线上点击测试结果补进去；不能把尚未执行的 UI 测试写成已经通过。

建议选做：根据 `DEMO_SCRIPT.md` 录制 **60–180秒**，展示真实网站交互而不是只讲PPT。

## 如出现发布错误

- `ModuleNotFoundError: No module named 'streamlit'`：先确认 Streamlit Cloud 正在自动安装根目录的 `requirements.txt`。
- `File does not exist: app.py`：检查 GitHub 是否把整个中文文件夹放在根目录下一层，而不是直接上传文件；如文件在子文件夹中，部署入口要填写实际相对路径。
- `App crashed`：在 Streamlit Cloud 点击 **Manage app → Logs**，复制最后几行报错到聊天中进一步排查。
- 大模型提示未配置：**不是产品宕机**；主链路为本地确定性规则。需要模型演示时，在云端 Secrets 中填私有密钥。

提醒：上面是部署说明，实际 GitHub 和 Streamlit 账号操作需要本人登录授权。当前项目包不包含真实公开网址。
