# MCP ReAct Agent Web

Vue 3 聊天界面，提供 Markdown 回复、加载提示、错误反馈与独立会话。

使用 Node.js `^20.19.0 || >=22.12.0`。在后端启动后运行：

```sh
npm ci
npm run dev
```

默认访问 `/api/chat`，Vite 开发与预览服务将请求转发到 `http://127.0.0.1:8000/chat`。
如需连接其他后端，复制 `.env.example` 为 `.env.local` 并设置 `VITE_API_BASE_URL`，不要添加 `/chat`。
这个变量会进入公开的前端产物，不能存放密钥；跨域地址需在后端允许对应前端来源。

```sh
npm test
npm run build
npm run preview
```

生产静态托管需将 `/api` 反向代理到后端并移除 `/api` 前缀，或在构建前设置后端地址。
`npm run preview` 仅用于本地预览。

同一页面通过 `sessionStorage` 保存 `thread_id` UUID；刷新页面会沿用会话，但不恢复本地消息列表。
“新对话”会清空本页消息并生成新的 UUID，不会删除后端已有会话。
后端的内存会话在后端重启后失效。

天气工具使用 OpenWeather 查询，需在后端配置服务密钥；季节工具提供内置提示。
文件工具将内容保存到固定的 `output` 目录并自动命名；地图工具需另行配置。
Markdown 禁用原始 HTML，并拒绝 `javascript:`、`data:`、`file:` 等危险链接。
