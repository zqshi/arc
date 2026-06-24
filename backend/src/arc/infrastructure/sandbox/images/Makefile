# 构建工具链镜像 (v6.0 容器化构建)
# 用法: make tauri-builder
#
# 镜像构建到本地 docker daemon, DockerSandboxRuntime 通过 docker_image 名引用
# (默认 arc/tauri-builder:linux, 见 domain/sandbox/build_images.py)。

TAURI_BUILDER_IMAGE := arc/tauri-builder:linux

.PHONY: tauri-builder clean

tauri-builder:
	docker build -t $(TAURI_BUILDER_IMAGE) -f tauri-builder.Dockerfile .

# 波次2/3 预留 (激活时取消注释):
# web-builder:
# 	docker build -t arc/web-builder:latest -f web-builder.Dockerfile .
# android-builder:
# 	docker build -t arc/android-builder:linux -f android-builder.Dockerfile .

clean:
	docker rmi $(TAURI_BUILDER_IMAGE) 2>/dev/null || true
