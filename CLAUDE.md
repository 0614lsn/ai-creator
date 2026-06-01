# Language / 语言

Always think and reply in Simplified Chinese. This includes all internal chain-of-thought, reasoning steps, tool explanations, and final code summaries. 始终使用简体中文进行思考、分析和回复，包括你所有的思考过程（Thinking）、工具使用解释以及最终的回答。

# 优先使用 MCP，不要 WebFetch 语雀 / ModelScope

WebFetch 抓 `*.yuque.com` 和 `modelscope.cn` 经常失败或拿不到结构化内容，
已经配置了对应的 MCP server，必须优先走 MCP。

## 语雀（`*.yuque.com`）

- **必须**使用 `yuque-mcp-server` 提供的工具，常用：
  - `yuque_get_doc` — 读单篇文档
  - `yuque_list_docs` / `yuque_get_toc` — 读知识库目录 / 文档列表
  - `yuque_search` — 搜索
  - `yuque_get_repo` — 读知识库元信息
- **禁止**对 `*.yuque.com` URL 调用 WebFetch。
- 只有当需求明确是「抓语雀站点的公开落地页 HTML」且 MCP 工具不支持时，才允许退回 WebFetch，
  并在调用前用一句话说明为什么 MCP 覆盖不到。

## ModelScope（`modelscope.cn` / `www.modelscope.cn`）

- **必须**使用 `modelscope-mcp-server` 提供的工具，常用：
  - `getModel` / `listModels` — 模型卡 / 模型列表
  - `getDataset` / `listDatasets` — 数据集
  - `getStudio` — Space / Studio
  - `getMCPDetailInfo` / `getMCPList` / `listMcpServers` — MCP 服务详情与列表
- **禁止**对 `modelscope.cn` URL 调用 WebFetch 抓取这些结构化资源。
- 仅当目标是纯营销/介绍页，且 MCP 工具明确不支持时，才允许 WebFetch。

## 通用原则

- 在调用工具前先判断：**这个域名有没有对应的 MCP server？** 有就用 MCP。
- 如果不确定 MCP server 支不支持某类资源，先列一下 MCP 工具清单再决定，
  不要直接退化到 WebFetch。
- 报错时优先换 MCP 工具的另一个方法，再考虑 WebFetch 兜底。
