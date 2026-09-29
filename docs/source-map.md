# 项目描述与独立实现映射

[返回 README](../README.md)

本项目根据用户提供的功能需求与学习原型进行独立实现。该文档将简历中的五项项目描述对应到新实现文件，并说明代码可以验证的能力与当前边界。

## 五项项目描述对应位置

| 简历中的工作 | 新实现文件 | 可以从代码确认的内容 |
| --- | --- | --- |
| 四层架构，FastMCP 封装本地工具，统一 stdio 与 SSE | [`api_server.py`](../api_server.py)、[`runtime.py`](../runtime.py)、[`weather_server.py`](../weather_server.py)、[`write_server.py`](../write_server.py)、[`servers_config.json`](../servers_config.json)、[`ChatBox.vue`](../frontend/src/components/ChatBox.vue) | 前端、API、Agent 与工具分层；两个本地 Server 提供三个工具；可选远程 SSE 服务配置 |
| LangGraph ReAct + 通义千问自主选择、生成参数与串联工具 | [`runtime.py`](../runtime.py)、[`agent_prompts.txt`](../agent_prompts.txt) | 工具集合传入 ReAct Agent；调用 `ainvoke` 执行模型与工具循环；无按用户关键词分派工具的业务分支 |
| 统一配置、启动发现、会话隔离 | [`configuration.py`](../configuration.py)、[`servers_config.json`](../servers_config.json)、[`runtime.py`](../runtime.py)、[`ChatBox.vue`](../frontend/src/components/ChatBox.vue) | 配置解析、`MultiServerMCPClient` 与工具加载；`InMemorySaver`；请求传递独立的 `thread_id` |
| 非流式 Web 接口与 MCP 生命周期 | [`api_server.py`](../api_server.py)、[`runtime.py`](../runtime.py) | FastAPI `lifespan`；异步非流式调用；`AsyncExitStack` 管理显式 MCP 会话 |
| Vue 聊天界面与 Web 工程细节 | [`ChatBox.vue`](../frontend/src/components/ChatBox.vue)、[`vite.config.js`](../frontend/vite.config.js)、[`api_server.py`](../api_server.py) | Markdown 渲染、加载反馈、异常提示、HTML 禁用与链接过滤；API 地址配置、开发代理与受限 Origin 列表 |

## 配置与生命周期

`configuration.py` 将 `${PYTHON_EXECUTABLE}` 解析为当前 Python 解释器，并以项目根目录解析相对脚本路径，避免开发机器绝对路径影响其他用户运行。`servers_config.json` 声明 stdio 本地服务与可选 SSE 地图服务；`runtime.py` 在启动时加载工具，并通过显式会话上下文管理资源。

API 要求请求提供 `thread_id`，前端生成并发送独立 ID，避免所有浏览器请求落入固定默认会话。会话 ID 的用途是检查点隔离，尚未实现用户身份与会话访问权限。

## 需要准确表述的边界

**“上下文持久化”应细化为进程内状态保存。** `InMemorySaver` 支持进程存活期间的跨轮检查点，不能在重启后恢复。简历可写为“通过 `InMemorySaver` 与 `thread_id` 实现进程内多轮上下文保存和会话隔离”。若要声称跨重启持久化，需要相应的数据库检查点实现与验证。

**“动态加载”指启动时加载。** 服务配置在启动时解析并发现工具；新增服务无需修改 Agent 主流程，但需要重启。当前没有运行时热插拔。

**“远程地图接入”是可选配置能力。** 默认发布版不启用地图服务。配置与生命周期支持 SSE，但能否获得地图工具要由实际服务地址、鉴权与连接结果确认；本仓库不提供高德服务端源码，也不记录虚构的远程实测结果。

**历史兼容问题与新实现应分别验证。** 新实现采用 `streaming=False` 与 `ainvoke`，但源码并不能证明历史流式异常的具体调用栈与根因，也不代表所有 LangGraph 版本都存在同样的问题。有关过往排查的项目描述应以实际日志和开发记录为依据。

**“XSS 防护”对应具体渲染约束。** 前端禁用 Markdown 原始 HTML，并对链接协议进行过滤；这不等于整个应用经过全面安全审计。

## 验证范围

自动测试包含真实 stdio MCP 工具加载与调用、本地 SSE 服务连接，并使用模拟模型验证多工具 ReAct 循环和会话隔离。这样的测试能检查本地集成逻辑，不代表通义千问、天气或高德地图外部服务的实时调用结果。运行命令和开发要求见 [贡献指南](../CONTRIBUTING.md)。

## 阅读建议与发布范围

建议从 `servers_config.json` 和两个 MCP Server 入手，理解能力如何被描述；再阅读 `runtime.py`，观察工具如何加载到 Agent；最后阅读 `api_server.py` 和 `ChatBox.vue`，串起会话 ID、一次请求与结果反馈。详细执行过程见 [架构说明](architecture.md)。

本仓库发布按功能需求独立实现的源码、配置示例与配套文档。
