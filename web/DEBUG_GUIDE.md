# 🚀 RAGFlow 前端调试运行指南

## 📋 前置条件

1. **Node.js**: 版本 >= 16.0.0
2. **npm**: 版本 >= 8.0.0
3. **后端服务**: 确保后端服务运行在 `192.168.0.118:9380`

## 🛠️ 安装和运行步骤

### 1. 安装依赖

```bash
# 进入前端项目目录
cd web

# 安装项目依赖
npm install
```

### 2. 启动开发服务器

```bash
# 启动开发服务器
npm run dev
```

### 3. 访问应用

- **前端地址**: http://192.168.0.118:3000
- **后端API**: http://192.168.0.118:9380

## 🔧 配置说明

### Vite 代理配置

项目已配置了 Vite 代理，将 `/api` 请求代理到后端服务器：

```typescript
// vite.config.ts
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://192.168.0.118:9380',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '/api')
    }
  }
}
```

### API 配置

API 服务配置在 `src/services/api.ts` 中：

```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://192.168.0.118:9380';
```

## 🎯 功能特性

### 知识库管理
- ✅ 创建知识库
- ✅ 更新知识库信息
- ✅ 删除知识库
- ✅ 查看知识库列表
- ✅ 查看知识库详情

### 技术栈
- **前端框架**: React 18 + TypeScript
- **UI组件库**: Ant Design 5.x
- **路由**: React Router DOM 6.x
- **HTTP客户端**: Axios
- **构建工具**: Vite 5.x

## 🐛 调试技巧

### 1. 浏览器开发者工具
- 打开 Chrome DevTools (F12)
- 查看 Network 标签页监控API请求
- 查看 Console 标签页查看错误信息

### 2. 常见问题排查

#### API请求失败
```bash
# 检查后端服务是否运行
curl http://192.168.0.118:9380/api/v1/kb/list
```

#### 端口冲突
```bash
# 如果3000端口被占用，可以修改vite.config.ts中的port配置
server: {
  port: 3001, // 改为其他端口
}
```

#### 依赖安装问题
```bash
# 清除缓存重新安装
rm -rf node_modules package-lock.json
npm install
```

## 📁 项目结构

```
web/
├── src/
│   ├── components/          # React组件
│   │   └── KnowledgeBaseList.tsx
│   ├── services/           # API服务
│   │   └── api.ts
│   ├── types/              # TypeScript类型定义
│   │   └── api.ts
│   ├── App.tsx             # 主应用组件
│   └── main.tsx            # 应用入口
├── package.json            # 项目配置
├── vite.config.ts          # Vite配置
└── tsconfig.json           # TypeScript配置
```

## 🚀 生产构建

```bash
# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

## 📝 开发注意事项

1. **API接口**: 确保后端API接口与前端类型定义一致
2. **CORS**: 后端需要配置CORS允许前端域名访问
3. **认证**: 如需认证，在 `api.ts` 中添加token处理逻辑
4. **错误处理**: 在API拦截器中添加统一的错误处理

## 🔗 相关链接

- [React 官方文档](https://react.dev/)
- [Ant Design 组件库](https://ant.design/)
- [Vite 构建工具](https://vitejs.dev/)
- [TypeScript 文档](https://www.typescriptlang.org/)
