# 项目概述

本项目是代码生成方向数据预处理 Agent 系统。

## 模块划分

- Frontend：Vue 3 前端，只调用 Spring Boot。
- Backend：Spring Boot 轻量后端，负责文件上传、任务状态、结果聚合、调用 PythonAgent。
- PythonAgent：FastAPI + LangGraph，负责 Agent 编排和 skills 执行。

## 关键约束

1. 不实现登录注册。
2. 不实现复杂权限。
3. 不实现 OSS，先使用本地文件存储。
4. 前端不直接调用 PythonAgent。
5. Spring Boot 不实现数据预处理算法。
6. PythonAgent 不连接 MySQL。
7. 图表由前端渲染，后端返回 ChartSpec。
8. 当前版本主要支持 Python 函数级代码数据。