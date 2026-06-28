# arc/web-builder:latest — Web 资源构建工具链镜像 (v6.12 波次2)
#
# 为 DockerSandboxRuntime 提供容器可构建目标 (web dist) 所需工具链:
# Node 20 + 构建工具链 (git/python3/build-base, 供 node-gyp 原生模块编译)。
#
# 范围: BINARY_APP 项目的 web 资源构建 (npm run build → dist), 不打包原生客户端。
# 区别于 tauri-builder (需 rust+webkit2gtk 出桌面包) 与 android-builder (需 JDK+SDK+NDK 出 apk):
# 本镜像最轻量, 仅做前端 web 资源构建。
#
# 基础镜像选 alpine (非 slim): 更轻量 (~136MB), 中国环境经加速器可稳定拉取;
# 前端构建 (vite/webpack) 无 glibc 专有依赖, alpine/musl 兼容充分。
#
# 构建: 见同目录 Makefile (make web-builder)
FROM node:20-alpine

# 构建工具链: git (依赖拉取) + python3/build-base (node-gyp 原生模块编译, 如 esbuild/better-sqlite3)
RUN apk add --no-cache \
    git \
    python3 \
    build-base \
    curl \
    ca-certificates

# pnpm 全局可用 (项目内优先用本地锁版本, 此为兜底)。
# 锁 pnpm@9 (非 latest): pnpm 11 要求 node 22+ 的 node:sqlite 模块, 与本镜像 node 20 不兼容。
RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /workspace
