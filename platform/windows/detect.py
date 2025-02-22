import methods
import os
from platform_methods import detect_arch

# To match other platforms
STACK_SIZE = 8388608


def is_active():
    return True


def get_name():
    return "Windows"


def can_build():
    if os.name == "nt":
        # Building natively on Windows
        # If VCINSTALLDIR is set in the OS environ, use traditional Godot logic to set up MSVC
        if os.getenv("VCINSTALLDIR"):  # MSVC, manual setup
            return True

        # Otherwise, let SCons find MSVC if installed, or else Mingw.
        # Since we're just returning True here, if there's no compiler
        # installed, we'll get errors when it tries to build with the
        # null compiler.
        return True

    if os.name == "posix":
        # Cross-compiling with MinGW-w64 (old MinGW32 is not supported)
        mingw32 = "i686-w64-mingw32-"
        mingw64 = "x86_64-w64-mingw32-"

        if os.getenv("MINGW32_PREFIX"):
            mingw32 = os.getenv("MINGW32_PREFIX")
        if os.getenv("MINGW64_PREFIX"):
            mingw64 = os.getenv("MINGW64_PREFIX")

        test = "gcc --version > /dev/null 2>&1"
        if os.system(mingw64 + test) == 0 or os.system(mingw32 + test) == 0:
            return True

    return False


def get_opts():
    from SCons.Variables import BoolVariable, EnumVariable

    # TODO: These shouldn't be hard-coded for x86.
    mingw32 = ""
    mingw64 = ""
    if os.name == "posix":
        mingw32 = "i686-w64-mingw32-"
        mingw64 = "x86_64-w64-mingw32-"

    if os.getenv("MINGW32_PREFIX"):
        mingw32 = os.getenv("MINGW32_PREFIX")
    if os.getenv("MINGW64_PREFIX"):
        mingw64 = os.getenv("MINGW64_PREFIX")

    return [
        ("mingw_prefix_32", "MinGW prefix (Win32)", mingw32),
        ("mingw_prefix_64", "MinGW prefix (Win64)", mingw64),
        # Targeted Windows version: 7 (and later), minimum supported version
        # XP support dropped after EOL due to missing API for IPv6 and other issues
        # Vista support dropped after EOL due to GH-10243
        ("target_win_version", "Targeted Windows version, >= 0x0601 (Windows 7)", "0x0601"),
        BoolVariable("debug_symbols", "Add debugging symbols to release/release_debug builds", True),
        EnumVariable("windows_subsystem", "Windows subsystem", "gui", ("gui", "console")),
        BoolVariable("separate_debug_symbols", "Create a separate file containing debugging symbols", False),
        ("msvc_version", "MSVC version to use. Ignored if VCINSTALLDIR is set in shell env.", None),
        BoolVariable("use_mingw", "Use the Mingw compiler, even if MSVC is installed.", False),
        BoolVariable("use_llvm", "Use the LLVM compiler", False),
        BoolVariable("use_thinlto", "Use ThinLTO", False),
        BoolVariable("use_static_cpp", "Link MinGW/MSVC C++ runtime libraries statically", True),
        BoolVariable("use_asan", "Use address sanitizer (ASAN)", False),
    ]


def get_flags():
    return [
        ("arch", detect_arch()),
    ]


def build_res_file(target, source, env):
    # TODO: This shouldn't be hard-coded for x86.
    if env["arch"] == "x86_32":
        cmdbase = env["mingw_prefix_32"]
    else:
        cmdbase = env["mingw_prefix_64"]
    cmdbase = cmdbase + "windres --include-dir . "
    import subprocess

    for x in range(len(source)):
        cmd = cmdbase + "-i " + str(source[x]) + " -o " + str(target[x])
        try:
            out = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE).communicate()
            if len(out[1]):
                return 1
        except Exception:
            return 1
    return 0


