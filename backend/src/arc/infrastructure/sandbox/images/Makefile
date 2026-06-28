# 构建工具链镜像 (v6.0 容器化构建)
# 用法: make tauri-builder / make web-builder
#
# 镜像构建到本地 docker daemon, DockerSandboxRuntime 通过 docker_image 名引用
# (默认镜像名见 domain/sandbox/build_images.py DEFAULT_BUILD_IMAGES)。

TAURI_BUILDER_IMAGE := arc/tauri-builder:linux
WEB_BUILDER_IMAGE := arc/web-builder:latest
ANDROID_BUILDER_IMAGE := arc/android-builder:linux

.PHONY: tauri-builder web-builder android-builder clean

tauri-builder:
	docker build -t $(TAURI_BUILDER_IMAGE) -f tauri-builder.Dockerfile .

# 波次2 (v6.12): web 资源构建 (BINARY_APP + WEB target, npm run build → dist)
web-builder:
	docker build -t $(WEB_BUILDER_IMAGE) -f web-builder.Dockerfile .

# 波次3 (v6.12): android apk (capacitor, BINARY_APP + CAPACITOR_APK target)
# 镜像大 (JDK+SDK+NDK ~3GB), 构建慢 (~10-20min, NDK 下载占大头)
android-builder:
	docker build -t $(ANDROID_BUILDER_IMAGE) -f android-builder.Dockerfile .

clean:
	docker rmi $(TAURI_BUILDER_IMAGE) $(WEB_BUILDER_IMAGE) $(ANDROID_BUILDER_IMAGE) 2>/dev/null || true
