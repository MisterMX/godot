def can_build(env, platform):
    # Thirdparty dependency OpenImage Denoise includes oneDNN library
    # and the version we use only supports x86_64.
    # It's also only relevant for tools build and desktop platforms,
    # as doing lightmap generation and denoising on Android or HTML5
    # would be a bit far-fetched.
    desktop_platforms = ["linuxbsd", "macos", "windows"]
    return env["tools"] and platform in desktop_platforms and env["arch"] == "x86_64"


def configure(env):
    pass
