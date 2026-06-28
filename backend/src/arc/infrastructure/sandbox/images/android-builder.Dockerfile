# arc/android-builder:linux — Android capacitor 构建工具链镜像 (v6.12 波次3)
#
# 为 DockerSandboxRuntime 提供容器可构建目标 (android apk) 所需工具链:
# JDK 21 + Android SDK (platform/build-tools/NDK) + Node 20 + Gradle + capacitor-cli。
#
# 范围: BINARY_APP 项目的 android apk 构建 (capacitor: npm run build → cap copy → cap build android)。
# 区别于 tauri-builder (桌面包) 与 web-builder (web dist): 本镜像重 (2-3GB, NDK 占大头)。
#
# 基础镜像选 eclipse-temurin:21-jdk (glibc, 官方 JDK21):
# capacitor 7 的 @capacitor/android 要求 source/target 21 (JDK 17 报 invalid source release: 21);
# Android SDK 预编译二进制 (aapt2/d8/NDK toolchain) 依赖 glibc, alpine/musl 兼容差。
# 强制 amd64: Android build-tools 的 aapt2 等是 x86_64 ELF, 无 arm64 linux 版;
# x86_64 CI/服务器原生跑; Apple Silicon 经 Rosetta 翻译整个 amd64 镜像 (含 x86 ld-linux + 原生 x86 aapt2)。
# 用 ARG (非 --platform 常量) 避免 buildx warning, build 时 --build-arg 可覆盖。
#
# 构建: 见同目录 Makefile (make android-builder, ~10-20min, NDK 下载占大头; Rosetta 环境更慢)
ARG BUILD_TARGET_PLATFORM=linux/amd64
FROM --platform=${BUILD_TARGET_PLATFORM} eclipse-temurin:21-jdk

# 基础工具 + Node 20 (capacitor 是 node 工具)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    zip \
    git \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Android SDK commandline tools
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=$ANDROID_HOME
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
RUN mkdir -p $ANDROID_HOME/cmdline-tools && \
    curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline.zip && \
    unzip -q /tmp/cmdline.zip -d $ANDROID_HOME/cmdline-tools && \
    mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest && \
    rm /tmp/cmdline.zip

# 接受 licenses + 装 platform-tools / platform-34 / build-tools / NDK(r26)
# NDK r26 (26.3.11579264) 对应 capacitor 推荐; licenses 预接受避免交互阻塞
RUN yes | sdkmanager --licenses >/dev/null 2>&1 && \
    sdkmanager --install \
      "platform-tools" \
      "platforms;android-34" \
      "build-tools;34.0.0" \
      "ndk;26.3.11579264"

# Gradle (capacitor android 项目用 gradle wrapper, 此为兜底)
RUN curl -fsSL https://services.gradle.org/distributions/gradle-8.7-bin.zip -o /tmp/gradle.zip && \
    unzip -q /tmp/gradle.zip -d /opt && \
    ln -s /opt/gradle-8.7/bin/gradle /usr/local/bin/gradle && \
    rm /tmp/gradle.zip

# capacitor cli 全局可用 (项目内优先用本地锁版本, 此为兜底)
RUN npm install -g @capacitor/cli

WORKDIR /workspace