def setup_msvc_manual(env):
    # FIXME: This is super hacky, and probably obsolete.
    # Won't work with detect_arch() used for `arch` by default.

    """Set up env to use MSVC manually, using VCINSTALLDIR"""
    if env["arch"] != "auto":
        print(
            """
            Arch argument is not supported for MSVC manual configuration (VCINSTALLDIR configured).
            Architecture depends on the Native/Cross Compile Tools Prompt/Developer Console (or Visual Studio settings) that is being used to run SCons.
            As a consequence, the arch argument is disabled. Run scons again without arch argument (example: scons p=windows)
            and SCons will attempt to detect what MSVC compiler will be executed and inform you.
            """
        )
        raise SCons.Errors.UserError("Arch argument should not be used when using VCINSTALLDIR")

    # Force ARCH arg
    # (Actually msys2 mingw can support 64-bit, we could detect that)
    # TODO: This is wrong, but not sure what to do about it.
    # We want to determine the arch and bitness in the SConstruct only.
    # We can check if it's correct in here, but if it's not, it should
    # just fail with an error message instead of trying to force it.

    # find compiler manually
    compiler_version_str = methods.detect_visual_c_compiler_version(env["ENV"])
    print("Found MSVC compiler: " + compiler_version_str)

    # If building for 64bit architecture, disable assembly optimisations for 32 bit builds (theora as of writing)... vc compiler for 64bit can not compile _asm
    if compiler_version_str == "amd64" or compiler_version_str == "x86_amd64":
        env["arch"] = "x86_64"
        env["x86_libtheora_opt_vc"] = False
        print("Compiled program architecture will be a 64 bit executable (forcing arch=x86_64).")
    elif compiler_version_str == "x86" or compiler_version_str == "amd64_x86":
        env["arch"] = "x86_32"
        env["x86_libtheora_opt_vc"] = True
        print("Compiled program architecture will be a 32 bit executable (forcing arch=x86_32).")
    else:
        print(
            "Failed to manually detect MSVC compiler architecture version.\n"
            "You should check your settings/compilation setup, or avoid setting VCINSTALLDIR."
        )
        sys.exit()


def setup_msvc_auto(env):
    """Set up MSVC using SCons's auto-detection logic"""

    # If MSVC_VERSION is set by SCons, we know MSVC is installed.
    # But we may want a different version or target arch.

    # Valid architectures for MSVC's TARGET_ARCH:
    # ['amd64', 'emt64', 'i386', 'i486', 'i586', 'i686', 'ia64', 'itanium', 'x86', 'x86_64', 'arm', 'arm64', 'aarch64']
    # Our x86_64 and arm64 are the same, and we need to map the 32-bit
    # architectures to other names since MSVC isn't as explicit.
    # The rest we don't need to worry about because they are
    # aliases or aren't supported by Godot (itanium & ia64).
    msvc_arch_aliases = {"x86_32": "x86", "arm32": "arm"}
    if env["arch"] in msvc_arch_aliases.keys():
        env["TARGET_ARCH"] = msvc_arch_aliases[env["arch"]]
    else:
        env["TARGET_ARCH"] = env["arch"]

    # The env may have already been set up with default MSVC tools, so
    # reset a few things so we can set it up with the tools we want.
    # (Ideally we'd decide on the tool config before configuring any
    # environment, and just set the env up once, but this function runs
    # on an existing env so this is the simplest way.)
    env["MSVC_SETUP_RUN"] = False  # Need to set this to re-run the tool
    env["MSVS_VERSION"] = None
    env["MSVC_VERSION"] = None

    if "msvc_version" in env:
        env["MSVC_VERSION"] = env["msvc_version"]
    env.Tool("msvc")
    env.Tool("mssdk")  # we want the MS SDK
    # Note: actual compiler version can be found in env['MSVC_VERSION'], e.g. "14.1" for VS2015
    print("Found MSVC version %s, arch %s" % (env["MSVC_VERSION"], env["TARGET_ARCH"]))
    if env["arch"] == "x86_32":
        env["x86_libtheora_opt_vc"] = False


def setup_mingw(env):
    """Set up env for use with mingw"""
    # Nothing to do here
    print("Using MinGW")


