# arc/tauri-builder:linux — Tauri linux 构建工具链镜像 (v6.0 波次1)
#
# 为 DockerSandboxRuntime 提供容器可构建目标 (deb/AppImage) 所需工具链:
# Rust + Node 20 + webkit2gtk-4.1 (tauri v2) + tauri-cli
#
# 范围: 仅 linux bundle (deb/AppImage)。macOS .dmg / Windows .exe 需原生 OS,
# 容器化沙箱无法构建, 推后到原生 runner / CI matrix (见 v6.0.0-current.md 决策)。
# web (波次2) / android apk (波次3) 用独立镜像, 不在此扩充。
#
# 构建: 见同目录 Makefile (make tauri-builder)
FROM rust:1-slim-bookworm

# tauri v2 linux 系统依赖: webkit2gtk-4.1 / gtk3 / soup3 / javascriptcore / librsvg(图标)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libwebkit2gtk-4.1-dev \
    libgtk-3-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev \
    libsoup-3.0-dev \
    libjavascriptcoregtk-4.1-dev \
    build-essential \
    patchelf \
    curl \
    file \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Node 20 — 前端 web 资源构建 (npm run build → dist, tauri 引用此 dist)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# tauri-cli (cargo install --locked 锁版本, 构建可复现)
# 注意: 安装后可执行文件为 cargo-tauri, 以 cargo 子命令调用: `cargo tauri build`
# (非裸 `tauri` 命令)
RUN cargo install tauri-cli --version "^2.0" --locked

WORKDIR /workspace
