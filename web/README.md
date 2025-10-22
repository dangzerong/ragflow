# RAGFlow 知识库管理前端

这是一个基于 React + TypeScript + Vite + Ant Design 构建的知识库管理前端应用。

## 功能特性

- 📚 知识库的创建、编辑、删除
- 📋 知识库列表展示
- 🔍 支持搜索和分页
- 📱 响应式设计
- 🎨 现代化的UI界面

## 技术栈

- **React 18** - 前端框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **Ant Design** - UI组件库
- **Axios** - HTTP客户端
- **React Router** - 路由管理

## 项目结构

```
web/
├── public/                 # 静态资源
├── src/
│   ├── components/         # React组件
│   │   └── KnowledgeBaseList.tsx
│   ├── services/          # API服务
│   │   └── api.ts
│   ├── types/             # TypeScript类型定义
│   │   └── api.ts
│   ├── App.tsx            # 主应用组件
│   ├── main.tsx           # 应用入口
│   └── index.css          # 全局样式
├── index.html             # HTML模板
├── package.json           # 项目配置
├── tsconfig.json          # TypeScript配置
├── tsconfig.node.json     # Node.js TypeScript配置
└── vite.config.ts         # Vite配置
```

## 快速开始

### 安装依赖

```bash
cd web
npm install
```

### 启动开发服务器

```bash
npm run dev
```

应用将在 `http://192.168.0.118:3000` 启动。

### 构建生产版本

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

## 环境配置

创建 `.env.local` 文件来配置环境变量：

```env
# API基础URL
VITE_API_BASE_URL=http://192.168.0.118:9380
```

## API接口

应用与后端API进行交互，主要接口包括：

- `POST /v1/kb/create` - 创建知识库
- `POST /v1/kb/update` - 更新知识库
- `POST /v1/kb/delete` - 删除知识库
- `GET /v1/kb/list` - 获取知识库列表
- `GET /v1/kb/{kb_id}` - 获取知识库详情

## 开发指南

### 添加新功能

1. 在 `src/types/api.ts` 中定义相关类型
2. 在 `src/services/api.ts` 中添加API调用方法
3. 在 `src/components/` 中创建React组件
4. 在 `App.tsx` 中集成新组件

### 代码规范

- 使用TypeScript进行类型检查
- 遵循React Hooks最佳实践
- 使用Ant Design组件保持UI一致性
- 保持组件的单一职责原则

## 部署

### 构建

```bash
npm run build
```

构建产物将生成在 `dist/` 目录中。

### 部署到Web服务器

将 `dist/` 目录中的文件部署到任何静态文件服务器，如：

- Nginx
- Apache
- CDN
- 云存储服务

## 许可证

MIT License