def configure_msvc(env, manual_msvc_config):
    """Configure env to work with MSVC"""

    # Build type

    if env["target"] == "release":
        if env["optimize"] == "speed":  # optimize for speed (default)
            env.Append(CCFLAGS=["/O2"])
            env.Append(LINKFLAGS=["/OPT:REF"])
        elif env["optimize"] == "size":  # optimize for size
            env.Append(CCFLAGS=["/O1"])
            env.Append(LINKFLAGS=["/OPT:REF"])
        env.Append(LINKFLAGS=["/ENTRY:mainCRTStartup"])

    elif env["target"] == "release_debug":
        if env["optimize"] == "speed":  # optimize for speed (default)
            env.Append(CCFLAGS=["/O2"])
            env.Append(LINKFLAGS=["/OPT:REF"])
        elif env["optimize"] == "size":  # optimize for size
            env.Append(CCFLAGS=["/O1"])
            env.Append(LINKFLAGS=["/OPT:REF"])

    elif env["target"] == "debug":
        env.AppendUnique(CCFLAGS=["/Zi", "/FS", "/Od", "/EHsc"])
        # Allow big objects. Only needed for debug, see MinGW branch for rationale.
        env.Append(LINKFLAGS=["/DEBUG"])

    if env["debug_symbols"]:
        env.AppendUnique(CCFLAGS=["/Zi", "/FS"])
        env.AppendUnique(LINKFLAGS=["/DEBUG"])

    if env["windows_subsystem"] == "gui":
        env.Append(LINKFLAGS=["/SUBSYSTEM:WINDOWS"])
    else:
        env.Append(LINKFLAGS=["/SUBSYSTEM:CONSOLE"])
        env.AppendUnique(CPPDEFINES=["WINDOWS_SUBSYSTEM_CONSOLE"])

    ## Compile/link flags

    if env["use_static_cpp"]:
        env.AppendUnique(CCFLAGS=["/MT"])
    else:
        env.AppendUnique(CCFLAGS=["/MD"])

    env.AppendUnique(CCFLAGS=["/Gd", "/GR", "/nologo"])
    env.AppendUnique(CCFLAGS=["/utf-8"])  # Force to use Unicode encoding.
    env.AppendUnique(CXXFLAGS=["/TP"])  # assume all sources are C++
    # Once it was thought that only debug builds would be too large,
    # but this has recently stopped being true. See the mingw function
    # for notes on why this shouldn't be enabled for gcc
    env.AppendUnique(CCFLAGS=["/bigobj"])

    if manual_msvc_config:  # should be automatic if SCons found it
        if os.getenv("WindowsSdkDir") is not None:
            env.Prepend(CPPPATH=[os.getenv("WindowsSdkDir") + "/Include"])
        else:
            print("Missing environment variable: WindowsSdkDir")

    env.AppendUnique(
        CPPDEFINES=[
            "WINDOWS_ENABLED",
            "WASAPI_ENABLED",
            "WINMIDI_ENABLED",
            "TYPED_METHOD_BIND",
            "WIN32",
            "MSVC",
            "WINVER=%s" % env["target_win_version"],
            "_WIN32_WINNT=%s" % env["target_win_version"],
        ]
    )
    env.AppendUnique(CPPDEFINES=["NOMINMAX"])  # disable bogus min/max WinDef.h macros
    if env["arch"] == "x86_64":
        env.AppendUnique(CPPDEFINES=["_WIN64"])

    ## Libs

    LIBS = [
        "winmm",
        "dsound",
        "kernel32",
        "ole32",
        "oleaut32",
        "sapi",
        "user32",
        "gdi32",
        "IPHLPAPI",
        "Shlwapi",
        "wsock32",
        "Ws2_32",
        "shell32",
        "advapi32",
        "dinput8",
        "dxguid",
        "imm32",
        "bcrypt",
        "Avrt",
        "dwmapi",
        "dwrite",
    ]

    if env["vulkan"]:
        env.AppendUnique(CPPDEFINES=["VULKAN_ENABLED"])
        if not env["use_volk"]:
            LIBS += ["vulkan"]

    if env["opengl3"]:
        env.AppendUnique(CPPDEFINES=["GLES3_ENABLED"])
        LIBS += ["opengl32"]

    env.Append(LINKFLAGS=[p + env["LIBSUFFIX"] for p in LIBS])

    if manual_msvc_config:
        if os.getenv("WindowsSdkDir") is not None:
            env.Append(LIBPATH=[os.getenv("WindowsSdkDir") + "/Lib"])
        else:
            print("Missing environment variable: WindowsSdkDir")

    ## LTO

    if env["use_lto"]:
        env.AppendUnique(CCFLAGS=["/GL"])
        env.AppendUnique(ARFLAGS=["/LTCG"])
        if env["progress"]:
            env.AppendUnique(LINKFLAGS=["/LTCG:STATUS"])
        else:
            env.AppendUnique(LINKFLAGS=["/LTCG"])

    if manual_msvc_config:
        env.Prepend(CPPPATH=[p for p in os.getenv("INCLUDE").split(";")])
        env.Append(LIBPATH=[p for p in os.getenv("LIB").split(";")])

    # Sanitizers
    if env["use_asan"]:
        env.extra_suffix += ".san"
        env.Append(LINKFLAGS=["/INFERASANLIBS"])
        env.Append(CCFLAGS=["/fsanitize=address"])

    # Incremental linking fix
    env["BUILDERS"]["ProgramOriginal"] = env["BUILDERS"]["Program"]
    env["BUILDERS"]["Program"] = methods.precious_program

    env.AppendUnique(LINKFLAGS=["/STACK:" + str(STACK_SIZE)])


def configure_mingw(env):
    # Workaround for MinGW. See:
    # https://www.scons.org/wiki/LongCmdLinesOnWin32
    env.use_windows_spawn_fix()

    ## Build type

    if env["target"] == "release":
        env.Append(CCFLAGS=["-msse2"])

        if env["optimize"] == "speed":  # optimize for speed (default)
            if env["arch"] == "x86_32":
                env.Append(CCFLAGS=["-O2"])
            else:
                env.Append(CCFLAGS=["-O3"])
        else:  # optimize for size
            env.Prepend(CCFLAGS=["-Os"])

        if env["debug_symbols"]:
            env.Prepend(CCFLAGS=["-g2"])

    elif env["target"] == "release_debug":
        env.Append(CCFLAGS=["-O2"])
        if env["debug_symbols"]:
            env.Prepend(CCFLAGS=["-g2"])
        if env["optimize"] == "speed":  # optimize for speed (default)
            env.Append(CCFLAGS=["-O2"])
        else:  # optimize for size
            env.Prepend(CCFLAGS=["-Os"])

    elif env["target"] == "debug":
        env.Append(CCFLAGS=["-g3"])
        # Allow big objects. It's supposed not to have drawbacks but seems to break
        # GCC LTO, so enabling for debug builds only (which are not built with LTO
        # and are the only ones with too big objects).
        env.Append(CCFLAGS=["-Wa,-mbig-obj"])

    if env["windows_subsystem"] == "gui":
        env.Append(LINKFLAGS=["-Wl,--subsystem,windows"])
    else:
        env.Append(LINKFLAGS=["-Wl,--subsystem,console"])
        env.AppendUnique(CPPDEFINES=["WINDOWS_SUBSYSTEM_CONSOLE"])

    ## Compiler configuration

    if os.name != "nt":
        env["PROGSUFFIX"] = env["PROGSUFFIX"] + ".exe"  # for linux cross-compilation

    mingw_prefix = ""

    # TODO: This doesn't seem to be working, or maybe I just have
    # MinGW set up incorrectly. It always gives me x86_64 builds,
    # even though arch == "x86_32" and the file name has x86_32 in it.
    if env["arch"] == "x86_32":
        if env["use_static_cpp"]:
            env.Append(LINKFLAGS=["-static"])
            env.Append(LINKFLAGS=["-static-libgcc"])
            env.Append(LINKFLAGS=["-static-libstdc++"])
        mingw_prefix = env["mingw_prefix_32"]
    else:
        if env["use_static_cpp"]:
            env.Append(LINKFLAGS=["-static"])
        mingw_prefix = env["mingw_prefix_64"]

    if env["use_llvm"]:
        env["CC"] = mingw_prefix + "clang"
        env["CXX"] = mingw_prefix + "clang++"
        env["AS"] = mingw_prefix + "as"
        env["AR"] = mingw_prefix + "ar"
        env["RANLIB"] = mingw_prefix + "ranlib"
    else:
        env["CC"] = mingw_prefix + "gcc"
        env["CXX"] = mingw_prefix + "g++"
        env["AS"] = mingw_prefix + "as"
        env["AR"] = mingw_prefix + "gcc-ar"
        env["RANLIB"] = mingw_prefix + "gcc-ranlib"

    env["x86_libtheora_opt_gcc"] = True

    if env["use_lto"]:
        if not env["use_llvm"] and env.GetOption("num_jobs") > 1:
            env.Append(CCFLAGS=["-flto"])
            env.Append(LINKFLAGS=["-flto=" + str(env.GetOption("num_jobs"))])
        else:
            if env["use_thinlto"]:
                env.Append(CCFLAGS=["-flto=thin"])
                env.Append(LINKFLAGS=["-flto=thin"])
            else:
                env.Append(CCFLAGS=["-flto"])
                env.Append(LINKFLAGS=["-flto"])

    env.Append(LINKFLAGS=["-Wl,--stack," + str(STACK_SIZE)])

    ## Compile flags

    env.Append(CCFLAGS=["-mwindows"])

    env.Append(CPPDEFINES=["WINDOWS_ENABLED", "WASAPI_ENABLED", "WINMIDI_ENABLED"])
    env.Append(CPPDEFINES=[("WINVER", env["target_win_version"]), ("_WIN32_WINNT", env["target_win_version"])])
    env.Append(
        LIBS=[
            "mingw32",
            "dsound",
            "ole32",
            "d3d9",
            "winmm",
            "gdi32",
            "iphlpapi",
            "shlwapi",
            "wsock32",
            "ws2_32",
            "kernel32",
            "oleaut32",
            "sapi",
            "dinput8",
            "dxguid",
            "ksuser",
            "imm32",
            "bcrypt",
            "avrt",
            "uuid",
            "dwmapi",
            "dwrite",
        ]
    )

    env.Append(CPPDEFINES=["VULKAN_ENABLED"])
    if not env["use_volk"]:
        env.Append(LIBS=["vulkan"])

    env.Append(CPPDEFINES=["GLES3_ENABLED"])
    env.Append(LIBS=["opengl32"])

    env.Append(CPPDEFINES=["MINGW_ENABLED", ("MINGW_HAS_SECURE_API", 1)])

    # resrc
    env.Append(BUILDERS={"RES": env.Builder(action=build_res_file, suffix=".o", src_suffix=".rc")})


def configure(env):
    # Validate arch.
    supported_arches = ["x86_32", "x86_64", "arm32", "arm64"]
    if env["arch"] not in supported_arches:
        print(
            'Unsupported CPU architecture "%s" for Windows. Supported architectures are: %s.'
            % (env["arch"], ", ".join(supported_arches))
        )
        sys.exit()

    # At this point the env has been set up with basic tools/compilers.
    env.Prepend(CPPPATH=["#platform/windows"])

    if os.name == "nt":
        env["ENV"] = os.environ  # this makes build less repeatable, but simplifies some things
        env["ENV"]["TMP"] = os.environ["TMP"]

    # First figure out which compiler, version, and target arch we're using
    if os.getenv("VCINSTALLDIR") and not env["use_mingw"]:
        # Manual setup of MSVC
        setup_msvc_manual(env)
        env.msvc = True
        manual_msvc_config = True
    elif env.get("MSVC_VERSION", "") and not env["use_mingw"]:
        setup_msvc_auto(env)
        env.msvc = True
        manual_msvc_config = False
    else:
        setup_mingw(env)
        env.msvc = False

    # Now set compiler/linker flags
    if env.msvc:
        configure_msvc(env, manual_msvc_config)

    else:  # MinGW
        configure_mingw(env)
